import pytest

import asyncio

from retry import retry

from pycardano import MultiAsset, TransactionOutput, Value, RawCBOR

from src.oracle_owner import OracleOwner
from src.owner_script import OwnerScript

from .base import TEST_RETRIES, TestBase


class TestAddFunds(TestBase):
    @retry(tries=TEST_RETRIES, backoff=1.5, delay=6, jitter=(0, 4))
    @pytest.mark.asyncio
    @pytest.mark.order(2)
    async def test_addFunds(self):
        tC3_quantity = self.get_tC3_at_aggstate_utxo(self.oracle_script_address)

        oracle_owner = OracleOwner(
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

        await oracle_owner.add_funds(self.tC3_add_funds)
        await asyncio.sleep(3)

        updated_tC3_quantity = self.get_tC3_at_aggstate_utxo(self.oracle_script_address)

        assert (
            updated_tC3_quantity == tC3_quantity + self.tC3_add_funds
        ), "The updated tC3 quantity at aggstate utxo is not correct"
