import pytest

import asyncio

from retry import retry

from .base import TEST_RETRIES
from .owner_actions import MultisigOracleOwnerActions


@pytest.mark.order(6)
class TestMultisigRemoveNodes(MultisigOracleOwnerActions):
    def setup_method(self, method):
        super().setup_method(method)

    @retry(tries=TEST_RETRIES, backoff=1.5, delay=6, jitter=(0, 4))
    @pytest.mark.asyncio
    async def test_remove_nodes(self):
        # Retrieve the contract address from the configuration file.
        oracle_addr = self.load_oracle_address()

        total_nodes = self.get_total_nodes(oracle_addr)

        nodes_to_be_removed = [self.node_3_pkh.hex()]

        platform_pkhs = [
            self.owner_verification_key.hash().payload.hex(),
            self.platform_verification_key.hash().payload.hex(),
        ]
        tx = await self.oracle_owner.mk_remove_nodes_tx(
            platform_pkhs, nodes_to_be_removed
        )
        self.staged_query.sign_tx(tx, self.owner_signing_key)
        await self.oracle_owner.staged_query.sign_and_submit_tx(
            tx, self.platform_signing_key
        )

        await asyncio.sleep(30)

        updated_total_nodes = self.get_total_nodes(oracle_addr)

        assert (
            total_nodes - len(nodes_to_be_removed) == updated_total_nodes
        ), f"Expected {total_nodes - len(nodes_to_be_removed)}, but got: {updated_total_nodes}"
