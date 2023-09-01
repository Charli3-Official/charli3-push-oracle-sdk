"""Datums implementation"""
from dataclasses import dataclass, field
from typing import Union, List, Optional
from pycardano import PlutusData
from pycardano.serialization import IndefiniteList


@dataclass
class DataFeed(PlutusData):
    """represents Data Feed of Node State"""

    CONSTR_ID = 0
    df_value: int
    df_last_update: int


@dataclass
class PriceFeed(PlutusData):
    """represents Price Feed of Node State"""

    CONSTR_ID = 0
    df: DataFeed


@dataclass
class Nothing(PlutusData):
    """represents Nothing of Node State"""

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
    ns_operator: bytes
    ns_feed: Union[PriceFeed, Nothing]


@dataclass
class NodeDatum(PlutusData):
    """represents Node Datum"""

    CONSTR_ID = 1
    node_state: NodeState


@dataclass
class OracleDatum(PlutusData):
    """Oracle Datum"""

    CONSTR_ID = 0
    price_data: Optional[PriceData] = field(default=None, metadata={"optional": True})


@dataclass
class PriceRewards(PlutusData):
    """Node Fee parameters"""

    CONSTR_ID = 0
    node_fee: int
    aggregate_fee: int
    platform_fee: int


@dataclass
class OraclePlatform(PlutusData):
    """Oracle Platform parameters"""

    pmultisig_pkhs: IndefiniteList
    """ allowed pkhs for platform authorization :: [PubKeyHash] """
    pmultisig_threshold: int
    """ required number of signatories for authorization :: Integer """


@dataclass
class OracleSettings(PlutusData):
    """Oracle Settings parameters"""

    CONSTR_ID = 0
    os_node_list: IndefiniteList
    os_updated_nodes: int
    os_updated_node_time: int
    os_aggregate_time: int
    os_aggregate_change: int
    os_minimum_deposit: int
    os_node_fee_price: PriceRewards
    os_iqr_multiplier: int
    os_divergence: int
    os_platform: OraclePlatform

    def required_nodes_num(self, percent_resolution: int = 10000) -> int:
        """Number of nodes required"""
        n_nodes = len(self.os_node_list)
        return int(self.os_updated_nodes * n_nodes / percent_resolution)


@dataclass
class AggState(PlutusData):
    """Agg State parameters"""

    CONSTR_ID = 0
    ag_settings: OracleSettings


@dataclass
class AggDatum(PlutusData):
    """Agg Datum"""

    CONSTR_ID = 2
    aggstate: AggState


@dataclass
class InitialOracleDatum(PlutusData):
    """Initial Oracle Datum"""

    CONSTR_ID = 0


@dataclass
class RewardInfo(PlutusData):
    """Reward Info parameters"""

    CONSTR_ID = 0
    reward_address: bytes
    reward_amount: int


@dataclass
class OracleReward(PlutusData):
    """Oracle Reward parameters"""

    CONSTR_ID = 0
    node_reward_list: List[RewardInfo]
    platform_reward: int


@dataclass
class RewardDatum(PlutusData):
    """Oracle Reward Datum"""

    CONSTR_ID = 3
    reward_state: OracleReward
