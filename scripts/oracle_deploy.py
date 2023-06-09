"""Deploy oracle on Cardano blockchain"""
import yaml
import cbor2
from pycardano import (
    Network,
    HDWallet,
    Address,
    PaymentVerificationKey,
    ExtendedSigningKey,
    ScriptHash,
    AssetName,
    PlutusV2Script,
)
from src.chain_query import ChainQuery
from src.owner_script import OwnerScript
from src.oracle_start import OracleStart
from src.datums import OracleSettings, PriceRewards

if __name__ == "__main__":
    # Load configuration from YAML file
    with open("oracle_deploy.yml", "r") as ymlfile:
        config = yaml.safe_load(ymlfile)

    MNEMONIC_24 = config["MNEMONIC_24"]
    script_start_slot = config["script_start_slot"]
    if config["network"] == "TESTNET":
        network = Network.TESTNET
    elif config["network"] == "MAINNET":
        network = Network.MAINNET
    chain_query = ChainQuery(
        config["chain_query"]["token_id"],
        base_url=config["chain_query"]["base_url"],
    )
    hdwallet = HDWallet.from_mnemonic(MNEMONIC_24)
    hdwallet_spend = hdwallet.derive_from_path("m/1852'/1815'/0'/0/0")
    spend_public_key = hdwallet_spend.public_key
    spend_vk = PaymentVerificationKey.from_primitive(spend_public_key)

    hdwallet_stake = hdwallet.derive_from_path("m/1852'/1815'/0'/2/0")
    stake_public_key = hdwallet_stake.public_key
    stake_vk = PaymentVerificationKey.from_primitive(stake_public_key)

    extended_signing_key = ExtendedSigningKey.from_hdwallet(hdwallet_spend)
    owner_addr = Address(spend_vk.hash(), stake_vk.hash(), network)
    owner_minting_script = OwnerScript(
        network,
        chain_query,
        spend_vk,
    )
    native_script = owner_minting_script.mk_owner_script(script_start_slot)
    c3_token_hash = ScriptHash.from_primitive(config["c3_token_hash"])
    c3_token_name = AssetName(config["c3_token_name"].encode())
    print(owner_addr)
    print(owner_minting_script.print_start_params(script_start_slot))
    with open(config["plutus_file_name"], "r") as f:
        script_hex = f.read()
        oracle_script = PlutusV2Script(cbor2.loads(bytes.fromhex(script_hex)))

    # Oracle settings
    agSettings = OracleSettings(
        os_node_list=[
            bytes.fromhex(node) for node in config["oracle_settings"]["os_node_list"]
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
        os_platform_pkh=bytes.fromhex(config["oracle_settings"]["os_platform_pkh"]),
    )
    start = OracleStart(
        network=network,
        chain_query=chain_query,
        signing_key=extended_signing_key,
        verification_key=spend_vk,
        stake_key=stake_vk,
        oracle_script=oracle_script,
        script_start_slot=script_start_slot,
        settings=agSettings,
        c3_token_hash=c3_token_hash,
        c3_token_name=c3_token_name,
    )
    start.start_oracle(config["initial_c3_amount"])
