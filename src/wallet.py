"""Wallet module."""
import cbor2
from pycardano import (
    HDWallet,
    Address,
    Network,
    ExtendedSigningKey,
    PaymentVerificationKey,
    MultiAsset,
    ScriptHash,
    VerificationKeyHash,
    AssetName,
    PlutusV2Script,
)
from datums import NodeDatum, NodeInfo, PriceFeed, DataFeed, OracleSettings, NodeFee
from redeemers import NodeUpdate
from chain_query import ChainQuery
from oracle_owner import OracleOwner
from oracle_start import OracleStart
from owner_script import OwnerScript

MNEMONIC_24 = "marriage cart opinion purpose elder maid slight eyebrow chalk trade maximum caught tomato shop sad visa iron gather dawn faith almost three pledge fault"


def payment_address_24_base():
    hdwallet = HDWallet.from_mnemonic(MNEMONIC_24)
    hdwallet_spend = hdwallet.derive_from_path("m/1852'/1815'/0'/0/0")
    spend_public_key = hdwallet_spend.public_key
    spend_vk = PaymentVerificationKey.from_primitive(spend_public_key)

    hdwallet_stake = hdwallet.derive_from_path("m/1852'/1815'/0'/2/0")
    stake_public_key = hdwallet_stake.public_key
    stake_vk = PaymentVerificationKey.from_primitive(stake_public_key)

    extended_signing_key = ExtendedSigningKey.from_hdwallet(hdwallet_spend)
    owner_addr = Address(spend_vk.hash(), stake_vk.hash(), network=Network.TESTNET)

    network = Network.TESTNET
    context = ChainQuery(
        "YOUR_TOKEN_ID_HERE",
        network,
        base_url="https://cardano-preprod.blockfrost.io/api",
    )

    oracle_addr = "addr_test1wzvpdaprmjaa2y8ayp4x93ptjzmazkjapulvepc5xttpwhs283cyl"
    print(owner_addr)
    node_nft = MultiAsset.from_primitive(
        {"2357d8f6ff76c0b6270a69b04dbb8bf710aafc669ce25a8ffec60ee9": {b"NodeFeed": 1}}
    )
    aggstate_nft = MultiAsset.from_primitive(
        {"2357d8f6ff76c0b6270a69b04dbb8bf710aafc669ce25a8ffec60ee9": {b"AggState": 1}}
    )
    oracle_nft = MultiAsset.from_primitive(
        {"2357d8f6ff76c0b6270a69b04dbb8bf710aafc669ce25a8ffec60ee9": {b"OracleFeed": 1}}
    )
    minting_nft_hash = ScriptHash.from_primitive(
        "2357d8f6ff76c0b6270a69b04dbb8bf710aafc669ce25a8ffec60ee9"
    )
    c3_token_hash = ScriptHash.from_primitive(
        "436941ead56c61dbf9b92b5f566f7d5b9cac08f8c957f28f0bd60d4b"
    )
    c3_token_name = AssetName(b"PAYMENTTOKEN")

    script_start_slot = 25740473
    owner_minting_script = OwnerScript(
        network,
        context,
        spend_vk,
    )
    native_script = owner_minting_script.mk_owner_script(script_start_slot)
    print(owner_minting_script.print_start_params(script_start_slot))
    oracle_owner = OracleOwner(
        network,
        context,
        extended_signing_key,
        spend_vk,
        node_nft,
        aggstate_nft,
        oracle_nft,
        minting_nft_hash,
        c3_token_hash,
        c3_token_name,
        oracle_addr,
        stake_vk,
        native_script,
        script_start_slot,
    )

    agSettings = OracleSettings(
        os_node_list=[
            b"\xc36\xa4\xd3\xef9\x91;c\xe6\x1f\x92\x00\x8dQ\x91Un\xd3\xc3\xc5\xc1\x1bPvK\xc1\xe4",
            b"\xd1p~H\x16q\xd4s\xeeZ\x8dV\x1a\xaa\xc4\xa1\xf4\xe8\xc97\xcea\xe5\xd1\x1f\xc0a\x1f",
            b"3\x18\xad\x8f\x0ct:gH1\xd6\x9eLa\xc0\xd8\x05\xed\xa6\x95\xb0\xf2\nO\xf0\xed\xeb\xc5",
            b'\\"+tb\xa0\xce\xb4\xd2\x05\xa5\xa5\x08\xf17V\n\xdf\x88c\x0b\x9b}\xccS\xb1\x83\xdd',
            b"0\xdf\xe7\xe9\x85\xa9\xfa<\xbf\x9f\xc0\xa5\xa6\xe3\xb4\xb4\xa1\xa1\x84\xc3\xb9\xf8\xc2\xf2\x004X\xf2",
        ],
        os_updated_nodes=6000,
        os_updated_node_time=3600000,
        os_aggregate_time=3600000,
        os_aggregate_change=200,
        os_node_fee_price=NodeFee(getNodeFee=5),
        os_mad_multiplier=20000,
        os_divergence=1500,
    )

    # with open("./oracleV2.plutus", "r") as f:
    #     script_hex = f.read()
    #     oracle_script = PlutusV2Script(cbor2.loads(bytes.fromhex(script_hex)))
    

    # start = OracleStart(network=network, context=context, signing_key=extended_signing_key,
    #                     verification_key=spend_vk,stake_key=stake_vk, oracle_script=oracle_script, script_start_slot=script_start_slot,
    #                     settings=agSettings, c3_token_hash=c3_token_hash, c3_token_name=c3_token_name)
    # start.start_oracle(5000)
    # oracle_owner.add_nodes(["c336a4d3ef39913b63e61f92008d5191556ed3c3c5c11b50764bc1e5"])
    # "d1707e481671d473ee5a8d561aaac4a1f4e8c937ce61e5d11fc0611f",
    # "3318ad8f0c743a674831d69e4c61c0d805eda695b0f20a4ff0edebc5",
    # "5c222b7462a0ceb4d205a5a508f137560adf88630b9b7dcc53b183dd",
    # "30dfe7e985a9fa3cbf9fc0a5a6e3b4b4a1a184c3b9f8c2f2003458f2"])
    # oracle_owner.convert_datums_to_inlineable()
    # oracle_owner.create_reference_script()
    # oracle_owner.remove_nodes(["5c222b7462a0ceb4d205a5a508f137560adf88630b9b7dcc53b183dd", "30dfe7e985a9fa3cbf9fc0a5a6e3b4b4a1a184c3b9f8c2f2003458f2"])
    # oracle_owner.edit_settings(agSettings)
    # context.create_collateral(owner_addr,extended_signing_key)
    # oracle_owner.add_funds(999801)
    # oracle_owner.oracle_close()
    # oracle_owner.initialize_oracle_datum()


payment_address_24_base()
