"""script to mint tokens"""

import asyncio

import cbor2
from pycardano import (
    Address,
    BlockFrostChainContext,
    Network,
    PaymentSigningKey,
    PaymentVerificationKey,
    PlutusV2Script,
)

from charli3_offchain_core.chain_query import ChainQuery
from charli3_offchain_core.mint import Mint

network = Network.TESTNET
blockfrost_base_url = "https://cardano-preprod.blockfrost.io/api"
blockfrost_project_id = "YOUR_TOKEN_ID_HERE"
blockfrost_context = BlockFrostChainContext(
    blockfrost_project_id,
    base_url=blockfrost_base_url,
)

context = ChainQuery(
    blockfrost_context,
)
# TODO: Add your node keys here
node_signing_key = PaymentSigningKey.load("path/to/your/node.skey")
node_verification_key = PaymentVerificationKey.load("path/to/your/node.vkey")
node_pub_key_hash = node_verification_key.hash()
node_address = Address(payment_part=node_pub_key_hash, network=network)
with open("../plutus-scripts/mint_script.plutus", "r") as f:
    script_hex = f.read()
    plutus_script_v2 = PlutusV2Script(cbor2.loads(bytes.fromhex(script_hex)))

c3_token = Mint(
    network, context, node_signing_key, node_verification_key, plutus_script_v2
)
asyncio.run(c3_token.mint_nft_with_script())
