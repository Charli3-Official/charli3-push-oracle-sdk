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
)
from datums import NodeDatum, NodeInfo, PriceFeed, DataFeed, OracleSettings, NodeFee
from redeemers import NodeUpdate
from chain_query import ChainQuery
from oracle_owner import OracleOwner

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
    print(spend_vk.hash())

    network = Network.TESTNET
    context = ChainQuery(
        "YOUR_TOKEN_ID_HERE",
        network,
        base_url="https://cardano-preprod.blockfrost.io/api",
    )

    oracle_addr = "addr_test1wz6jdu4f0eeamgzz2a8wt3eufux33nv6ju35z6r4de5rl0sncyqgh"
    # oracle_script_hash = Address.from_primitive(oracle_addr).payment_part
    # oracle_v2_script=context._get_script(oracle_script_hash)
    print(owner_addr, type(owner_addr))
    node_nft = MultiAsset.from_primitive(
        {"2e527c8e42d0f28fd3f4025f60c0a89bc5815c8e2efc3fb973e3fc20": {b"NodeFeed": 1}}
    )
    aggstate_nft = MultiAsset.from_primitive(
        {"2e527c8e42d0f28fd3f4025f60c0a89bc5815c8e2efc3fb973e3fc20": {b"AggState": 1}}
    )
    oracle_nft = MultiAsset.from_primitive(
        {"2e527c8e42d0f28fd3f4025f60c0a89bc5815c8e2efc3fb973e3fc20": {b"OracleFeed": 1}}
    )
    minting_nft_hash = ScriptHash.from_primitive(
        "2e527c8e42d0f28fd3f4025f60c0a89bc5815c8e2efc3fb973e3fc20"
    )
    c3_token_hash = ScriptHash.from_primitive(
        "436941ead56c61dbf9b92b5f566f7d5b9cac08f8c957f28f0bd60d4b"
    )
    c3_token_name = AssetName(b"PAYMENTTOKEN")

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
    )

    ag_settings = OracleSettings(
        os_node_list=[
            b"\xda(\x13\x13t\x9a\xf2\x03\xe2\xb1\x19\xdf\x16\x89U\x17G\r\xd2Hd7 Kf\xb8\x83f",
            b"\xed\x06\x9eV\xd4k\x12lJ\xaf\xcc\x19\x87\xf5\x06\x9b\xa6\x0b\x07p\xea\x85\x8e\x94\xac\x9a.\xc7",
            b"7\x08\x03\x14\xef\xdawS\xfaN\xf1\xf8\xa1\x9e\xc9\xb7\xe9#v\xd0gx\xe1\x8dEk\x94m",
            b'\xecL\x19\x94\xd7\x9d\x1a\x07\xf2o[\xd7\xab\xa2\x85\x8c\xd0<\r\x1f\x1f\x18\xcf\xd2\xcf"\xff`',
            b"\xddc\xf5\xa0\xdd\xba\x85\x7f?\xe41\xfe+\xc1\xe7\x14v\xf44\xef0\xf8\xbe\xfc&\x1c\xf7\x16",
        ],
        os_updated_nodes=7500,
        os_updated_node_time=3600000,
        os_aggregate_time=3600000,
        os_aggregate_change=2000,
        os_node_fee_price=NodeFee(getNodeFee=15000),
        os_mad_multiplier=2000,
        os_divergence=5000,
    )
    # oracle_owner.add_nodes([VerificationKeyHash.from_primitive("bd95d582888acda57a20256bb03e4c4abb6bdf09a47d788605412c53")])
    # oracle_owner.add_nodes(["dd63f5a0ddba857f3fe431fe2bc1e71476f434ef30f8befc261cf716"])
    # oracle_owner.convert_datums_to_inlineable()
    # oracle_owner.create_reference_script()
    # oracle_owner.remove_nodes(["1a550d5f572584e1add125b5712f709ac3b9828ad86581a4759022ba"])
    oracle_owner.edit_settings(ag_settings)
    # context.create_collateral(owner_addr,extended_signing_key)
    # oracle_owner.add_funds(70000000)
    # oracle_owner.oracle_close()


payment_address_24_base()
