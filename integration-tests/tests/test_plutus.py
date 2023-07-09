import time
import cbor2
import pytest
from retry import retry
import asyncio

from pycardano import MultiAsset, TransactionOutput, Value, RawCBOR

from .base import TEST_RETRIES, TestBase

from src.oracle_start import OracleStart
from src.datums import OracleDatum
from src.owner_script import OwnerScript


class TestPlutus(TestBase):
    def test_oracle_plutus_v2(self):
        assert self.oracle_script_address == self.oracle_addr

    @pytest.mark.asyncio
    async def test_oracle_deploy(self):
        await self.mint_payment_token()
        await asyncio.sleep(3)

        start = OracleStart(
            network=self.NETWORK,
            chain_query=self.chain_context,
            signing_key=self.owner_signing_key,
            verification_key=self.owner_verification_key,
            oracle_script=self.oracle_plutus_script_v2,
            script_start_slot=self.script_start_slot,
            settings=self.agSettings,
            c3_token_hash=self.payment_script_hash,
            c3_token_name=self.c3_token_name,
        )
        await start.start_oracle(self.c3_initial_amount)
        await asyncio.sleep(3)

        oracle_owner = OwnerScript(
            self.NETWORK, self.chain_context, self.owner_verification_key
        )

        owner_script = oracle_owner.mk_owner_script(self.script_start_slot)
        owner_script_hash = owner_script.hash()

        oracle_nft = MultiAsset.from_primitive(
            {owner_script_hash.payload: {b"OracleFeed": 1}}
        )

        # oracle_datum = OracleDatum(price_data=None)
        oracle_datum = RawCBOR(cbor=b"\xd8y\x80")
        oracle_output = TransactionOutput(
            self.oracle_script_address,
            Value(2000000, oracle_nft),
            datum=oracle_datum,
        )

        self.assert_output(self.oracle_script_address, oracle_output)
