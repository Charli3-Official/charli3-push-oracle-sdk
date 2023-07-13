"""A CLI for managing the oracle owner actions."""
import asyncio
import click
import yaml
from pycardano import (
    HDWallet,
    Address,
    Network,
    ExtendedSigningKey,
    PaymentVerificationKey,
    MultiAsset,
    ScriptHash,
    AssetName,
    BlockFrostChainContext,
)

from charli3_offchain_core.chain_query import ChainQuery
from charli3_offchain_core.oracle_owner import OracleOwner
from charli3_offchain_core.owner_script import OwnerScript
from charli3_offchain_core.utils.logging_config import logging


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
    with open(config_file, "r") as f:
        oracle_owner_config = yaml.safe_load(f)
    MNEMONIC_24 = oracle_owner_config["MNEMONIC_24"]

    network = Network.MAINNET
    if oracle_owner_config["network"] == "testnet":
        network = Network.TESTNET

    blockfrost_base_url = oracle_owner_config["chain_query"]["base_url"]
    blockfrost_project_id = oracle_owner_config["chain_query"]["token_id"]

    blockfrost_context = BlockFrostChainContext(
        blockfrost_project_id,
        base_url=blockfrost_base_url,
    )

    chain_query = ChainQuery(
        blockfrost_context,
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
    native_script = OwnerScript(
        network,
        chain_query,
        spend_vk,
    ).mk_owner_script(script_start_slot)
    logger.info("Owner address: %s", owner_addr)

    # (Rest of your setup code here...)
    oracle_owner = OracleOwner(
        network,
        chain_query,
        extended_signing_key,
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
        minting_script=native_script,
        validity_start=script_start_slot,
    )
    ctx.obj["oracle_owner"] = oracle_owner


@cli.command()
@click.pass_context
def add_nodes(ctx):
    """Add nodes to the oracle interactively."""
    oracle_owner: OracleOwner = ctx.obj["oracle_owner"]
    nodes_to_add = []
    while True:
        node = click.prompt("Enter a node to add or 'q' to quit", default="q")
        if node == "q":
            break
        nodes_to_add.append(node)
    if nodes_to_add:
        asyncio.run(oracle_owner.add_nodes(nodes_to_add))
        logger.info("Nodes added: %s", nodes_to_add)

@cli.command()
@click.pass_context
def remove_nodes(ctx):
    """Remove nodes from the oracle interactively."""
    oracle_owner: OracleOwner = ctx.obj["oracle_owner"]
    nodes_to_remove = []
    while True:
        node = click.prompt("Enter a node to remove or 'q' to quit", default="q")
        if node == "q":
            break
        nodes_to_remove.append(node)
    if nodes_to_remove:
        asyncio.run(oracle_owner.remove_nodes(nodes_to_remove))
        logger.info("Nodes removed: %s", nodes_to_remove)


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
def oracle_close(ctx):
    """Close the oracle."""
    oracle_owner: OracleOwner = ctx.obj["oracle_owner"]
    asyncio.run(oracle_owner.oracle_close())
    logger.info("Oracle closed.")


@cli.command()
@click.pass_context
def platform_collect(ctx):
    """Collect the oracle's platform rewards."""
    oracle_owner: OracleOwner = ctx.obj["oracle_owner"]
    asyncio.run(oracle_owner.platform_collect())
    logger.info("Platform rewards collected.")


@cli.command()
@click.pass_context
def create_reference_script(ctx):
    """Create the reference script."""
    oracle_owner: OracleOwner = ctx.obj["oracle_owner"]
    asyncio.run(oracle_owner.create_reference_script())
    logger.info("Reference script created.")


@cli.command()
@click.pass_context
def edit_settings(ctx):
    """Interactively edit the oracle settings."""
    oracle_owner: OracleOwner = ctx.obj["oracle_owner"]
    ag_settings = oracle_owner.get_oracle_settings()

    SETTINGS_MAP = {
        "1": ("os_updated_nodes", int),
        "2": ("os_updated_node_time", int),
        "3": ("os_aggregate_time", int),
        "4": ("os_aggregate_change", int),
        "5": ("os_node_fee_price.node_fee", int),
        "6": ("os_node_fee_price.aggregate_fee", int),
        "7": ("os_node_fee_price.platform_fee", int),
        "8": ("os_mad_multiplier", int),
        "9": ("os_divergence", int),
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

    if changes_made:
        asyncio.run(oracle_owner.edit_settings(ag_settings))
        click.echo("Settings have been updated.")
    else:
        click.echo("No changes were made.")


if __name__ == "__main__":
    cli()  # pylint: disable=E1120
