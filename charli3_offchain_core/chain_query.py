""" This module contains the ChainQuery class, which is used to query the blockchain."""

import asyncio
import time
from dataclasses import dataclass, field
from typing import List, Literal, Mapping, Optional, Tuple, Union

import cbor2
from blockfrost import ApiError
from pycardano import (
    Address,
    BlockFrostChainContext,
    ExtendedSigningKey,
    GenesisParameters,
    InsufficientUTxOBalanceException,
    KupoOgmiosV6ChainContext,
    PaymentSigningKey,
    PlutusV2Script,
    RawCBOR,
    ScriptHash,
    Transaction,
    TransactionBuilder,
    TransactionId,
    TransactionInput,
    TransactionOutput,
    UTxO,
    UTxOSelectionException,
    VerificationKeyWitness,
    plutus_script_hash,
)

from charli3_offchain_core.datums import NodeDatum
from charli3_offchain_core.utils.exceptions import CollateralException
from charli3_offchain_core.utils.logging_config import logging

logger = logging.getLogger("ChainQuery")


@dataclass
class SlotConfig:
    zero_time: int = field(metadata={"doc": "POSIX timestamp in milliseconds"})
    zero_slot: int
    slot_length: int = field(metadata={"doc": "milliseconds"})


NetworkLiteral = Literal["MAINNET", "PREVIEW", "PREPROD", "CUSTOM"]


def cardano_magic_to_network(network_magic: int) -> NetworkLiteral:
    match network_magic:
        case 764824073:
            return "MAINNET"
        case 1:
            return "PREPROD"
        case 2:
            return "PREVIEW"
        case 4:
            return "CUSTOM"
        case _:
            # return "MAINNET"
            raise UnknownNetworkMagic(network_magic)


# see https://github.com/Anastasia-Labs/lucid-evolution/blob/c81935fd75bd68c54d74b977bd3a431236b886d6/packages/plutus/src/time.ts#L8
SLOT_CONFIG_NETWORK: Mapping[NetworkLiteral, SlotConfig] = {
    "MAINNET": SlotConfig(
        zero_time=1596059091000, zero_slot=4492800, slot_length=1000
    ),  # Starting at Shelley era
    "PREVIEW": SlotConfig(
        zero_time=1666656000000, zero_slot=0, slot_length=1000
    ),  # Starting at Shelley era
    "PREPROD": SlotConfig(
        zero_time=1654041600000 + 1728000000, zero_slot=86400, slot_length=1000
    ),
    "CUSTOM": SlotConfig(zero_time=0, zero_slot=0, slot_length=0),
}


class NoContextSetup(Exception):
    pass


class UnknownNetworkMagic(Exception):
    pass


class ChainQuery:
    """chainQuery methods"""

    def __init__(
        self,
        blockfrost_context: BlockFrostChainContext = None,
        kupo_ogmios_context: KupoOgmiosV6ChainContext = None,
        oracle_address: Optional[str] = None,
        is_local_testnet: bool = False,
    ):
        if blockfrost_context is None and kupo_ogmios_context is None:
            raise ValueError("At least one of the chain contexts must be provided.")

        self.blockfrost_context = blockfrost_context
        self.ogmios_context = kupo_ogmios_context
        self.oracle_address = oracle_address
        self.context = blockfrost_context if blockfrost_context else kupo_ogmios_context
        self.is_local_testnet = is_local_testnet

        self._datum_cache = {}

    @property
    def genesis_params(self) -> GenesisParameters:

        if self.ogmios_context:
            genesis_params = self.ogmios_context.genesis_param
        elif self.blockfrost_context:
            genesis_params = self.blockfrost_context.genesis_param
        return genesis_params  # pylint: disable=E0606

    @property
    def last_block_slot(self) -> int:
        if self.ogmios_context:
            last_block_slot = self.ogmios_context.last_block_slot
        elif self.blockfrost_context:
            last_block_slot = self.blockfrost_context.last_block_slot
        return last_block_slot  # pylint: disable=E0606

    def get_current_posix_chain_time_ms(self) -> int:
        if self.is_local_testnet:
            return round(time.time_ns() * 1e-6)
        genesis_params = self.genesis_params
        network = cardano_magic_to_network(genesis_params.network_magic)
        slot_config = SLOT_CONFIG_NETWORK[network]

        ms_after_origin = (
            self.last_block_slot - slot_config.zero_slot
        ) * slot_config.slot_length

        return slot_config.zero_time + ms_after_origin

    async def get_metadata_cbor(
        self, tx_id: TransactionId, slot: Optional[int]
    ) -> Optional[RawCBOR]:
        """get metadata cbor for TransactionId in Slot"""
        if self.blockfrost_context:
            response = self.blockfrost_context.api.transaction_metadata_cbor(
                tx_id.to_cbor().hex()
            ).json()
            return RawCBOR(bytes.fromhex(response.metadata))
        if self.ogmios_context:
            if not slot:
                logger.error(
                    "Slot number was not provided when retrieving metadata with Kupo."
                )
                return None
            metadata_cbor = await self.ogmios_context.get_metadata_cbor(tx_id, slot)
            return metadata_cbor
        logger.warning("No context present to retrieve metadata.")
        return None

    async def get_tip(self) -> int:
        if self.blockfrost_context:
            response = self.blockfrost_context.api.block_latest().json()
            return response.slot
        if self.ogmios_context:
            return self.ogmios_context.last_block_slot
        raise NoContextSetup

    def _get_datum(self, utxo):
        """get datum for UTxO"""
        if utxo.output.datum_hash is not None:
            datum = self.context.api.script_datum_cbor(str(utxo.output.datum_hash)).cbor
            return datum
        return None

    def get_datums_for_utxo(self, utxos):
        """insert datum for UTxOs"""
        result = []
        if len(utxos) > 0:
            for utxo in utxos:
                datum = self._get_datum(utxo)
                result.append(datum)
        return result

    def get_node_datums_with_utxo(self, utxos: List[UTxO]) -> List[UTxO]:
        """insert datum for UTxOs"""
        result: List[UTxO] = []
        if len(utxos) > 0:
            for utxo in utxos:
                if utxo.output.amount.multi_asset:
                    datum = self._get_datum(utxo)
                    if datum:
                        utxo.output.datum = NodeDatum.from_cbor(datum)
                    result.append(utxo)
        return result

    async def get_address_balance(self, address: Address) -> int:
        """Get the lovelace balance of an address
        Args:
            address (Address): The address to get the balance from.

        Returns:
            int: The balance of the address in lovelaces."""
        if self.blockfrost_context is not None:
            response = self.blockfrost_context.api.address(str(address))
            for i in response.amount:
                if i.unit == "lovelace":
                    return int(i.quantity)

    async def get_reference_script_utxo(
        self,
        oracle_addr: Address,
        reference_script_input: TransactionInput,
        oracle_script_hash: ScriptHash,
    ) -> UTxO:
        """function to get reference script utxo
        Args:
            oracle_addr (Address): oracle address
            reference_script_input (TransactionInput): reference script input
            oracle_script_hash (ScriptHash): oracle script hash

        Returns:
            UTxO: utxo with plutus script
        """
        utxos = await self.get_utxos(oracle_addr)
        if len(utxos) > 0:
            for utxo in utxos:
                if utxo.input == reference_script_input:
                    if isinstance(self.context, BlockFrostChainContext):
                        script = await self.get_plutus_script(oracle_script_hash)
                        utxo.output.script = script
                    return utxo

    async def get_plutus_script(self, scripthash: ScriptHash) -> PlutusV2Script:
        """
        function to get plutus script and verify it's script hash

        Args:
            scripthash (ScriptHash): script hash of plutus script

        Returns:
            PlutusV2Script: plutus script if script hash matches else None

        """
        if isinstance(self.context, BlockFrostChainContext):
            plutus_script = self.context._get_script(str(scripthash))
            if plutus_script_hash(plutus_script) != scripthash:
                plutus_script = PlutusV2Script(cbor2.dumps(plutus_script))
            if plutus_script_hash(plutus_script) == scripthash:
                return plutus_script

            logger.error("script hash mismatch")

        if isinstance(self.context, KupoOgmiosV6ChainContext):
            logger.error("ogmios context does not support get_script")
            return None

    async def get_utxos(self, address: Union[str, Address, None] = None) -> List[UTxO]:
        """
        get utxos from oracle address.

        Args:
            address (str, Address, optional): The address to get the utxos from. Defaults to None.

        Returns:
            List[UTxO]: The list of utxos.
        """
        if address is None:
            address = self.oracle_address
        if self.blockfrost_context is not None:
            logger.info("Getting utxos from blockfrost")
            return self.blockfrost_context.utxos(str(address))
        if self.ogmios_context is not None:
            logger.info("Getting utxos from ogmios")
            return self.ogmios_context.utxos(str(address))

    async def process_common_inputs(
        self,
        builder: TransactionBuilder,
        address: Address,
        signing_key: Union[PaymentSigningKey, ExtendedSigningKey],
        user_defined_expenses: int = 0,
    ) -> TransactionBuilder:
        """process common inputs for transaction builder

        Args:
            builder (TransactionBuilder): transaction builder
            address (Address): address belonging to signing_key, used for balancing, collateral and change
            signing_key (Union[PaymentSigningKey, ExtendedSigningKey]): signing key
            user_defined_expenses (int): Quantity to cover transaction fees and collateral
        (Default is 0 if not provided, as it will automatically obtain input UTxOs.)

        Returns:
            TransactionBuilder: transaction builder
        """

        # Add input address for tx balancing,
        if user_defined_expenses != 0:
            # Include an input UTXO that exclusively contains ADA (tx fees).
            utxo_for_tx_fees = await self.utxo_for_tx_fees(
                address, signing_key, user_defined_expenses
            )
            builder.add_input(utxo_for_tx_fees)
            builder.required_signers = [address.payment_part]
            return builder
        else:
            # this could include any address utxos and spend them for tx fees
            builder.add_input_address(address)

            # Fresh output for convenience of using for collateral in future
            # **NOTE** This value should align with the user_defined_expenses in the
            # aggregation transaction, as the node executes the aggregation, so the
            # value should cover both collateral and transaction fees.
            # Under normal circumstances, the node updates its value and creates
            # the output  for covering the aggregation, taking advantage of its
            # low memory consumption.
            builder.add_output(TransactionOutput(address, 9000000))

            non_nft_utxo = await self.get_or_create_collateral(address, signing_key)

            if non_nft_utxo is not None:
                builder.collaterals.append(non_nft_utxo)
                builder.required_signers = [address.payment_part]

                return builder

        raise CollateralException("Unable to find or create collateral.")

    async def get_or_create_collateral(
        self,
        address: Address,
        signing_key: Union[PaymentSigningKey, ExtendedSigningKey],
        collateral_amount: int = 9000000,
    ) -> UTxO:
        """get or create collateral
        Args:
            address (Address): address belonging to signing_key, used for balancing, collateral and change
            signing_key (Union[PaymentSigningKey, ExtendedSigningKey]): signing key
        Returns:
            UTxO: utxo
        """
        non_nft_utxo = await self.find_collateral(address, collateral_amount)

        if non_nft_utxo is None:
            await self.create_collateral(address, signing_key, collateral_amount)
            non_nft_utxo = await self.find_collateral(address, collateral_amount)

        return non_nft_utxo

    async def utxo_for_tx_fees(
        self,
        address: Address,
        signing_key: Union[PaymentSigningKey, ExtendedSigningKey],
        required_amount: int,
    ) -> UTxO:
        """get or create utxo for convert blockchain transaction fees
        Args:
            address (Address): address belonging to signing_key, used for balancing, collateral and change
            signing_key (Union[PaymentSigningKey, ExtendedSigningKey]): signing key
            required_amount (int): required amount to cover transaction fees.
        Returns:
            UTxO: utxo
        """
        non_nft_utxo = await self.find_collateral(address, required_amount)

        if non_nft_utxo is None:
            # We reuse the create_collater because it has the same principle
            await self.create_collateral(address, signing_key, required_amount)
            non_nft_utxo = await self.find_collateral(address, required_amount)

        return non_nft_utxo

    async def find_collateral(
        self, target_address: Union[str, Address], required_amount: int
    ) -> UTxO:
        """
        This method finds an UTxO  for the given address with the
        following requirements:
        - required_amount - 1 <= required_amunt < required_amount + 1.
        - no multi asset
        Args:
            target_address (str, Address): The address to find the collateral for.

        Returns:
            UTxO: The  utxo covering the fees if found, None otherwise.

        Note: When used to locate the UTXO for covering expenses in the
        aggregation transaction:
        The aggregation transaction typically consumes approximately 1.3 ADA.
        As we are consolidating collateral and transaction fees into a single UTxO,
        we must ensure that the UTxO used contains at most the required ADA amount.
        We limit the amount to a range of plus and minus 1 because when adding
        collateral, we aim to avoid exposing ourselves to substantial
        potential losses.
        """
        try:
            utxos = await self.get_utxos(address=target_address)
            for utxo in utxos:
                # A collateral should contain no multi asset
                if not utxo.output.amount.multi_asset:
                    if utxo.output.amount < (required_amount + 10000000):
                        if utxo.output.amount.coin >= (required_amount - 1000000):
                            return utxo
        except ApiError as err:
            if err.status_code == 404:
                logger.info("No utxos for tx fees found")
                raise err

            logger.warning(
                "Requirements for tx fees couldn't be satisfied. need an utxo of >= 2 %s",
                err,
            )
        return None

    async def submit_tx_builder(
        self,
        builder: TransactionBuilder,
        signing_key: Union[PaymentSigningKey, ExtendedSigningKey],
        address: Address,
        user_defined_expense: int = 0,
    ) -> Tuple[str, Transaction]:
        """adds collateral and signers to tx, sign and submit tx.

        Args:
            builder (TransactionBuilder): transaction builder
            signing_key (Union[PaymentSigningKey, ExtendedSigningKey]):
        signing key
            address (Address): address belonging to signing_key, used for
        balancing, collateral and change
            user_defined_fee: When not equal to 0, a UTxO with the specified
        ADA amount is searched for to cover blockchain fees.

        Returns:
            Tuple[str, Transaction]: The status of the transaction and the
            transaction object.
        """
        # The minimum suggested amount is 15 ADA for the Aggregate transaction,
        # but ~1.3 ADA is commonly used for covering fees.
        # The aggregate tx is considered the most costly transaction.

        if user_defined_expense > 0:
            builder = await self.process_common_inputs(
                builder, address, signing_key, user_defined_expense
            )
        else:
            builder = await self.process_common_inputs(builder, address, signing_key)

        signed_tx = builder.build_and_sign(
            [signing_key],
            change_address=address,
            auto_validity_start_offset=0,
            auto_ttl_offset=120,
        )

        try:
            return await self.submit_tx_with_print(signed_tx)
        except CollateralException as err:
            logger.error("Error submitting transaction: %s", err)
            return "collateral error", signed_tx
        except (InsufficientUTxOBalanceException, UTxOSelectionException) as exc:
            logger.error("Insufficient Funds in the wallet. %s", exc)
            return "insufficient funds", signed_tx
        except Exception as err:
            logger.error("Error submitting transaction: %s", err)
            return "error", signed_tx

    async def wait_for_tx(
        self, tx_id: TransactionId
    ) -> Tuple[str, Optional[Transaction]]:
        """
        Waits for a transaction with the given ID to be confirmed.
        Retries the API call every 20 seconds if the transaction is not found.
        Stops retrying after a certain number of attempts.

        Args:
            tx_id (TransactionId): The transaction ID to wait for.

        Returns:
            Tuple[str, Optional[Transaction]]: The status of the transaction and
            the transaction object if found, None otherwise.
        """

        async def _wait_for_tx(
            context: Union[BlockFrostChainContext, KupoOgmiosV6ChainContext],
            tx_id: TransactionId,
            check_fn: callable,
            retries: int = 0,
            max_retries: int = 10,
        ) -> Tuple[str, Optional[Transaction]]:
            """Wait for a transaction to be confirmed.

            Args:
                context (Union[BlockFrostChainContext, KupoOgmiosV6ChainContext]): The chain context to use. # pylint: disable=line-too-long
                tx_id (TransactionId): The transaction ID to wait for.
                check_fn (callable): The function to use to check if the transaction is confirmed.
                retries (int, optional): The number of retries. Defaults to 0.
                max_retries (int, optional): The maximum number of retries. Defaults to 10.

            Returns:
                The transaction object if found, None otherwise.
            """
            status = "initiated"
            transaction = None
            while retries < max_retries:
                try:
                    transaction = await check_fn(context, tx_id)
                    if transaction:
                        logger.info("Transaction submitted with tx_id: %s", str(tx_id))
                        status = "success"
                        return status, transaction

                except ApiError as err:
                    if err.status_code == 404:
                        pass
                    else:
                        status = "error: " + str(err)
                        return status, None

                except Exception as err:
                    status = "error: " + str(err)
                    return status, None

                wait_time = 20
                logger.info(
                    "Waiting for transaction confirmation: %s. Retrying in %d seconds",
                    str(tx_id),
                    wait_time,
                )
                retries += 1
                await asyncio.sleep(wait_time)

            logger.error(
                "Transaction not found after %d retries. Giving up.", max_retries
            )
            return status, transaction

        async def check_blockfrost(
            context: BlockFrostChainContext, tx_id: TransactionId
        ) -> Transaction:
            """
            Check if the transaction is confirmed using the blockfrost API.

            Args:
                context (BlockFrostChainContext): The chain context to use.
                tx_id (TransactionId): The transaction ID to wait for.

            Returns:
                The transaction object if found, None otherwise.
            """
            return context.api.transaction(tx_id)

        async def check_ogmios(
            context: KupoOgmiosV6ChainContext, tx_id: TransactionId
        ) -> Transaction:
            """
            Check if the transaction is confirmed using the ogmios API.

            Args:
                context (KupoOgmiosV6ChainContext): The chain context to use.
                tx_id (TransactionId): The transaction ID to wait for.

            Returns:
                The transaction object if found, None otherwise.
            """
            response = context._query_utxos_by_tx_id(tx_id, 0)
            return response if response != [] else None

        if self.ogmios_context:
            return await _wait_for_tx(self.ogmios_context, tx_id, check_ogmios)
        if self.blockfrost_context:
            return await _wait_for_tx(self.blockfrost_context, tx_id, check_blockfrost)

    async def submit_tx_with_print(self, tx: Transaction) -> Tuple[str, Transaction]:
        """
        This method submits a transaction to the chain and prints the transaction ID.

        Args:
            tx: The transaction to submit.

        Returns:
            Tuple[str, Transaction]: The status of the transaction and the transaction object.
        """
        logger.info("Submitting transaction: %s", str(tx.id))
        logger.debug("tx: %s", tx)

        if self.ogmios_context is not None:
            logger.info("Submitting tx with ogmios")
            self.ogmios_context.submit_tx(tx.to_cbor())
        elif self.blockfrost_context is not None:
            logger.info("Submitting tx with blockfrost")
            self.blockfrost_context.submit_tx(tx.to_cbor())

        status, _ = await self.wait_for_tx(str(tx.id))
        return status, tx

    async def create_collateral(
        self,
        target_address: Union[str, Address],
        skey: Union[PaymentSigningKey, ExtendedSigningKey],
        required_amount: int,
    ) -> None:
        """
        This method creates a collateral utxo for the given address with the following requirements:
        - amount = 5000000 lovelaces

        Args:
            target_address (str, Address): The address to create the collateral for.
            skey (PaymentSigningKey, ExtendedSigningKey): The signing key to sign the transaction.
            required_amount: The required ADA amount in the UTxO.

        Returns:
            None
        """
        logger.info("creating collateral UTxO.")
        collateral_builder = TransactionBuilder(self.context)

        collateral_builder.add_input_address(target_address)
        collateral_builder.add_output(
            TransactionOutput(target_address, required_amount)
        )

        await self.submit_tx_with_print(
            collateral_builder.build_and_sign(
                [skey],
                target_address,
                auto_validity_start_offset=0,
                auto_ttl_offset=120,
            )
        )


class StagedTxSubmitter(ChainQuery):
    """Handles tx submission in separate stages: build, sign n times, submit"""

    async def process_common_inputs(
        self,
        builder: TransactionBuilder,
        address: Address,
        signing_key: Union[PaymentSigningKey, ExtendedSigningKey],
    ) -> TransactionBuilder:
        """process common inputs for transaction builder

        Args:
            builder (TransactionBuilder): transaction builder
            address (Address): address belonging to signing_key, used for balancing, collateral and change
            signing_key (Union[PaymentSigningKey, ExtendedSigningKey]): signing key

        Returns:
            TransactionBuilder: transaction builder
        """
        # Add input address for tx balancing,
        # this could include any address utxos and spend them for tx fees
        builder.add_input_address(address)

        # Fresh output for convenience of using for collateral in future
        builder.add_output(TransactionOutput(address, 5000000))

        non_nft_utxo = await self.get_or_create_collateral(address, signing_key)

        if non_nft_utxo is not None:
            builder.collaterals.append(non_nft_utxo)

            return builder

        raise CollateralException("Unable to find or create collateral.")

    async def build_tx(
        self,
        builder: TransactionBuilder,
        signing_key: Union[PaymentSigningKey, ExtendedSigningKey],
        address: Address,
    ) -> Transaction:
        """adds collateral and builds tx.

        Args:
            builder (TransactionBuilder): transaction builder
            signing_key (Union[PaymentSigningKey, ExtendedSigningKey]): signing key
            address (Address): address belonging to signing_key, used for balancing, collateral and change
        """
        builder = await self.process_common_inputs(builder, address, signing_key)

        tx_body = builder.build(
            change_address=address,
            collateral_change_address=address,
            auto_validity_start_offset=0,
            auto_ttl_offset=1000,
        )
        witness_set = builder.build_witness_set()
        witness_set.vkey_witnesses = []

        return Transaction(tx_body, witness_set, auxiliary_data=builder.auxiliary_data)

    def sign_tx(
        self,
        tx: Transaction,
        signing_key: Union[PaymentSigningKey, ExtendedSigningKey],
    ) -> None:
        """add signature to tx witness.

        Args:
            tx (Transaction): transaction object
            signing_key (Union[PaymentSigningKey, ExtendedSigningKey]): signing key
        """
        signature = signing_key.sign(tx.transaction_body.hash())

        # Initialize vkey_witnesses if it's None
        if tx.transaction_witness_set.vkey_witnesses is None:
            tx.transaction_witness_set.vkey_witnesses = []

        tx.transaction_witness_set.vkey_witnesses.append(
            VerificationKeyWitness(signing_key.to_verification_key(), signature)
        )

    async def sign_and_submit_tx(
        self,
        tx: Transaction,
        signing_key: Union[PaymentSigningKey, ExtendedSigningKey],
    ) -> None:
        """sign and submit tx.

        Args:
            builder (TransactionBuilder): transaction builder
            signing_key (Union[PaymentSigningKey, ExtendedSigningKey]): signing key
        """
        self.sign_tx(tx, signing_key)

        try:
            await self.submit_tx_with_print(tx)
        except CollateralException as err:
            logger.error("Error submitting transaction: %s", err)
        except (InsufficientUTxOBalanceException, UTxOSelectionException) as exc:
            print("Insufficient Funds in the wallet.", exc)
        except Exception as err:
            logger.error("Error submitting transaction: %s", err)
