"""Node contract transactions class"""
import time
from typing import List
import cbor2
from pycardano import (Network, Address, PaymentVerificationKey, PaymentSigningKey,
                       TransactionOutput, TransactionBuilder, Redeemer, RedeemerTag,
                       MultiAsset, UTxO, plutus_script_hash, PlutusV2Script)
from datums import NodeDatum, NodeInfo, PriceFeed, DataFeed
from redeemers import NodeUpdate
from chain_query import ChainQuery


class Node():
    """node transaction implementation"""
    def __init__(self,
                    network: Network,
                    context: ChainQuery,
                    signing_key: PaymentSigningKey,
                    verification_key: PaymentVerificationKey,
                    node_nft: MultiAsset,
                    oracle_addr: Address
                 ) -> None:
        self.network = network
        self.context = context
        self.signing_key = signing_key
        self.verification_key = verification_key
        self.pub_key_hash = self.verification_key.hash()
        self.address = Address(payment_part=self.pub_key_hash, network=self.network)
        self.node_nft = node_nft
        self.node_info = NodeInfo(bytes.fromhex(str(self.pub_key_hash)))
        self.oracle_addr = oracle_addr
        self.oracle_script_hash = self.oracle_addr.payment_part

    def update(self, rate: int):
        """build's partial node update tx."""
        oracle_utxos = self.context.utxos(str(self.oracle_addr))
        node_own_utxo = self.get_node_own_utxo(oracle_utxos)
        node_own_datum : NodeDatum = NodeDatum.from_cbor(node_own_utxo.output.datum.cbor)
        time_ms = round(time.time_ns()*1e-6)
        new_node_feed = PriceFeed(DataFeed(rate, time_ms))
        node_own_datum.node_state.nodeFeed = new_node_feed

        node_update_utxo_output = TransactionOutput(
            address=node_own_utxo.output.address,
            amount=node_own_utxo.output.amount,
            datum=node_own_datum
        )

        node_update_redeemer = Redeemer(
            RedeemerTag.SPEND, NodeUpdate())

        builder = TransactionBuilder(self.context)

        (
            builder
            .add_script_input(node_own_utxo, redeemer=node_update_redeemer)
            .add_output(node_update_utxo_output)
            .add_input_address(self.address)
        )

        # self.submit_tx_builder(builder)

    def create_reference_script(self):
        """build's partial reference script tx."""

        oracle_script = self.context._get_script(str(self.oracle_script_hash))
        if plutus_script_hash(oracle_script) != self.oracle_script_hash:
            oracle_script = PlutusV2Script(cbor2.dumps(oracle_script))

        if plutus_script_hash(oracle_script) == self.oracle_script_hash:
            reference_script_utxo_output = TransactionOutput(
                address=self.oracle_addr,
                amount=20000000,
                script=oracle_script
            )

            builder = TransactionBuilder(self.context)

            (
                builder
                .add_output(reference_script_utxo_output)
                .add_input_address(self.address)
            )

            self.submit_tx_builder(builder)
        else:
            print("script hash mismatch")

    def submit_tx_builder(self, builder: TransactionBuilder):
        """adds collateral and signers to tx , sign and submit tx."""
        non_nft_utxo = self.context.find_collateral(self.address)

        if non_nft_utxo is None:
            self.context.create_collateral(self.address, self.signing_key)
            non_nft_utxo = self.context.find_collateral(self.address)

        builder.collaterals.append(non_nft_utxo)
        builder.required_signers = [self.pub_key_hash]

        signed_tx = builder.build_and_sign(
            [self.signing_key], change_address=self.address)
        self.context.submit_tx_with_print(signed_tx)

    def get_node_own_utxo(self, oracle_utxos: List[UTxO]) -> UTxO:
        """returns node's own utxo from list of oracle UTxOs"""
        nodes_utxos = self.filter_utxos_by_asset(oracle_utxos, self.node_nft)
        return self.filter_node_utxos_by_node_info(nodes_utxos)

    def filter_utxos_by_asset(self, utxos: List[UTxO], asset: MultiAsset) -> List[UTxO]:
        """filter list of UTxOs by given asset"""
        return list(filter(lambda x: x.output.amount.multi_asset >= asset, utxos))

    def filter_node_utxos_by_node_info(self, nodes_utxo: List[UTxO]) -> UTxO:
        """filter list of UTxOs by given node_info"""
        node_datum : NodeDatum
        if len(nodes_utxo) > 0:
            for utxo in nodes_utxo:
                if utxo.output.datum:
                    node_datum = NodeDatum.from_cbor(utxo.output.datum.cbor)
                    if node_datum.node_state.nodeOperator == self.node_info:
                        return utxo
        return None
