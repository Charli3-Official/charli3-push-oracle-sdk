import pytest

import asyncio

from retry import retry

from pycardano import UTxO

from .base import TEST_RETRIES, OracleOwnerActions
from charli3_offchain_core.datums import OracleDatum
from charli3_offchain_core.oracle_checks import filter_utxos_by_asset
from charli3_offchain_core.node import Node


@pytest.mark.order(6)
class TestAggregate(OracleOwnerActions):
    def setup_method(self, method):
        super().setup_method(method)

    @retry(tries=TEST_RETRIES, backoff=1.5, delay=6, jitter=(0, 4))
    @pytest.mark.asyncio
    async def test_aggregate(self):
        nodes = []
        # Aggregation with 3 nodes because of memmory limitations
        for i in range(1, 4):
            skey, vkey = self.wallet_keys[i]
            node = Node(
                self.NETWORK,
                self.CHAIN_CONTEXT,
                skey,
                vkey,
                self.single_node_nft,
                self.aggstate_nft,
                self.oracle_feed_nft,
                self.reward_nft,
                self.oracle_addr,
                self.payment_script_hash,
                self.tC3_token_name,
            )
            nodes.append(node)

        update_tasks = [
            node.update(value) for node, value in zip(nodes, self.nodes_values)
        ]

        # Run all updates in parallel
        await asyncio.gather(*update_tasks)

        # After all updates are done, sleep for a while
        await asyncio.sleep(30)

        print("Aggregating...")
        await nodes[-1].aggregate()

        await asyncio.sleep(30)

        updated_oracle_utxos = self.CHAIN_CONTEXT.context.utxos(self.oracle_addr)
        updated_oracle_feed_utxo: UTxO = filter_utxos_by_asset(
            updated_oracle_utxos, self.oracle_feed_nft
        )[0]
        updated_oracle_feed_utxo_datum = OracleDatum.from_cbor(
            updated_oracle_feed_utxo.output.datum.cbor
        )
        exchange_rate = updated_oracle_feed_utxo_datum.price_data.get_price()
        expected_exchange_rate = 411500511
        assert (
            exchange_rate == expected_exchange_rate
        ), f"Expected exchange_rate: {expected_exchange_rate}, but got: {exchange_rate}"
