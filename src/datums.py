"""Datums implementation"""
from dataclasses import dataclass, field
from typing import Union
from pycardano import PlutusData
from pycardano.serialization import IndefiniteList


@dataclass
class NodeInfo(PlutusData):
    CONSTR_ID = 0
    niNodeOperator: bytes


@dataclass
class DataFeed(PlutusData):
    CONSTR_ID = 0
    dfValue: int
    dfLastUpdate: int


@dataclass
class PriceFeed(PlutusData):
    CONSTR_ID = 0
    df: DataFeed


@dataclass
class Nothing(PlutusData):
    CONSTR_ID = 1


@dataclass
class PriceData(PlutusData):
    """represents cip oracle datum PriceMap(Tag +2)"""

    CONSTR_ID = 2
    price_map: dict

    def get_price(self) -> int:
        """get price from price map"""
        return self.price_map[0]

    def get_timestamp(self) -> int:
        """get timestamp of the feed"""
        return self.price_map[1]

    def get_expiry(self) -> int:
        """get expiry of the feed"""
        return self.price_map[2]

    @classmethod
    def set_price_map(cls, price: int, timestamp: int, expiry: int):
        """set price_map"""
        price_map = {0: price, 1: timestamp, 2: expiry}
        return cls(price_map)


@dataclass
class NodeState(PlutusData):
    """represents Node State of Node Datum"""

    CONSTR_ID = 0
    nodeOperator: NodeInfo
    nodeFeed: Union[PriceFeed, Nothing]


@dataclass
class NodeDatum(PlutusData):
    """represents Node Datum"""

    CONSTR_ID = 1
    node_state: NodeState


@dataclass
class OracleDatum(PlutusData):
    CONSTR_ID = 0
    price_data: PriceData = field(default=None, metadata={"optional": True})


@dataclass
class NodeFee(PlutusData):
    CONSTR_ID = 0
    getNodeFee: int


@dataclass
class OracleSettings(PlutusData):
    """Oracle Settings parameters"""

    CONSTR_ID = 0
    os_node_list: IndefiniteList
    os_updated_nodes: int
    os_updated_node_time: int
    os_aggregate_time: int
    os_aggregate_change: int
    os_node_fee_price: NodeFee
    os_mad_multiplier: int
    os_divergence: int

    def required_nodes_num(self, percent_resolution: int = 10000) -> int:
        """Number of nodes required"""
        n_nodes = len(self.os_node_list)
        return int(self.os_updated_nodes * n_nodes / percent_resolution)


@dataclass
class AggState(PlutusData):
    CONSTR_ID = 0
    agSettings: OracleSettings


@dataclass
class AggDatum(PlutusData):
    CONSTR_ID = 2
    aggstate: AggState


@dataclass
class InitialOracleDatum(PlutusData):
    CONSTR_ID = 0
