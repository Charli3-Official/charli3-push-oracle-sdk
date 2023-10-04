"""Deployment of the oracle contract  on Cardano blockchain"""
from typing import Tuple
import asyncio
import zipfile
import os
import subprocess
import json
import cbor2
import yaml
import click
from pycardano import (
    Network,
    HDWallet,
    MultiAsset,
    Address,
    Transaction,
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
from charli3_offchain_core.tx_validation import TxValidator, TxValidationException
from scripts.cli_common import (
    collect_multisig_pkhs,
    load_plutus_script,
    write_tx_to_file,
    read_tx_from_file,
    COLOR_DEFAULT,
    COLOR_RED,
)

logger = logging.getLogger("oracle_deploy")


@click.group(invoke_without_command=True)
@click.pass_context
@click.option(
    "-p",
    "--script-path",
    help="Optional: give path to existing precompiled oracle script",
)
def cli(ctx, script_path):
    """A CLI for managing the oracle deploy."""
    ctx.ensure_object(dict)  # Initialize the context object if not already present
    if "oracle_start" not in ctx.obj:
        setup(ctx, "oracle_deploy.yml", script_path)


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
    work_dir = os.path.join(os.getcwd(), unzip_dir)

    # Unzip the file
    with zipfile.ZipFile(file_name, "r") as zip_ref:
        zip_ref.extractall(work_dir)

    # Generate the YAML file
    validator_arguments = {
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
    validator_arg_path = os.path.join(work_dir, "validator-argument.yml")
    generate_validator_arguments(validator_arg_path, validator_arguments)

    # Make the binary executable
    binary_file_path = os.path.join(work_dir, binary_name)
    os.chmod(binary_file_path, 0o755)

    # Prepare the command and arguments
    script_path = os.path.join(work_dir, "OracleV3.plutus")
    command = [binary_file_path]
    if args:
        command.extend(["--argument-path", validator_arg_path])
        command.extend(["--script-path", script_path])
        command.extend(args)

    # Execute the binary
    process = subprocess.Popen(command)
    output, error = process.communicate()

    # If you want to print the output
    if output:
        print("Output: ", output)

    if error:
        print("Error: ", error)

    plutus_script = load_plutus_script(script_path)
    return plutus_script


def setup(ctx, config_file, script_path):
    """Setup the oracle owner actions."""
    # Load configuration from YAML file
    with open(config_file, "r") as ymlfile:
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
    oracle_platform = OraclePlatform(
        pmultisig_pkhs=IndefiniteList(
            [
                bytes.fromhex(party)
                for party in config["oracle_settings"]["os_platform"]["pmultisig_pkhs"]
            ]
        ),
        pmultisig_threshold=config["oracle_settings"]["os_platform"][
            "pmultisig_threshold"
        ],
    )
    owner_minting_script = OwnerScript(
        chain_query,
        [
            VerificationKeyHash.from_primitive(pkh)
            for pkh in oracle_platform.pmultisig_pkhs
        ],
        oracle_platform.pmultisig_threshold,
    )
    native_script = owner_minting_script.mk_owner_script(script_start_slot)
    c3_token_hash = ScriptHash.from_primitive(config["c3_token_hash"])
    c3_token_name = AssetName(config["c3_token_name"].encode())

    logger.info("Owner address: %s", owner_addr)
    owner_minting_script.print_start_params(script_start_slot)

    c3_oracle_rate_token_name = config.get("exchange_rate_token_name") or None
    c3_oracle_rate_token_hash = config.get("exchange_rate_token_hash")
    if c3_oracle_rate_token_hash is not None:
        c3_oracle_rate_token_hash = ScriptHash.from_primitive(c3_oracle_rate_token_hash)

    if script_path:
        oracle_script = load_plutus_script(script_path)
    else:
        oracle_script = unzip_and_execute_binary(
            file_name="binary/serialized.zip",
            unzip_dir="tmp",
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
        os_aggregate_valid_range=config["oracle_settings"]["os_aggregate_valid_range"],
        os_node_fee_price=PriceRewards(
            node_fee=config["oracle_settings"]["os_node_fee_price"]["node_fee"],
            aggregate_fee=config["oracle_settings"]["os_node_fee_price"][
                "aggregate_fee"
            ],
            platform_fee=config["oracle_settings"]["os_node_fee_price"]["platform_fee"],
        ),
        os_iqr_multiplier=config["oracle_settings"]["os_iqr_multiplier"],
        os_divergence=config["oracle_settings"]["os_divergence"],
        os_platform=oracle_platform,
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
    ctx.obj["oracle_start"] = start
    ctx.obj["config"] = config


@cli.command()
@click.pass_context
def mk_start_oracle(ctx):
    """Make start oracle tx interactively."""
    oracle_start: OracleStart = ctx.obj["oracle_start"]
    config = ctx.obj["config"]
    platform_pkhs = collect_multisig_pkhs()
    if platform_pkhs:
        tx = asyncio.run(
            oracle_start.mk_start_oracle_tx(platform_pkhs, config["initial_c3_amount"])
        )
        logger.info("Created start oracle tx id: %s", tx.id)
        write_tx_to_file("start_oracle.cbor", tx)


@cli.command()
@click.pass_context
def sign_tx(ctx):
    """Parse tx and sign interactively."""
    oracle_start: OracleStart = ctx.obj["oracle_start"]
    try:
        tx, filename = parse_and_check_tx_interactively(oracle_start)
    except TxValidationException as err:
        logger.error(f"Tx validation failed, aborting, reason: {err}")
    else:
        answer = click.prompt("Do you want to sign this tx? y/n")
        if answer == "y":
            oracle_start.staged_query.sign_tx(tx, oracle_start.signing_key)
            logger.info("Tx signed")
            write_tx_to_file(filename, tx)
        else:
            logger.info("Tx signature aborted")


@cli.command()
@click.pass_context
def sign_and_submit_tx(ctx):
    """Parse, sign and submit tx interactively."""
    oracle_start: OracleStart = ctx.obj["oracle_start"]
    try:
        tx, _ = parse_and_check_tx_interactively(oracle_start)
    except TxValidationException as err:
        logger.error(f"Tx validation failed, aborting, reason: {err}")
    else:
        answer = click.prompt("Do you want to sign and submit this tx? y/n")
        if answer == "y":
            asyncio.run(
                oracle_start.staged_query.sign_and_submit_tx(
                    tx, oracle_start.signing_key
                )
            )
            logger.info("Tx signed and submitted")
        else:
            logger.info("Tx signature aborted")


def parse_and_check_tx_interactively(
    oracle_start: OracleStart,
) -> Tuple[Transaction, str]:
    """Parse, validate, and return transaction with its filename"""
    filename = click.prompt("Enter filename containing tx cbor")
    tx = read_tx_from_file(filename)
    allow_own_inputs = False
    aggstate_nft = MultiAsset.from_primitive(
        {oracle_start.owner_script_hash.payload: {b"AggState": 1}}
    )
    tx_validator = TxValidator(
        oracle_start.network,
        oracle_start.chain_query,
        oracle_start.verification_key,
        oracle_start.stake_key,
        oracle_start.oracle_address,
        aggstate_nft,
        tx,
    )
    answer = click.prompt(
        "Were you the one who created and balanced this tx with your own inputs? y/n"
    )
    if answer == "y":
        tx_id = click.prompt("Enter original tx id")
        allow_own_inputs = True
        tx_validator.raise_if_wrong_tx_id(tx_id)
    tx_validator.raise_if_invalid(allow_own_inputs, assume_oracle_exists=False)
    click.echo(tx)
    click.echo(
        f"{COLOR_RED}Please review contents of the above tx once again manually before signing{COLOR_DEFAULT}",
        color=True,
    )
    return tx, filename


if __name__ == "__main__":
    cli()  # pylint: disable=E1120
