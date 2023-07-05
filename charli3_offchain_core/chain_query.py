""" This module contains the ChainQuery class, which is used to query the blockchain."""
from typing import List
from retry import retry
from pycardano import (
    BlockFrostChainContext,
    TransactionBuilder,
    TransactionOutput,
    Transaction,
    UTxO,
)
from blockfrost import ApiError
from charli3_offchain_core.datums import NodeDatum


class ChainQuery:
    """Class to query the blockchain."""

    def __init__(self, project_id: str, base_url: str = None):
        self.context = BlockFrostChainContext(project_id=project_id, base_url=base_url)

    def _get_datum(self, utxo):
        """get datum for UTxO"""
        if utxo.output.datum_hash is not None:
            datum = self.context.api.script_datum_cbor(str(utxo.output.datum_hash)).cbor
            return datum
        return None

    def get_datums_for_utxo(self, utxos):
        """insert datum for UTxOs"""
        result = []
        if len(utxos) > 0:
            for utxo in utxos:
                datum = self._get_datum(utxo)
                result.append(datum)
        return result

    def get_node_datums_with_utxo(self, utxos: List[UTxO]) -> List[UTxO]:
        """insert datum for UTxOs"""
        result: List[UTxO] = []
        if len(utxos) > 0:
            for utxo in utxos:
                if utxo.output.amount.multi_asset:
                    datum = self._get_datum(utxo)
                    if datum:
                        utxo.output.datum = NodeDatum.from_cbor(datum)
                    result.append(utxo)
        return result

    @retry(
        delay=10,
        tries=10,
    )
    def wait_for_tx(self, tx_id):
        """method to wait for a transaction to be included in the blockchain."""
        self.context.api.transaction(tx_id)
        print(f"Transaction {tx_id} has been successfully included in the blockchain.")

    def submit_tx_with_print(self, tx: Transaction):
        """method to submit a transaction and print the result."""
        print("############### Transaction created ###############")
        print(tx)
        serialized_tx = tx.to_cbor()
        tx_size = len(serialized_tx) / 1024
        print(f"Transaction size: {tx_size:.2f} KB")
        print("############### Submitting transaction ###############")
        response = self.context.submit_tx(tx)
        print(f"Transaction response: {response}")
        self.wait_for_tx(str(tx.id))

    def find_collateral(self, target_address):
        """method to find collateral utxo."""
        try:
            for utxo in self.context.utxos(target_address):
                # A collateral should contain no multi asset
                if not utxo.output.amount.multi_asset:
                    if utxo.output.amount < 10000000:
                        if utxo.output.amount.coin >= 5000000:
                            return utxo
        except ApiError as err:
            if err.status_code == 404:
                print("No utxos found")
                raise err
            else:
                print(
                    "Requirements for collateral couldn't be satisfied. need an utxo of >= 5000000\
                    and < 10000000, %s",
                    err,
                )
        return None

    def create_collateral(self, target_address, skey):
        """create collateral utxo"""
        print("creating collateral UTxO.")
        collateral_builder = TransactionBuilder(self.context)

        collateral_builder.add_input_address(target_address)
        collateral_builder.add_output(TransactionOutput(target_address, 5000000))

        self.submit_tx_with_print(
            collateral_builder.build_and_sign([skey], target_address)
        )
