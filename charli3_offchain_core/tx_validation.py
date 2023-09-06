from typing import List, Optional, Tuple, Union
from pycardano import Transaction, Network, PaymentVerificationKey, Address, UTxO
from charli3_offchain_core.utils.logging_config import logging
from charli3_offchain_core.oracle_checks import check_type
from charli3_offchain_core.chain_query import ChainQuery


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
        tx: Transaction,
    ) -> None:
        check_type(network, Network, "network")
        check_type(chainquery, ChainQuery, "chainquery")
        check_type(tx, Transaction, "tx")
        check_type(verification_key, PaymentVerificationKey, "verification_key")
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
        self.tx = tx
        self._validate_own_inputs()

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

    def raise_if_invalid(self, allow_own_inputs: bool) -> None:
        if self.has_own_inputs and not allow_own_inputs:
            raise TxValidationException("Transaction contains own wallets inputs")
        if self.has_own_collateral_inputs and not allow_own_inputs:
            raise TxValidationException(
                "Transaction contains own wallets collateral inputs"
            )
