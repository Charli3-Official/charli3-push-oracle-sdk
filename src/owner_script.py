"""Oracle Owner NFT minting script"""
from typing import Tuple
from pycardano import (
    Network,
    PaymentVerificationKey,
    ScriptAll,
    ScriptPubkey,
    NativeScript,
    InvalidBefore,
)
from src.chain_query import ChainQuery


class OwnerScript:
    """Oracle Owner NFT minting script class"""

    def __init__(
        self,
        network: Network,
        chain_query: ChainQuery,
        owner_verification_key: PaymentVerificationKey,
    ) -> None:
        self.network = network
        self.chain_query = chain_query
        self.context = self.chain_query.context
        self.owner_verification_key = owner_verification_key
        self.owner_pub_key_hash = self.owner_verification_key.hash()

    def create_owner_script(self) -> Tuple[int, NativeScript]:
        """Create owner script and return script start slot and script"""
        # requires later addition of
        # tx_builder.validity_start = script_start_slot
        script_start_slot: int = self.context.last_block_slot

        # remember to save that value for later script hash construction
        print(f"Script start slot: {script_start_slot}")

        owner_script = self.mk_owner_script(script_start_slot)

        return (script_start_slot, owner_script)

    def mk_owner_script(self, script_start_slot: int) -> NativeScript:
        """Create owner script with script start slot as a parameter to make a unique script hash"""
        # A policy that requires a signature from the public key
        pub_key_policy = ScriptPubkey(self.owner_pub_key_hash)

        # A time policy that validates before a certain slot:
        # this is to parametrize script and make a unique script hash (e.g. to make a NFT),
        # and it is done to ensure that owner could spend/burn later.
        # "type": "after" means that minting/spending is valid after a slot
        # RequireTimeAfter means that minting/spending tx must be submitted after a slot
        valid_after_slot = InvalidBefore(script_start_slot)

        # Combine two policies using ScriptAll policy
        policy = ScriptAll([pub_key_policy, valid_after_slot])

        return policy

    def print_start_params(self, script_start_slot: int = None):
        """Print oracle start params to compile oracle plutus script with"""

        oracle_creator = self.owner_pub_key_hash
        print(f"Oracle Creator: {oracle_creator.payload.hex()}")

        if script_start_slot is None:
            _, nft_policy = self.create_owner_script()
            print(f"Oracle NFT currency symbol: {nft_policy.hash().payload.hex()}")
        else:
            nft_policy = self.mk_owner_script(script_start_slot)
            print(f"Oracle NFT currency symbol: {nft_policy.hash().payload.hex()}")
