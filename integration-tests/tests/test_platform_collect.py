import pytest

import asyncio

from retry import retry

from pycardano import UTxO

from .base import TEST_RETRIES, OracleOwnerActions
from charli3_offchain_core.datums import AggDatum, PriceRewards, RewardDatum
from charli3_offchain_core.oracle_checks import filter_utxos_by_asset


@pytest.mark.order(8)
class TestPlatformCollect(OracleOwnerActions):
    def setup_method(self, method):
        super().setup_method(method)

    @retry(tries=TEST_RETRIES, backoff=1.5, delay=6, jitter=(0, 4))
    @pytest.mark.asyncio
    async def test_platform_collect(self):
        # Get Reward UTxO's Datum
        oracle_utxos = self.CHAIN_CONTEXT.context.utxos(self.oracle_addr)
        reward_utxo: UTxO = filter_utxos_by_asset(oracle_utxos, self.reward_nft)[0]

        reward_utxo_datum = RewardDatum.from_cbor(reward_utxo.output.datum.cbor)
        # Get the platform quantity
        reward_quantity = reward_utxo_datum.reward_state.platform_reward

        await self.oracle_owner.platform_collect()

        await asyncio.sleep(30)

        # Get Reward UTxO's Datum afeter execute the transaction
        updated_oracle_utxos = self.CHAIN_CONTEXT.context.utxos(self.oracle_addr)
        reward_utxo: UTxO = filter_utxos_by_asset(
            updated_oracle_utxos, self.reward_nft
        )[0]

        updated_reward_utxo_datum = RewardDatum.from_cbor(reward_utxo.output.datum.cbor)
        # Get the platform quantity
        updated_reward_quantity = updated_reward_utxo_datum.reward_state.platform_reward

        assert (
            reward_quantity != updated_reward_quantity
        ), f"The platfrome reward is the same after collect-platfrom-tx, got {updated_reward_quantity}"
        assert (
            updated_reward_quantity == 0
        ), f"Expected 0 platform reward after collect-platform-tx, but got {updated_reward_quantity}"
