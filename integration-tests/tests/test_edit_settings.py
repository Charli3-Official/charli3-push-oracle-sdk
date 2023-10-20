import pytest

import asyncio

from retry import retry

from pycardano import UTxO

from .base import TEST_RETRIES
from .owner_actions import OracleOwnerActions
from charli3_offchain_core.datums import AggDatum, PriceRewards
from charli3_offchain_core.oracle_checks import filter_utxos_by_asset


@pytest.mark.order(4)
class TestEditSettings(OracleOwnerActions):
    def setup_method(self, method):
        super().setup_method(method)

    @retry(tries=TEST_RETRIES, backoff=1.5, delay=6, jitter=(0, 4))
    @pytest.mark.asyncio
    async def test_edit_settings(self):
        # Get aggState Datum
        oracle_utxos = self.CHAIN_CONTEXT.context.utxos(self.oracle_addr)
        aggstate_utxo: UTxO = filter_utxos_by_asset(oracle_utxos, self.aggstate_nft)[0]
        aggstate_utxo_datum = AggDatum.from_cbor(aggstate_utxo.output.datum.cbor)

        # Update-settings transaction
        updated_oSettings = aggstate_utxo_datum.aggstate.ag_settings
        updated_oSettings.os_updated_nodes = self.updated_config["os_updated_nodes"]
        updated_oSettings.os_updated_node_time = self.updated_config[
            "os_updated_node_time"
        ]
        updated_oSettings.os_aggregate_time = self.updated_config["os_aggregate_time"]
        updated_oSettings.os_aggregate_change = self.updated_config[
            "os_aggregate_change"
        ]
        updated_oSettings.os_minimum_deposit = self.updated_config["os_minimum_deposit"]
        updated_oSettings.os_node_fee_price = PriceRewards(
            node_fee=self.updated_config["os_node_fee_price"]["node_fee"],
            aggregate_fee=self.updated_config["os_node_fee_price"]["aggregate_fee"],
            platform_fee=self.updated_config["os_node_fee_price"]["platform_fee"],
        )

        updated_oSettings.os_iqr_multiplier = self.updated_config["os_iqr_multiplier"]
        updated_oSettings.os_divergence = self.updated_config["os_divergence"]

        platform_pkhs = [self.oracle_owner.pub_key_hash.payload.hex()]
        tx = await self.oracle_owner.mk_edit_settings_tx(
            platform_pkhs, updated_oSettings
        )
        await asyncio.sleep(5)
        await self.oracle_owner.staged_query.sign_and_submit_tx(
            tx, self.oracle_owner.signing_key
        )

        await asyncio.sleep(30)

        # Get updated aggState Datum
        updated_oracle_utxos = self.CHAIN_CONTEXT.context.utxos(self.oracle_addr)
        updated_aggstate_utxo: UTxO = filter_utxos_by_asset(
            updated_oracle_utxos, self.aggstate_nft
        )[0]
        updated_aggstate_utxo_datum = AggDatum.from_cbor(
            updated_aggstate_utxo.output.datum.cbor
        )

        updated_aggSettings = updated_aggstate_utxo_datum.aggstate.ag_settings

        # Assert
        assert (
            updated_oSettings == updated_aggSettings
        ), f"Expected os_updated_nodes: {updated_oSettings}, but got: {updated_aggSettings}"
