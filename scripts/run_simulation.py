"""Run simulation of the C3 protocol."""
import time
import yaml
from pycardano import (
    Network,
    Address,
    PaymentVerificationKey,
    MultiAsset,
    ScriptHash,
    AssetName,
    ExtendedSigningKey,
    HDWallet,
)
from src.datums import *
from src.redeemers import *
from src.chain_query import ChainQuery
from src.node import Node

with open("run-node-simulator.yml", "r") as stream:
    config = yaml.safe_load(stream)

network = Network.MAINNET
if config["network"] == "testnet":
    network = Network.TESTNET

context = ChainQuery(
    config["chain_query"]["token_id"],
    base_url=config["chain_query"]["base_url"],
)
nft_hash = config["oracle_info"]["minting_nft_hash"]

oracle_addr = Address.from_primitive(config["oracle_info"]["oracle_addr"])
oracle_script_hash = oracle_addr.payment_part

node_nft = MultiAsset.from_primitive({nft_hash: {b"NodeFeed": 1}})
aggstate_nft = MultiAsset.from_primitive({nft_hash: {b"AggState": 1}})
oracle_nft = MultiAsset.from_primitive({nft_hash: {b"OracleFeed": 1}})
reward_nft = MultiAsset.from_primitive({nft_hash: {b"Reward": 1}})

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
    )
    print(node_pub_key_hash)
    nodes.append(node)

# Update all nodes in sequence
for i, node in enumerate(nodes):
    node.update(updates[i]["update"])
    # Check if this is the last update
    if i == len(nodes) - 1:
        time.sleep(30)
        print("Aggregating...")
        node.aggregate()

# Wait for all nodes to aggregate
time.sleep(30)
# Collect all nodes with 20 seconds pause in between
for node in nodes:
    node.collect(node.address)
    time.sleep(20)
