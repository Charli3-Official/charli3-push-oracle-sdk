""" This module contains the ChainQuery class, which is used to query the blockchain."""
import logging
import asyncio

from typing import List
from retry import retry
from pycardano import (
    BlockFrostChainContext,
    OgmiosChainContext,
    TransactionBuilder,
    TransactionOutput,
    Transaction,
    UTxO,
)
from blockfrost import ApiError
from src.datums import NodeDatum

logger = logging.getLogger("ChainQuery")


class ChainQuery:
    """Class to query the blockchain."""

    def __init__(
        self,
        blockfrost_context: BlockFrostChainContext = None,
        ogmios_context: OgmiosChainContext = None,
        oracle_address: str = None,
    ):
        if blockfrost_context is None and ogmios_context is None:
            raise ValueError("At least one of the chain contexts must be provided.")

        self.blockfrost_context = blockfrost_context
        self.ogmios_context = ogmios_context
        self.oracle_address = oracle_address
        self.context = blockfrost_context if blockfrost_context else ogmios_context

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

    async def wait_for_tx(self, tx_id):
        """method to wait for a transaction to be included in the blockchain."""

        async def _wait_for_tx(context, tx_id, check_fn):
            """Wait for a transaction to be confirmed."""
            while True:
                response = await check_fn(context, tx_id)
                if response:
                    logger.info("Transaction submitted with tx_id: %s", str(tx_id))
                    return response
                else:
                    await asyncio.sleep(5)  # sleep for 5 seconds before checking again

        async def check_blockfrost(context, tx_id):
            return context.api.transaction(tx_id)

        async def check_ogmios(context, tx_id):
            response = context._query_utxos_by_tx_id(tx_id, 0)
            return response if response != [] else None

        if self.ogmios_context:
            return await _wait_for_tx(self.ogmios_context, tx_id, check_ogmios)
        elif self.blockfrost_context:
            return await _wait_for_tx(self.blockfrost_context, tx_id, check_blockfrost)

    async def submit_tx_with_print(self, tx: Transaction):
        logger.info("Submitting transaction: %s", str(tx.id))
        logger.debug("tx: %s", tx)

        if self.ogmios_context is not None:
            logger.info("Submitting tx with ogmios")
            self.ogmios_context.submit_tx(tx.to_cbor())
        elif self.blockfrost_context is not None:
            logger.info("Submitting tx with blockfrost")
            self.blockfrost_context.submit_tx(tx.to_cbor())

        await self.wait_for_tx(str(tx.id))

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

    async def create_collateral(self, target_address, skey):
        """create collateral utxo"""
        print("creating collateral UTxO.")
        collateral_builder = TransactionBuilder(self.context)

        collateral_builder.add_input_address(target_address)
        collateral_builder.add_output(TransactionOutput(target_address, 5000000))

        await self.submit_tx_with_print(
            collateral_builder.build_and_sign([skey], target_address)
        )
