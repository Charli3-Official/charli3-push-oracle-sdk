from typing import List, Optional
from pycardano import (
    Transaction,
    Network,
    PaymentVerificationKey,
    Address,
    UTxO,
    MultiAsset,
    VerificationKeyHash,
    TransactionId,
)
from charli3_offchain_core.utils.logging_config import logging
from charli3_offchain_core.oracle_checks import (
    check_type,
    filter_utxos_by_asset,
    filter_utxos_by_currency,
)
from charli3_offchain_core.chain_query import ChainQuery
from charli3_offchain_core.datums import AggDatum

logger = logging.getLogger("Tx-Validation")


class TxValidationException(Exception):
    pass


class TxValidator:
    """Off-chain transaction validation"""

    def __init__(
        self,
        network: Network,
        chainquery: ChainQuery,
        verification_key: PaymentVerificationKey,
        stake_key: Optional[PaymentVerificationKey],
        oracle_addr: Address,
        aggstate_nft: MultiAsset,
        tx: Transaction,
    ) -> None:
        check_type(network, Network, "network")
        check_type(chainquery, ChainQuery, "chainquery")
        check_type(tx, Transaction, "tx")
        check_type(verification_key, PaymentVerificationKey, "verification_key")
        check_type(oracle_addr, Address, "oracle_addr")
        check_type(aggstate_nft, MultiAsset, "aggstate_nft")
        if stake_key is not None:
            check_type(stake_key, PaymentVerificationKey, "stake_key")
        self.network = network
        self.chainquery = chainquery
        self.verification_key = verification_key
        self.pub_key_hash = self.verification_key.hash()
        self.stake_key = stake_key
        if self.stake_key:
            self.stake_key_hash = self.stake_key.hash()
        else:
            self.stake_key_hash = None
        self.full_address = Address(
            payment_part=self.pub_key_hash,
            staking_part=self.stake_key_hash,
            network=self.network,
        )
        self.payment_address = Address(
            payment_part=self.pub_key_hash,
            network=self.network,
        )
        self.oracle_addr = oracle_addr
        self.tx = tx
        self.aggstate_nft = aggstate_nft

        self._validate_own_inputs()
        self._validate_signatories()
        self._validate_oracle_inputs()

    def _validate_own_inputs(
        self,
    ) -> None:
        self.has_own_inputs = False
        self.has_own_collateral_inputs = False
        body = self.tx.transaction_body

        own_utxos: List[UTxO] = self.chainquery.context.utxos(
            self.full_address
        ) + self.chainquery.context.utxos(self.payment_address)

        tx_inputs = body.inputs
        tx_collateral_inputs = body.collateral
        for utxo in own_utxos:
            if utxo.input in tx_inputs:
                self.has_own_inputs = True
            if utxo.input in tx_collateral_inputs:
                self.has_own_collateral_inputs = True
            if self.has_own_inputs and self.has_own_collateral_inputs:
                break

        if self.has_own_inputs:
            logger.warning("Transaction contains own wallets inputs")
        if self.has_own_collateral_inputs:
            logger.warning("Transaction contains own wallets collateral inputs")

    def _validate_signatories(self) -> None:
        self.own_signature_required = (
            self.pub_key_hash in self.tx.transaction_body.required_signers
        )
        if not self.own_signature_required:
            logger.warning("Transaction does not require signature from this wallet")

        self.all_signatories_allowed = True
        oracle_utxos = self.chainquery.context.utxos(self.oracle_addr)
        aggstate_utxos: List[UTxO] = filter_utxos_by_asset(
            oracle_utxos, self.aggstate_nft
        )
        aggstate_utxo: UTxO = dict(enumerate(aggstate_utxos)).get(0)
        if aggstate_utxo:
            self.oracle_exists = True
            aggstate_datum: AggDatum = AggDatum.from_cbor(
                aggstate_utxo.output.datum.cbor
            )
            allowed_signatories: List[VerificationKeyHash] = [
                VerificationKeyHash.from_primitive(pkh)
                for pkh in aggstate_datum.aggstate.ag_settings.os_platform.pmultisig_pkhs
            ]
            for signatory in self.tx.transaction_body.required_signers:
                if signatory not in allowed_signatories:
                    self.all_signatories_allowed = False
                    break
            if not self.all_signatories_allowed:
                logger.warning(
                    "Transaction required signature outside of oracle platform"
                )
        else:
            self.oracle_exists = False
            logger.warning("Could not find aggstate utxo, oracle does not exist")

    def _validate_oracle_inputs(self) -> None:
        self.contains_oracle_inputs = False
        oracle_nft_currency = next(iter(self.aggstate_nft.keys()))
        oracle_utxos = filter_utxos_by_currency(
            self.chainquery.context.utxos(self.oracle_addr), oracle_nft_currency
        )
        for utxo in oracle_utxos:
            if utxo.input in self.tx.transaction_body.inputs:
                self.contains_oracle_inputs = True
        if not self.contains_oracle_inputs:
            logger.warning("Transaction does not consume any up-to-date oracle inputs")

    def raise_if_invalid(
        self, allow_own_inputs: bool, assume_oracle_exists: bool = True
    ) -> None:
        """Raises TxValidationException if tx is not valid"""
        if not self.tx.valid:
            raise TxValidationException("Transaction not valid")

        if assume_oracle_exists and not self.oracle_exists:
            raise TxValidationException("Oracle does not exist")
        if not assume_oracle_exists and self.oracle_exists:
            raise TxValidationException(
                "Transaction is trying to start oracle that already exists"
            )
        if assume_oracle_exists and not self.contains_oracle_inputs:
            raise TxValidationException(
                "Transaction does not consume any up-to-date oracle inputs"
            )

        if self.has_own_inputs and not allow_own_inputs:
            raise TxValidationException("Transaction contains own wallets inputs")
        if self.has_own_collateral_inputs and not allow_own_inputs:
            raise TxValidationException(
                "Transaction contains own wallets collateral inputs"
            )

        if not self.own_signature_required:
            raise TxValidationException(
                "Transaction does not require signature from this wallet"
            )
        if not self.all_signatories_allowed:
            raise TxValidationException(
                "Transaction required signature outside of oracle platform"
            )

    def raise_if_wrong_tx_id(self, tx_id: str) -> None:
        """
        Raises TxValidationException if tx has not matching tx id.
        This is useful for wallet, who balanced the tx,
        therefore it contains his own inputs and he knows original tx id.
        """
        if self.tx.id != TransactionId.from_primitive(tx_id):
            raise TxValidationException("Transaction has wrong tx id")
