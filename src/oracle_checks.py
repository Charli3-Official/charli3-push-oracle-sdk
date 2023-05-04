"""Implementing Oracle checks and filters"""
from typing import List, Tuple
from pycardano import (
    UTxO,
    MultiAsset,
    DatumHash,
    IndefiniteList,
    ScriptHash,
    AssetName,
)
from src.datums import (
    NodeDatum,
    NodeInfo,
    NodeState,
    OracleDatum,
    AggDatum,
    AggState,
    PriceFeed,
    Nothing,
)


def filter_utxos_by_asset(utxos: List[UTxO], asset: MultiAsset) -> List[UTxO]:
    """Filter list of UTxOs by given asset type.

    Args:
        utxos: A list of UTxO objects to be filtered.
        asset: The asset type to filter by.

    Returns:
        A list of UTxO objects that match the specified asset type.
    """
    if utxos is None or not utxos:
        return []

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
            node_datum: NodeDatum = NodeDatum.from_cbor(datum)
            if node_datum.node_state.nodeOperator == node_info:
                return datum
    return None


def filter_node_utxos_by_node_info(utxos: List[UTxO], node_info: NodeInfo) -> UTxO:
    """Filter node UTxOs by node info.

    Args:
        utxos: The list of UTxOs to filter.
        node_info: The node info to use for filtering.

    Returns:
        The first UTxO that matches the given node info, or None if no match is found.
    """
    if utxos is None or not utxos:
        return None

    return next(
        (
            utxo
            for utxo in utxos
            if utxo.output.datum
            and NodeDatum.from_cbor(utxo.output.datum.cbor).node_state.nodeOperator
            == node_info
        ),
        None,
    )


def check_node_exists(node_list: IndefiniteList, node: bytes) -> bool:
    """Check if node is present in node_list.

    Args:
        node_list: The list of nodes to check.
        node: The node to search for in the list.

    Returns:
        True if the node is in the list, False otherwise.
    """
    if node_list is None or node is None:
        return False

    return node in node_list


def get_node_own_utxo(
    oracle_utxos: List[UTxO], node_nft: MultiAsset, node_info: NodeInfo
) -> UTxO:
    """returns node's own utxo from list of oracle UTxOs"""
    nodes_utxos = filter_utxos_by_asset(oracle_utxos, node_nft)
    return filter_node_utxos_by_node_info(nodes_utxos, node_info)


def check_utxo_asset_balance(
    input_utxo: UTxO,
    asset_policy_id: ScriptHash,
    token_name: AssetName,
    min_amount: int,
) -> bool:
    """Check if input UTxO has minimum asset balance.

    Args:
        input_utxo: The UTxO object to check.
        asset_policy_id: The asset policy ID to use.
        token_name: The token name to use.
        min_amount: The minimum amount required.

    Returns:
        True if the input UTxO has at least the minimum required balance, False otherwise.
    """
    if input_utxo.output.amount.multi_asset is None:
        return False

    if input_utxo.output.amount.multi_asset[asset_policy_id] is None:
        return False

    if input_utxo.output.amount.multi_asset[asset_policy_id][token_name] is None:
        return False

    # Check if input UTxO has at least the minimum required balance
    return (
        input_utxo.output.amount.multi_asset[asset_policy_id][token_name] >= min_amount
    )


def filter_valid_node_utxos(
    node_utxos: List[UTxO],
    current_timestamp: int,
    aggstate_datum: AggDatum,
    oracle_feed_datum: OracleDatum,
) -> List[UTxO]:
    """Filter node UTxOs by node expiry and after last aggregation.

    Args:
        node_utxos: A list of UTxO objects to be filtered.
        current_timestamp: The current timestamp.
        aggstate_datum: An AggDatum object.
        oracle_feed_datum: An OracleDatum object.

    Returns:
        A list of UTxO objects that are valid according to the specified criteria.
    """
    result: List[UTxO] = []
    node_expiry = aggstate_datum.aggstate.agSettings.os_updated_node_time

    if len(node_utxos) > 0:
        for utxo in node_utxos:
            if utxo.output.datum:
                node_datum: NodeDatum = NodeDatum.from_cbor(utxo.output.datum.cbor)

                if not isinstance(node_datum.node_state.nodeFeed, Nothing):
                    # nodes are initialized
                    if (
                        node_datum.node_state.nodeFeed.df.dfLastUpdate + node_expiry
                        > current_timestamp
                    ):
                        # nodes are not expired
                        print(oracle_feed_datum.price_data)
                        if oracle_feed_datum.price_data is not None:
                            # To DO: check if nodes are included in last aggregation
                            pass
                        else:
                            print(node_datum.node_state.nodeFeed.df.dfLastUpdate)
                            result.append(utxo)
    return result


def convert_cbor_to_node_datums(node_utxos: List[UTxO]) -> List[UTxO]:
    """
    Convert CBOR encoded NodeDatum objects to their corresponding Python objects.

    Parameters:
    - node_utxos (List[UTxO]): A list of UTxO objects that contain NodeDatum objects in CBOR
      encoding.

    Returns:
    - A list of UTxO objects that contain NodeDatum objects in their original Python format.
    """
    result: List[UTxO] = []

    if len(node_utxos) > 0:
        for utxo in node_utxos:
            if utxo.output.datum:
                node_datum: NodeDatum = NodeDatum.from_cbor(utxo.output.datum.cbor)
                utxo.output.datum = node_datum
                result.append(utxo)
    return result


def get_oracle_utxos_with_datums(
    oracle_utxos: List[UTxO],
    aggstate_nft: MultiAsset,
    oracle_nft: MultiAsset,
    node_nft: MultiAsset,
) -> Tuple[UTxO, UTxO, List[UTxO]]:
    """
    Given a list of UTxOs, filters them by asset and converts the data to the appropriate datum object.

    Parameters:
        - oracle_utxos (List[UTxO]): The list of UTxOs to filter and convert.
        - aggstate_nft (MultiAsset): The asset used to filter the UTxOs for the AggDatum object.
        - oracle_nft (MultiAsset): The asset used to filter the UTxOs for the OracleDatum object.
        - node_nft (MultiAsset): The asset used to filter the UTxOs for the NodeDatum objects.

    Returns:
        Tuple[UTxO, UTxO, List[UTxO]] : A tuple containing the filtered and converted UTxOs for the
        AggDatum, OracleDatum, and NodeDatum objects.
    """
    aggstate_utxo = next(
        (
            utxo
            for utxo in oracle_utxos
            if utxo.output.amount.multi_asset >= aggstate_nft
        ),
        None,
    )
    oraclefeed_utxo = next(
        (utxo for utxo in oracle_utxos if utxo.output.amount.multi_asset >= oracle_nft),
        None,
    )
    nodes_utxos = [
        utxo for utxo in oracle_utxos if utxo.output.amount.multi_asset >= node_nft
    ]
    node_utxos_with_datum = convert_cbor_to_node_datums(nodes_utxos)

    try:
        if aggstate_utxo.output.datum:
            aggstate_utxo.output.datum = AggDatum.from_cbor(
                aggstate_utxo.output.datum.cbor
            )
    except Exception:
        print("Invalid CBOR data for AggDatum")

    try:
        if oraclefeed_utxo.output.datum:
            oraclefeed_utxo.output.datum = OracleDatum.from_cbor(
                oraclefeed_utxo.output.datum.cbor
            )
    except Exception:
        print("Invalid CBOR data for OracleDatum")

    return (oraclefeed_utxo, aggstate_utxo, node_utxos_with_datum)
