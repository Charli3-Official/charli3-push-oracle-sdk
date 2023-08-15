"""Redeemers for the Plutus Smart Contracts"""

from dataclasses import dataclass
from pycardano import PlutusData


@dataclass
class NodeUpdate(PlutusData):
    """Node Update Redeemer"""

    CONSTR_ID = 0


@dataclass
class NodeCollect(PlutusData):
    """Node Collect Redeemer"""

    CONSTR_ID = 1


@dataclass
class PlatformCollect(PlutusData):
    """Platform Collect Redeemer"""

    CONSTR_ID = 2


@dataclass
class Aggregate(PlutusData):
    """Aggregate Redeemer"""

    CONSTR_ID = 3


@dataclass
class UpdateSettings(PlutusData):
    """Update Settings Redeemer"""

    CONSTR_ID = 4


@dataclass
class AddNodes(PlutusData):
    """Add nodes Redeemer"""

    CONSTR_ID = 5


@dataclass
class RemoveNodes(PlutusData):
    """Remove nodes Redeemer"""

    CONSTR_ID = 6


@dataclass
class OracleClose(PlutusData):
    """Oracle Close Redeemer"""

    CONSTR_ID = 7


@dataclass
class AddFunds(PlutusData):
    """Top up contract redeemer"""

    CONSTR_ID = 8


@dataclass
class MintToken(PlutusData):
    """Mint Token Redeemer"""

    CONSTR_ID = 0
