#import cbor2
import time
from pycardano import ( Network, Address, PaymentVerificationKey, PaymentSigningKey,
                       TransactionOutput, TransactionBuilder, Redeemer, RedeemerTag, MultiAsset
                       , ExecutionUnits)
from datums import *
from redeemers import *
from chain_query import ChainQuery

network = Network.TESTNET
context = ChainQuery("YOUR_TOKEN_ID_HERE",
                    network, 
                    base_url="https://cardano-preprod.blockfrost.io/api")

oracle_addr = "addr_test1wqnw0lcnqdg6gaxmrc787q75kjrd37skmnnlet3zeegnxlc3kcukz"
oracle_script_hash = Address.from_primitive(oracle_addr).payment_part
oracle_v2_script=context._get_script(oracle_script_hash)

# Code to generate new skey and vkey
# node_signing_key = PaymentSigningKey.generate()
# node_signing_key.save("node.skey")
# node_verification_key = PaymentVerificationKey.from_signing_key(node_signing_key)
# node_verification_key.save("node.vkey")

node_signing_key = PaymentSigningKey.load("node.skey")
node_verification_key = PaymentVerificationKey.load("node.vkey")
node_pub_key_hash = node_verification_key.hash()
node_address = Address(payment_part=node_pub_key_hash, network=network)

node_nft = MultiAsset.from_primitive({"e8567563996ac0e51a900dda39578c4174a8a63625669cbd47c846fa":{b'NodeFeed': 1}})

utxos = context.utxos(str(oracle_addr))
nodes_utxos = context.filter_utxos_by_asset(utxos,node_nft)
# nodes_datums = context.get_datums_for_utxo(nodes_utxos)
# print(nodes_utxos)
node_info = NodeInfo(bytes.fromhex(str(node_pub_key_hash)))
# node_own_datum_cbor = context.filter_node_datums_by_node_info(nodes_datums,node_info)
# node_own_datum =  NodeDatum.from_cbor(node_own_datum_cbor)
node_own_datum=   NodeDatum(nodeDatum=NodeState(nodeOperator=NodeInfo(niNodeOperator=b'7\x08\x03\x14\xef\xdawS\xfaN\xf1\xf8\xa1\x9e\xc9\xb7\xe9#v\xd0gx\xe1\x8dEk\x94m'), 
                    nodeFeed=PriceFeed(df=DataFeed(dfValue=323226, dfLastUpdate=1668826556820))))
node_own_datum_hash = node_own_datum.hash()
node_own_utxo = context.filter_utxos_by_datum_hash(nodes_utxos,node_own_datum_hash)[0]
# print(node_own_utxo)
# print(node_own_datum_hash)

time_ms = round(time.time_ns()*1e-6)
new_node_feed = PriceFeed(DataFeed(323226,time_ms))
new_node_datum = NodeDatum(nodeDatum=NodeState(nodeOperator=NodeInfo(niNodeOperator=b'7\x08\x03\x14\xef\xdawS\xfaN\xf1\xf8\xa1\x9e\xc9\xb7\xe9#v\xd0gx\xe1\x8dEk\x94m'), 
                    nodeFeed=PriceFeed(df=DataFeed(dfValue=323226, dfLastUpdate=1668826556820))))

new_node_datum.nodeDatum.nodeFeed = new_node_feed
new_node_datum_hash = new_node_datum.hash()

new_node_utxo_output = TransactionOutput(
    address=node_own_utxo.output.address,
    amount=node_own_utxo.output.amount,
    #datum_hash=new_node_datum_hash,
    datum= new_node_datum
)
print(new_node_datum_hash)
# print(node_own_datum)
node_update_redeemer = Redeemer(RedeemerTag.SPEND,NodeUpdate(),ExecutionUnits(1000000, 100000000))
# print(node_update_redeemer)
# print(new_node_utxo_output)

non_nft_utxo = context.find_collateral(node_address)
# print(non_nft_utxo)

if non_nft_utxo is None:
    context.create_collateral(node_address, node_signing_key)
    non_nft_utxo = context.find_collateral(node_address)

builder = TransactionBuilder(context)
(
    builder
    .add_script_input(node_own_utxo, oracle_v2_script, node_own_datum, node_update_redeemer)
    .add_output(new_node_utxo_output)
    .add_input_address(node_address)
)
builder.collaterals.append(non_nft_utxo)
builder.required_signers = [node_pub_key_hash]
signed_tx = builder.build_and_sign([node_signing_key], change_address=node_address)
context.submit_tx_with_print(signed_tx)