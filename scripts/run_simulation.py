"""Run simulation of the C3 protocol."""
import asyncio
import yaml
from typing import Union
from pycardano import (
    Network,
    Address,
    PaymentVerificationKey,
    MultiAsset,
    ScriptHash,
    AssetName,
    ExtendedSigningKey,
    HDWallet,
    BlockFrostChainContext,
)
from charli3_offchain_core.chain_query import ChainQuery
from charli3_offchain_core.node import Node

with open("run-node-simulator.yml", "r") as stream:
    config = yaml.safe_load(stream)

network = Network.MAINNET
if config["network"] == "testnet":
    network = Network.TESTNET

blockfrost_base_url = config["chain_query"]["base_url"]
blockfrost_project_id = config["chain_query"]["token_id"]

blockfrost_context = BlockFrostChainContext(
    blockfrost_project_id,
    base_url=blockfrost_base_url,
)

context = ChainQuery(
    blockfrost_context,
)
nft_hash = config["oracle_info"]["minting_nft_hash"]

oracle_addr = Address.from_primitive(config["oracle_info"]["oracle_addr"])
oracle_script_hash = oracle_addr.payment_part

node_nft = MultiAsset.from_primitive({nft_hash: {b"NodeFeed": 1}})
aggstate_nft = MultiAsset.from_primitive({nft_hash: {b"AggState": 1}})
oracle_nft = MultiAsset.from_primitive({nft_hash: {b"OracleFeed": 1}})
reward_nft = MultiAsset.from_primitive({nft_hash: {b"Reward": 1}})


def c3_create_oracle_rate_nft(token_name, minting_policy) -> Union[MultiAsset, None]:
    if token_name and minting_policy:
        return MultiAsset.from_primitive(
            {minting_policy.payload: {bytes(token_name, "utf-8"): 1}}
        )
    else:
        return None


c3_oracle_rate_nft_hash = (
    ScriptHash.from_primitive(config["oracle_info"]["c3_rate_nft_hash"])
    if config["oracle_info"]["c3_rate_nft_hash"]
    else None
)

c3_oracle_rate_nft_name = config["oracle_info"]["c3_rate_nft_name"] or None
c3_oracle_rate_nft = c3_create_oracle_rate_nft(
    c3_oracle_rate_nft_name, c3_oracle_rate_nft_hash
)

c3_oracle_rate_address = (
    Address.from_primitive(config["oracle_info"]["c3_oracle_rate_address"])
    if config["oracle_info"]["c3_oracle_rate_address"]
    else None
)

c3_token_hash = ScriptHash.from_primitive(config["oracle_info"]["c3_token_hash"])
c3_token_name = AssetName(config["oracle_info"]["c3_token_name"].encode())

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
        context,
        node_signing_key,
        node_verification_key,
        node_nft,
        aggstate_nft,
        oracle_nft,
        reward_nft,
        oracle_addr,
        c3_token_hash,
        c3_token_name,
        None,
        c3_oracle_rate_address,
        c3_oracle_rate_nft,
    )
    print(node_pub_key_hash)
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


if __name__ == "__main__":
    asyncio.run(main())
