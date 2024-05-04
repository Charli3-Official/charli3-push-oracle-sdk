import asyncio
import os

import cbor2
import pytest
import yaml
from pycardano import (
    Address,
    MultiAsset,
    RawCBOR,
    TransactionOutput,
    UTxO,
    Value,
    plutus_script_hash,
)
from retry import retry

from charli3_offchain_core.mint import Mint
from charli3_offchain_core.oracle_checks import filter_utxos_by_asset
from charli3_offchain_core.oracle_start import OracleStart
from scripts.oracle_deploy import execute_binary_from_image

from .base import TEST_RETRIES, MultisigTestBase


@pytest.mark.order(1)
class TestMultisigDeployment(MultisigTestBase):
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

    def update_oracle_address(self, new_address):
        # Update the configuration file with the new contract address
        config_path = os.path.join(self.DIR_PATH, "../configuration.yml")
        with open(config_path, "r") as file:
            # Load the YAML data from the file
            config = yaml.safe_load(file)

        # Update the multisig_oracle_script_address
        config["multisig_oracle_script_address"] = new_address

        # Write the updated data back to the file
        with open(config_path, "w") as file:
            yaml.safe_dump(config, file)

    @pytest.mark.asyncio
    @pytest.mark.order(1)
    async def test_oracle_deploy(self):
        await self.tC3.mint_nft_with_script()

        # Oracle contract script
        oracle_plutus_script_v2 = execute_binary_from_image(
            artifacts_dir=os.path.join(self.DIR_PATH, "..", "..", "tmp"),
            oracle_mp=self.owner_script_hash,
            payment_mp=self.payment_script_hash,
            payment_tn="Charli3",
            args=["-a", "-v"],
            argument_filename="multisig_argument.yml",
            script_filename="MultisigOracle.plutus",
        )

        # Contract hash
        script_hash = plutus_script_hash(oracle_plutus_script_v2)

        # Contract address
        oracle_script_address = Address(payment_part=script_hash, network=self.NETWORK)

        # Update the configuration file with the created Oracle script address.
        self.update_oracle_address(str(oracle_script_address))

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
        )

        # Contract's deployment
        platform_pkhs = [
            self.owner_verification_key.hash().payload.hex(),
            self.platform_verification_key.hash().payload.hex(),
        ]
        tx = await deployment.mk_start_oracle_tx(platform_pkhs, self.tC3_initial_amount)
        self.staged_query.sign_tx(tx, self.platform_signing_key)
        await self.staged_query.sign_and_submit_tx(tx, self.owner_signing_key)

        oracle_addr = self.load_oracle_address()
        assert oracle_addr == oracle_script_address, (
            f"Unexpected contract address: {oracle_script_address} "
            f"Expected: {oracle_addr}"
        )

    @pytest.mark.order(2)
    def test_oraclefeed_nft_existence(self):
        # Expected oracle feed NFT
        oracle_nft = MultiAsset.from_primitive(
            {self.owner_script_hash.payload: {b"OracleFeed": 1}}
        )
        oracle_datum = RawCBOR(cbor=b"\xd8y\x80")

        # Retrieve the contract address from the configuration file.
        oracle_addr = self.load_oracle_address()

        # Expected Oracle's Feed UTXO
        expected_oracle_feed_output = TransactionOutput(
            oracle_addr,
            Value(2000000, oracle_nft),
            datum=oracle_datum,
        )

        self.assert_output(oracle_addr, expected_oracle_feed_output)

    @pytest.mark.order(3)
    def test_number_of_existing_node_utxos(self):
        # Retrieve the contract address from the configuration file.
        oracle_addr = self.load_oracle_address()

        total_nodes = self.get_total_nodes(oracle_addr)
        assert total_nodes == 3, f"Expected 3 Nodes, received {total_nodes}"

    @pytest.mark.order(4)
    def test_aggstate_nft_existence(self):
        # Retrieve the contract address from the configuration file.
        oracle_addr = self.load_oracle_address()

        oracle_utxos = self.CHAIN_CONTEXT.context.utxos(oracle_addr)
        aggstate_utxo: UTxO = filter_utxos_by_asset(oracle_utxos, self.aggstate_nft)
        assert aggstate_utxo != [], "AggState UTxO not found"

    @pytest.mark.order(5)
    def test_reward_nft_existence(self):
        # Retrieve the contract address from the configuration file.
        oracle_addr = self.load_oracle_address()

        oracle_utxos = self.CHAIN_CONTEXT.context.utxos(oracle_addr)
        reward_utxo: UTxO = filter_utxos_by_asset(oracle_utxos, self.reward_nft)
        assert reward_utxo != [], "Reward UTxO not found"
