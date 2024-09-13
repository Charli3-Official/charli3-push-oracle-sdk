"""Start oracle by submitting a reference script and minting its NFT"""

from typing import List, Optional, Union

from pycardano import (
    Address,
    Asset,
    AssetName,
    ExtendedSigningKey,
    IndefiniteList,
    MultiAsset,
    Network,
    PaymentSigningKey,
    PaymentVerificationKey,
    PlutusV2Script,
    ScriptHash,
    Transaction,
    TransactionBuilder,
    TransactionOutput,
    Value,
    VerificationKeyHash,
    plutus_script_hash,
)

from charli3_offchain_core.chain_query import ChainQuery, StagedTxSubmitter
from charli3_offchain_core.datums import (
    AggDatum,
    AggState,
    NodeDatum,
    NodeState,
    Nothing,
    OracleDatum,
    OracleReward,
    OracleSettings,
    RewardDatum,
    RewardInfo,
)
from charli3_offchain_core.owner_script import OwnerScript


class OracleStart:
    """Start oracle by submitting a reference script and minting its NFT"""

    def __init__(
        self,
        network: Network,
        chain_query: ChainQuery,
        signing_key: Union[PaymentSigningKey, ExtendedSigningKey],
        verification_key: PaymentVerificationKey,
        oracle_script: PlutusV2Script,
        script_start_slot: int,
        settings: OracleSettings,
        c3_token_hash: ScriptHash,
        c3_token_name: AssetName,
        native_script_with_signers: bool = True,
        stake_key: Optional[PaymentVerificationKey] = None,
    ) -> None:
        self.network = network
        self.chain_query = chain_query
        self.staged_query = StagedTxSubmitter(
            chain_query.blockfrost_context,
            chain_query.ogmios_context,
            None,
        )
        self.context = self.chain_query.context
        self.signing_key = signing_key
        self.verification_key = verification_key
        self.pub_key_hash = self.verification_key.hash()
        self.stake_key = stake_key
        self.stake_key_hash = (
            self.stake_key.hash() if self.stake_key is not None else None
        )
        self.address = Address(
            payment_part=self.pub_key_hash,
            staking_part=self.stake_key_hash,
            network=self.network,
        )
        self.oracle_script = oracle_script
        self.oracle_script_hash = plutus_script_hash(self.oracle_script)
        self.oracle_address = Address(
            payment_part=self.oracle_script_hash, network=self.network
        )
        self.script_start_slot = script_start_slot
        self.oracle_settings = settings
        self.node_pkh_list = self.oracle_settings.os_node_list
        self.c3_token_hash = c3_token_hash
        self.c3_token_name = c3_token_name
        self.native_script_with_signers = native_script_with_signers
        # Create a locking script that hold oracle script and also mints oracle NFT
        if self.native_script_with_signers:
            oracle_owner = OwnerScript(
                self.chain_query,
                [
                    VerificationKeyHash.from_primitive(pkh)
                    for pkh in self.oracle_settings.os_platform.pmultisig_pkhs
                ],
                self.oracle_settings.os_platform.pmultisig_threshold,
            )
        else:
            oracle_owner = OwnerScript(self.chain_query, is_mock_script=True)
        self.oracle_owner = oracle_owner
        self.owner_script = oracle_owner.mk_owner_script(self.script_start_slot)
        self.owner_script_hash = self.owner_script.hash()

    async def mk_start_oracle_tx(
        self, platform_multisig_pkhs: List[str], initial_c3_amount: int
    ) -> Transaction:
        """Start oracle"""
        print(self.owner_script_hash)
        c3_asset = MultiAsset(
            {self.c3_token_hash: Asset({self.c3_token_name: initial_c3_amount})}
        )
        # Create a transaction builder
        builder = TransactionBuilder(self.context)

        # Required since owner script is InvalidBefore type
        builder.validity_start = self.script_start_slot

        ############ Reference script creation: ############
        owner_script_addr = Address(
            payment_part=self.owner_script_hash, network=self.network
        )

        print(f"Locking script address: {owner_script_addr}")
        print(f"Oracle script address: {self.oracle_address}")

        print(self.context.utxos(self.address))

        ############ Oracle NFT minting: ############
        oracle_nfts = MultiAsset.from_primitive(
            {
                self.owner_script_hash.payload: {
                    b"NodeFeed": len(
                        self.node_pkh_list
                    ),  # Negative sign indicates burning
                    b"AggState": 1,
                    b"OracleFeed": 1,
                    b"Reward": 1,
                }
            }
        )
        builder.mint = oracle_nfts
        single_node_nft = MultiAsset.from_primitive(
            {self.owner_script_hash.payload: {b"NodeFeed": 1}}
        )
        oracle_nft = MultiAsset.from_primitive(
            {self.owner_script_hash.payload: {b"OracleFeed": 1}}
        )
        aggstate_nft = MultiAsset.from_primitive(
            {self.owner_script_hash.payload: {b"AggState": 1}}
        )
        reward_nft = MultiAsset.from_primitive(
            {self.owner_script_hash.payload: {b"Reward": 1}}
        )
        # Set native script
        builder.native_scripts = [self.owner_script]

        node_reward_list = []
        # Prepare each datum
        for node in self.node_pkh_list:
            node_datum = NodeDatum(
                node_state=NodeState(ns_operator=node, ns_feed=Nothing())
            )
            node_reward_list.append(RewardInfo(reward_address=node, reward_amount=0))
            node_output = TransactionOutput(
                self.oracle_address,
                Value(2000000, single_node_nft),
                datum=node_datum,
            )
            builder.add_output(node_output)

        # Prepare oracle datum
        oracle_datum = OracleDatum(price_data=None)
        oracle_output = TransactionOutput(
            self.oracle_address,
            Value(2000000, oracle_nft),
            datum=oracle_datum,
        )
        builder.add_output(oracle_output)

        # Prepare aggstate datum
        self.oracle_settings.os_node_list = IndefiniteList(
            self.oracle_settings.os_node_list
        )
        aggstate_datum = AggDatum(aggstate=AggState(ag_settings=self.oracle_settings))
        aggstate_output = TransactionOutput(
            self.oracle_address,
            Value(3000000, aggstate_nft + c3_asset),
            datum=aggstate_datum,
        )
        builder.add_output(aggstate_output)

        # Prepare reward datum
        reward_datum = RewardDatum(
            reward_state=OracleReward(
                node_reward_list=node_reward_list,
                platform_reward=0,
            )
        )
        reward_output = TransactionOutput(
            self.oracle_address,
            Value(3000000, reward_nft),
            datum=reward_datum,
        )
        builder.add_output(reward_output)

        platform_multisig_vkhs = list(
            map(VerificationKeyHash.from_primitive, platform_multisig_pkhs)
        )
        builder.required_signers = platform_multisig_vkhs

        tx = await self.staged_query.build_tx(builder, self.signing_key, self.address)

        return tx
