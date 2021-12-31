from pycardano import (BlockFrostChainContext, Network, Address, plutus_script_hash, PaymentVerificationKey, PaymentSigningKey,
                       Transaction, TransactionBuilder, PlutusData, Redeemer, ScriptHash)

addr = "addr_test1wzzejx35hv5epp4uyga8hm7upnxe9xdhjsfu4h6mh6jndpccke9y0"
pkh = Address.from_primitive(addr).payment_part
print(pkh)

network = Network.TESTNET
context = BlockFrostChainContext("YOUR_TOKEN_ID_HERE",
                                 network, 
                                 base_url="https://cardano-preprod.blockfrost.io/api")

script_hash = ScriptHash.from_primitive("acfb029ff8e79d1c7c86142954ef3225149a1322adbe06fda4599435")
print(type(script_hash),":",script_hash)
# plutus_script=context._get_script(script_hash)
# script_hash_v2=plutus_script_hash(plutus_script)
print(Address(script_hash, network=network))
