import pytest
import asyncio
import os
import cbor2

from retry import retry
from pycardano import (
    MultiAsset,
    Address,
    TransactionOutput,
    Value,
    RawCBOR,
    plutus_script_hash,
    UTxO,
)
from .base import TEST_RETRIES, TestBase
from charli3_offchain_core.oracle_start import OracleStart
from charli3_offchain_core.oracle_checks import filter_utxos_by_asset
from charli3_offchain_core.mint import Mint
from scripts.oracle_deploy import execute_binary_from_image


@pytest.mark.order(1)
class TestDeployment(TestBase):
    @retry(tries=TEST_RETRIES, backoff=1.5, delay=6, jitter=(0, 4))
    def setup_method(self, method):
        super().setup_method(method)  # Call base class's setup_method
        # Payment Token
        self.tC3 = Mint(
            self.NETWORK,
            self.CHAIN_CONTEXT,
            self.owner_signing_key,
            self.owner_verification_key,
            self.payment_script,
        )

    @pytest.mark.asyncio
    async def test_oracle_deploy(self):
        await self.tC3.mint_nft_with_script()

        # Oracle contract script
        oracle_plutus_script_v2 = execute_binary_from_image(
            artifacts_dir=os.path.join(self.DIR_PATH, "..", "..", "tmp"),
            oracle_mp=self.owner_script_hash,
            payment_mp=self.payment_script_hash,
            payment_tn="Charli3",
            args=["-a", "-v"],
        )

        # Oracle contract script using a cbor file
        # oracle_script_path = os.path.join(self.DIR_PATH, "OracleV3.plutus")
        # with open(oracle_script_path, "r") as f:
        #     script_hex = f.read()
        #     oracle_plutus_script_v2 = PlutusV2Script(
        #         cbor2.loads(bytes.fromhex(script_hex))
        #     )

        # Contract hash
        script_hash = plutus_script_hash(oracle_plutus_script_v2)

        # Contract address
        oracle_script_address = Address(payment_part=script_hash, network=self.NETWORK)
        print("Charli3's oracle contract address: ", oracle_script_address)

        deployment = OracleStart(
            network=self.NETWORK,
            chain_query=self.CHAIN_CONTEXT,
            signing_key=self.owner_signing_key,
            verification_key=self.owner_verification_key,
            oracle_script=oracle_plutus_script_v2,
            script_start_slot=self.script_start_slot,
            settings=self.agSettings,
            c3_token_hash=self.payment_script_hash,
            c3_token_name=self.tC3_token_name,
            native_script_with_signers=False,
        )

        # Contract's deployment
        platform_pkhs = [self.owner_verification_key.hash().payload.hex()]
        tx = await deployment.mk_start_oracle_tx(platform_pkhs, self.tC3_initial_amount)
        await self.staged_query.sign_and_submit_tx(tx, self.owner_signing_key)

        assert self.oracle_addr == oracle_script_address, (
            f"Unexpected contract address: {oracle_script_address} "
            f"Expected: {self.oracle_addr}"
        )

    def test_oraclefeed_nft_existence(self):
        # Expected oracle feed NFT
        oracle_nft = MultiAsset.from_primitive(
            {self.owner_script_hash.payload: {b"OracleFeed": 1}}
        )
        oracle_datum = RawCBOR(cbor=b"\xd8y\x80")

        # Expected Oracle's Feed UTXO
        expected_oracle_feed_output = TransactionOutput(
            self.oracle_addr,
            Value(2000000, oracle_nft),
            datum=oracle_datum,
        )
        self.assert_output(self.oracle_addr, expected_oracle_feed_output)

    def test_number_of_existing_node_utxos(self):
        total_nodes = self.get_total_nodes(self.oracle_addr)
        assert total_nodes == 3, f"Expected 3 Nodes, received {total_nodes}"

    def test_aggstate_nft_existence(self):
        oracle_utxos = self.CHAIN_CONTEXT.context.utxos(self.oracle_addr)
        aggstate_utxo: UTxO = filter_utxos_by_asset(oracle_utxos, self.aggstate_nft)
        assert aggstate_utxo != [], "AggState UTxO not found"

    def test_reward_nft_existence(self):
        oracle_utxos = self.CHAIN_CONTEXT.context.utxos(self.oracle_addr)
        reward_utxo: UTxO = filter_utxos_by_asset(oracle_utxos, self.reward_nft)
        assert reward_utxo != [], "Reward UTxO not found"
