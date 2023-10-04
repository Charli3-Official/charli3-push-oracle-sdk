"""Oracle Owner NFT minting script"""
from typing import Tuple, List
from pycardano import (
    VerificationKeyHash,
    ScriptAll,
    ScriptPubkey,
    NativeScript,
    InvalidBefore,
    ScriptNofK,
)
from charli3_offchain_core.chain_query import ChainQuery


class OwnerScriptException(Exception):
    pass


class OwnerScript:
    """Oracle Owner NFT minting script class"""

    def __init__(
        self,
        chain_query: ChainQuery,
        multisig_parties: List[VerificationKeyHash] = None,
        multisig_threshold: int = None,
        is_mock_script: bool = False,
    ) -> None:
        self.chain_query = chain_query
        self.context = self.chain_query.context
        self.is_mock_script = is_mock_script
        if is_mock_script:
            self.multisig_parties = None
            self.multisig_threshold = None
        elif multisig_parties is None or not multisig_parties:
            raise OwnerScriptException(
                "multisig parties param should be set for production scripts"
            )
        elif multisig_threshold is None:
            raise OwnerScriptException(
                "multisig threshold param should be set for production scripts"
            )
        elif multisig_threshold <= 0 or multisig_threshold > len(multisig_parties):
            raise OwnerScriptException(
                "multisig threshold param should be positive and not exceed parties number"
            )
        else:
            self.multisig_parties = multisig_parties
            self.multisig_threshold = multisig_threshold

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
        # A time policy that validates before a certain slot:
        # this is to parametrize script and make a unique script hash (e.g. to make a NFT),
        # and it is done to ensure that owner could spend/burn later.
        # "type": "after" means that minting/spending is valid after the slot
        # InvalidBefore means that minting/spending tx must not be submitted before the slot
        valid_after_slot = InvalidBefore(script_start_slot)

        if not self.is_mock_script:
            # A policy that requires a signature from one of the multisig parties
            pub_key_policies = [ScriptPubkey(pkh) for pkh in self.multisig_parties]
            # Multisig policy requires *threshold* of multisig parties signatures
            multisig_policy = ScriptNofK(self.multisig_threshold, pub_key_policies)
            # Combine two policies using ScriptAll policy
            policy = ScriptAll([multisig_policy, valid_after_slot])
        else:
            policy = valid_after_slot

        return policy

    def print_start_params(self, script_start_slot: int = None):
        """Print oracle start params to compile oracle plutus script with"""

        print(f"Oracle Platform Parties: {self.multisig_parties}")

        if script_start_slot is None:
            _, nft_policy = self.create_owner_script()
            print(f"Oracle NFT currency symbol: {nft_policy.hash().payload.hex()}")
        else:
            nft_policy = self.mk_owner_script(script_start_slot)
            print(f"Oracle NFT currency symbol: {nft_policy.hash().payload.hex()}")
