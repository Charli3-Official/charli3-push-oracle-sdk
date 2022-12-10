from pycardano import (HDWallet, Address, Network, ExtendedSigningKey, PaymentVerificationKey,
                        MultiAsset, ScriptHash, VerificationKeyHash)
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

    print(Address(spend_vk.hash(), stake_vk.hash(), network=Network.TESTNET).encode())
    print(spend_vk.hash())

    network = Network.TESTNET
    context = ChainQuery("YOUR_TOKEN_ID_HERE",
                        network,
                        base_url="https://cardano-preprod.blockfrost.io/api")

    oracle_addr = "addr_test1wpvzsfp3v02dqc7cu3gse36705w5llu80au9v8hpjlx6l5s5lz9h8"
    # oracle_script_hash = Address.from_primitive(oracle_addr).payment_part
    # oracle_v2_script=context._get_script(oracle_script_hash)

    node_nft = MultiAsset.from_primitive({"553db372db25c16975e95a0a7dec754dd697650b5bfe10e005699b15":
                    {b'NodeFeed': 1}})
    aggstate_nft = MultiAsset.from_primitive({"553db372db25c16975e95a0a7dec754dd697650b5bfe10e005699b15":
                    {b'AggState': 1}})
    oracle_nft = MultiAsset.from_primitive({"553db372db25c16975e95a0a7dec754dd697650b5bfe10e005699b15":
                    {b'OracleFeed': 1}})
    minting_nft_hash = ScriptHash.from_primitive("553db372db25c16975e95a0a7dec754dd697650b5bfe10e005699b15")

    oracle_owner = OracleOwner(network, context, extended_signing_key, spend_vk, node_nft, aggstate_nft
                    , oracle_nft ,minting_nft_hash, oracle_addr, stake_vk)
    agSettings=OracleSettings(osNodeList=[b'\xda(\x13\x13t\x9a\xf2\x03\xe2\xb1\x19\xdf\x16\x89U\x17G\r\xd2Hd7 Kf\xb8\x83f',
        b'\xed\x06\x9eV\xd4k\x12lJ\xaf\xcc\x19\x87\xf5\x06\x9b\xa6\x0b\x07p\xea\x85\x8e\x94\xac\x9a.\xc7',
        b'7\x08\x03\x14\xef\xdawS\xfaN\xf1\xf8\xa1\x9e\xc9\xb7\xe9#v\xd0gx\xe1\x8dEk\x94m',
        b'*\xedk|:\x8e\x9bP\xb34\xabN\xe5\xe5}1\x15\xfb\x93\x82\xc6\xc9\x02\xcbh[\xd5\xe5',
        b'\xbd\x95\xd5\x82\x88\x8a\xcd\xa5z %k\xb0>LJ\xbbk\xdf\t\xa4}x\x86\x05A,S'],
        osUpdatedNodes=5000, 
        osUpdatedNodeTime=600000, 
        osAggregateTime=600000, 
        osAggregateChange=2000, 
        osNodeFeePrice=NodeFee(getNodeFee=1500000), 
        osMadMultiplier=2000, 
        osDivergence=5000)
    # oracle_owner.add_nodes([VerificationKeyHash.from_primitive("bd95d582888acda57a20256bb03e4c4abb6bdf09a47d788605412c53")])
    # oracle_owner.add_nodes(["bd95d582888acda57a20256bb03e4c4abb6bdf09a47d788605412c53","1a550d5f572584e1add125b5712f709ac3b9828ad86581a4759022ba"])
    # oracle_owner.convert_datums_to_inlineable()
    # oracle_owner.create_reference_script()
    # oracle_owner.remove_nodes(["1a550d5f572584e1add125b5712f709ac3b9828ad86581a4759022ba"])
    oracle_owner.edit_settings(agSettings)


payment_address_24_base()