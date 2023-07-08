"""Start oracle by submitting a reference script and minting its NFT"""
from typing import Optional, Union
from pycardano import (
    Network,
    Address,
    PaymentVerificationKey,
    PaymentExtendedSigningKey,
    ExtendedSigningKey,
    PaymentSigningKey,
    TransactionOutput,
    TransactionBuilder,
    Value,
    MultiAsset,
    PlutusV2Script,
    plutus_script_hash,
    ScriptHash,
    AssetName,
    Asset,
    IndefiniteList,
)
from src.datums import (
    NodeDatum,
    OracleDatum,
    AggDatum,
    NodeState,
    OracleSettings,
    AggState,
    Nothing,
    RewardDatum,
    OracleReward,
    RewardInfo,
)
from src.chain_query import ChainQuery
from src.owner_script import OwnerScript


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
        stake_key: Optional[PaymentVerificationKey] = None,
    ) -> None:
        self.network = network
        self.chain_query = chain_query
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

    async def start_oracle(self, initial_c3_amount: int):
        """Start oracle"""
        # Create a locking script that hold oracle script and also mints oracle NFT
        oracle_owner = OwnerScript(
            self.network, self.chain_query, self.verification_key
        )
        owner_script = oracle_owner.mk_owner_script(self.script_start_slot)
        owner_script_hash = owner_script.hash()
        c3_asset = MultiAsset(
            {self.c3_token_hash: Asset({self.c3_token_name: initial_c3_amount})}
        )
        # Create a transaction builder
        builder = TransactionBuilder(self.context)

        # Required since owner script is InvalidBefore type
        builder.validity_start = self.script_start_slot

        ############ Reference script creation: ############
        owner_script_addr = Address(
            payment_part=owner_script_hash, network=self.network
        )

        print(f"Locking script address: {owner_script_addr}")
        print(f"Oracle script address: {self.oracle_address}")

        print(self.context.utxos(self.address))

        # Reference script output
        reference_script_utxo = TransactionOutput(
            address=self.oracle_address, amount=60000000, script=self.oracle_script
        )

        # Add reference script
        builder.add_output(reference_script_utxo)

        ############ Oracle NFT minting: ############
        oracle_nfts = MultiAsset.from_primitive(
            {
                owner_script_hash.payload: {
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
            {owner_script_hash.payload: {b"NodeFeed": 1}}
        )
        oracle_nft = MultiAsset.from_primitive(
            {owner_script_hash.payload: {b"OracleFeed": 1}}
        )
        aggstate_nft = MultiAsset.from_primitive(
            {owner_script_hash.payload: {b"AggState": 1}}
        )
        reward_nft = MultiAsset.from_primitive(
            {owner_script_hash.payload: {b"Reward": 1}}
        )
        # Set native script
        builder.native_scripts = [owner_script]

        node_reward_list = []
        # Prepare each datum
        for node in self.node_pkh_list:
            node_datum = NodeDatum(
                node_state=NodeState(nodeOperator=node, nodeFeed=Nothing())
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
        aggstate_datum = AggDatum(aggstate=AggState(agSettings=self.oracle_settings))
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
                platform_reward=RewardInfo(
                    bytes(self.oracle_settings.os_platform_pkh), 0
                ),
            )
        )
        reward_output = TransactionOutput(
            self.oracle_address,
            Value(3000000, reward_nft),
            datum=reward_datum,
        )
        builder.add_output(reward_output)

        await self.submit_tx_builder(builder)

    async def _process_common_inputs(self, builder: TransactionBuilder):
        builder.add_input_address(self.address)
        builder.add_output(TransactionOutput(self.address, 5000000))

        non_nft_utxo = await self._get_or_create_collateral()

        if non_nft_utxo is not None:
            builder.collaterals.append(non_nft_utxo)
            builder.required_signers = [self.pub_key_hash]

            return builder
        else:
            raise Exception("Unable to find or create collateral.")

    async def _get_or_create_collateral(self):
        non_nft_utxo = self.chain_query.find_collateral(self.address)

        if non_nft_utxo is None:
            await self.chain_query.create_collateral(self.address, self.signing_key)
            non_nft_utxo = self.chain_query.find_collateral(self.address)

        return non_nft_utxo

    async def submit_tx_builder(self, builder: TransactionBuilder):
        """adds collateral and signers to tx, sign and submit tx."""
        builder = await self._process_common_inputs(builder)
        signed_tx = builder.build_and_sign(
            [self.signing_key],
            change_address=self.address,
            auto_validity_start_offset=0,
            auto_ttl_offset=120,
        )

        try:
            await self.chain_query.submit_tx_with_print(signed_tx)
            print("Transaction submitted successfully.")
        except Exception as err:
            print("Error submitting transaction: ", err)
