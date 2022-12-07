import cbor2
import time
from pycardano import ( Network, Address, PaymentVerificationKey, PaymentSigningKey,
                       TransactionOutput, TransactionBuilder, Redeemer, RedeemerTag, MultiAsset
                       , ExecutionUnits, PlutusV2Script)
from datums import *
from redeemers import *
from chain_query import ChainQuery
from node import Node
from mint import Mint

network = Network.TESTNET
context = ChainQuery("YOUR_TOKEN_ID_HERE",
                    network,
                    base_url="https://cardano-preprod.blockfrost.io/api")

oracle_addr = Address.from_primitive("addr_test1wpvzsfp3v02dqc7cu3gse36705w5llu80au9v8hpjlx6l5s5lz9h8")
oracle_script_hash = oracle_addr.payment_part
# oracle_v2_script=context._get_script(oracle_script_hash)

# Code to generate new skey and vkey
# node_signing_key = PaymentSigningKey.generate()
# node_signing_key.save("oracle-owner.skey")
# node_verification_key = PaymentVerificationKey.from_signing_key(node_signing_key)
# node_verification_key.save("oracle-owner.vkey")

node_signing_key = PaymentSigningKey.load("node.skey")
node_verification_key = PaymentVerificationKey.load("node.vkey")
node_pub_key_hash = node_verification_key.hash()
node_address = Address(payment_part=node_pub_key_hash, network=network)
print(node_pub_key_hash)
print(node_address)
# with open("./mint_script.plutus", "r") as f:
#             script_hex = f.read()
#             plutus_script_v2 = PlutusV2Script(cbor2.loads(bytes.fromhex(script_hex)))
node_nft = MultiAsset.from_primitive({"553db372db25c16975e95a0a7dec754dd697650b5bfe10e005699b15":
                    {b'NodeFeed': 1}})

# aggstate_nft = MultiAsset.from_primitive({"e8567563996ac0e51a900dda39578c4174a8a63625669cbd47c846fa":
#                     {b'AggState': 1}})

# oracle_nft = MultiAsset.from_primitive({"e8567563996ac0e51a900dda39578c4174a8a63625669cbd47c846fa":
#                     {b'OracleFeed': 1}})
node = Node(network, context, node_signing_key, node_verification_key, node_nft, oracle_addr)
node.create_reference_script()
# node.update(304204)
# c3_token = Mint(network, context, node_signing_key, node_verification_key, plutus_script_v2)
# c3_token.mint_nft_with_script()
# utxos = context.utxos(str(oracle_addr))
# oracle_utxo = context.filter_utxos_by_asset(utxos, oracle_nft)
# print(oracle_utxo)
# oracle_datum  = OracleDatum.from_cbor("d8799fd87b9fa3021b000001837ba4b397011b000001837b9b8bd70001ffff")
# print(oracle_datum)
# new_oracle_datum = OracleDatum(PriceData.set_price_map(1,1664226134999,1664226734999))
# print(new_oracle_datum)
# nodes_utxos = context.filter_utxos_by_asset(utxos,node_nft)
# # nodes_datums = context.get_datums_for_utxo(nodes_utxos)
# # print(nodes_utxos)
# node_info = NodeInfo(bytes.fromhex(str(node_pub_key_hash)))
# node_own_datum_cbor = context.filter_node_datums_by_node_info(nodes_datums,node_info)
# node_own_datum =  NodeDatum.from_cbor(node_own_datum_cbor)
# node_own_datum=   NodeDatum(nodeDatum=NodeState(nodeOperator=NodeInfo(niNodeOperator=b'7\x08\x03\x14\xef\xdawS\xfaN\xf1\xf8\xa1\x9e\xc9\xb7\xe9#v\xd0gx\xe1\x8dEk\x94m'), 
#                     nodeFeed=PriceFeed(df=DataFeed(dfValue=323226, dfLastUpdate=1668826556820))))
# node_own_datum_hash = node_own_datum.hash()
# node_own_utxo = context.filter_utxos_by_datum_hash(nodes_utxos,node_own_datum_hash)[0]
# node_own_utxo = context.filter_node_utxos_by_node_info(nodes_utxos,node_info)
# print(node_own_utxo)
# node_own_datum =  NodeDatum.from_cbor(node_own_utxo.output.datum.cbor)
# print(node_own_datum)

# time_ms = round(time.time_ns()*1e-6)
# new_node_feed = PriceFeed(DataFeed(308900,time_ms))
# new_node_datum = NodeDatum.from_cbor(node_own_utxo.output.datum.cbor)

# new_node_datum.nodeDatum.nodeFeed = new_node_feed
# # new_node_datum_hash = new_node_datum.hash()

# new_node_utxo_output = TransactionOutput(
#     address=node_own_utxo.output.address,
#     amount=node_own_utxo.output.amount,
#     #datum_hash=new_node_datum_hash,
#     datum= new_node_datum
# )
# # print(new_node_datum_hash)
# # print(node_own_datum)
# node_update_redeemer = Redeemer(RedeemerTag.SPEND,NodeUpdate(),ExecutionUnits(1000000, 80000000))
# # print(node_update_redeemer)
# # print(new_node_utxo_output)

# non_nft_utxo = context.find_collateral(node_address)
# # print(non_nft_utxo)

# if non_nft_utxo is None:
#     context.create_collateral(node_address, node_signing_key)
#     non_nft_utxo = context.find_collateral(node_address)

# builder = TransactionBuilder(context)
# (
#     builder
#     .add_script_input(node_own_utxo, redeemer=node_update_redeemer)
#     .add_output(new_node_utxo_output)
#     .add_input_address(node_address)
# )
# builder.collaterals.append(non_nft_utxo)
# builder.required_signers = [node_pub_key_hash]
# signed_tx = builder.build_and_sign([node_signing_key], change_address=node_address)
# context.submit_tx_with_print(signed_tx)