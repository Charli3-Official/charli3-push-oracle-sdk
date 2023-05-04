"""Run simulation of the C3 protocol."""
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


MNEMONIC_24_1 = ""
MNEMONIC_24_2 = ""
MNEMONIC_24_3 = ""
MNEMONIC_24_4 = ""
MNEMONIC_24_5 = ""

network = Network.TESTNET
context = ChainQuery(
    "YOUR_TOKEN_ID_HERE",
    base_url="https://cardano-preprod.blockfrost.io/api",
)

oracle_addr = Address.from_primitive(
    "addr_test1wzuwy4ychtqjre4h90wrhnzum5gngdcsqyladhz34rffsrgqn5nl4"
)
oracle_script_hash = oracle_addr.payment_part

node_nft = MultiAsset.from_primitive(
    {"2357d8f6ff76c0b6270a69b04dbb8bf710aafc669ce25a8ffec60ee9": {b"NodeFeed": 1}}
)

aggstate_nft = MultiAsset.from_primitive(
    {"2357d8f6ff76c0b6270a69b04dbb8bf710aafc669ce25a8ffec60ee9": {b"AggState": 1}}
)

oracle_nft = MultiAsset.from_primitive(
    {"2357d8f6ff76c0b6270a69b04dbb8bf710aafc669ce25a8ffec60ee9": {b"OracleFeed": 1}}
)

c3_token_hash = ScriptHash.from_primitive(
    "436941ead56c61dbf9b92b5f566f7d5b9cac08f8c957f28f0bd60d4b"
)
c3_token_name = AssetName(b"PAYMENTTOKEN")

updates = [
    {
        "mnemonic": MNEMONIC_24_1,
        "update": 300000,
    },
    {
        "mnemonic": MNEMONIC_24_2,
        "update": 410700,
    },
    {
        "mnemonic": MNEMONIC_24_3,
        "update": 411456,
    },
    {
        "mnemonic": MNEMONIC_24_4,
        "update": 411563,
    },
    {
        "mnemonic": MNEMONIC_24_5,
        "update": 412423,
    },
]
for update in updates:
    hdwallet = HDWallet.from_mnemonic(update["mnemonic"])
    hdwallet_spend = hdwallet.derive_from_path("m/1852'/1815'/0'/0/0")
    spend_public_key = hdwallet_spend.public_key
    node_verification_key = PaymentVerificationKey.from_primitive(spend_public_key)
    node_pub_key_hash = node_verification_key.hash()

    node_signing_key = ExtendedSigningKey.from_hdwallet(hdwallet_spend)
    owner_addr = Address(node_pub_key_hash, network=Network.TESTNET)

    node = Node(
        network,
        context,
        node_signing_key,
        node_verification_key,
        node_nft,
        aggstate_nft,
        oracle_nft,
        oracle_addr,
        c3_token_hash,
        c3_token_name,
    )

    node_address = Address(payment_part=node_pub_key_hash, network=network)
    print(node_pub_key_hash)
    print(node_address)
    node.update(update["update"])
    # node.aggregate()
