"""An example that demonstrates low-level construction of a transaction."""
import asyncio
import os
import yaml
import glob
import cbor2
from retry import retry
from pycardano import (
    Network,
    Address,
    PaymentVerificationKey,
    PaymentSigningKey,
    AssetName,
    MultiAsset,
    OgmiosChainContext,
    PlutusV2Script,
    plutus_script_hash,
    IndefiniteList,
)
from charli3_offchain_core.datums import OracleSettings, PriceRewards, OraclePlatform
from charli3_offchain_core.chain_query import ChainQuery, StagedTxSubmitter
from charli3_offchain_core.oracle_owner import OracleOwner
from charli3_offchain_core.owner_script import OwnerScript

TEST_RETRIES = 6


class TestBase:
    NETWORK = Network.MAINNET
    OGMIOS_WS = "ws://localhost:1337"
    KUPO_URL = "http://localhost:1442"
    OGMIOS_CONTEXT = OgmiosChainContext(
        ws_url=OGMIOS_WS, network=NETWORK, kupo_url=KUPO_URL
    )
    CHAIN_CONTEXT = ChainQuery(ogmios_context=OGMIOS_CONTEXT)
    DIR_PATH = os.path.dirname(os.path.realpath(__file__))

    def setup_method(self, method):
        # Chain query
        self.staged_query = StagedTxSubmitter(
            self.CHAIN_CONTEXT.blockfrost_context, self.CHAIN_CONTEXT.ogmios_context
        )

        self.initialize_script_paths()
        self.initialize_payment_script()
        self.wallet_dir = "./wallets"
        self.initialize_wallet_keys()

        # Oracle settings
        self.load_oracle_configuration()
        self.initialize_oracle_settings()
        self.script_start_slot = self.config["oracle_owner"]["script_start_slot"]
        self.tC3_token_name = AssetName(b"Charli3")
        self.tC3_initial_amount = self.config["oracle_owner"]["tC3_initial_amount"]
        self.tC3_add_funds = self.config["oracle_owner"]["tC3_add_funds"]
        self.updated_config = self.config["updated_oracle_settings"]
        self.oracle_addr = Address.from_primitive(
            str(self.config["oracle_info"]["oracle_script_address"])
        )
        self.nodes_values = self.config["nodes_values"]
        self.initialize_oracle_nfts()

    # Load cluster wallets
    def load_wallet_keys(self):
        vkey_files = glob.glob(f"{self.wallet_dir}/*.vkey")
        skey_files = glob.glob(f"{self.wallet_dir}/*.skey")

        keys = []
        for vkey_file, skey_file in zip(sorted(vkey_files), sorted(skey_files)):
            signing_key = PaymentSigningKey.load(skey_file)
            verification_key = PaymentVerificationKey.load(vkey_file)
            keys.append((signing_key, verification_key))
        return keys

    # Wallet initialization
    def initialize_wallet_keys(self):
        self.wallet_keys = self.load_wallet_keys()

        self.owner_signing_key, self.owner_verification_key = self.wallet_keys[0]
        self.owner_address = Address(
            self.owner_verification_key.hash(), None, self.NETWORK
        )

        # Node Operators credentials (at the time of deployment)
        self.node_1_signing_key, self.node_1_verification_key = self.wallet_keys[1]
        self.node_1_pkh = bytes.fromhex(str(self.node_1_verification_key.hash()))

        self.node_2_signing_key, self.node_2_verification_key = self.wallet_keys[2]
        self.node_2_pkh = bytes.fromhex(str(self.node_2_verification_key.hash()))

        self.node_3_signing_key, self.node_3_verification_key = self.wallet_keys[3]
        self.node_3_pkh = bytes.fromhex(str(self.node_3_verification_key.hash()))

        self.node_4_signing_key, self.node_4_verification_key = self.wallet_keys[4]
        self.node_4_pkh = bytes.fromhex(str(self.node_4_verification_key.hash()))

        self.node_5_signing_key, self.node_5_verification_key = self.wallet_keys[5]
        self.node_5_pkh = bytes.fromhex(str(self.node_5_verification_key.hash()))

        # Node Operators credentials (add and remove operations)
        self.node_6_signing_key, self.node_6_verification_key = self.wallet_keys[6]
        self.node_6_pkh_str = str(self.node_6_verification_key.hash())

        self.node_7_signing_key, self.node_7_verification_key = self.wallet_keys[7]
        self.node_7_pkh_str = str(self.node_7_verification_key.hash())

        # Platform owner credential (oracle-owner's actions)
        self.platform_signing_key, self.platform_verification_key = self.wallet_keys[8]
        self.platform_pkh = bytes.fromhex(str(self.platform_verification_key.hash()))

    # Integration tests configurations
    def load_oracle_configuration(self):
        config_path = os.path.join(self.DIR_PATH, "../configuration.yml")
        with open(config_path) as stream:
            self.config = yaml.safe_load(stream)

    # Oracle Settings (AggState UTxO's Datum)
    def initialize_oracle_settings(self):
        self.agSettings = OracleSettings(
            os_node_list=[
                self.node_1_pkh,
                self.node_2_pkh,
                self.node_3_pkh,
                # self.node_4_pkh,
                # self.node_5_pkh,
            ],
            os_updated_nodes=self.config["oracle_settings"]["os_updated_nodes"],
            os_updated_node_time=self.config["oracle_settings"]["os_updated_node_time"],
            os_aggregate_time=self.config["oracle_settings"]["os_aggregate_time"],
            os_aggregate_change=self.config["oracle_settings"]["os_aggregate_change"],
            os_minimum_deposit=self.config["oracle_settings"]["os_minimum_deposit"],
            os_aggregate_valid_range=self.config["oracle_settings"][
                "os_aggregate_valid_range"
            ],
            os_node_fee_price=PriceRewards(
                node_fee=self.config["oracle_settings"]["os_node_fee_price"][
                    "node_fee"
                ],
                aggregate_fee=self.config["oracle_settings"]["os_node_fee_price"][
                    "aggregate_fee"
                ],
                platform_fee=self.config["oracle_settings"]["os_node_fee_price"][
                    "platform_fee"
                ],
            ),
            os_iqr_multiplier=self.config["oracle_settings"]["os_iqr_multiplier"],
            os_divergence=self.config["oracle_settings"]["os_divergence"],
            os_platform=OraclePlatform(
                pmultisig_pkhs=IndefiniteList([self.platform_pkh]),
                pmultisig_threshold=self.config["oracle_settings"]["os_platform"][
                    "pmultisig_threshold"
                ],
            ),
        )

    def initialize_oracle_nfts(self):
        # Initialize your oracle NFTs here
        oracle_owner = OwnerScript(self.CHAIN_CONTEXT, is_mock_script=True)
        self.native_script = oracle_owner.mk_owner_script(self.script_start_slot)

        # Oracle's currency symbol (NFT's hash)
        self.owner_script_hash = self.native_script.hash()

        # Oracle's NFTs
        self.oracle_feed_nft = MultiAsset.from_primitive(
            {self.owner_script_hash.payload: {b"OracleFeed": 1}}
        )
        self.single_node_nft = MultiAsset.from_primitive(
            {self.owner_script_hash.payload: {b"NodeFeed": 1}}
        )
        self.aggstate_nft = MultiAsset.from_primitive(
            {self.owner_script_hash.payload: {b"AggState": 1}}
        )
        self.reward_nft = MultiAsset.from_primitive(
            {self.owner_script_hash.payload: {b"Reward": 1}}
        )

    def initialize_payment_script(self):
        payment_path = os.path.join(self.mint_path)
        with open(payment_path, "r") as f:
            script_hex = f.read()
            self.payment_script = PlutusV2Script(cbor2.loads(bytes.fromhex(script_hex)))
            self.payment_script_hash = plutus_script_hash(self.payment_script)

    def initialize_script_paths(self):
        self.serialized_path = os.path.join(
            self.DIR_PATH, "..", "..", "binary", "serialized.zip"
        )
        self.mint_path = os.path.join(self.DIR_PATH, "..", "..", "mint_script.plutus")

    @retry(tries=TEST_RETRIES, delay=3)
    def assert_output(self, target_address, target_output):
        utxos = self.CHAIN_CONTEXT.context.utxos(target_address)
        found = False
        for utxo in utxos:
            output = utxo.output

            if output == target_output:
                found = True

        assert found, f"Cannot find target UTxO in address: {target_address}"

    @retry(tries=TEST_RETRIES, delay=3)
    def get_tC3_at_aggstate_utxo(
        self,
        target_address,
    ):
        oracle_utxos = self.CHAIN_CONTEXT.context.utxos(target_address)

        aggstate_utxo = next(
            (
                utxo
                for utxo in oracle_utxos
                if utxo.output.amount.multi_asset >= self.aggstate_nft
            ),
            0,
        )
        return aggstate_utxo.output.amount.multi_asset[self.payment_script_hash][
            self.tC3_token_name
        ]

    @retry(tries=TEST_RETRIES, delay=3)
    def get_aggstate_utxo_datum(self, target_address):
        oracle_utxos = self.CHAIN_CONTEXT.context.utxos(target_address)

        aggstate_utxo = next(
            (
                utxo
                for utxo in oracle_utxos
                if utxo.output.amount.multi_asset >= self.aggstate_nft
            ),
            0,
        )
        return aggstate_utxo.output.datum

    @retry(tries=TEST_RETRIES, delay=3)
    def get_total_nodes(self, target_address):
        oracle_utxos = self.CHAIN_CONTEXT.context.utxos(target_address)
        return sum(
            1
            for utxo in oracle_utxos
            if utxo.output.amount.multi_asset >= self.single_node_nft
        )

    @retry(tries=TEST_RETRIES, delay=4)
    def check_chain_context(self):
        print(f"Current chain tip: {self.CHAIN_CONTEXT.ogmios_context.last_block_slot}")


class OracleOwnerActions(TestBase):
    def setup_method(self, method):
        super().setup_method(method)

        self.oracle_owner = OracleOwner(
            network=self.NETWORK,
            chainquery=self.CHAIN_CONTEXT,
            signing_key=self.platform_signing_key,
            verification_key=self.platform_verification_key,
            node_nft=self.single_node_nft,
            aggstate_nft=self.aggstate_nft,
            oracle_nft=self.oracle_feed_nft,
            reward_nft=self.reward_nft,
            minting_nft_hash=self.owner_script_hash,
            c3_token_hash=self.payment_script_hash,
            c3_token_name=self.tC3_token_name,
            oracle_addr=str(self.oracle_addr),
            stake_key=None,
            minting_script=self.native_script,
            validity_start=self.script_start_slot,
        )
