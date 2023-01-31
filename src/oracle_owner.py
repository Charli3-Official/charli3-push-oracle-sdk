"""Oracle Owner contract transactions class"""
import time
from copy import deepcopy
from typing import List, Optional
import cbor2
from pycardano import (
    Network,
    Address,
    PaymentVerificationKey,
    Value,
    PlutusV2Script,
    AssetName,
    Asset,
    TransactionOutput,
    TransactionBuilder,
    Redeemer,
    RedeemerTag,
    plutus_script_hash,
    MultiAsset,
    UTxO,
    PaymentExtendedSigningKey,
    VerificationKeyHash,
    ScriptHash,
)
from pycardano.exception import InsufficientUTxOBalanceException, UTxOSelectionException
from datums import (
    NodeDatum,
    NodeInfo,
    AggDatum,
    OracleSettings,
    NodeState,
    Nothing,
    InitialOracleDatum,
)
from redeemers import Aggregate, UpdateSettings, MintToken, OracleClose
from chain_query import ChainQuery, ApiError
from oracle_checks import filter_utxos_by_asset, check_node_exists, get_node_own_utxo


class OracleOwner:
    """oracle owner transaction implementation"""

    def __init__(
        self,
        network: Network,
        context: ChainQuery,
        signing_key: PaymentExtendedSigningKey,
        verification_key: PaymentVerificationKey,
        node_nft: MultiAsset,
        aggstate_nft: MultiAsset,
        oracle_nft: MultiAsset,
        minting_nft_hash: ScriptHash,
        c3_token_hash: ScriptHash,
        c3_token_name: AssetName,
        oracle_addr: Address,
        stake_key: Optional[PaymentVerificationKey],
    ) -> None:
        self.network = network
        self.context = context
        self.signing_key = signing_key
        self.verification_key = verification_key
        self.pub_key_hash = self.verification_key.hash()
        self.stake_key = stake_key
        if self.stake_key:
            self.stake_key_hash = self.stake_key.hash()
        else:
            self.stake_key_hash = None
        self.address = Address(
            payment_part=self.pub_key_hash,
            staking_part=self.stake_key_hash,
            network=self.network,
        )
        self.node_nft = node_nft
        self.aggstate_nft = aggstate_nft
        self.oracle_nft = oracle_nft
        self.oracle_addr = Address.from_primitive(oracle_addr)
        self.oracle_script_hash = self.oracle_addr.payment_part
        self.nft_hash = minting_nft_hash
        self.c3_token_hash = c3_token_hash
        self.c3_token_name = c3_token_name
        self.single_node_nft = MultiAsset.from_primitive(
            {self.nft_hash.payload: {b"NodeFeed": 1}}
        )

    def add_nodes(self, pkhs: List[str]):
        """Add nodes to oracle script."""
        eligible_nodes: List[bytes] = []
        pkhs = list(map(lambda x: bytes(VerificationKeyHash.from_primitive(x)), pkhs))
        oracle_utxos = self.context.utxos(str(self.oracle_addr))
        aggstate_utxo: UTxO = filter_utxos_by_asset(oracle_utxos, self.aggstate_nft)[0]
        aggstate_datum: AggDatum = AggDatum.from_cbor(aggstate_utxo.output.datum.cbor)

        # check if node already exist in aggstate node list
        for node in pkhs:
            if not check_node_exists(
                aggstate_datum.aggstate.agSettings.os_node_list, node
            ):
                eligible_nodes.append(node)

        if len(eligible_nodes) > 0:
            # prepare datums, redeemers and new node utxos for eligible nodes
            add_nodes_redeemer = Redeemer(RedeemerTag.SPEND, UpdateSettings())
            updated_aggstate_datum = self._add_nodes_to_aggstate(
                aggstate_datum, eligible_nodes
            )

            builder = TransactionBuilder(self.context)
            builder.add_script_input(
                aggstate_utxo, redeemer=deepcopy(add_nodes_redeemer)
            )

            aggstate_tx_output = deepcopy(aggstate_utxo.output)
            aggstate_tx_output.datum = updated_aggstate_datum
            builder.add_output(aggstate_tx_output)

            nft_minting_script = self.get_plutus_script(self.nft_hash)

            node_nfts = MultiAsset.from_primitive(
                {
                    self.nft_hash.payload: {
                        b"NodeFeed": len(
                            eligible_nodes
                        ),  # Name & Quantity of node nft to mint
                    }
                }
            )

            builder.add_minting_script(
                nft_minting_script, redeemer=Redeemer(RedeemerTag.MINT, MintToken())
            )

            builder.mint = node_nfts

            # creating new node utxos for eligible new nodes with minting new node nfts
            for node in eligible_nodes:
                node_datum = NodeDatum(
                    node_state=NodeState(
                        nodeOperator=NodeInfo(node), nodeFeed=Nothing()
                    )
                )
                node_output = TransactionOutput(
                    self.oracle_addr,
                    Value(2000000, self.single_node_nft),
                    datum=node_datum,
                )
                builder.add_output(node_output)

            self.submit_tx_builder(builder)

        else:
            print("no eligible nodes to add.")

    def remove_nodes(self, pkhs: List[str]):
        """remove nodes from oracle script."""
        eligible_nodes: List[bytes] = []
        pkhs = list(map(lambda x: bytes(VerificationKeyHash.from_primitive(x)), pkhs))
        oracle_utxos = self.context.utxos(str(self.oracle_addr))
        aggstate_utxo: UTxO = filter_utxos_by_asset(oracle_utxos, self.aggstate_nft)[0]
        aggstate_datum: AggDatum = AggDatum.from_cbor(aggstate_utxo.output.datum.cbor)

        # check if node already exist in aggstate node list
        for node in pkhs:
            if check_node_exists(aggstate_datum.aggstate.agSettings.os_node_list, node):
                eligible_nodes.append(node)

        if len(eligible_nodes) > 0:
            # prepare datums, redeemers and new node utxos for eligible nodes
            remove_nodes_redeemer = Redeemer(RedeemerTag.SPEND, UpdateSettings())
            updated_aggstate_datum = self._remove_nodes_from_aggstate(
                aggstate_datum, eligible_nodes
            )

            builder = TransactionBuilder(self.context)
            builder.add_script_input(
                aggstate_utxo, redeemer=deepcopy(remove_nodes_redeemer)
            )

            aggstate_tx_output = deepcopy(aggstate_utxo.output)
            aggstate_tx_output.datum = updated_aggstate_datum
            builder.add_output(aggstate_tx_output)

            nft_minting_script = self.get_plutus_script(self.nft_hash)

            node_nfts = MultiAsset.from_primitive(
                {
                    self.nft_hash.payload: {
                        b"NodeFeed": -len(
                            eligible_nodes
                        ),  # Negative sign indicates burning
                    }
                }
            )

            builder.add_minting_script(
                nft_minting_script, redeemer=Redeemer(RedeemerTag.MINT, MintToken())
            )

            builder.mint = node_nfts

            # finding node utxos for eligible remove nodes with burning node nfts
            for node in eligible_nodes:
                node_info = NodeInfo(node)
                node_utxo = get_node_own_utxo(oracle_utxos, self.node_nft, node_info)
                builder.add_script_input(
                    node_utxo, redeemer=deepcopy(remove_nodes_redeemer)
                )

            self.submit_tx_builder(builder)

        else:
            print("no eligible nodes to remove.")

    def edit_settings(self, settings: OracleSettings):
        """edit settings of oracle script."""
        oracle_utxos = self.context.utxos(str(self.oracle_addr))
        aggstate_utxo: UTxO = filter_utxos_by_asset(oracle_utxos, self.aggstate_nft)[0]
        aggstate_datum: AggDatum = AggDatum.from_cbor(aggstate_utxo.output.datum.cbor)

        if (
            settings != aggstate_datum.aggstate.agSettings
            and settings.os_node_list == aggstate_datum.aggstate.agSettings.os_node_list
        ):

            # prepare datums, redeemers and new node utxos for eligible nodes
            edit_settings_redeemer = Redeemer(RedeemerTag.SPEND, UpdateSettings())
            updated_aggstate_datum = self._update_aggstate(aggstate_datum, settings)

            builder = TransactionBuilder(self.context)
            builder.add_script_input(
                aggstate_utxo, redeemer=deepcopy(edit_settings_redeemer)
            )

            aggstate_tx_output = deepcopy(aggstate_utxo.output)
            aggstate_tx_output.datum = updated_aggstate_datum
            builder.add_output(aggstate_tx_output)

            self.submit_tx_builder(builder)
        else:
            print("Settings not changed or modified osNodeList")

    def add_funds(self, funds: int):
        """add funds (payment token) to aggstate UTxO of oracle script."""

        try:
            oracle_utxos = self.context.utxos(str(self.oracle_addr))
            aggstate_utxo: UTxO = filter_utxos_by_asset(
                oracle_utxos, self.aggstate_nft
            )[0]

            if funds > 0:

                # prepare datums, redeemers and new node utxos for eligible nodes
                add_funds_redeemer = Redeemer(RedeemerTag.SPEND, UpdateSettings())

                builder = TransactionBuilder(self.context)
                builder.add_script_input(
                    aggstate_utxo, redeemer=deepcopy(add_funds_redeemer)
                )

                aggstate_tx_output = deepcopy(aggstate_utxo.output)
                aggstate_tx_output.amount.multi_asset[self.c3_token_hash][
                    self.c3_token_name
                ] += funds
                builder.add_output(aggstate_tx_output)

                self.submit_tx_builder(builder)

        except (InsufficientUTxOBalanceException, UTxOSelectionException) as exc:
            print("Insufficient Funds in Owner wallet.", exc)

    def oracle_close(self):
        """remove all oralce utxos from oracle script."""

        oracle_utxos = self.context.utxos(str(self.oracle_addr))
        aggstate_utxo: UTxO = filter_utxos_by_asset(oracle_utxos, self.aggstate_nft)[0]
        oraclefeed_utxo: UTxO = filter_utxos_by_asset(oracle_utxos, self.oracle_nft)[0]

        node_utxos: List[UTxO] = filter_utxos_by_asset(oracle_utxos, self.node_nft)

        if oraclefeed_utxo and aggstate_utxo:
            # prepare datums, redeemers and new node utxos for eligible nodes
            oracle_close_redeemer = Redeemer(RedeemerTag.SPEND, OracleClose())

            builder = TransactionBuilder(self.context)
            builder.add_script_input(
                aggstate_utxo, redeemer=deepcopy(oracle_close_redeemer)
            )
            builder.add_script_input(
                oraclefeed_utxo, redeemer=deepcopy(oracle_close_redeemer)
            )

            nft_minting_script = self.get_plutus_script(self.nft_hash)

            oracle_nfts = MultiAsset.from_primitive(
                {
                    self.nft_hash.payload: {
                        b"NodeFeed": -len(
                            node_utxos
                        ),  # Negative sign indicates burning
                        b"AggState": -1,
                        b"OracleFeed": -1,
                    }
                }
            )

            builder.add_minting_script(
                nft_minting_script, redeemer=Redeemer(RedeemerTag.MINT, MintToken())
            )

            builder.mint = oracle_nfts

            # finding node utxos for oracle_close
            # TO DO :: transfer c3 tokens to respective node operator address
            for node in node_utxos:
                builder.add_script_input(node, redeemer=deepcopy(oracle_close_redeemer))

            self.submit_tx_builder(builder)

        else:
            print("oracle close error.")

    def create_reference_script(self):
        """build's partial reference script tx."""

        oracle_script = self.get_plutus_script(self.oracle_script_hash)

        if plutus_script_hash(oracle_script) == self.oracle_script_hash:
            reference_script_utxo_output = TransactionOutput(
                address=self.oracle_addr, amount=20000000, script=oracle_script
            )

            builder = TransactionBuilder(self.context)

            (
                builder.add_output(reference_script_utxo_output).add_input_address(
                    self.address
                )
            )

            self.submit_tx_builder(builder)
        else:
            print("script hash mismatch")

    def convert_datums_to_inlineable(self):
        """convert all oracle utxos to Inlineable"""
        oracle_utxos = self.context.utxos(str(self.oracle_addr))

        aggregate_redeemer = Redeemer(RedeemerTag.SPEND, Aggregate())
        builder = TransactionBuilder(self.context)

        aggstate_utxo: UTxO = filter_utxos_by_asset(oracle_utxos, self.aggstate_nft)[0]

        if aggstate_utxo.output.datum_hash:
            aggstate_datum: AggDatum = AggDatum.from_cbor(
                self.context._get_datum(aggstate_utxo)
            )

            agg_state_utxo_output = TransactionOutput(
                address=aggstate_utxo.output.address,
                amount=aggstate_utxo.output.amount + 1000000,
                datum=aggstate_datum,
            )

            builder.add_script_input(
                aggstate_utxo,
                redeemer=deepcopy(aggregate_redeemer),
                datum=aggstate_datum,
            )
            builder.add_output(agg_state_utxo_output)

        oraclefeed_utxo: UTxO = filter_utxos_by_asset(oracle_utxos, self.oracle_nft)[0]

        if oraclefeed_utxo.output.datum_hash:
            oraclefeed_datum: InitialOracleDatum = InitialOracleDatum.from_cbor(
                self.context._get_datum(oraclefeed_utxo)
            )

            oraclefeed_utxo_output = TransactionOutput(
                address=oraclefeed_utxo.output.address,
                amount=oraclefeed_utxo.output.amount,
                datum=oraclefeed_datum,
            )

            builder.add_script_input(
                oraclefeed_utxo,
                redeemer=deepcopy(aggregate_redeemer),
                datum=oraclefeed_datum,
            )
            builder.add_output(oraclefeed_utxo_output)

        nodes_utxos: List[UTxO] = filter_utxos_by_asset(oracle_utxos, self.node_nft)
        node_utxos_with_datum: List[UTxO] = self.context.get_node_datums_with_utxo(
            nodes_utxos
        )

        for utxo in node_utxos_with_datum:
            builder.add_script_input(
                utxo, redeemer=deepcopy(aggregate_redeemer), datum=utxo.output.datum
            )
            tx_output = deepcopy(utxo.output)
            tx_output.datum_hash = None
            builder.add_output(tx_output)

        self.submit_tx_builder(builder)

    def submit_tx_builder(self, builder: TransactionBuilder):
        """adds collateral and signers to tx , sign and submit tx."""
        # abstracting common inputs here.
        builder.add_input_address(self.address)
        builder.add_output(TransactionOutput(self.address, 5000000))

        try:
            non_nft_utxo = self.context.find_collateral(self.address)

            if non_nft_utxo is None:
                self.context.create_collateral(self.address, self.signing_key)
                non_nft_utxo = self.context.find_collateral(self.address)

            if non_nft_utxo is not None:
                builder.collaterals.append(non_nft_utxo)
                builder.required_signers = [self.pub_key_hash]

                signed_tx = builder.build_and_sign(
                    [self.signing_key], change_address=self.address
                )
                self.context.submit_tx_with_print(signed_tx)
            else:
                print("collateral utxo is None.")

        except ApiError as err:
            if err.status_code == 404:
                print("No utxos found at the node address, fund the wallet.")

    def _add_nodes_to_aggstate(
        self, aggstate_datum: AggDatum, nodes: List[bytes]
    ) -> AggDatum:
        """add nodes to aggstate datum"""
        aggstate_datum.aggstate.agSettings.os_node_list.extend(nodes)
        return aggstate_datum

    def _remove_nodes_from_aggstate(
        self, aggstate_datum: AggDatum, nodes: List[bytes]
    ) -> AggDatum:
        """remove nodes to aggstate datum"""
        for node in nodes:
            if node in aggstate_datum.aggstate.agSettings.os_node_list:
                aggstate_datum.aggstate.agSettings.os_node_list.remove(node)

        return aggstate_datum

    def _update_aggstate(
        self, aggstate_datum: AggDatum, settings: OracleSettings
    ) -> AggDatum:
        """update settings to aggstate datum"""
        aggstate_datum.aggstate.agSettings = settings
        return aggstate_datum

    def get_plutus_script(self, scripthash: ScriptHash) -> PlutusV2Script:
        """function to get plutus script and verify it's script hash"""
        plutus_script = self.context._get_script(str(scripthash))
        if plutus_script_hash(plutus_script) != scripthash:
            plutus_script = PlutusV2Script(cbor2.dumps(plutus_script))
        if plutus_script_hash(plutus_script) == scripthash:
            return plutus_script
        else:
            print("script hash mismatch")
