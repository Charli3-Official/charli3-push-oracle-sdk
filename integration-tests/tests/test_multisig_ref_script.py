import asyncio
import os

import pytest
from retry import retry

from scripts.cli_common import load_plutus_script

from .base import TEST_RETRIES
from .owner_actions import MultisigOracleOwnerActions


@pytest.mark.order(2)
class TestMultisigReferenceScript(MultisigOracleOwnerActions):
    def setup_method(self, method):
        super().setup_method(method)

        script_path = os.path.join(
            self.DIR_PATH, "..", "..", "tmp", "MultisigOracle.plutus"
        )
        self.oracle_script = load_plutus_script(script_path)

    @retry(tries=TEST_RETRIES, backoff=1.5, delay=6, jitter=(0, 4))
    @pytest.mark.asyncio
    async def test_create_reference_script(self):
        await self.oracle_owner.create_reference_script(self.oracle_script)

        await asyncio.sleep(30)

        on_chain_script = self.CHAIN_CONTEXT.get_plutus_script(
            self.oracle_owner.oracle_script_hash
        )

        assert on_chain_script is not None, "Oracle reference script not found"
