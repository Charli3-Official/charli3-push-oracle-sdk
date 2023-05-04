"""Oracle Owner contract transactions class"""
from copy import deepcopy
from typing import List, Optional, Tuple
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
    plutus_script_hash,
    MultiAsset,
    UTxO,
    PaymentExtendedSigningKey,
    VerificationKeyHash,
    ScriptHash,
    NativeScript,
    TransactionInput,
)
from pycardano.exception import InsufficientUTxOBalanceException, UTxOSelectionException
from src.datums import (
    NodeDatum,
    NodeInfo,
    AggDatum,
    OracleSettings,
    NodeState,
    Nothing,
    InitialOracleDatum,
    OracleDatum,
    PriceData,
)
from src.redeemers import Aggregate, UpdateSettings, MintToken, OracleClose
from src.chain_query import ChainQuery
from src.oracle_checks import (
    filter_utxos_by_asset,
    check_node_exists,
    get_node_own_utxo,
)
from src.utils.exceptions import CollateralException


class OracleOwner:
    """oracle owner transaction implementation"""

    def __init__(
        self,
        network: Network,
        chainquery: ChainQuery,
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
        reference_script_input: Optional[TransactionInput] = None,
        minting_script: Optional[NativeScript] = None,
        validity_start: Optional[int] = None,
    ) -> None:
        self.network = network
        self.chainquery = chainquery
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
        self.reference_script_input = reference_script_input
        self.script_utxo = (
            self.get_reference_script_utxo() if self.reference_script_input else None
        )
        if minting_script:
            self.minting_script = minting_script
            self.validity_start = validity_start
        else:
            self.minting_script = None
            self.validity_start = None

    def add_nodes(self, pkhs: List[str]):
        """Add nodes to oracle script."""
        pkhs = list(map(lambda x: bytes(VerificationKeyHash.from_primitive(x)), pkhs))
        eligible_nodes = self._get_eligible_nodes(pkhs, operation="add")

        if not eligible_nodes:
            print("No eligible nodes to add.")
            return

        aggstate_utxo, aggstate_datum = self._get_aggstate_utxo_and_datum()
        if len(eligible_nodes) > 0:
            updated_aggstate_datum = self._add_nodes_to_aggstate(
                aggstate_datum, eligible_nodes
            )
            node_nfts = self._get_node_nfts("add", len(eligible_nodes))
            builder = self._prepare_builder(
                aggstate_utxo, updated_aggstate_datum, node_nfts
            )
            node_outputs = self._create_node_outputs(eligible_nodes)
            for node_output in node_outputs:
                builder.add_output(node_output)

            self.submit_tx_builder(builder)

    def remove_nodes(self, pkhs: List[str]):
        """Remove nodes from the oracle script."""
        pkhs = [bytes.fromhex(pkh) for pkh in pkhs]
        eligible_nodes = self._get_eligible_nodes(pkhs, operation="remove")

        if not eligible_nodes:
            print("No eligible nodes to remove.")
            return

        aggstate_utxo, aggstate_datum = self._get_aggstate_utxo_and_datum()
        if len(eligible_nodes) > 0:
            updated_aggstate_datum = self._remove_nodes_from_aggstate(
                aggstate_datum, eligible_nodes
            )
            node_nfts = self._get_node_nfts("remove", len(eligible_nodes))
            builder = self._prepare_builder(
                aggstate_utxo, updated_aggstate_datum, node_nfts
            )
            self._burn_node_nfts(eligible_nodes, builder)

            self.submit_tx_builder(builder)

    def edit_settings(self, settings: OracleSettings):
        """edit settings of oracle script."""
        aggstate_utxo, aggstate_datum = self._get_aggstate_utxo_and_datum()

        if (
            settings != aggstate_datum.aggstate.agSettings
            and settings.os_node_list == aggstate_datum.aggstate.agSettings.os_node_list
        ):
            # prepare datums
            updated_aggstate_datum = self._update_aggstate(aggstate_datum, settings)
            # prepare builder
            builder = self._prepare_builder(aggstate_utxo, updated_aggstate_datum, None)

            self.submit_tx_builder(builder)
        else:
            print("Settings not changed or modified osNodeList")

    def add_funds(self, funds: int):
        """add funds (payment token) to aggstate UTxO of oracle script."""

        try:
            aggstate_utxo, _ = self._get_aggstate_utxo_and_datum()
            if funds > 0:
                # prepare datums, redeemers and new node utxos for eligible nodes
                add_funds_redeemer = Redeemer(UpdateSettings())

                builder = TransactionBuilder(self.chainquery.context)
                builder.add_script_input(
                    aggstate_utxo,
                    script=self.script_utxo,
                    redeemer=deepcopy(add_funds_redeemer),
                )

                aggstate_tx_output = deepcopy(aggstate_utxo.output)

                # check if c3 token already exist in aggstate utxo
                if (
                    self.c3_token_hash in aggstate_tx_output.amount.multi_asset
                    and self.c3_token_name
                    in aggstate_tx_output.amount.multi_asset[self.c3_token_hash]
                ):
                    aggstate_tx_output.amount.multi_asset[self.c3_token_hash][
                        self.c3_token_name
                    ] += funds
                else:
                    c3_asset = MultiAsset(
                        {self.c3_token_hash: Asset({self.c3_token_name: funds})}
                    )
                    aggstate_tx_output.amount.multi_asset += c3_asset
                builder.add_output(aggstate_tx_output)

                self.submit_tx_builder(builder)

        except (InsufficientUTxOBalanceException, UTxOSelectionException) as exc:
            print("Insufficient Funds in Owner wallet.", exc)

    def oracle_close(self):
        """remove all oralce utxos from oracle script."""

        oracle_utxos = self.chainquery.context.utxos(str(self.oracle_addr))
        aggstate_utxo: UTxO = filter_utxos_by_asset(oracle_utxos, self.aggstate_nft)[0]
        oraclefeed_utxo: UTxO = filter_utxos_by_asset(oracle_utxos, self.oracle_nft)[0]

        node_utxos: List[UTxO] = filter_utxos_by_asset(oracle_utxos, self.node_nft)

        if oraclefeed_utxo and aggstate_utxo:
            # prepare datums, redeemers and new node utxos for eligible nodes
            oracle_close_redeemer = Redeemer(OracleClose())

            builder = TransactionBuilder(self.chainquery.context)
            builder.add_script_input(
                aggstate_utxo,
                script=self.script_utxo,
                redeemer=deepcopy(oracle_close_redeemer),
            )
            builder.add_script_input(
                oraclefeed_utxo,
                script=self.script_utxo,
                redeemer=deepcopy(oracle_close_redeemer),
            )

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

            if self.minting_script:
                builder.native_scripts = [self.minting_script]
                builder.validity_start = self.validity_start
            else:
                nft_minting_script = self.get_plutus_script(self.nft_hash)
                builder.add_minting_script(
                    nft_minting_script, redeemer=Redeemer(MintToken())
                )

            builder.mint = oracle_nfts

            # finding node utxos for oracle_close
            # TO DO :: transfer c3 tokens to respective node operator address
            for node in node_utxos:
                builder.add_script_input(
                    node,
                    script=self.script_utxo,
                    redeemer=deepcopy(oracle_close_redeemer),
                )

            self.submit_tx_builder(builder)

        else:
            print("oracle close error.")

    def create_reference_script(self):
        """build's partial reference script tx."""

        oracle_script = self.get_plutus_script(self.oracle_script_hash)

        if plutus_script_hash(oracle_script) == self.oracle_script_hash:
            reference_script_utxo_output = TransactionOutput(
                address=self.oracle_addr, amount=58568590, script=oracle_script
            )

            builder = TransactionBuilder(self.chainquery.context)

            (builder.add_output(reference_script_utxo_output))

            self.submit_tx_builder(builder)
        else:
            print("script hash mismatch")

    def convert_datums_to_inlineable(self):
        """convert all oracle utxos to Inlineable"""
        oracle_utxos = self.chainquery.context.utxos(str(self.oracle_addr))

        aggregate_redeemer = Redeemer(Aggregate())
        builder = TransactionBuilder(self.chainquery.context)

        aggstate_utxo: UTxO = filter_utxos_by_asset(oracle_utxos, self.aggstate_nft)[0]

        if aggstate_utxo.output.datum_hash:
            aggstate_datum: AggDatum = AggDatum.from_cbor(
                self.chainquery._get_datum(aggstate_utxo)
            )

            agg_state_utxo_output = TransactionOutput(
                address=aggstate_utxo.output.address,
                amount=aggstate_utxo.output.amount + 1000000,
                datum=aggstate_datum,
            )

            builder.add_script_input(
                aggstate_utxo,
                script=self.script_utxo,
                redeemer=deepcopy(aggregate_redeemer),
                datum=aggstate_datum,
            )
            builder.add_output(agg_state_utxo_output)

        oraclefeed_utxo: UTxO = filter_utxos_by_asset(oracle_utxos, self.oracle_nft)[0]

        if oraclefeed_utxo.output.datum_hash:
            oraclefeed_datum: InitialOracleDatum = InitialOracleDatum.from_cbor(
                self.chainquery._get_datum(oraclefeed_utxo)
            )

            oraclefeed_utxo_output = TransactionOutput(
                address=oraclefeed_utxo.output.address,
                amount=oraclefeed_utxo.output.amount,
                datum=oraclefeed_datum,
            )

            builder.add_script_input(
                oraclefeed_utxo,
                script=self.script_utxo,
                redeemer=deepcopy(aggregate_redeemer),
                datum=oraclefeed_datum,
            )
            builder.add_output(oraclefeed_utxo_output)

        nodes_utxos: List[UTxO] = filter_utxos_by_asset(oracle_utxos, self.node_nft)
        node_utxos_with_datum: List[UTxO] = self.chainquery.get_node_datums_with_utxo(
            nodes_utxos
        )

        for utxo in node_utxos_with_datum:
            builder.add_script_input(
                utxo,
                script=self.script_utxo,
                redeemer=deepcopy(aggregate_redeemer),
                datum=utxo.output.datum,
            )
            tx_output = deepcopy(utxo.output)
            tx_output.datum_hash = None
            builder.add_output(tx_output)

        self.submit_tx_builder(builder)

    def initialize_oracle_datum(self):
        """initialise oracle datum"""
        oracle_utxos = self.chainquery.context.utxos(str(self.oracle_addr))
        oraclefeed_utxo: UTxO = filter_utxos_by_asset(oracle_utxos, self.oracle_nft)[0]
        oraclefeed_datum: OracleDatum = OracleDatum.from_cbor(
            oraclefeed_utxo.output.datum.cbor
        )

        if oraclefeed_datum.price_data is None:
            edit_settings_redeemer = Redeemer(UpdateSettings())
            builder = TransactionBuilder(self.chainquery.context)
            builder.add_script_input(
                oraclefeed_utxo,
                script=self.script_utxo,
                redeemer=edit_settings_redeemer,
            )

            oraclefeed_output = deepcopy(oraclefeed_utxo.output)
            oraclefeed_output.datum = OracleDatum(
                price_data=PriceData.set_price_map(price=0, timestamp=0, expiry=0)
            )
            builder.add_output(oraclefeed_output)

            self.submit_tx_builder(builder)

    def _process_common_inputs(self, builder: TransactionBuilder):
        builder.add_input_address(self.address)
        builder.add_output(TransactionOutput(self.address, 5000000))

        non_nft_utxo = self._get_or_create_collateral()

        if non_nft_utxo is not None:
            builder.collaterals.append(non_nft_utxo)
            builder.required_signers = [self.pub_key_hash]

            return builder
        else:
            raise CollateralException("Unable to find or create collateral.")

    def _get_or_create_collateral(self):
        non_nft_utxo = self.chainquery.find_collateral(self.address)

        if non_nft_utxo is None:
            self.chainquery.create_collateral(self.address, self.signing_key)
            non_nft_utxo = self.chainquery.find_collateral(self.address)

        return non_nft_utxo

    def submit_tx_builder(self, builder: TransactionBuilder):
        """adds collateral and signers to tx, sign and submit tx."""
        builder = self._process_common_inputs(builder)
        signed_tx = builder.build_and_sign(
            [self.signing_key], change_address=self.address
        )

        try:
            self.chainquery.submit_tx_with_print(signed_tx)
            print("Transaction submitted successfully.")
        except CollateralException as err:
            print("Error submitting transaction: ", err)
        except Exception as err:
            print("Error submitting transaction: ", err)

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

    def _get_eligible_nodes(self, pkhs: List[bytes], operation: str) -> List[bytes]:
        """Get eligible nodes to add or remove."""
        eligible_nodes: List[bytes] = []
        _, aggstate_datum = self._get_aggstate_utxo_and_datum()
        node_list = aggstate_datum.aggstate.agSettings.os_node_list

        for node in pkhs:
            node_exists = check_node_exists(node_list, node)
            if (operation == "add" and not node_exists) or (
                operation == "remove" and node_exists
            ):
                eligible_nodes.append(node)

        return eligible_nodes

    def _get_aggstate_utxo_and_datum(self) -> Tuple[UTxO, AggDatum]:
        """Get aggstate utxo and datum."""
        oracle_utxos = self.chainquery.context.utxos(str(self.oracle_addr))
        aggstate_utxo: UTxO = filter_utxos_by_asset(oracle_utxos, self.aggstate_nft)[0]
        aggstate_datum: AggDatum = AggDatum.from_cbor(aggstate_utxo.output.datum.cbor)
        return aggstate_utxo, aggstate_datum

    def _prepare_builder(
        self,
        aggstate_utxo: UTxO,
        updated_aggstate_datum: AggDatum,
        mint_assets: Optional[MultiAsset] = None,
        aggstate_tx_output: Optional[TransactionOutput] = None,
    ) -> TransactionBuilder:
        """Prepare transaction builder."""
        redeemer = Redeemer(UpdateSettings())

        builder = TransactionBuilder(self.chainquery.context)
        builder.add_script_input(
            utxo=aggstate_utxo, script=self.script_utxo, redeemer=deepcopy(redeemer)
        )

        if not aggstate_tx_output:
            aggstate_tx_output = deepcopy(aggstate_utxo.output)
            aggstate_tx_output.datum = updated_aggstate_datum
        builder.add_output(aggstate_tx_output)

        if mint_assets:
            self._handle_minting(builder, mint_assets)

        return builder

    def _handle_minting(
        self, builder: TransactionBuilder, mint_assets: MultiAsset
    ) -> None:
        """Handle minting by adding minting script and minting assets to builder."""
        if self.minting_script:
            builder.native_scripts = [self.minting_script]
            builder.validity_start = self.validity_start
        else:
            nft_minting_script = self.get_plutus_script(self.nft_hash)
            builder.add_minting_script(
                nft_minting_script, redeemer=Redeemer(MintToken())
            )

        builder.mint = mint_assets

    def _get_node_nfts(self, operation: str, eligible_nodes: int) -> MultiAsset:
        """Get node nfts in MultiAsset format."""
        node_nfts = MultiAsset.from_primitive(
            {
                self.nft_hash.payload: {
                    b"NodeFeed": eligible_nodes
                    if operation == "add"
                    else -eligible_nodes
                }
            }
        )
        return node_nfts

    def _create_node_outputs(
        self, eligible_nodes: List[bytes]
    ) -> List[TransactionOutput]:
        """Create node outputs and return them as a list."""
        node_outputs = []
        for node in eligible_nodes:
            node_datum = NodeDatum(
                node_state=NodeState(nodeOperator=NodeInfo(node), nodeFeed=Nothing())
            )
            node_output = TransactionOutput(
                self.oracle_addr,
                Value(2000000, self.single_node_nft),
                datum=node_datum,
            )
            node_outputs.append(node_output)
        return node_outputs

    def _burn_node_nfts(self, eligible_nodes: List[bytes], builder: TransactionBuilder):
        redeemer = Redeemer(UpdateSettings())
        oracle_utxos = self.chainquery.context.utxos(str(self.oracle_addr))

        for node in eligible_nodes:
            node_info = NodeInfo(node)
            node_utxo = get_node_own_utxo(oracle_utxos, self.node_nft, node_info)
            print(node_utxo, type(node_info))
            builder.add_script_input(
                node_utxo, script=self.script_utxo, redeemer=deepcopy(redeemer)
            )

    def get_plutus_script(self, scripthash: ScriptHash) -> PlutusV2Script:
        """function to get plutus script and verify it's script hash"""
        plutus_script = self.chainquery.context._get_script(str(scripthash))
        if plutus_script_hash(plutus_script) != scripthash:
            plutus_script = PlutusV2Script(cbor2.dumps(plutus_script))
        if plutus_script_hash(plutus_script) == scripthash:
            return plutus_script
        else:
            print("script hash mismatch")

    def get_reference_script_utxo(self) -> UTxO:
        """function to get reference script utxo"""
        utxos = self.chainquery.context.utxos(str(self.oracle_addr))
        if len(utxos) > 0:
            for utxo in utxos:
                if utxo.input == self.reference_script_input:
                    script = self.get_plutus_script(self.oracle_script_hash)
                    utxo.output.script = script
                    return utxo
