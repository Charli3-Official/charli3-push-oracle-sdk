"""script to mint tokens"""
import cbor2
from pycardano import (
    Network,
    Address,
    PaymentVerificationKey,
    PaymentSigningKey,
    PlutusV2Script,
)
from charli3_offchain_core.chain_query import ChainQuery
from charli3_offchain_core.mint import Mint

network = Network.TESTNET
context = ChainQuery(
    "YOUR_TOKEN_ID_HERE",
    base_url="https://cardano-preprod.blockfrost.io/api",
)

node_signing_key = PaymentSigningKey.load("node.skey")
node_verification_key = PaymentVerificationKey.load("node.vkey")
node_pub_key_hash = node_verification_key.hash()
node_address = Address(payment_part=node_pub_key_hash, network=network)
with open("./mint_script.plutus", "r") as f:
    script_hex = f.read()
    plutus_script_v2 = PlutusV2Script(cbor2.loads(bytes.fromhex(script_hex)))

c3_token = Mint(
    network, context, node_signing_key, node_verification_key, plutus_script_v2
)
c3_token.mint_nft_with_script()
