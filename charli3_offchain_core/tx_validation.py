from typing import List, Optional, Tuple, Union
from pycardano import (
    Transaction,
    Network,
    PaymentVerificationKey,
    Address,
    UTxO,
    MultiAsset,
    VerificationKeyHash,
)
from charli3_offchain_core.utils.logging_config import logging
from charli3_offchain_core.oracle_checks import check_type, filter_utxos_by_asset
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
        oracle_addr: str,
        aggstate_nft: MultiAsset,
        tx: Transaction,
    ) -> None:
        check_type(network, Network, "network")
        check_type(chainquery, ChainQuery, "chainquery")
        check_type(tx, Transaction, "tx")
        check_type(verification_key, PaymentVerificationKey, "verification_key")
        check_type(oracle_addr, str, "oracle_addr")
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
        self.oracle_addr = Address.from_primitive(oracle_addr)
        self.tx = tx
        self.aggstate_nft = aggstate_nft

        self._validate_own_inputs()
        self._validate_signatories()

    def _validate_own_inputs(
        self,
    ) -> None:
        self.has_own_inputs = False
        self.has_own_collateral_inputs = False
        body = self.tx.transaction_body

        own_utxos: List[UTxO] = self.chainquery.get_utxos(
            self.full_address
        ) + self.chainquery.get_utxos(self.payment_address)

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
        aggstate_utxo: UTxO = filter_utxos_by_asset(oracle_utxos, self.aggstate_nft)[0]
        aggstate_datum: AggDatum = AggDatum.from_cbor(aggstate_utxo.output.datum.cbor)
        allowed_signatories: List[VerificationKeyHash] = [
            VerificationKeyHash.from_primitive(pkh)
            for pkh in aggstate_datum.aggstate.ag_settings.os_platform.pmultisig_pkhs
        ]
        for signatory in self.tx.transaction_body.required_signers:
            if not signatory in allowed_signatories:
                self.all_signatories_allowed = False
                break
        if not self.all_signatories_allowed:
            logger.warning("Transaction required signature outside of oracle platform")

    def raise_if_invalid(self, allow_own_inputs: bool) -> None:
        """Raises TxValidationException if tx is not valid"""
        if not self.tx.valid:
            raise TxValidationException("Transaction not valid")

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
