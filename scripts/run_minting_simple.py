"""script to mint tokens with native script"""
from pycardano import (
    Network,
    Address,
    PaymentVerificationKey,
    HDWallet,
    ExtendedSigningKey,
    MultiAsset,
    TransactionBuilder,
)
import yaml
from charli3_offchain_core.owner_script import OwnerScript
from charli3_offchain_core.chain_query import ChainQuery

network = Network.TESTNET
chain_query = ChainQuery(
    "YOUR_TOKEN_ID_HERE",
    base_url="https://cardano-preprod.blockfrost.io/api",
)

with open("oracle_deploy.yml", "r") as ymlfile:
    config = yaml.safe_load(ymlfile)

MNEMONIC_24 = config["MNEMONIC_24"]

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


def submit_tx_builder(tx_builder: TransactionBuilder):
    """adds collateral and signers to tx , sign and submit tx."""
    collateral_utxo = chain_query.find_collateral(owner_addr)

    if collateral_utxo is None:
        chain_query.create_collateral(owner_addr, extended_signing_key)
        collateral_utxo = chain_query.find_collateral(owner_addr)

    tx_builder.collaterals.append(collateral_utxo)

    signed_tx = tx_builder.build_and_sign(
        [extended_signing_key],
        change_address=owner_addr,
        collateral_change_address=owner_addr,
    )
    chain_query.submit_tx_with_print(signed_tx)


script_start_slot, owner_script = owner_minting_script.create_owner_script()
owner_minting_script.print_start_params(script_start_slot)
owner_script_hash = owner_script.hash()

c3_tokens = MultiAsset.from_primitive(
    {owner_script_hash.payload: {b"TestC3": 1_000_000}}
)

builder = TransactionBuilder(chain_query.context)

# Required since owner script is InvalidBefore type
builder.validity_start = script_start_slot

builder.mint = c3_tokens

# Set native script
builder.native_scripts = [owner_script]

builder.add_input_address(owner_addr)

pub_key_hash = spend_vk.hash()
builder.required_signers = [pub_key_hash]

submit_tx_builder(builder)
