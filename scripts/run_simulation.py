"""Run simulation of the C3 protocol."""

import asyncio
from typing import Union

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
    OgmiosChainContext,
    PaymentVerificationKey,
    ScriptHash,
    TransactionId,
    TransactionInput,
)

from charli3_offchain_core.chain_query import ChainQuery
from charli3_offchain_core.node import Node

with open("run-node-simulator.yml", "r", encoding="utf-8") as stream:
    config = yaml.safe_load(stream)

network = Network.MAINNET
if config["network"] == "testnet":
    network = Network.TESTNET

chain_query_config = config["chain_query"]

blockfrost_config = chain_query_config.get("blockfrost")
ogmios_config = chain_query_config.get("ogmios")

blockfrost_context = None  # pylint: disable=invalid-name
ogmios_context = None  # pylint: disable=invalid-name

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
    if ogmios_config.get("pogmios"):
        _, ws_string = ogmios_ws_url.split("ws://")
        ws_url, port = ws_string.split(":")
        ogmios_context = ogmios.OgmiosChainContext(
            host=ws_url, port=int(port), network=network
        )
    else:
        ogmios_context = OgmiosChainContext(
            network=network,
            ws_url=ogmios_ws_url,
            kupo_url=kupo_url,
        )

chain_query = ChainQuery(
    blockfrost_context=blockfrost_context, ogmios_context=ogmios_context
)
nft_hash = config["oracle_info"]["minting_nft_hash"]

oracle_addr = Address.from_primitive(config["oracle_info"]["oracle_addr"])
oracle_script_hash = oracle_addr.payment_part

node_nft = MultiAsset.from_primitive({nft_hash: {b"NodeFeed": 1}})
aggstate_nft = MultiAsset.from_primitive({nft_hash: {b"AggState": 1}})
oracle_nft = MultiAsset.from_primitive({nft_hash: {b"OracleFeed": 1}})
reward_nft = MultiAsset.from_primitive({nft_hash: {b"Reward": 1}})


def create_c3_oracle_rate_nft(token_name, minting_policy) -> Union[MultiAsset, None]:
    """Create C3 oracle rate NFT."""
    if token_name and minting_policy:
        return MultiAsset.from_primitive(
            {minting_policy.payload: {bytes(token_name, "utf-8"): 1}}
        )
    else:
        return None


c3_oracle_rate_nft_hash = None  # pylint: disable=invalid-name
if (
    "oracle_info" in config
    and "c3_rate_nft_hash" in config["oracle_info"]
    and config["oracle_info"]["c3_rate_nft_hash"]
):
    c3_oracle_rate_nft_hash = ScriptHash.from_primitive(
        config["oracle_info"]["c3_rate_nft_hash"]
    )

c3_oracle_rate_nft_name = None  # pylint: disable=invalid-name
if (
    "oracle_info" in config
    and "c3_rate_nft_name" in config["oracle_info"]
    and config["oracle_info"]["c3_rate_nft_name"]
):
    c3_oracle_rate_nft_name = config["oracle_info"]["c3_rate_nft_name"]

c3_oracle_rate_nft = create_c3_oracle_rate_nft(
    c3_oracle_rate_nft_name, c3_oracle_rate_nft_hash
)

c3_oracle_rate_address = None  # pylint: disable=invalid-name
if (
    "oracle_info" in config
    and "c3_oracle_rate_address" in config["oracle_info"]
    and config["oracle_info"]["c3_oracle_rate_address"]
):
    c3_oracle_rate_address = Address.from_primitive(
        config["oracle_info"]["c3_oracle_rate_address"]
    )

c3_token_hash = ScriptHash.from_primitive(config["oracle_info"]["c3_token_hash"])
c3_token_name = AssetName(config["oracle_info"]["c3_token_name"].encode())

if "reference_script_input" in config["oracle_info"]:
    reference_script_input = config["oracle_info"]["reference_script_input"]
    tx_id_hex, index = reference_script_input.split("#")
    tx_id = TransactionId(bytes.fromhex(tx_id_hex))
    index = int(index)
    reference_script_input = TransactionInput(tx_id, index)
else:
    reference_script_input = None  # pylint: disable=invalid-name

updates = config["updates"]

nodes = []
for i, update in enumerate(updates):
    hdwallet = HDWallet.from_mnemonic(update["mnemonic"])
    hdwallet_spend = hdwallet.derive_from_path("m/1852'/1815'/0'/0/0")
    spend_public_key = hdwallet_spend.public_key
    node_verification_key = PaymentVerificationKey.from_primitive(spend_public_key)
    node_pub_key_hash = node_verification_key.hash()

    node_signing_key = ExtendedSigningKey.from_hdwallet(hdwallet_spend)
    owner_addr = Address(node_pub_key_hash, network=network)

    node = Node(
        network,
        chain_query,
        node_signing_key,
        node_verification_key,
        node_nft,
        aggstate_nft,
        oracle_nft,
        reward_nft,
        oracle_addr,
        c3_token_hash,
        c3_token_name,
        reference_script_input,
        c3_oracle_rate_address,
        c3_oracle_rate_nft,
    )
    nodes.append(node)


async def main():
    """Run simulation."""
    # Create tasks for all updates
    update_tasks = [
        node.update(update["update"]) for node, update in zip(nodes, updates)
    ]

    # Run all updates in parallel
    await asyncio.gather(*update_tasks)

    # After all updates are done, sleep for a while
    await asyncio.sleep(30)

    # Aggregate last node
    print("Aggregating...")
    await nodes[-1].aggregate()

    # Wait for all nodes to aggregate
    await asyncio.sleep(30)
    # Collect all nodes with 20 seconds pause in between
    for node in nodes:
        await node.collect(node.address)
        await asyncio.sleep(20)
    print("Simulation end")


if __name__ == "__main__":
    asyncio.run(main())
