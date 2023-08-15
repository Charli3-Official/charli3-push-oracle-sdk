import pytest

import asyncio

from retry import retry

from .base import TEST_RETRIES, OracleOwnerActions


@pytest.mark.order(5)
class TestRemoveNodes(OracleOwnerActions):
    def setup_method(self, method):
        super().setup_method(method)

    @retry(tries=TEST_RETRIES, backoff=1.5, delay=6, jitter=(0, 4))
    @pytest.mark.asyncio
    async def test_remove_nodes(self):
        total_nodes = self.get_total_nodes(self.oracle_addr)

        nodes_to_be_removed = [self.node_6_pkh_str, self.node_7_pkh_str]
        await self.oracle_owner.remove_nodes(nodes_to_be_removed)

        await asyncio.sleep(30)

        updated_total_nodes = self.get_total_nodes(self.oracle_addr)

        assert (
            total_nodes - len(nodes_to_be_removed) == updated_total_nodes
        ), f"Expected {total_nodes - len(nodes_to_be_removed)}, but got: {updated_total_nodes}"
