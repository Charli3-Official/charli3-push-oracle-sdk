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
)
from src.datums import OracleSettings, PriceRewards
from src.chain_query import ChainQuery
from scripts.oracle_deploy import unzip_and_execute_binary
from src.owner_script import OwnerScript
from src.mint import Mint


TEST_RETRIES = 6

# Get the absolute path of the directory of the current file
dir_path = os.path.dirname(os.path.realpath(__file__))


@retry(tries=TEST_RETRIES, delay=4)
def check_chain_context(chain_context):
    print(f"Current chain tip: {chain_context.ogmios_context.last_block_slot}")


def load_wallet_keys(wallet_dir):
    vkey_files = glob.glob(f"{wallet_dir}/*.vkey")
    skey_files = glob.glob(f"{wallet_dir}/*.skey")

    keys = []
    for vkey_file, skey_file in zip(sorted(vkey_files), sorted(skey_files)):
        signing_key = PaymentSigningKey.load(skey_file)
        verification_key = PaymentVerificationKey.load(vkey_file)
        keys.append((signing_key, verification_key))
    return keys


class TestBase:
    NETWORK = Network.MAINNET

    OGMIOS_WS = "ws://localhost:1337"

    KUPO_URL = "http://localhost:1442"

    ogmios_context = OgmiosChainContext(OGMIOS_WS, Network.TESTNET, kupo_url=KUPO_URL)
    chain_context = ChainQuery(ogmios_context=ogmios_context)

    check_chain_context(chain_context)

    # Test configurations
    with open("./configuration.yml", "r") as stream:
        config = yaml.safe_load(stream)

    # Oracle Configuration
    script_start_slot = config["oracle_owner"]["script_start_slot"]
    tC3_token_name = AssetName(b"Charli3")
    tC3_initial_amount = config["oracle_owner"]["tC3_initial_amount"]
    tC3_add_funds = config["oracle_owner"]["tC3_add_funds"]

    # Load temporal wallets
    wallet_keys = load_wallet_keys("./wallets/")

    # Oracle Owner
    owner_signing_key = wallet_keys[0][0]
    owner_verification_key = wallet_keys[0][1]
    owner_address = Address(owner_verification_key.hash(), None, NETWORK)

    # Nodes
    node_1_signing_key = wallet_keys[1][0]
    node_1_verification_key = wallet_keys[1][1]
    node_1_pkh = bytes.fromhex(str(node_1_verification_key.hash()))

    node_2_signing_key = wallet_keys[2][0]
    node_2_verification_key = wallet_keys[2][1]
    node_2_pkh = bytes.fromhex(str(node_2_verification_key.hash()))

    node_3_signing_key = wallet_keys[3][0]
    node_3_verification_key = wallet_keys[3][1]
    node_3_pkh = bytes.fromhex(str(node_3_verification_key.hash()))

    node_4_signing_key = wallet_keys[4][0]
    node_4_verification_key = wallet_keys[4][1]
    node_4_pkh = bytes.fromhex(str(node_4_verification_key.hash()))

    node_5_signing_key = wallet_keys[5][0]
    node_5_verification_key = wallet_keys[5][1]
    node_5_pkh = bytes.fromhex(str(node_5_verification_key.hash()))

    # Platform
    platform_6_signing_key = wallet_keys[6][0]
    platform_6_verification_key = wallet_keys[6][1]
    platform_6_pkh = bytes.fromhex(str(platform_6_verification_key.hash()))

    # Oracle Settings
    agSettings = OracleSettings(
        os_node_list=[
            node_1_pkh,
            node_2_pkh,
            node_3_pkh,
            node_4_pkh,
            node_5_pkh,
        ],
        os_updated_nodes=config["oracle_settings"]["os_updated_nodes"],
        os_updated_node_time=config["oracle_settings"]["os_updated_node_time"],
        os_aggregate_time=config["oracle_settings"]["os_aggregate_time"],
        os_aggregate_change=config["oracle_settings"]["os_aggregate_change"],
        os_node_fee_price=PriceRewards(
            node_fee=config["oracle_settings"]["os_node_fee_price"]["node_fee"],
            aggregate_fee=config["oracle_settings"]["os_node_fee_price"][
                "aggregate_fee"
            ],
            platform_fee=config["oracle_settings"]["os_node_fee_price"]["platform_fee"],
        ),
        os_mad_multiplier=config["oracle_settings"]["os_mad_multiplier"],
        os_divergence=config["oracle_settings"]["os_divergence"],
        os_platform_pkh=platform_6_pkh,
    )

    owner_minting_script = OwnerScript(
        NETWORK,
        chain_context,
        owner_verification_key,
    )
    native_script = owner_minting_script.mk_owner_script(script_start_slot)
    owner_script_hash = native_script.hash()

    oracle_nft = MultiAsset.from_primitive(
        {owner_script_hash.payload: {b"OracleFeed": 1}}
    )

    single_node_nft = MultiAsset.from_primitive(
        {owner_script_hash.payload: {b"NodeFeed": 1}}
    )

    oracle_nft = MultiAsset.from_primitive(
        {owner_script_hash.payload: {b"OracleFeed": 1}}
    )

    aggstate_nft = MultiAsset.from_primitive(
        {owner_script_hash.payload: {b"AggState": 1}}
    )

    reward_nft = MultiAsset.from_primitive({owner_script_hash.payload: {b"Reward": 1}})

    payment_path = os.path.join(dir_path, "..", "..", "mint_script.plutus")
    with open(payment_path, "r") as f:
        script_hex = f.read()
        payment_script = PlutusV2Script(cbor2.loads(bytes.fromhex(script_hex)))
    payment_script_hash = plutus_script_hash(payment_script)

    # Build the path relative to this file
    serialized_path = os.path.join(dir_path, "..", "..", "binary", "serialized.zip")

    oracle_plutus_script_v2 = unzip_and_execute_binary(
        file_name=serialized_path,
        unzip_dir="binary",
        binary_name="serialized",
        owner_ppkh=owner_address.payment_part,
        oracle_mp=native_script.hash(),
        payment_mp=payment_script_hash,
        payment_tn="tC3",
        args=["-a", "-v"],
    )

    script_hash = plutus_script_hash(oracle_plutus_script_v2)
    oracle_script_address = Address(payment_part=script_hash, network=NETWORK)

    async def mint_payment_token(self):
        tC3 = Mint(
            self.NETWORK,
            self.chain_context,
            self.owner_signing_key,
            self.owner_verification_key,
            self.payment_script,
        )
        await tC3.mint_nft_with_script()

    @retry(tries=TEST_RETRIES, delay=3)
    def assert_output(self, target_address, target_output):
        utxos = self.chain_context.context.utxos(target_address)
        found = False

        for utxo in utxos:
            output = utxo.output

            if output == target_output:
                found = True

        assert found, f"Cannot find target UTxO in address: {target_address}"

    def get_tC3_at_aggstate_utxo(
        self,
        target_address,
    ):
        oracle_utxos = self.chain_context.context.utxos(target_address)

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
