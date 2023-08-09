import pytest

import asyncio

from retry import retry

from .base import TEST_RETRIES, OracleOwnerActions


@pytest.mark.order(4)
class TestAddNodes(OracleOwnerActions):
    def setup_method(self, method):
        super().setup_method(method)

    @retry(tries=TEST_RETRIES, backoff=1.5, delay=6, jitter=(0, 4))
    @pytest.mark.asyncio
    async def test_add_nodes(self):
        total_nodes = self.get_total_nodes(self.oracle_addr)

        new_nodes = [self.node_6_pkh_str, self.node_7_pkh_str]

        await self.oracle_owner.add_nodes(new_nodes)

        await asyncio.sleep(30)

        updated_total_nodes = self.get_total_nodes(self.oracle_addr)

        assert (
            total_nodes + len(new_nodes) == updated_total_nodes
        ), f"Expected {total_nodes + len(new_nodes)}, but got: {updated_total_nodes}"
