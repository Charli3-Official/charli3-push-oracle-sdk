"""Deployment of the oracle contract  on Cardano blockchain"""
import asyncio
import zipfile
import os
import subprocess
import json
import cbor2
import yaml
from pycardano import (
    Network,
    HDWallet,
    Address,
    PaymentVerificationKey,
    ExtendedSigningKey,
    ScriptHash,
    AssetName,
    PlutusV2Script,
    IndefiniteList,
    BlockFrostChainContext,
    VerificationKeyHash,
)
from charli3_offchain_core.chain_query import ChainQuery
from charli3_offchain_core.owner_script import OwnerScript
from charli3_offchain_core.oracle_start import OracleStart
from charli3_offchain_core.datums import OracleSettings, PriceRewards, OraclePlatform
from charli3_offchain_core.utils.logging_config import logging


def generate_validator_arguments(file_name, arguments):
    """Generate the validator arguments in YAML format"""
    str_arguments = {}
    for key, value in arguments.items():
        if isinstance(
            value, (ScriptHash, VerificationKeyHash)
        ):  # add other classes if necessary
            str_arguments[key] = (
                value.to_sting() if hasattr(value, "to_string") else str(value)
            )
        else:
            str_arguments[key] = value

    with open(file_name, "w") as file:
        yaml.safe_dump(
            str_arguments, file, default_flow_style=False, allow_unicode=True
        )


def unzip_and_execute_binary(
    file_name,
    unzip_dir,
    binary_name,
    oracle_mp,
    payment_mp,
    payment_tn,
    rate_tn=None,
    rate_mp=None,
    args=None,
) -> PlutusV2Script:
    """Unzip the binary file and execute it and return the Plutus script"""

    # Unzip the file
    with zipfile.ZipFile(file_name, "r") as zip_ref:
        zip_ref.extractall(unzip_dir)

    # Generate the YAML file
    validator_arguments = {
        "file_name": "OracleV3",
        "oracle_mp": oracle_mp,
        "aggState_tn": "AggState",
        "reward_tn": "Reward",
        "oracleFeed_tn": "OracleFeed",
        "nodeFeed_tn": "NodeFeed",
        "payment_mp": payment_mp,
        "payment_tn": payment_tn,
        "rate_tn": rate_tn,
        "rate_mp": rate_mp,
    }
    generate_validator_arguments(
        os.path.join(os.getcwd(), "validator-argument.yml"), validator_arguments
    )

    # Make the binary executable
    binary_file_path = os.path.join(unzip_dir, binary_name)
    os.chmod(binary_file_path, 0o755)

    # Prepare the command and arguments
    command = [binary_file_path]
    if args:
        command.extend(args)

    # Execute the binary
    process = subprocess.Popen(command)
    output, error = process.communicate()

    # If you want to print the output
    if output:
        print("Output: ", output)

    if error:
        print("Error: ", error)

    # Remove the YAML file and the binary
    os.remove(os.path.join(os.getcwd(), "validator-argument.yml"))
    os.remove(binary_file_path)

    # Load the Plutus script file
    with open("OracleV3.plutus", "r") as f:
        plutus_data = json.load(f)
    # Get the "cborHex" from the Plutus script file
    script_hex = plutus_data.get("cborHex")

    # Convert the "cborHex" to PlutusScriptV2
    plutus_script = PlutusV2Script(cbor2.loads(bytes.fromhex(script_hex)))

    # Remove the Plutus script file
    os.remove("OracleV3.plutus")

    return plutus_script


if __name__ == "__main__":
    logger = logging.getLogger("oracle_deploy")
    # Load configuration from YAML file
    with open("oracle_deploy.yml", "r") as ymlfile:
        config = yaml.safe_load(ymlfile)

    MNEMONIC_24 = config["MNEMONIC_24"]
    script_start_slot = config["script_start_slot"]
    if config["network"] == "TESTNET":
        network = Network.TESTNET
    elif config["network"] == "MAINNET":
        network = Network.MAINNET
    blockfrost_base_url = config["chain_query"]["base_url"]
    blockfrost_project_id = config["chain_query"]["token_id"]

    blockfrost_context = BlockFrostChainContext(
        blockfrost_project_id,
        base_url=blockfrost_base_url,
    )

    chain_query = ChainQuery(
        blockfrost_context,
    )

    chain_query = ChainQuery(blockfrost_context=blockfrost_context)

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

    logger.info("Owner address: %s", owner_addr)
    logger.info(
        "Owner minting script params: %s",
        owner_minting_script.print_start_params(script_start_slot),
    )

    c3_oracle_rate_token_name = config.get("exchange_rate_token_name") or None
    c3_oracle_rate_token_hash = config.get("exchange_rate_token_hash")
    if c3_oracle_rate_token_hash is not None:
        c3_oracle_rate_token_hash = ScriptHash.from_primitive(c3_oracle_rate_token_hash)

    oracle_script = unzip_and_execute_binary(
        file_name="binary/serialized.zip",
        unzip_dir="binary",
        binary_name="serialized",
        oracle_mp=native_script.hash(),
        payment_mp=c3_token_hash,
        payment_tn=config["c3_token_name"],
        rate_tn=c3_oracle_rate_token_name,
        rate_mp=c3_oracle_rate_token_hash,
        args=["-a", "-v"],
    )

    # Oracle settings
    agSettings = OracleSettings(
        os_node_list=[
            bytes.fromhex(node) for node in config["oracle_settings"]["os_node_list"]
        ],
        os_updated_nodes=config["oracle_settings"]["os_updated_nodes"],
        os_updated_node_time=config["oracle_settings"]["os_updated_node_time"],
        os_aggregate_time=config["oracle_settings"]["os_aggregate_time"],
        os_aggregate_change=config["oracle_settings"]["os_aggregate_change"],
        os_minimum_deposit=config["oracle_settings"]["os_minimum_deposit"],
        os_node_fee_price=PriceRewards(
            node_fee=config["oracle_settings"]["os_node_fee_price"]["node_fee"],
            aggregate_fee=config["oracle_settings"]["os_node_fee_price"][
                "aggregate_fee"
            ],
            platform_fee=config["oracle_settings"]["os_node_fee_price"]["platform_fee"],
        ),
        os_iqr_multiplier=config["oracle_settings"]["os_iqr_multiplier"],
        os_divergence=config["oracle_settings"]["os_divergence"],
        os_platform=OraclePlatform(
            pmultisig_pkhs=IndefiniteList(
                [
                    bytes.fromhex(party)
                    for party in config["oracle_settings"]["os_platform"][
                        "pmultisig_pkhs"
                    ]
                ]
            ),
            pmultisig_threshold=config["oracle_settings"]["os_platform"][
                "pmultisig_threshold"
            ],
        ),
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
    asyncio.run(start.start_oracle(config["initial_c3_amount"]))
