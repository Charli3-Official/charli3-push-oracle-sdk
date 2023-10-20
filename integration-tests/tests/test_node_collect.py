import pytest

import asyncio

from retry import retry

from pycardano import UTxO

from .base import TEST_RETRIES
from .owner_actions import OracleOwnerActions
from charli3_offchain_core.datums import RewardDatum
from charli3_offchain_core.oracle_checks import filter_utxos_by_asset
from charli3_offchain_core.node import Node


@pytest.mark.order(8)
class TestNodeCollect(OracleOwnerActions):
    def setup_method(self, method):
        super().setup_method(method)

    @retry(tries=TEST_RETRIES, backoff=1.5, delay=6, jitter=(0, 4))
    @pytest.mark.asyncio
    async def test_node_collect(self):
        nodes = []
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

        for node in nodes:
            await node.collect(node.address)
            await asyncio.sleep(20)

        # Get Reward UTxO's Datum
        oracle_utxos = self.CHAIN_CONTEXT.context.utxos(self.oracle_addr)
        reward_utxo: UTxO = filter_utxos_by_asset(oracle_utxos, self.reward_nft)[0]

        reward_utxo_datum = RewardDatum.from_cbor(reward_utxo.output.datum.cbor)

        node_reward_list = reward_utxo_datum.reward_state.node_reward_list

        for i in node_reward_list:
            assert (
                i.reward_amount == 0
            ), f"Expected node reward to be 0 after the node collection transaction, but instead got {i.reward_amount}"
