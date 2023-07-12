import pytest

import asyncio

from retry import retry

from pycardano import MultiAsset, TransactionOutput, Value, RawCBOR

from src.oracle_owner import OracleOwner
from src.owner_script import OwnerScript

from .base import TEST_RETRIES, TestBase

class TestAddNodes(TestBase):
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

    @retry(tries=TEST_RETRIES, backoff=1.5, delay=6, jitter=(0, 4))
    @pytest.mark.asyncio
    @pytest.mark.order(3)
    async def test_addNodes(self):
        total_nodes = self.get_total_nodes(self.oracle_script_address)

        new_nodes = [self.node_6_pkh_str, self.node_7_pkh_str]
        await self.oracle_owner.add_nodes(new_nodes)
        await asyncio.sleep(7)

        updated_total_nodes = self.get_total_nodes(self.oracle_script_address)

        assert total_nodes + len(new_nodes) == updated_total_nodes, \
            f"Expected {total_nodes + len(new_nodes)}, but got: {updated_total_nodes}"
