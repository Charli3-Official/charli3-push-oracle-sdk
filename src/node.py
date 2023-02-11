"""Node contract transactions class"""
import time
from copy import deepcopy
from typing import List
from pycardano import (
    Network,
    Address,
    PaymentVerificationKey,
    PaymentSigningKey,
    AssetName,
    TransactionOutput,
    TransactionBuilder,
    Redeemer,
    RedeemerTag,
    Asset,
    MultiAsset,
    UTxO,
    ScriptHash,
    Value,
)
from datums import (
    NodeDatum,
    NodeInfo,
    PriceFeed,
    DataFeed,
    AggDatum,
    OracleDatum,
    PriceData,
)
from redeemers import NodeUpdate, Aggregate, UpdateAndAggregate, NodeCollect
from chain_query import ChainQuery
from oracle_checks import check_utxo_asset_balance, get_oracle_utxos_with_datums
from aggregate_conditions import aggregation_conditions


class Node:
    """node transaction implementation"""

    def __init__(
        self,
        network: Network,
        context: ChainQuery,
        signing_key: PaymentSigningKey,
        verification_key: PaymentVerificationKey,
        node_nft: MultiAsset,
        aggstate_nft: MultiAsset,
        oracle_nft: MultiAsset,
        oracle_addr: Address,
        c3_token_hash: ScriptHash,
        c3_token_name: AssetName,
    ) -> None:
        self.network = network
        self.context = context
        self.signing_key = signing_key
        self.verification_key = verification_key
        self.pub_key_hash = self.verification_key.hash()
        self.address = Address(payment_part=self.pub_key_hash, network=self.network)
        self.node_nft = node_nft
        self.aggstate_nft = aggstate_nft
        self.oracle_nft = oracle_nft
        self.node_info = NodeInfo(bytes.fromhex(str(self.pub_key_hash)))
        self.oracle_addr = oracle_addr
        self.c3_token_hash = c3_token_hash
        self.c3_token_name = c3_token_name
        self.oracle_script_hash = self.oracle_addr.payment_part

    def update(self, rate: int):
        """build's partial node update tx."""
        oracle_utxos = self.context.utxos(str(self.oracle_addr))
        node_own_utxo = self.get_node_own_utxo(oracle_utxos)
        time_ms = round(time.time_ns() * 1e-6)
        new_node_feed = PriceFeed(DataFeed(rate, time_ms))

        node_own_utxo.output.datum.node_state.nodeFeed = new_node_feed

        node_update_redeemer = Redeemer(RedeemerTag.SPEND, NodeUpdate())

        builder = TransactionBuilder(self.context)

        (
            builder.add_script_input(
                node_own_utxo, redeemer=node_update_redeemer
            ).add_output(node_own_utxo.output)
        )

        self.submit_tx_builder(builder)

    def aggregate(self, rate: int = None, update_node_output: bool = False):
        """build's partial node aggregate tx."""
        oracle_utxos = self.context.utxos(str(self.oracle_addr))
        curr_time_ms = round(time.time_ns() * 1e-6)
        oraclefeed_utxo, aggstate_utxo, nodes_utxos = get_oracle_utxos_with_datums(
            oracle_utxos, self.aggstate_nft, self.oracle_nft, self.node_nft
        )
        aggstate_datum: AggDatum = aggstate_utxo.output.datum
        oraclefeed_datum: OracleDatum = oraclefeed_utxo.output.datum
        total_nodes = len(aggstate_datum.aggstate.agSettings.os_node_list)
        single_node_fee = (
            aggstate_datum.aggstate.agSettings.os_node_fee_price.getNodeFee
        )
        min_c3_required = single_node_fee * total_nodes

        # Handling update_aggregate logic here.
        if update_node_output:
            new_node_feed = PriceFeed(DataFeed(rate, curr_time_ms))
            nodes_utxos = self.update_own_node_utxo(nodes_utxos, new_node_feed)

        # Calculations and Conditions check for aggregation.
        if check_utxo_asset_balance(
            aggstate_utxo, self.c3_token_hash, self.c3_token_name, min_c3_required
        ):

            valid_nodes, agg_value = aggregation_conditions(
                aggstate_datum.aggstate.agSettings,
                oraclefeed_datum,
                bytes(self.pub_key_hash),
                curr_time_ms,
                nodes_utxos,
            )

            if len(valid_nodes) > 0 and set(valid_nodes).issubset(set(nodes_utxos)):

                c3_fees = len(valid_nodes) * single_node_fee
                oracle_feed_expiry = (
                    curr_time_ms + aggstate_datum.aggstate.agSettings.os_aggregate_time
                )

                if update_node_output:
                    aggregate_redeemer = Redeemer(
                        RedeemerTag.SPEND,
                        UpdateAndAggregate(pub_key_hash=bytes(self.pub_key_hash)),
                    )
                else:
                    aggregate_redeemer = Redeemer(RedeemerTag.SPEND, Aggregate())

                builder = TransactionBuilder(self.context)

                aggstate_tx_output = deepcopy(aggstate_utxo.output)
                aggstate_tx_output.amount.multi_asset[self.c3_token_hash][
                    self.c3_token_name
                ] -= c3_fees

                oraclefeed_tx_output = deepcopy(oraclefeed_utxo.output)
                oraclefeed_tx_output.datum = OracleDatum(
                    PriceData.set_price_map(agg_value, curr_time_ms, oracle_feed_expiry)
                )

                (
                    builder.add_script_input(
                        aggstate_utxo, redeemer=deepcopy(aggregate_redeemer)
                    )
                    .add_script_input(
                        oraclefeed_utxo, redeemer=deepcopy(aggregate_redeemer)
                    )
                    .add_output(aggstate_tx_output)
                    .add_output(oraclefeed_tx_output)
                )

                for utxo in valid_nodes:
                    builder.add_script_input(
                        utxo, redeemer=deepcopy(aggregate_redeemer)
                    )
                    tx_output = deepcopy(utxo.output)
                    if (
                        self.c3_token_hash in tx_output.amount.multi_asset
                        and self.c3_token_name
                        in tx_output.amount.multi_asset[self.c3_token_hash]
                    ):
                        tx_output.amount.multi_asset[self.c3_token_hash][
                            self.c3_token_name
                        ] += single_node_fee
                    else:
                        # Handle the case where the key does not exist
                        # For example, set the value to a default value
                        c3_asset = MultiAsset(
                            {
                                self.c3_token_hash: Asset(
                                    {self.c3_token_name: single_node_fee}
                                )
                            }
                        )
                        tx_output.amount.multi_asset += c3_asset

                    builder.add_output(tx_output)

                self.submit_tx_builder(builder)
            else:
                print(
                    "The required minimum number of nodes for aggregation has not been met. \
                     aggregation conditions failed."
                )

        else:
            print("Not enough C3s to perform aggregation")

    def update_aggregate(self, rate: int):
        """build's partial node update_aggregate tx."""
        self.aggregate(rate=rate, update_node_output=True)

    def collect(self, reward_address: Address):
        """build's partial node collect tx."""
        oracle_utxos = self.context.utxos(str(self.oracle_addr))
        node_own_utxo = self.get_node_own_utxo(oracle_utxos)

        # preparing multiasset.
        c3_amount = node_own_utxo.output.amount.multi_asset[self.c3_token_hash][
            self.c3_token_name
        ]

        c3_asset = MultiAsset(
            {self.c3_token_hash: Asset({self.c3_token_name: c3_amount})}
        )

        tx_output = deepcopy(node_own_utxo.output)
        tx_output.amount.multi_asset -= c3_asset

        node_collect_redeemer = Redeemer(RedeemerTag.SPEND, NodeCollect())

        builder = TransactionBuilder(self.context)

        (
            builder.add_script_input(node_own_utxo, redeemer=node_collect_redeemer)
            .add_output(tx_output)
            .add_output(TransactionOutput(reward_address, Value(2000000, c3_asset)))
        )

        self.submit_tx_builder(builder)


    def submit_tx_builder(self, builder: TransactionBuilder):
        """adds collateral and signers to tx , sign and submit tx."""
        # abstracting common inputs here.
        builder.add_input_address(self.address)
        builder.add_output(TransactionOutput(self.address, 5000000))

        non_nft_utxo = self.context.find_collateral(self.address)

        if non_nft_utxo is None:
            self.context.create_collateral(self.address, self.signing_key)
            non_nft_utxo = self.context.find_collateral(self.address)

        if non_nft_utxo is not None:
            builder.collaterals.append(non_nft_utxo)
            builder.required_signers = [self.pub_key_hash]

            signed_tx = builder.build_and_sign(
                [self.signing_key], change_address=self.address
            )
            self.context.submit_tx_with_print(signed_tx)
        else:
            print("collateral utxo is None.")

    def get_node_own_utxo(self, oracle_utxos: List[UTxO]) -> UTxO:
        """returns node's own utxo from list of oracle UTxOs"""
        nodes_utxos = self.filter_utxos_by_asset(oracle_utxos, self.node_nft)
        return self.filter_node_utxos_by_node_info(nodes_utxos)

    def filter_utxos_by_asset(self, utxos: List[UTxO], asset: MultiAsset) -> List[UTxO]:
        """filter list of UTxOs by given asset"""
        return list(filter(lambda x: x.output.amount.multi_asset >= asset, utxos))

    def filter_node_utxos_by_node_info(self, nodes_utxo: List[UTxO]) -> UTxO:
        """filter list of UTxOs by given node_info"""
        if len(nodes_utxo) > 0:
            for utxo in nodes_utxo:
                if utxo.output.datum:

                    if utxo.output.datum.cbor:
                        utxo.output.datum = NodeDatum.from_cbor(utxo.output.datum.cbor)

                    if utxo.output.datum.node_state.nodeOperator == self.node_info:
                        return utxo
        return None

    def update_own_node_utxo(
        self, nodes_utxo: List[UTxO], updated_node_feed: PriceFeed
    ) -> List[UTxO]:
        """update own node utxo and return node utxos"""
        if len(nodes_utxo) > 0:
            for utxo in nodes_utxo:
                if utxo.output.datum.node_state.nodeOperator == self.node_info:
                    utxo.output.datum.node_state.nodeFeed = updated_node_feed

        return nodes_utxo
