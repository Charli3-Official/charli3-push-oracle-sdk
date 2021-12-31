from pycardano import PlutusData
from pycardano.serialization import IndefiniteList
from dataclasses import dataclass

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
class PriceMap():
    price_map: dict

@dataclass
class PriceData(PlutusData):
    CONSTR_ID= 2
    price_map: dict

@dataclass
class NodeState(PlutusData):
    CONSTR_ID = 0 
    nodeOperator: NodeInfo
    nodeFeed: PriceFeed       
    
@dataclass
class NodeDatum(PlutusData):
    CONSTR_ID= 1
    NodeDatum: NodeState

@dataclass
class OracleDatum(PlutusData):
    CONSTR_ID= 0
    oracleDatum: PriceData

@dataclass
class NodeFee(PlutusData):
    CONSTR_ID= 0
    getNodeFee : int

@dataclass
class OracleSettings(PlutusData):
    CONSTR_ID=0
    osNodeList        : IndefiniteList
    osUpdatedNodes    : int
    osUpdatedNodeTime : int
    osAggregateTime   : int
    osAggregateChange : int
    osNodeFeePrice    : NodeFee
    osMadMultiplier   : int
    osDivergence      : int

@dataclass
class AggState(PlutusData):
    CONSTR_ID=0
    agSettings: OracleSettings


@dataclass
class AggDatum(PlutusData):
    CONSTR_ID= 2
    aggDatum: AggState