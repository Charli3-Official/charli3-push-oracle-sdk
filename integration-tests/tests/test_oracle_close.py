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
        # Removing nodes beacuse of memory limitations
        nodes_to_be_removed = [
            str(self.node_1_verification_key.hash()),
            str(self.node_2_verification_key.hash()),
        ]
        await self.oracle_owner.remove_nodes(nodes_to_be_removed)

        await self.oracle_owner.oracle_close()

        await asyncio.sleep(30)

        oracle_utxos = self.CHAIN_CONTEXT.context.utxos(self.oracle_addr)
        for utxo in oracle_utxos:
            assert (
                utxo.output.datum == None
            ), f"Expected not to generate UTxOs with datums, but got {utxo.output.datum}"
