""" Conditions for calculating aggregation."""
from typing import Tuple, List
from pycardano import IndefiniteList, UTxO
from src.datums import (
    OracleSettings,
    PriceFeed,
    PriceData,
    DataFeed,
    OracleDatum,
    NodeDatum,
    Nothing,
)
from src.consensus import aggregation

factor_resolution: int = 10000


def check_oracle_settings(oset: OracleSettings) -> bool:
    """Check if an OracleSettings value is valid."""
    return (
        check_valid_node_list(oset.os_node_list)
        and check_valid_percentage(oset.os_updated_nodes)
        and check_valid_percentage(oset.os_aggregate_change)
        and check_positive(oset.os_updated_node_time)
        and check_positive(oset.os_aggregate_time)
        and check_positive(oset.os_node_fee_price)
        and check_positive(oset.os_mad_multiplier)
        and check_positive(oset.os_divergence)
    )


def check_valid_node_list(node_list: IndefiniteList) -> bool:
    """Check if the list of nodes has no repetitions."""
    return len(node_list) == len(set(node_list))


def check_valid_percentage(percentage: int) -> bool:
    """Check if a percentage is between 0 and factor_resolution."""
    return 0 <= percentage <= factor_resolution


def check_positive(value: int) -> bool:
    """Check if a value is greater than 0."""
    return value > 0


def check_feed_last_update(
    upd_node_time: int, ofeed: OracleDatum, curr_time: int, node_feed: NodeDatum
) -> bool:
    """
    Check if the last update of a data feed succeeded after the last aggregation and
    it's inside the node time expiry window.
    """
    if not isinstance(node_feed.node_state.nodeFeed, Nothing):
        dfeed = node_feed.node_state.nodeFeed.df
        if (ofeed.price_data is None) or (
            dfeed.dfLastUpdate > ofeed.price_data.get_timestamp()
        ):
            node_update_range = (dfeed.dfLastUpdate, dfeed.dfLastUpdate + upd_node_time)

            if node_update_range[0] <= curr_time <= node_update_range[1]:
                return True
            else:
                print("Old node feed")
                return False
        else:
            print("Old aggregated feed")
            return False


def check_agg_time(oset: OracleSettings, ofeed: OracleDatum, curr_time: int) -> bool:
    """
    Check that a time interval is not contained in the aggregate time window.

    :param os: OracleSettings object
    :param ofeed: OracleFeed object
    :param curr_time: current time to check
    :return: True if the time range is valid, False otherwise
    """
    # check if the last aggregated feed exists
    if ofeed.price_data is not None:
        last_agg_feed_time = ofeed.price_data.get_timestamp()
        # check if aggregated time window is expired or not.
        if last_agg_feed_time + oset.os_aggregate_time > curr_time > last_agg_feed_time:
            print("Aggregation time not expired.")
            return False
    return True


def check_agg_change(oset: OracleSettings, ofeed: OracleDatum, new_agg: int) -> bool:
    """
    Check that the new aggregated value (calculated from a list
    of price feeds) changed by a value greater or equal
    than the specified threshold.

    :param os: OracleSettings object
    :param ofeed: OracleDatum object
    :param new_agg: new aggregation value
    :return: True if the change is valid, False otherwise
    """
    if not ofeed.price_data:
        return True
    else:
        old_agg = ofeed.price_data.get_price()
        updated_percentage = (abs(new_agg - old_agg) * factor_resolution) // old_agg
        if updated_percentage >= oset.os_aggregate_change:
            return True
        else:
            print(
                "New aggregation feed didn't change more than the specified threshold."
            )
            return False


def check_aggregator_permission(oset: OracleSettings, pkh: bytes) -> bool:
    """
    Check whether given public key has permission for aggregation.
    :param oset: OracleSettings object
    :param pkh: public key
    :return: True if permission is valid else False
    """
    if oset.os_node_list is None:
        print("os_node_list should not be None.")
        return False
    elif pkh not in oset.os_node_list:
        print("PublicKey has no aggregator permission.")
        return False
    else:
        return True


def check_aggregation_update_time(
    oset: OracleSettings, ofeed: OracleDatum, curr_time: int, new_agg: int
) -> bool:
    """
    Check if the aggregate conditions time change or value change are met.
    """
    if check_agg_time(oset, ofeed, curr_time) or check_agg_change(oset, ofeed, new_agg):
        return True
    else:
        print(
            "Aggregate value conditions don't hold:\n- Time Oracle feed not old",
            "Oracle feed didn't change enough",
        )
        return False


def check_node_updates_condition(
    oset: OracleSettings, ofeed: OracleDatum, curr_time: int, nodes: List[UTxO]
) -> List[UTxO]:
    """This function checks the valid nodes percentage and also filter out the valid nodes."""
    # check if the number of nodes is sufficient to update the feed

    updated_nodes: List[UTxO] = []
    for node in nodes:
        if check_feed_last_update(
            oset.os_updated_node_time, ofeed, curr_time, node.output.datum
        ):
            updated_nodes.append(node)

    updated_percentage = (len(updated_nodes) * factor_resolution) // len(
        oset.os_node_list
    )
    if updated_percentage < oset.os_updated_nodes:
        return []
    else:
        # filter the list of nodes using check_feed_last_update method
        return updated_nodes


def check_node_consensus_condition(
    oset: OracleSettings, nodes: List[UTxO]
) -> Tuple[List[UTxO], int]:
    """
    Filter out the valid nodes based on consensus value.

    Parameters:
    - oset (OracleSettings): OracleSettings object that contains the consensus parameters.
    - nodes (List[UTxO]): A list of UTxO objects representing the nodes.

    Returns:
    - A tuple of
    * A list of UTxO objects representing the valid nodes based on consensus value.
    * The aggregated feed value.
    """
    updated_nodes_value = [
        node.output.datum.node_state.nodeFeed.df.dfValue for node in nodes
    ]
    agg_value, _, lower, upper = aggregation(
        oset.os_mad_multiplier, oset.os_divergence, updated_nodes_value
    )
    print(updated_nodes_value, lower, upper)
    valid_nodes = [
        node
        for node in nodes
        if lower <= node.output.datum.node_state.nodeFeed.df.dfValue <= upper
    ]

    return valid_nodes, agg_value


def aggregation_conditions(
    oset: OracleSettings,
    ofeed: OracleDatum,
    pkh: bytes,
    curr_time: int,
    nodes: List[UTxO],
) -> Tuple[List[UTxO], int]:
    """main function to check different aggregation conditions and also to calculate aggregation."""
    if check_aggregator_permission(oset, pkh):
        valid_nodes = check_node_updates_condition(oset, ofeed, curr_time, nodes)
        if len(valid_nodes) > 0:
            valid_nodes_with_consensus, agg_value = check_node_consensus_condition(
                oset, valid_nodes
            )

            if check_aggregation_update_time(oset, ofeed, curr_time, agg_value):
                return (valid_nodes_with_consensus, agg_value)

            else:
                print(
                    "The aggregation is not being performed within the specified time window"
                )
                return [], 0
        else:
            print("Lower percentage of nodes to do the aggregation")
            return [], 0
    else:
        print(
            "The specified public key hash does not have permission to perform an aggregation"
        )
        return [], 0
