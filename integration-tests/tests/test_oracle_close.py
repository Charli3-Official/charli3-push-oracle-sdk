import pytest

import asyncio

from retry import retry

from .base import TEST_RETRIES, OracleOwnerActions


@pytest.mark.order(9)
class TestOracleClose(OracleOwnerActions):
    def setup_method(self, method):
        super().setup_method(method)

    @retry(tries=TEST_RETRIES, backoff=1.5, delay=6, jitter=(0, 4))
    @pytest.mark.asyncio
    async def test_oracle_close(self):
        await self.oracle_owner.oracle_close()

        await asyncio.sleep(30)

        oracle_utxos = self.CHAIN_CONTEXT.context.utxos(self.oracle_addr)
        for utxo in oracle_utxos:
            assert (
                utxo.output.datum == None
            ), f"Expected not to generate UTxOs with datums, but got {utxo.output.datum}"
