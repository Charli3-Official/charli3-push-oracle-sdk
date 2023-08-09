import pytest

import asyncio
from pycardano import Address, UTxO
from retry import retry

from .base import TEST_RETRIES, OracleOwnerActions
from charli3_offchain_core.mint import Mint
from charli3_offchain_core.oracle_checks import filter_utxos_by_asset


@pytest.mark.order(2)
class TestAddFunds(OracleOwnerActions):
    def setup_method(self, method):
        super().setup_method(method)

        # Payment Token
        self.tC3 = Mint(
            self.NETWORK,
            self.CHAIN_CONTEXT,
            self.platform_signing_key,
            self.platform_verification_key,
            self.payment_script,
        )

    @retry(tries=TEST_RETRIES, backoff=1.5, delay=6, jitter=(0, 4))
    @pytest.mark.asyncio
    async def test_add_funds(self):
        await self.tC3.mint_nft_with_script()

        tC3_quantity = self.get_tC3_at_aggstate_utxo(self.oracle_addr)

        await self.oracle_owner.add_funds(self.tC3_add_funds)

        await asyncio.sleep(30)

        updated_tC3_quantity = self.get_tC3_at_aggstate_utxo(self.oracle_addr)

        assert (
            updated_tC3_quantity == tC3_quantity + self.tC3_add_funds
        ), "The updated tC3 quantity at aggstate utxo is not correct"
