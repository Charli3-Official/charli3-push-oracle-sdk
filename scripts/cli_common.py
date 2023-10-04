from typing import List
import json
import cbor2
import click
from pycardano import Transaction, PlutusV2Script

# ANSI colors
COLOR_RED = "\033[0;31m"
COLOR_DEFAULT = "\033[39m"


def collect_multisig_pkhs() -> List[str]:
    platform_pkhs = []
    while True:
        pkh = click.prompt("Enter a platform pkh or 'q' to quit", default="q")
        if pkh == "q":
            break
        platform_pkhs.append(pkh)
    return platform_pkhs


def write_tx_to_file(filename: str, tx: Transaction) -> None:
    with open(filename, "w") as f:
        tx_hex = tx.to_cbor().hex()
        f.write(tx_hex)
        print(f"Tx written to file {filename}")


def read_tx_from_file(filename: str) -> Transaction:
    with open(filename, "r") as f:
        tx_hex = f.read()
        tx = Transaction.from_cbor(bytes.fromhex(tx_hex))
        return tx


def load_plutus_script(script_path) -> PlutusV2Script:
    """Parse and return a plutus v2 script from file path"""
    # Load the Plutus script file
    with open(script_path, "r") as f:
        plutus_data = json.load(f)
    # Get the "cborHex" from the Plutus script file
    script_hex = plutus_data.get("cborHex")

    # Convert the "cborHex" to PlutusScriptV2
    plutus_script = PlutusV2Script(cbor2.loads(bytes.fromhex(script_hex)))

    return plutus_script
