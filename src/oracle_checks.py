"""Implementing Oracle checks and filters"""
from typing import List
from pycardano import UTxO, MultiAsset, DatumHash, IndefiniteList
from datums import NodeDatum, NodeInfo, NodeState, OracleDatum, AggDatum, AggState

def filter_utxos_by_asset(utxos:List[UTxO] , asset: MultiAsset):
    """filter list of UTxOs by given asset"""
    return list(filter(lambda x: x.output.amount.multi_asset >= asset, utxos))

def filter_utxos_by_datum_hash(utxos: List[UTxO], datum_hash: DatumHash):
    """filter list of UTxOs by given datum_hash"""
    result: List[UTxO] = []
    if len(utxos) > 0:
        for utxo in utxos:
            if utxo.output.datum_hash == datum_hash:
                result.append(utxo)
    return result


def filter_node_datums_by_node_info(node_datums: List[NodeDatum], node_info: NodeInfo):
    """filter node datums by node info"""
    if len(node_datums) > 0:
        for datum in node_datums:
            node_datum: NodeDatum= NodeDatum.from_cbor(datum)
            if node_datum.node_state.nodeOperator == node_info:
                return datum
    return None

def filter_node_utxos_by_node_info(utxos: List[UTxO], node_info:NodeInfo):
    """filter node UTxOs by node info"""
    if len(utxos) > 0:
        for utxo in utxos:
            if utxo.output.datum:
                node_datum: NodeDatum = NodeDatum.from_cbor(utxo.output.datum.cbor)
                if node_datum.node_state.nodeOperator == node_info:
                    return utxo
    return None

def check_node_exists(node_list: IndefiniteList, node: bytes) -> bool:
    """check if node is present in node_list"""
    return node in node_list

def get_node_own_utxo(oracle_utxos: List[UTxO], node_nft: MultiAsset, node_info:NodeInfo) -> UTxO:
    """returns node's own utxo from list of oracle UTxOs"""
    nodes_utxos = filter_utxos_by_asset(oracle_utxos, node_nft)
    return filter_node_utxos_by_node_info(nodes_utxos, node_info)
    