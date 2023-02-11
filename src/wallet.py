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
    owner_addr = Address(spend_vk.hash(), stake_vk.hash(), network=Network.MAINNET)

    network = Network.MAINNET
    context = ChainQuery(
        "mainnetC1kgA6sHNIkRmjNA5jLCa8gUfKc8omBg",
        network,
        base_url="https://cardano-mainnet.blockfrost.io/api",
    )

    oracle_addr = "addr1wyd8cezjr0gcf8nfxuc9trd4hs7ec520jmkwkqzywx6l5jg0al0ya"
    print(owner_addr)
    node_nft = MultiAsset.from_primitive(
        {"3d0d75aad1eb32f0ce78fb1ebc101b6b51de5d8f13c12daa88017624": {b"NodeFeed": 1}}
    )
    aggstate_nft = MultiAsset.from_primitive(
        {"3d0d75aad1eb32f0ce78fb1ebc101b6b51de5d8f13c12daa88017624": {b"AggState": 1}}
    )
    oracle_nft = MultiAsset.from_primitive(
        {"3d0d75aad1eb32f0ce78fb1ebc101b6b51de5d8f13c12daa88017624": {b"OracleFeed": 1}}
    )
    minting_nft_hash = ScriptHash.from_primitive(
        "3d0d75aad1eb32f0ce78fb1ebc101b6b51de5d8f13c12daa88017624"
    )
    c3_token_hash = ScriptHash.from_primitive(
        "8e51398904a5d3fc129fbf4f1589701de23c7824d5c90fdb9490e15a"
    )
    c3_token_name = AssetName(b"CHARLI3")

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

    agSettings = OracleSettings(
        os_node_list=[
            b"\xdbS\x98\xb3%\x04\x1d\xdf\xc6\xb0\xd4\xe5\xb6\ns\x8f\x04i(A~`+\xf7E\x8447",
            b"6\x96\x19L\x8dm.\x12\x8f\xed\xb8&]P\xbde\x88\xd3\xe0\xe7\xfdG\x9c$IT\x00\x93",
            b"\x19\xb9!\xcc\xad\x17\xa5\x05n\x1f\x0e\xb5u\xd4ex;\x8b\xbc\x8cQ\xa6\xf7\x1eO\x88\xc8\x0b",
            b"u\xd8o\x9e\xc9\xa1\x17\x95Xh\xcb&\xda\xf2\x15\xcaM\xfb\x1bw\xfc)|\x8d\xb2\x16\xb2\xd4",
            b"\x84\x02\xfc\x11\x8fi-S\xb27\xf00\x11\x05\xe0\x19\x1f\xbb\x9e\x85\xff\x9d\xe1\xe03\xc0\xbc\xc8",
        ],
        os_updated_nodes=6000,
        os_updated_node_time=3600000,
        os_aggregate_time=3600000,
        os_aggregate_change=200,
        os_node_fee_price=NodeFee(getNodeFee=2580000),
        os_mad_multiplier=20000,
        os_divergence=1500,
    )
    # oracle_owner.add_nodes(["007df380aef26e44739db3f4fe67d8137446e630dab3df16d9fbddc5",
    # "cef7fb5f89a9c76a65acdd746d9e84104d6f824d7dc44f427fcaa1dd",
    # "4ad1571e7df63d4d6c49240c8372eb639f57c0ef669338c0d752f29b",
    # "f6f69e5af37c2978cb2124c12202f2185fd5c14ee93bb832911daf8e",
    # "2d7103fdaf4beecbbef37edc6d24d311230f2836d0af791e3a6364d2"])
    # oracle_owner.convert_datums_to_inlineable()
    # oracle_owner.create_reference_script()
    # oracle_owner.remove_nodes(["49bd983d12353a48d39ad15212220ebd71dd3f897eb29ab89f3cb58e"])
    # oracle_owner.edit_settings(agSettings)
    # context.create_collateral(owner_addr,extended_signing_key)
    # oracle_owner.add_funds(229620000)
    # oracle_owner.oracle_close()


payment_address_24_base()
