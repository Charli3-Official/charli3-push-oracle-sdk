"""A CLI for managing the oracle owner actions."""

import asyncio
from typing import Tuple

import click
import ogmios
import yaml
from pycardano import (
    Address,
    AssetName,
    BlockFrostChainContext,
    ExtendedSigningKey,
    HDWallet,
    MultiAsset,
    Network,
    PaymentSigningKey,
    PaymentVerificationKey,
    ScriptHash,
    Transaction,
    TransactionId,
    TransactionInput,
    VerificationKeyHash,
)

from charli3_offchain_core.backend.kupo import KupoContext
from charli3_offchain_core.chain_query import ChainQuery
from charli3_offchain_core.oracle_owner import OracleOwner
from charli3_offchain_core.owner_script import OwnerScript
from charli3_offchain_core.tx_validation import TxValidationException, TxValidator
from charli3_offchain_core.utils.logging_config import logging
from scripts.cli_common import (
    COLOR_DEFAULT,
    COLOR_RED,
    collect_multisig_pkhs,
    load_plutus_script,
    read_tx_from_file,
    write_tx_to_file,
)

logger = logging.getLogger("oracle_owner_actions")


@click.group(invoke_without_command=True)
@click.pass_context
def cli(ctx):
    """A CLI for managing the oracle owner actions."""
    ctx.ensure_object(dict)  # Initialize the context object if not already present
    if "oracle_owner" not in ctx.obj:
        setup(ctx, "oracle-owner-actions.yml")


def setup(ctx, config_file):
    """Setup the oracle owner actions."""
    # Load the configuration file
    with open(config_file, "r", encoding="utf-8") as f:
        oracle_owner_config = yaml.safe_load(f)

    spend_vk, stake_vk, spend_sk = None, None, None

    if oracle_owner_config["MNEMONIC_24"]:
        MNEMONIC_24 = oracle_owner_config["MNEMONIC_24"]
        hdwallet = HDWallet.from_mnemonic(MNEMONIC_24)
        hdwallet_spend = hdwallet.derive_from_path("m/1852'/1815'/0'/0/0")
        spend_public_key = hdwallet_spend.public_key
        spend_vk = PaymentVerificationKey.from_primitive(spend_public_key)

        hdwallet_stake = hdwallet.derive_from_path("m/1852'/1815'/0'/2/0")
        stake_public_key = hdwallet_stake.public_key
        stake_vk = PaymentVerificationKey.from_primitive(stake_public_key)

        spend_sk = ExtendedSigningKey.from_hdwallet(hdwallet_spend)

    elif oracle_owner_config["payment_vk"] and oracle_owner_config["payment_sk"]:
        spend_sk = PaymentSigningKey.load(
            "multi-signature/key/" + oracle_owner_config["payment_sk"]
        )

        spend_vk = PaymentVerificationKey.load(
            "multi-signature/key/" + oracle_owner_config["payment_vk"]
        )

        stake_vk = PaymentVerificationKey.load(
            "multi-signature/key/" + oracle_owner_config["stake_vk"]
        )

    network = Network.MAINNET
    if oracle_owner_config["network"] == "testnet":
        network = Network.TESTNET

    chain_query_config = oracle_owner_config["chain_query"]

    blockfrost_config = chain_query_config.get("blockfrost")
    ogmios_config = chain_query_config.get("ogmios")

    blockfrost_context = None
    ogmios_context = None
    kupo_context = None

    if (
        blockfrost_config
        and blockfrost_config.get("api_url")
        and blockfrost_config.get("project_id")
    ):
        blockfrost_token = blockfrost_config["project_id"]
        blockfrost_url = blockfrost_config["api_url"]
        blockfrost_context = BlockFrostChainContext(
            blockfrost_token,
            base_url=blockfrost_url,
        )

    if ogmios_config and ogmios_config.get("ws_url") and ogmios_config.get("kupo_url"):
        ogmios_ws_url = ogmios_config["ws_url"]
        kupo_url = ogmios_config.get("kupo_url")

        _, ws_string = ogmios_ws_url.split("ws://")
        ws_url, port = ws_string.split(":")
        ogmios_context = ogmios.OgmiosChainContext(
            host=ws_url, port=int(port), network=network
        )
        kupo_context = KupoContext(kupo_url)

    chain_query = ChainQuery(
        blockfrost_context=blockfrost_context,
        ogmios_context=ogmios_context,
        kupo_context=kupo_context,
    )

    owner_addr = Address(spend_vk.hash(), stake_vk.hash(), network)
    oracle_addr = oracle_owner_config["oracle_owner"]["oracle_addr"]
    nft_hash = oracle_owner_config["oracle_owner"]["minting_nft_hash"]
    minting_nft_hash = ScriptHash.from_primitive(nft_hash)
    c3_token_hash = ScriptHash.from_primitive(
        oracle_owner_config["oracle_owner"]["c3_token_hash"]
    )
    c3_token_name = AssetName(
        oracle_owner_config["oracle_owner"]["c3_token_name"].encode()
    )
    node_nft = MultiAsset.from_primitive({nft_hash: {b"NodeFeed": 1}})
    aggstate_nft = MultiAsset.from_primitive({nft_hash: {b"AggState": 1}})
    oracle_nft = MultiAsset.from_primitive({nft_hash: {b"OracleFeed": 1}})
    reward_nft = MultiAsset.from_primitive({nft_hash: {b"Reward": 1}})
    script_start_slot = oracle_owner_config["oracle_owner"]["script_start_slot"]
    oracle_platform = oracle_owner_config["oracle_owner"]["oracle_platform"]
    native_script = OwnerScript(
        chain_query,
        [
            VerificationKeyHash.from_primitive(pkh)
            for pkh in oracle_platform["multisig_pkhs"]
        ],
        oracle_platform["multisig_threshold"],
    ).mk_owner_script(script_start_slot)
    logger.info("Owner address: %s", owner_addr)

    if (
        "reference_script_input" in oracle_owner_config["oracle_owner"]
        and chain_query.blockfrost_context is not None
    ):
        reference_script_input = oracle_owner_config["oracle_owner"][
            "reference_script_input"
        ]
        tx_id_hex, index = reference_script_input.split("#")
        tx_id = TransactionId(bytes.fromhex(tx_id_hex))
        index = int(index)
        reference_script_input = TransactionInput(tx_id, index)
    else:
        reference_script_input = None

    # (Rest of your setup code here...)
    oracle_owner = OracleOwner(
        network,
        chain_query,
        spend_sk,
        spend_vk,
        node_nft,
        aggstate_nft,
        oracle_nft,
        reward_nft,
        minting_nft_hash,
        c3_token_hash,
        c3_token_name,
        oracle_addr,
        stake_vk,
        reference_script_input,
        minting_script=native_script,
        validity_start=script_start_slot,
    )
    ctx.obj["oracle_owner"] = oracle_owner


@cli.command()
@click.pass_context
def mk_add_nodes(ctx):
    """Make add nodes tx interactively."""
    oracle_owner: OracleOwner = ctx.obj["oracle_owner"]
    nodes_to_add = []
    while True:
        node = click.prompt("Enter a node to add or 'q' to quit", default="q")
        if node == "q":
            break
        nodes_to_add.append(node)
    platform_pkhs = collect_multisig_pkhs()
    if nodes_to_add and platform_pkhs:
        tx = asyncio.run(oracle_owner.mk_add_nodes_tx(platform_pkhs, nodes_to_add))
        logger.info("Created add nodes tx id: %s", tx.id)
        write_tx_to_file("add_nodes.cbor", tx)


@cli.command()
@click.pass_context
def mk_remove_nodes(ctx):
    """Make remove nodes tx interactively."""
    oracle_owner: OracleOwner = ctx.obj["oracle_owner"]
    nodes_to_remove = []
    while True:
        node = click.prompt("Enter a node to remove or 'q' to quit", default="q")
        if node == "q":
            break
        nodes_to_remove.append(node)
    platform_pkhs = collect_multisig_pkhs()
    if nodes_to_remove and platform_pkhs:
        tx = asyncio.run(
            oracle_owner.mk_remove_nodes_tx(platform_pkhs, nodes_to_remove)
        )
        logger.info("Created remove nodes tx id: %s", tx.id)
        write_tx_to_file("remove_nodes.cbor", tx)


@cli.command()
@click.argument("funds_to_add", type=click.INT)
@click.pass_context
def add_funds(ctx, funds_to_add):
    """Add funds to the oracle."""
    oracle_owner: OracleOwner = ctx.obj["oracle_owner"]
    asyncio.run(oracle_owner.add_funds(funds_to_add))
    logger.info("Funds added: %s", funds_to_add)


@cli.command()
@click.pass_context
def mk_oracle_close(ctx):
    """Make tx for closing the oracle."""
    oracle_owner: OracleOwner = ctx.obj["oracle_owner"]
    platform_pkhs = collect_multisig_pkhs()
    raw_addr = click.prompt("Enter the withdrawal address for the C3 tokens")
    disbursementChoice = click.prompt(
        "Select an option:\n"
        "TO_NODES: Pay unclaimed C3 tokens to node operators and collect the network remainder\n"
        "TO_ONE_ADDRESS: Collect all C3 tokens in the network, including unclaimed C3 tokens\n"
        "Option",
        default="TO_NODES",
        show_default=True,
    )
    withdrawal_addr = Address.from_primitive(raw_addr)
    if platform_pkhs and disbursementChoice in ["TO_NODES", "TO_ONE_ADDRESS"]:
        tx = asyncio.run(
            oracle_owner.mk_oracle_close_tx(
                platform_pkhs, withdrawal_addr, disbursementChoice
            )
        )
        logger.info("Created oracle close tx id: %s", tx.id)
        write_tx_to_file("oracle_close.cbor", tx)


@cli.command()
@click.pass_context
def mk_platform_collect(ctx):
    """Make tx that collects the oracles rewards."""
    oracle_owner: OracleOwner = ctx.obj["oracle_owner"]
    platform_pkhs = collect_multisig_pkhs()
    raw_addr = click.prompt("Enter withdrawal address")
    withdrawal_addr = Address.from_primitive(raw_addr)
    if platform_pkhs and withdrawal_addr:
        tx = asyncio.run(
            oracle_owner.mk_platform_collect_tx(platform_pkhs, withdrawal_addr)
        )
        logger.info("Created platform collect tx id: %s", tx.id)
        write_tx_to_file("platform_collect.cbor", tx)


@cli.command()
@click.pass_context
@click.option(
    "-p",
    "--script-path",
    help="Path to existing precompiled oracle script",
)
def create_reference_script(ctx, script_path):
    """Create the reference script."""
    oracle_owner: OracleOwner = ctx.obj["oracle_owner"]
    oracle_script = load_plutus_script(script_path)
    asyncio.run(oracle_owner.create_reference_script(oracle_script))
    logger.info("Reference script created.")


@cli.command()
@click.pass_context
def mk_edit_settings(ctx):
    """Interactively create edit oracle settings tx."""
    oracle_owner: OracleOwner = ctx.obj["oracle_owner"]
    ag_settings = oracle_owner.get_oracle_settings()

    SETTINGS_MAP = {
        "0": ("os_minimum_deposit", int),
        "1": ("os_updated_nodes", int),
        "2": ("os_updated_node_time", int),
        "3": ("os_aggregate_time", int),
        "4": ("os_aggregate_change", int),
        "5": ("os_node_fee_price.node_fee", int),
        "6": ("os_node_fee_price.aggregate_fee", int),
        "7": ("os_node_fee_price.platform_fee", int),
        "8": ("os_iqr_multiplier", int),
        "9": ("os_divergence", int),
        "10": ("os_aggregate_valid_range", int),
    }

    changes_made = False

    while True:
        click.echo(f"Current settings: {ag_settings}\n")

        for option, (setting, _) in SETTINGS_MAP.items():
            click.echo(f"{option}: {setting}")

        setting_option = click.prompt(
            "Please enter the setting number or 'q' to finish",
            type=click.Choice(list(SETTINGS_MAP.keys()) + ["q"], case_sensitive=False),
        )

        if setting_option == "q":
            break

        setting_name, setting_type = SETTINGS_MAP[setting_option]
        new_value = click.prompt(
            f"Enter a new value for {setting_name}", type=setting_type
        )

        if (
            "." in setting_name
        ):  # for nested attribute changes like os_node_fee_price.node_fee
            attr, nested_attr = setting_name.split(".")
            setattr(getattr(ag_settings, attr), nested_attr, new_value)
        else:
            setattr(ag_settings, setting_name, new_value)

        changes_made = True

    platform_pkhs = collect_multisig_pkhs()

    if changes_made and platform_pkhs:
        tx = asyncio.run(oracle_owner.mk_edit_settings_tx(platform_pkhs, ag_settings))
        logger.info("Created edit settings tx id: %s", tx.id)
        write_tx_to_file("edit_settings.cbor", tx)
    else:
        click.echo("No changes were made.")


@cli.command()
@click.pass_context
def sign_tx(ctx):
    """Parse tx and sign interactively."""
    oracle_owner: OracleOwner = ctx.obj["oracle_owner"]
    try:
        tx, filename = parse_and_check_tx_interactively(oracle_owner)
    except TxValidationException as err:
        logger.error("Tx validation failed, aborting, reason: %s", err)
    else:
        answer = click.prompt("Do you want to sign this tx? y/n")
        if answer == "y":
            oracle_owner.staged_query.sign_tx(tx, oracle_owner.signing_key)
            logger.info("Tx signed")
            write_tx_to_file(filename, tx)
        else:
            logger.info("Tx signature aborted")


@cli.command()
@click.pass_context
def sign_and_submit_tx(ctx):
    """Parse, sign and submit tx interactively."""
    oracle_owner: OracleOwner = ctx.obj["oracle_owner"]
    try:
        tx, _ = parse_and_check_tx_interactively(oracle_owner)
    except TxValidationException as err:
        logger.error("Tx validation failed, aborting, reason: %s", err)
    else:
        answer = click.prompt("Do you want to sign and submit this tx? y/n")
        if answer == "y":
            asyncio.run(
                oracle_owner.staged_query.sign_and_submit_tx(
                    tx, oracle_owner.signing_key
                )
            )
            logger.info("Tx signed and submitted")
        else:
            logger.info("Tx signature aborted")


def parse_and_check_tx_interactively(
    oracle_owner: OracleOwner,
) -> Tuple[Transaction, str]:
    """Parse, validate, and return transaction with its filename"""
    filename = click.prompt("Enter filename containing tx cbor")
    tx = read_tx_from_file(filename)
    allow_own_inputs = False
    tx_validator = TxValidator(
        oracle_owner.network,
        oracle_owner.chainquery,
        oracle_owner.verification_key,
        oracle_owner.stake_key,
        oracle_owner.oracle_addr,
        oracle_owner.aggstate_nft,
        tx,
    )
    answer = click.prompt(
        "Were you the one who created and balanced this tx with your own inputs? y/n"
    )
    if answer == "y":
        tx_id = click.prompt("Enter original tx id")
        allow_own_inputs = True
        tx_validator.raise_if_wrong_tx_id(tx_id)
    tx_validator.raise_if_invalid(allow_own_inputs)
    click.echo(tx)
    click.echo(
        f"{COLOR_RED}Please review contents of the above tx once again manually before signing{COLOR_DEFAULT}",
        color=True,
    )
    return tx, filename


if __name__ == "__main__":
    cli()  # pylint: disable=E1120
