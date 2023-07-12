import pytest

import asyncio

from retry import retry

from pycardano import MultiAsset, TransactionOutput, Value, RawCBOR

from src.oracle_owner import OracleOwner
from src.owner_script import OwnerScript
from src.datums import OracleSettings, AggDatum, PriceRewards

from .base import TEST_RETRIES, TestBase


class TestEditSettings(TestBase):
    def setup_method(self, method):
        self.oracle_owner = OracleOwner(
            network=self.NETWORK,
            chainquery=self.chain_context,
            signing_key=self.owner_signing_key,
            verification_key=self.owner_verification_key,
            node_nft=self.oracle_nft,
            aggstate_nft=self.aggstate_nft,
            oracle_nft=self.oracle_nft,
            reward_nft=self.reward_nft,
            minting_nft_hash=self.owner_script_hash,
            c3_token_hash=self.payment_script_hash,
            c3_token_name=self.tC3_token_name,
            oracle_addr=str(self.oracle_script_address),
            stake_key=None,
            minting_script=self.native_script,
            validity_start=self.script_start_slot,
        )

    def get_aggstate_utxo_datum_cbor(self, address):
        aggstate_utxo_raw_datum = self.get_aggstate_utxo_datum(address)
        return AggDatum.from_cbor(aggstate_utxo_raw_datum.cbor)

    @retry(tries=TEST_RETRIES, backoff=1.5, delay=6, jitter=(0, 4))
    @pytest.mark.asyncio
    @pytest.mark.order(3)
    async def test_editSettings(self):
        aggstate_utxo_datum = self.get_aggstate_utxo_datum_cbor(self.oracle_script_address)
        aggSettings = aggstate_utxo_datum.aggstate.agSettings
        aggSettings.os_updated_nodes = self.updated_config["os_updated_nodes"]

        await self.oracle_owner.edit_settings(aggSettings)
        await asyncio.sleep(3)

        updated_aggstate_utxo_datum = self.get_aggstate_utxo_datum_cbor(self.oracle_script_address)

        assert aggSettings == updated_aggstate_utxo_datum.aggstate.agSettings, \
                f"Expected os_updated_nodes: {aggSettings}, but got: {updated_aggstate_utxo_datum.aggstate.agSettings}"
