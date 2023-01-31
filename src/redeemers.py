from dataclasses import dataclass
from pycardano import PlutusData

@dataclass
class NodeUpdate(PlutusData):
    CONSTR_ID = 0


@dataclass
class NodeCollect(PlutusData):
    CONSTR_ID = 1


@dataclass
class Aggregate(PlutusData):
    CONSTR_ID = 2


@dataclass
class UpdateAndAggregate(PlutusData):
    CONSTR_ID = 3
    pub_key_hash: bytes


@dataclass
class UpgradeOracle(PlutusData):
    CONSTR_ID = 4


@dataclass
class UpdateSettings(PlutusData):
    CONSTR_ID = 5


@dataclass
class OracleClose(PlutusData):
    CONSTR_ID = 6


@dataclass
class MintToken(PlutusData):
    CONSTR_ID = 0
