"""Oracle Owner Actions Class"""

from charli3_offchain_core.oracle_owner import OracleOwner

from .base import MultisigTestBase, TestBase


class OracleOwnerActions(TestBase):
    """Set up the oralce owner actions methods"""

    def setup_method(self, method):
        super().setup_method(method)

        self.oracle_addr = self.load_oracle_address()
        self.oracle_owner = OracleOwner(
            network=self.NETWORK,
            chainquery=self.CHAIN_CONTEXT,
            signing_key=self.platform_signing_key,
            verification_key=self.platform_verification_key,
            node_nft=self.single_node_nft,
            aggstate_nft=self.aggstate_nft,
            oracle_nft=self.oracle_feed_nft,
            reward_nft=self.reward_nft,
            minting_nft_hash=self.owner_script_hash,
            c3_token_hash=self.payment_script_hash,
            c3_token_name=self.tC3_token_name,
            oracle_addr=str(self.oracle_addr),
            stake_key=None,
            minting_script=self.native_script,
            validity_start=self.script_start_slot,
        )


class MultisigOracleOwnerActions(MultisigTestBase):
    def setup_method(self, method):
        super().setup_method(method)

        self.oracle_addr = self.load_oracle_address()
        self.oracle_owner = OracleOwner(
            network=self.NETWORK,
            chainquery=self.CHAIN_CONTEXT,
            signing_key=self.platform_signing_key,
            verification_key=self.platform_verification_key,
            node_nft=self.single_node_nft,
            aggstate_nft=self.aggstate_nft,
            oracle_nft=self.oracle_feed_nft,
            reward_nft=self.reward_nft,
            minting_nft_hash=self.owner_script_hash,
            c3_token_hash=self.payment_script_hash,
            c3_token_name=self.tC3_token_name,
            oracle_addr=str(self.oracle_addr),
            stake_key=None,
            minting_script=self.native_script,
            validity_start=self.script_start_slot,
        )
