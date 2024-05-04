"""Oracle Owner contract transactions class"""

from copy import deepcopy
from typing import List, Literal, Optional, Tuple, Union

from pycardano import (
    Address,
    Asset,
    AssetName,
    ExtendedSigningKey,
    MultiAsset,
    NativeScript,
    Network,
    PaymentExtendedSigningKey,
    PaymentSigningKey,
    PaymentVerificationKey,
    PlutusV2Script,
    Redeemer,
    ScriptHash,
    Transaction,
    TransactionBuilder,
    TransactionInput,
    TransactionOutput,
    UTxO,
    Value,
    VerificationKeyHash,
    plutus_script_hash,
)

from charli3_offchain_core.chain_query import ChainQuery, StagedTxSubmitter
from charli3_offchain_core.datums import (
    AggDatum,
    NodeDatum,
    NodeState,
    Nothing,
    OracleDatum,
    OracleSettings,
    PriceData,
    RewardDatum,
    RewardInfo,
)
from charli3_offchain_core.oracle_checks import (
    check_node_exists,
    check_type,
    filter_utxos_by_asset,
    get_node_own_utxo,
)
from charli3_offchain_core.redeemers import (
    AddFunds,
    AddNodes,
    MintToken,
    OracleClose,
    PlatformCollect,
    RemoveNodes,
    UpdateSettings,
)
from charli3_offchain_core.utils.logging_config import logging

logger = logging.getLogger("Oracle-Owner")


class OracleOwner:
    """oracle owner transaction implementation"""

    def __init__(
        self,
        network: Network,
        chainquery: ChainQuery,
        signing_key: Union[
            ExtendedSigningKey, PaymentExtendedSigningKey, PaymentSigningKey
        ],
        verification_key: PaymentVerificationKey,
        node_nft: MultiAsset,
        aggstate_nft: MultiAsset,
        oracle_nft: MultiAsset,
        reward_nft: MultiAsset,
        minting_nft_hash: ScriptHash,
        c3_token_hash: ScriptHash,
        c3_token_name: AssetName,
        oracle_addr: str,
        stake_key: Optional[PaymentVerificationKey],
        reference_script_input: Optional[TransactionInput] = None,
        minting_script: Optional[NativeScript] = None,
        validity_start: Optional[int] = None,
    ) -> None:
        check_type(network, Network, "network")
        check_type(chainquery, ChainQuery, "chainquery")
        if not isinstance(
            signing_key,
            (PaymentExtendedSigningKey, ExtendedSigningKey, PaymentSigningKey),
        ):
            check_type(signing_key, PaymentExtendedSigningKey, "signing_key")
        check_type(verification_key, PaymentVerificationKey, "verification_key")
        check_type(node_nft, MultiAsset, "node_nft")
        check_type(aggstate_nft, MultiAsset, "aggstate_nft")
        check_type(oracle_nft, MultiAsset, "oracle_nft")
        check_type(reward_nft, MultiAsset, "reward_nft")
        check_type(minting_nft_hash, ScriptHash, "minting_nft_hash")
        check_type(c3_token_hash, ScriptHash, "c3_token_hash")
        check_type(c3_token_name, AssetName, "c3_token_name")
        check_type(oracle_addr, str, "oracle_addr")
        if stake_key is not None:
            check_type(stake_key, PaymentVerificationKey, "stake_key")
        if reference_script_input is not None:
            check_type(
                reference_script_input, TransactionInput, "reference_script_input"
            )
        if minting_script is not None:
            check_type(minting_script, NativeScript, "minting_script")
        if validity_start is not None:
            check_type(validity_start, int, "validity_start")
        self.network = network
        self.chainquery = chainquery
        self.staged_query = StagedTxSubmitter(
            chainquery.blockfrost_context, chainquery.ogmios_context
        )
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
        self.reward_nft = reward_nft
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
            self.chainquery.get_reference_script_utxo(
                self.oracle_addr, self.reference_script_input, self.oracle_script_hash
            )
            if self.reference_script_input
            else None
        )
        if minting_script:
            self.minting_script = minting_script
            self.validity_start = validity_start
        else:
            self.minting_script = None
            self.validity_start = None

    async def mk_add_nodes_tx(
        self, platform_multisig_pkhs: List[str], pkhs: List[str]
    ) -> Transaction:
        """Add nodes to oracle script."""
        pkhs = list(map(lambda x: bytes(VerificationKeyHash.from_primitive(x)), pkhs))
        eligible_nodes = self._get_eligible_nodes(pkhs, operation="add")

        if not eligible_nodes:
            logger.error("No eligible nodes to add.")
            return

        aggstate_utxo, aggstate_datum = self._get_aggstate_utxo_and_datum()
        reward_utxo, reward_datum = self._get_reward_utxo_and_datum()

        if len(eligible_nodes) > 0:
            updated_aggstate_datum = self._add_nodes_to_aggstate(
                aggstate_datum, eligible_nodes
            )
            updated_reward_datum = self._add_nodes_to_rewardstate(
                reward_datum, eligible_nodes
            )
            updated_reward_utxo_output = deepcopy(reward_utxo.output)
            updated_reward_utxo_output.datum = updated_reward_datum
            node_nfts = self._get_node_nfts("add", len(eligible_nodes))
            add_redeemer = Redeemer(AddNodes())

            builder = self._prepare_builder(
                aggstate_utxo,
                updated_aggstate_datum,
                node_nfts,
                reward_utxo=reward_utxo,
                updated_reward_utxo_output=updated_reward_utxo_output,
                redeemer=add_redeemer,
            )
            node_outputs = self._create_node_outputs(eligible_nodes)
            for node_output in node_outputs:
                builder.add_output(node_output)

            platform_multisig_vkhs = list(
                map(VerificationKeyHash.from_primitive, platform_multisig_pkhs)
            )
            builder.required_signers = platform_multisig_vkhs

            tx = await self.staged_query.build_tx(
                builder, self.signing_key, self.address
            )

            return tx

    async def mk_remove_nodes_tx(
        self, platform_multisig_pkhs: List[str], pkhs: List[str]
    ) -> Transaction:
        """Remove nodes from the oracle script."""
        pkhs = [bytes.fromhex(pkh) for pkh in pkhs]
        eligible_nodes = self._get_eligible_nodes(pkhs, operation="remove")

        if not eligible_nodes:
            logger.error("No eligible nodes to remove.")
            return

        aggstate_utxo, aggstate_datum = self._get_aggstate_utxo_and_datum()
        reward_utxo, reward_datum = self._get_reward_utxo_and_datum()

        if len(eligible_nodes) > 0:
            updated_aggstate_datum = self._remove_nodes_from_aggstate(
                aggstate_datum, eligible_nodes
            )
            (
                updated_reward_datum,
                remove_nodes_info,
                reward_amount_to_distribute,
            ) = self._remove_nodes_from_rewardstate(reward_datum, eligible_nodes)
            if reward_amount_to_distribute >= 0:
                updated_reward_utxo_output = deepcopy(reward_utxo.output)

                if reward_amount_to_distribute > 0:
                    c3_asset_to_distribute = MultiAsset(
                        {
                            self.c3_token_hash: Asset(
                                {self.c3_token_name: reward_amount_to_distribute}
                            )
                        }
                    )
                    updated_reward_utxo_output.amount.multi_asset -= (
                        c3_asset_to_distribute
                    )
                updated_reward_utxo_output.datum = updated_reward_datum
            else:
                updated_reward_utxo_output = deepcopy(reward_utxo.output)

            node_nfts = self._get_node_nfts("remove", len(eligible_nodes))
            remove_redeemer = Redeemer(RemoveNodes())
            builder = self._prepare_builder(
                aggstate_utxo=aggstate_utxo,
                updated_aggstate_datum=updated_aggstate_datum,
                mint_assets=node_nfts,
                reward_utxo=reward_utxo,
                updated_reward_utxo_output=updated_reward_utxo_output,
                redeemer=remove_redeemer,
            )
            # Handle removing node payouts from rewardstate
            for node in remove_nodes_info:
                if node.reward_amount > 0:
                    c3_asset = MultiAsset(
                        {
                            self.c3_token_hash: Asset(
                                {self.c3_token_name: node.reward_amount}
                            )
                        }
                    )
                    node_pkh = VerificationKeyHash(node.reward_address)
                    node_address = Address(payment_part=node_pkh, network=self.network)
                    builder.add_output(
                        TransactionOutput(
                            address=node_address,
                            amount=Value(2000000, c3_asset),
                        )
                    )
            self._burn_node_nfts(eligible_nodes, builder, remove_redeemer)

            platform_multisig_vkhs = list(
                map(VerificationKeyHash.from_primitive, platform_multisig_pkhs)
            )
            builder.required_signers = platform_multisig_vkhs

            tx = await self.staged_query.build_tx(
                builder, self.signing_key, self.address
            )

            return tx

    async def mk_edit_settings_tx(
        self, platform_multisig_pkhs: List[str], settings: OracleSettings
    ) -> Transaction:
        """edit settings of oracle script."""
        aggstate_utxo, aggstate_datum = self._get_aggstate_utxo_and_datum()

        if (
            settings != aggstate_datum.aggstate.ag_settings
            and settings.os_node_list
            == aggstate_datum.aggstate.ag_settings.os_node_list
        ):
            # prepare datums
            updated_aggstate_datum = self._update_aggstate(aggstate_datum, settings)

            # prepare builder
            builder = self._prepare_builder(
                aggstate_utxo=aggstate_utxo,
                updated_aggstate_datum=updated_aggstate_datum,
            )

            platform_multisig_vkhs = list(
                map(VerificationKeyHash.from_primitive, platform_multisig_pkhs)
            )
            builder.required_signers = platform_multisig_vkhs

            tx = await self.staged_query.build_tx(
                builder, self.signing_key, self.address
            )

            return tx
        else:
            logger.error("Settings not changed or modified osNodeList")

    def get_oracle_settings(self) -> OracleSettings:
        """get oracle settings from oracle script."""
        _, aggstate_datum = self._get_aggstate_utxo_and_datum()
        return aggstate_datum.aggstate.ag_settings

    async def add_funds(self, funds: int):
        """add funds (payment token) to aggstate UTxO of oracle script."""

        aggstate_utxo, _ = self._get_aggstate_utxo_and_datum()

        if funds > 0:
            # prepare datums, redeemers and new node utxos for eligible nodes
            add_funds_redeemer = Redeemer(AddFunds())

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

            await self.chainquery.submit_tx_builder(
                builder, self.signing_key, self.address
            )
        else:
            logger.error("Funds should be greater than 0.")

    async def mk_platform_collect_tx(
        self, platform_multisig_pkhs: List[str], withdrawal_addr: Address
    ) -> Transaction:
        """Collect oracle admin c3 rewards from oracle script."""

        reward_utxo, reward_datum = self._get_reward_utxo_and_datum()
        aggstate_utxo, _ = self._get_aggstate_utxo_and_datum()

        # check if platform reward is available
        if reward_datum.reward_state.platform_reward > 0:
            platform_reward = reward_datum.reward_state.platform_reward
            reward_datum.reward_state.platform_reward = 0

            # add platform reward to owner address
            c3_asset = MultiAsset(
                {self.c3_token_hash: Asset({self.c3_token_name: platform_reward})}
            )
            tx_output = deepcopy(reward_utxo.output)
            tx_output.amount.multi_asset -= c3_asset
            tx_output.datum = reward_datum

            # prepare builder
            platform_collect_redeemer = Redeemer(PlatformCollect())

            builder = TransactionBuilder(self.chainquery.context)
            builder.add_script_input(
                reward_utxo,
                script=self.script_utxo,
                redeemer=deepcopy(platform_collect_redeemer),
            ).add_output(tx_output).add_output(
                TransactionOutput(
                    address=withdrawal_addr,
                    amount=Value(2000000, c3_asset),
                )
            )

            # Reference AggState
            builder.reference_inputs.add(aggstate_utxo)

            platform_multisig_vkhs = list(
                map(VerificationKeyHash.from_primitive, platform_multisig_pkhs)
            )
            builder.required_signers = platform_multisig_vkhs

            tx = await self.staged_query.build_tx(
                builder, self.signing_key, self.address
            )

            return tx
        else:
            logger.error("No platform reward available to collect for owner.")

    async def mk_oracle_close_tx(
        self,
        platform_multisig_pkhs: List[str],
        withdrawal_addr: Address,
        disbursementChoice: Literal["TO_NODES", "TO_ONE_ADDRESS"],
    ) -> Transaction:
        """remove all oralce utxos from oracle script."""

        oracle_utxos = self.chainquery.context.utxos(self.oracle_addr)
        node_utxos: List[UTxO] = filter_utxos_by_asset(oracle_utxos, self.node_nft)

        oraclefeed_utxo: UTxO = filter_utxos_by_asset(oracle_utxos, self.oracle_nft)[0]
        aggstate_utxo: UTxO = filter_utxos_by_asset(oracle_utxos, self.aggstate_nft)[0]

        reward_utxo, reward_datum = self._get_reward_utxo_and_datum()

        if oraclefeed_utxo and aggstate_utxo and reward_utxo:
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
            builder.add_script_input(
                reward_utxo,
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
                        b"Reward": -1,
                    }
                }
            )

            if self.minting_script:
                builder.native_scripts = [self.minting_script]
                builder.validity_start = self.validity_start
            else:
                nft_minting_script = self.chainquery.get_plutus_script(self.nft_hash)
                builder.add_minting_script(
                    nft_minting_script, redeemer=Redeemer(MintToken())
                )

            builder.mint = oracle_nfts

            # finding node utxos for oracle_close
            for node in node_utxos:
                builder.add_script_input(
                    node,
                    script=self.script_utxo,
                    redeemer=deepcopy(oracle_close_redeemer),
                )

            def get_c3_amount(utxo):
                multi_asset = utxo.output.amount.multi_asset
                return multi_asset.get(self.c3_token_hash, {}).get(
                    self.c3_token_name, 0
                )

            if disbursementChoice == "TO_NODES":
                # Distribute unclaimed C3 tokens to each node operator
                for reward_info in reward_datum.reward_state.node_reward_list:
                    reward_pkh = VerificationKeyHash(reward_info.reward_address)

                    reward_node_address = Address(
                        payment_part=reward_pkh, network=self.network
                    )

                    c3_node_amount = reward_info.reward_amount

                    # Remove nodes with 0 rewards
                    if c3_node_amount > 0:
                        c3_asset = MultiAsset(
                            {
                                self.c3_token_hash: Asset(
                                    {self.c3_token_name: c3_node_amount}
                                )
                            }
                        )
                        builder.add_output(
                            TransactionOutput(
                                reward_node_address, Value(2000000, c3_asset)
                            )
                        )

                platform_reward = reward_datum.reward_state.platform_reward

                c3_undistributed_amount = (
                    get_c3_amount(aggstate_utxo)
                    + get_c3_amount(oraclefeed_utxo)
                    + platform_reward
                )
            else:
                c3_undistributed_amount = (
                    get_c3_amount(aggstate_utxo)
                    + get_c3_amount(reward_utxo)
                    + get_c3_amount(oraclefeed_utxo)
                )

            # C3 Asset
            c3_undistributed_asset = MultiAsset(
                {
                    self.c3_token_hash: Asset(
                        {self.c3_token_name: c3_undistributed_amount}
                    )
                }
            )
            # Create an output transaction for the undistributed C3 tokens
            output = TransactionOutput(
                address=withdrawal_addr, amount=Value(2000000, c3_undistributed_asset)
            )

            # Add the output to the transaction builder
            builder.add_output(output)

            platform_multisig_vkhs = list(
                map(VerificationKeyHash.from_primitive, platform_multisig_pkhs)
            )
            builder.required_signers = platform_multisig_vkhs

            tx = await self.staged_query.build_tx(
                builder, self.signing_key, self.address
            )

            return tx
        else:
            logger.error("oracle close error.")

    async def create_reference_script(self, oracle_script: PlutusV2Script = None):
        """build's partial reference script tx."""

        # The ADA amount required to cover the creation of the reference script.
        script_transaction_fee_amount = 64000000

        if not oracle_script:
            oracle_script = self.chainquery.get_plutus_script(self.oracle_script_hash)

        if plutus_script_hash(oracle_script) == self.oracle_script_hash:
            # Reference script output
            reference_script_utxo = TransactionOutput(
                address=self.oracle_addr,
                amount=script_transaction_fee_amount,
                script=oracle_script,
            )

            builder = TransactionBuilder(self.chainquery.context)

            # Add reference script
            builder.add_output(reference_script_utxo)

            await self.chainquery.submit_tx_builder(
                builder, self.signing_key, self.address
            )
        else:
            logger.error("script hash mismatch")

    async def initialize_oracle_datum(self):
        """initialise oracle datum"""
        oracle_utxos = self.chainquery.context.utxos(self.oracle_addr)
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

            await self.chainquery.submit_tx_builder(
                builder, self.signing_key, self.address
            )

    def _add_nodes_to_aggstate(
        self, aggstate_datum: AggDatum, nodes: List[bytes]
    ) -> AggDatum:
        """add nodes to aggstate datum"""
        aggstate_datum.aggstate.ag_settings.os_node_list.extend(nodes)
        return aggstate_datum

    def _add_nodes_to_rewardstate(
        self, rewardstate_datum: RewardDatum, nodes: List[bytes]
    ) -> RewardDatum:
        """add nodes to rewardstate datum"""
        node_reward_list: List[RewardInfo] = []
        for node in nodes:
            node_reward_list.append(RewardInfo(reward_address=node, reward_amount=0))

        rewardstate_datum.reward_state.node_reward_list.extend(node_reward_list)
        return rewardstate_datum

    def _remove_nodes_from_aggstate(
        self, aggstate_datum: AggDatum, nodes: List[bytes]
    ) -> AggDatum:
        """remove nodes to aggstate datum"""
        for node in nodes:
            if node in aggstate_datum.aggstate.ag_settings.os_node_list:
                aggstate_datum.aggstate.ag_settings.os_node_list.remove(node)

        return aggstate_datum

    def _remove_nodes_from_rewardstate(
        self, rewardstate_datum: RewardDatum, nodes: List[bytes]
    ) -> Tuple[RewardDatum, List[RewardInfo], int]:
        """remove nodes to rewardstate datum"""
        nodes_removed = []
        total_reward = 0
        for node in nodes:
            for node_reward in rewardstate_datum.reward_state.node_reward_list:
                if node_reward.reward_address == node:
                    rewardstate_datum.reward_state.node_reward_list.remove(node_reward)
                    nodes_removed.append(node_reward)
                    total_reward += node_reward.reward_amount
        # TODO: Handle removing nodes payouts from rewardstate
        return rewardstate_datum, nodes_removed, total_reward

    def _update_aggstate(
        self, aggstate_datum: AggDatum, settings: OracleSettings
    ) -> AggDatum:
        """update settings to aggstate datum"""
        aggstate_datum.aggstate.ag_settings = settings
        return aggstate_datum

    def _get_eligible_nodes(self, pkhs: List[bytes], operation: str) -> List[bytes]:
        """Get eligible nodes to add or remove."""
        eligible_nodes: List[bytes] = []
        _, aggstate_datum = self._get_aggstate_utxo_and_datum()
        node_list = aggstate_datum.aggstate.ag_settings.os_node_list

        for node in pkhs:
            node_exists = check_node_exists(node_list, node)
            if (operation == "add" and not node_exists) or (
                operation == "remove" and node_exists
            ):
                eligible_nodes.append(node)

        return eligible_nodes

    def _get_aggstate_utxo_and_datum(self) -> Tuple[UTxO, AggDatum]:
        """Get aggstate utxo and datum."""
        oracle_utxos = self.chainquery.context.utxos(self.oracle_addr)
        aggstate_utxo: UTxO = filter_utxos_by_asset(oracle_utxos, self.aggstate_nft)[0]
        aggstate_datum: AggDatum = AggDatum.from_cbor(aggstate_utxo.output.datum.cbor)
        return aggstate_utxo, aggstate_datum

    def _get_reward_utxo_and_datum(self) -> Tuple[UTxO, RewardDatum]:
        """Get reward utxo and datum."""
        oracle_utxos = self.chainquery.context.utxos(self.oracle_addr)
        rewardstate_utxo: UTxO = filter_utxos_by_asset(oracle_utxos, self.reward_nft)[0]
        rewardstate_datum: RewardDatum = RewardDatum.from_cbor(
            rewardstate_utxo.output.datum.cbor
        )
        return rewardstate_utxo, rewardstate_datum

    def _prepare_builder(
        self,
        aggstate_utxo: UTxO,
        updated_aggstate_datum: AggDatum,
        mint_assets: Optional[MultiAsset] = None,
        aggstate_tx_output: Optional[TransactionOutput] = None,
        reward_utxo: Optional[UTxO] = None,
        updated_reward_utxo_output: Optional[TransactionOutput] = None,
        redeemer: Optional[Redeemer] = None,
    ) -> TransactionBuilder:
        """Prepare transaction builder."""
        if not redeemer:
            redeemer = Redeemer(UpdateSettings())
        builder = TransactionBuilder(self.chainquery.context)
        builder.add_script_input(
            utxo=aggstate_utxo, script=self.script_utxo, redeemer=deepcopy(redeemer)
        )

        if not aggstate_tx_output:
            aggstate_tx_output = deepcopy(aggstate_utxo.output)
            aggstate_tx_output.datum = updated_aggstate_datum
        builder.add_output(aggstate_tx_output)

        if updated_reward_utxo_output and reward_utxo:
            # in case where reward datum is updated or value change
            builder.add_script_input(
                utxo=reward_utxo,
                script=self.script_utxo,
                redeemer=deepcopy(redeemer),
            )
            builder.add_output(updated_reward_utxo_output)

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
            nft_minting_script = self.chainquery.get_plutus_script(self.nft_hash)
            builder.add_minting_script(
                nft_minting_script, redeemer=Redeemer(MintToken())
            )

        builder.mint = mint_assets

    def _get_node_nfts(self, operation: str, eligible_nodes: int) -> MultiAsset:
        """Get node nfts in MultiAsset format."""
        node_nfts = MultiAsset.from_primitive(
            {
                self.nft_hash.payload: {
                    b"NodeFeed": (
                        eligible_nodes if operation == "add" else -eligible_nodes
                    )
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
                node_state=NodeState(ns_operator=node, ns_feed=Nothing())
            )
            node_output = TransactionOutput(
                self.oracle_addr,
                Value(2000000, self.single_node_nft),
                datum=node_datum,
            )
            node_outputs.append(node_output)
        return node_outputs

    def _burn_node_nfts(
        self,
        eligible_nodes: List[bytes],
        builder: TransactionBuilder,
        redeemer: Redeemer,
    ):
        oracle_utxos = self.chainquery.context.utxos(self.oracle_addr)

        for node in eligible_nodes:
            node_utxo = get_node_own_utxo(oracle_utxos, self.node_nft, node)
            builder.add_script_input(
                node_utxo, script=self.script_utxo, redeemer=deepcopy(redeemer)
            )
