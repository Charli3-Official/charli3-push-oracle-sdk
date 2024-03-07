"""Node contract transactions class"""

import time
from copy import deepcopy
from typing import List, Union, Tuple
from pycardano import (
    Network,
    Address,
    PaymentVerificationKey,
    PaymentSigningKey,
    ExtendedSigningKey,
    AssetName,
    TransactionOutput,
    TransactionBuilder,
    Redeemer,
    Asset,
    MultiAsset,
    UTxO,
    ScriptHash,
    Value,
    TransactionInput,
)
from charli3_offchain_core.datums import (
    NodeDatum,
    PriceFeed,
    DataFeed,
    AggDatum,
    OracleDatum,
    PriceData,
    RewardDatum,
)
from charli3_offchain_core.redeemers import NodeUpdate, Aggregate, NodeCollect
from charli3_offchain_core.chain_query import ChainQuery
from charli3_offchain_core.oracle_checks import (
    check_utxo_asset_balance,
    get_oracle_utxos_with_datums,
    c3_get_rate,
)
from charli3_offchain_core.aggregate_conditions import aggregation_conditions
from charli3_offchain_core.utils.logging_config import logging

logger = logging.getLogger("Node")

# CONSTANT
COIN_PRECISION = 1000000


class Node:
    """node transaction implementation"""

    def __init__(
        self,
        network: Network,
        chain_query: ChainQuery,
        signing_key: Union[PaymentSigningKey, ExtendedSigningKey],
        verification_key: PaymentVerificationKey,
        node_nft: MultiAsset,
        aggstate_nft: MultiAsset,
        oracle_nft: MultiAsset,
        reward_nft: MultiAsset,
        oracle_addr: Address,
        c3_token_hash: ScriptHash,
        c3_token_name: AssetName,
        reference_script_input: Union[None, TransactionInput] = None,
        oracle_rate_addr: Union[Address, None] = None,
        oracle_rate_nft: Union[MultiAsset, None] = None,
    ) -> None:
        self.network = network
        self.chain_query = chain_query
        self.context = self.chain_query.context
        self.signing_key = signing_key
        self.verification_key = verification_key
        self.pub_key_hash = self.verification_key.hash()
        self.address = Address(payment_part=self.pub_key_hash, network=self.network)
        self.node_nft = node_nft
        self.aggstate_nft = aggstate_nft
        self.oracle_nft = oracle_nft
        self.reward_nft = reward_nft
        self.node_operator = bytes.fromhex(str(self.pub_key_hash))
        self.oracle_addr = oracle_addr
        self.c3_token_hash = c3_token_hash
        self.c3_token_name = c3_token_name
        self.reference_script_input = reference_script_input
        self.oracle_script_hash = self.oracle_addr.payment_part
        self.oracle_rate_addr = oracle_rate_addr
        self.rate_nft = oracle_rate_nft

    async def update(self, rate: int) -> None:
        """build's partial node update tx.

        This method is called by the node to update its own feed.

        Args:
            rate (int): price rate to be updated.

        Returns:
            None

        """
        logger.info("node update called: %d", rate)
        oracle_utxos = await self.chain_query.get_utxos(self.oracle_addr)
        node_own_utxo = self.get_node_own_utxo(oracle_utxos)

        if node_own_utxo is not None:
            time_ms = round(time.time_ns() * 1e-6)
            new_node_feed = PriceFeed(DataFeed(rate, time_ms))

            node_own_utxo.output.datum.node_state.ns_feed = new_node_feed

            node_update_redeemer = Redeemer(NodeUpdate())

            builder = TransactionBuilder(self.context)

            script_utxo = (
                await self.chain_query.get_reference_script_utxo(
                    self.oracle_addr,
                    self.reference_script_input,
                    self.oracle_script_hash,
                )
                if self.reference_script_input
                else None
            )

            builder.add_script_input(
                node_own_utxo, script=script_utxo, redeemer=node_update_redeemer
            ).add_output(node_own_utxo.output)

            await self.chain_query.submit_tx_builder(
                builder, self.signing_key, self.address
            )
        else:
            logger.error("Node's own utxo is not found")

    async def aggregate(
        self,
    ):
        """build's partial node aggregate tx.

        This method is called by the node to aggregate the oracle feed.

        Args:
            rate (int): price rate to be updated.

        Returns:
            bool : This flag indicates the transaction/operation status:
                True: if transaction is successful and accepted by the network.
                False: if transaction is failed or dropped from the mempool.

        """
        c3_oracle_rate_feed = None
        c3_oracle_rate_utxo = None

        c3_oracle_rate_utxos = (
            await self.chain_query.get_utxos(self.oracle_rate_addr)
            if self.oracle_rate_addr
            else None
        )

        if c3_oracle_rate_utxos is not None:
            (c3_oracle_rate_feed, c3_oracle_rate_utxo) = c3_get_rate(
                c3_oracle_rate_utxos, self.rate_nft
            )

        oracle_utxos = await self.chain_query.get_utxos(self.oracle_addr)
        curr_time_ms = round(time.time_ns() * 1e-6)
        (
            oraclefeed_utxo,
            aggstate_utxo,
            reward_utxo,
            nodes_utxos,
        ) = get_oracle_utxos_with_datums(
            oracle_utxos,
            self.aggstate_nft,
            self.oracle_nft,
            self.reward_nft,
            self.node_nft,
        )
        aggstate_datum: AggDatum = aggstate_utxo.output.datum
        oraclefeed_datum: OracleDatum = oraclefeed_utxo.output.datum
        reward_datum: RewardDatum = reward_utxo.output.datum
        total_nodes = len(aggstate_datum.aggstate.ag_settings.os_node_list)
        fees = aggstate_datum.aggstate.ag_settings.os_node_fee_price

        def scale_reward(val: int) -> int:
            assert (
                c3_oracle_rate_feed is not None
            ), "oracle_rate_feed should not be None"
            return (val * c3_oracle_rate_feed) // COIN_PRECISION

        if not c3_oracle_rate_feed:
            min_c3_required = (
                fees.node_fee * total_nodes + fees.aggregate_fee + fees.platform_fee
            )
        else:
            min_c3_required = (
                scale_reward(fees.node_fee) * total_nodes
                + scale_reward(fees.aggregate_fee)
                + scale_reward(fees.platform_fee)
            )

        # Calculations and Conditions check for aggregation.
        if check_utxo_asset_balance(
            aggstate_utxo, self.c3_token_hash, self.c3_token_name, min_c3_required
        ):
            valid_nodes, agg_value = aggregation_conditions(
                aggstate_datum.aggstate.ag_settings,
                oraclefeed_datum,
                bytes(self.pub_key_hash),
                curr_time_ms,
                nodes_utxos,
            )
            if len(valid_nodes) > 0 and set(valid_nodes).issubset(set(nodes_utxos)):
                if not c3_oracle_rate_feed:
                    c3_fees = (
                        len(valid_nodes) * fees.node_fee
                        + fees.aggregate_fee
                        + fees.platform_fee
                    )
                else:
                    c3_fees = (
                        len(valid_nodes) * scale_reward(fees.node_fee)
                        + scale_reward(fees.aggregate_fee)
                        + scale_reward(fees.platform_fee)
                    )

                oracle_feed_expiry = (
                    curr_time_ms + aggstate_datum.aggstate.ag_settings.os_aggregate_time
                )

                logger.info("aggregate called with agg_value: %d", agg_value)
                aggregate_redeemer = Redeemer(Aggregate())

                script_utxo = (
                    await self.chain_query.get_reference_script_utxo(
                        self.oracle_addr,
                        self.reference_script_input,
                        self.oracle_script_hash,
                    )
                    if self.reference_script_input
                    else None
                )

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
                        aggstate_utxo,
                        script=script_utxo,
                        redeemer=deepcopy(aggregate_redeemer),
                    )
                    .add_script_input(
                        oraclefeed_utxo,
                        script=script_utxo,
                        redeemer=deepcopy(aggregate_redeemer),
                    )
                    .add_output(aggstate_tx_output)
                    .add_output(oraclefeed_tx_output)
                )

                # Managing reward output, updating each node's reward amount in reward datum.
                aggregate_fee_added = False

                for utxo in valid_nodes:
                    node_operator = utxo.output.datum.node_state.ns_operator
                    for reward_info in reward_datum.reward_state.node_reward_list:
                        if reward_info.reward_address == node_operator:
                            reward_info.reward_amount += (
                                fees.node_fee
                                if not c3_oracle_rate_feed
                                else scale_reward(fees.node_fee)
                            )
                        if (
                            reward_info.reward_address == self.node_operator
                            and not aggregate_fee_added
                        ):
                            reward_info.reward_amount += (
                                fees.aggregate_fee
                                if not c3_oracle_rate_feed
                                else scale_reward(fees.aggregate_fee)
                            )
                            aggregate_fee_added = True

                # add platform fee to reward datum
                reward_datum.reward_state.platform_reward += (
                    fees.platform_fee
                    if not c3_oracle_rate_feed
                    else scale_reward(fees.platform_fee)
                )
                reward_tx_output = deepcopy(reward_utxo.output)

                if (
                    self.c3_token_hash in reward_tx_output.amount.multi_asset
                    and self.c3_token_name
                    in reward_tx_output.amount.multi_asset[self.c3_token_hash]
                ):
                    reward_tx_output.amount.multi_asset[self.c3_token_hash][
                        self.c3_token_name
                    ] += c3_fees
                else:
                    # Handle the case where the key does not exist
                    # For example, set the value to a default value
                    c3_asset = MultiAsset(
                        {self.c3_token_hash: Asset({self.c3_token_name: c3_fees})}
                    )

                    reward_tx_output.amount.multi_asset += c3_asset
                reward_tx_output.datum = reward_datum

                builder.add_script_input(
                    reward_utxo, redeemer=deepcopy(aggregate_redeemer)
                ).add_output(reward_tx_output)

                # Adding reference oracle rate utxo
                if c3_oracle_rate_utxo:
                    builder.reference_inputs.add(c3_oracle_rate_utxo.input)

                # adding node utxos as reference inputs,
                # all node utxos referenced as reference inputs.
                builder.reference_inputs.update(nodes_utxos)

                # collateral + aggregation transaction fees
                # Do not alter this value unless you have a clear understanding
                # of the implications. If changed update the value inside the
                # process_common_inputs as well.
                # The suggested value is 9 ADA. In practice, it can be lower
                # (3 ADA), but reducing it too much may lead to errors in the
                # integration-test module.

                user_defined_expense = 9000000
                await self.chain_query.submit_tx_builder(
                    builder, self.signing_key, self.address, user_defined_expense
                )
            else:
                logger.error(
                    "The required minimum number of nodes for aggregation has not been met. \
                     aggregation conditions failed."
                )

        else:
            logger.error("Not enough C3s to perform aggregation")

    async def collect(self, reward_address: Address) -> None:
        """
        build's partial node collect tx.

        This method is called by the node to collect the C3s from the oracle feed.

        Args:
            None

        Returns:
            None

        """
        oracle_utxos = await self.chain_query.get_utxos(self.oracle_addr)
        reward_utxo, reward_datum = self._get_reward_utxo_and_datum(oracle_utxos)

        # preparing multiasset.
        for reward_info in reward_datum.reward_state.node_reward_list:
            if reward_info.reward_address == self.node_operator:
                # get the reward amount and set it to 0
                c3_amount = reward_info.reward_amount
                reward_info.reward_amount = 0
                break
        if c3_amount == 0:
            logger.error("No reward to collect")
            return

        c3_asset = MultiAsset(
            {self.c3_token_hash: Asset({self.c3_token_name: c3_amount})}
        )

        tx_output = deepcopy(reward_utxo.output)
        tx_output.amount.multi_asset -= c3_asset
        tx_output.datum = reward_datum

        node_collect_redeemer = Redeemer(NodeCollect())

        script_utxo = (
            await self.chain_query.get_reference_script_utxo(
                self.oracle_addr,
                self.reference_script_input,
                self.oracle_script_hash,
            )
            if self.reference_script_input
            else None
        )

        builder = TransactionBuilder(self.context)

        (
            builder.add_script_input(
                reward_utxo, script=script_utxo, redeemer=node_collect_redeemer
            )
            .add_output(tx_output)
            .add_output(TransactionOutput(reward_address, Value(2000000, c3_asset)))
        )

        await self.chain_query.submit_tx_builder(
            builder, self.signing_key, self.address
        )

    def get_node_own_utxo(self, oracle_utxos: List[UTxO]) -> UTxO:
        """returns node's own utxo from list of oracle UTxOs

        Args:
            oracle_utxos (List[UTxO]): List of oracle UTxOs

        Returns:
            UTxO: node's own UTxO

        """
        nodes_utxos = self.filter_utxos_by_asset(oracle_utxos, self.node_nft)
        return self.filter_node_utxos_by_node_operator(nodes_utxos)

    def filter_utxos_by_asset(self, utxos: List[UTxO], asset: MultiAsset) -> List[UTxO]:
        """
        filter list of UTxOs by given asset

        Args:
            utxos (List[UTxO]): List of UTxOs
            asset (MultiAsset): asset to filter by

        Returns:
            List[UTxO]: List of UTxOs filtered by given asset

        """
        return list(filter(lambda x: x.output.amount.multi_asset >= asset, utxos))

    def filter_node_utxos_by_node_operator(self, nodes_utxo: List[UTxO]) -> UTxO:
        """
        filter list of UTxOs by given node_operator

        Args:
            nodes_utxo (List[UTxO]): List of UTxOs

        Returns:
            UTxO: node's own UTxO filtered by given node_operator

        """
        if len(nodes_utxo) > 0:
            for utxo in nodes_utxo:
                if utxo.output.datum:
                    if utxo.output.datum.cbor:
                        utxo.output.datum = NodeDatum.from_cbor(utxo.output.datum.cbor)

                    if utxo.output.datum.node_state.ns_operator == self.node_operator:
                        return utxo
        return None

    def update_own_node_utxo(
        self, nodes_utxo: List[UTxO], updated_node_feed: PriceFeed
    ) -> List[UTxO]:
        """
        update own node utxo and return node utxos

        Args:
            nodes_utxo (List[UTxO]): List of UTxOs
            updated_node_feed (PriceFeed): updated node feed

        Returns:
            List[UTxO]: List of UTxOs

        """
        if len(nodes_utxo) > 0:
            for utxo in nodes_utxo:
                if utxo.output.datum.node_state.ns_operator == self.node_operator:
                    utxo.output.datum.node_state.ns_feed = updated_node_feed

        return nodes_utxo

    def _get_reward_utxo_and_datum(
        self, oracle_utxos: List[UTxO]
    ) -> Tuple[UTxO, RewardDatum]:
        """Get reward utxo and datum."""
        rewardstate_utxo: UTxO = self.filter_utxos_by_asset(
            oracle_utxos, self.reward_nft
        )[0]
        rewardstate_datum: RewardDatum = RewardDatum.from_cbor(
            rewardstate_utxo.output.datum.cbor
        )
        return rewardstate_utxo, rewardstate_datum
