"""offchain code containing mint class"""
from dataclasses import dataclass
from pycardano import (
    Network,
    Address,
    PaymentVerificationKey,
    PaymentSigningKey,
    TransactionOutput,
    TransactionBuilder,
    Redeemer,
    Value,
    MultiAsset,
    PlutusV2Script,
    plutus_script_hash,
    PlutusData,
    AuxiliaryData,
    AlonzoMetadata,
    Metadata,
)
from charli3_offchain_core.chain_query import ChainQuery


@dataclass
class MintToken(PlutusData):
    """MintToken class"""

    CONSTR_ID = 0


class Mint:
    """Mint class"""

    def __init__(
        self,
        network: Network,
        chain_query: ChainQuery,
        signing_key: PaymentSigningKey,
        verification_key: PaymentVerificationKey,
        plutus_v2_mint_script: PlutusV2Script,
    ) -> None:
        self.network = network
        self.chain_query = chain_query
        self.context = self.chain_query.context
        self.signing_key = signing_key
        self.verification_key = verification_key
        self.pub_key_hash = self.verification_key.hash()
        self.address = Address(payment_part=self.pub_key_hash, network=self.network)
        self.minting_script_plutus_v2 = plutus_v2_mint_script

    async def mint_nft_with_script(self):
        """mint tokens with plutus v2 script"""
        policy_id = plutus_script_hash(self.minting_script_plutus_v2)

        c3_token = MultiAsset.from_primitive(
            {
                policy_id.payload: {
                    b"Charli3": 1000000000,  # Name of our token  # Quantity of this token
                }
            }
        )

        metadata = {
            0: {
                policy_id.payload.hex(): {
                    "Charli3": {
                        "description": "This is charli3 test tokens",
                        "name": "Charli3",
                    }
                }
            }
        }
        # print("tC3 Token policy ID: ", policy_id.payload.hex())
        # Place metadata in AuxiliaryData, the format acceptable by a transaction.
        auxiliary_data = AuxiliaryData(AlonzoMetadata(metadata=Metadata(metadata)))

        # Create a transaction builder
        builder = TransactionBuilder(self.context)

        # Add our own address as the input address
        builder.add_input_address(self.address)

        # Add minting script with an empty datum and a minting redeemer
        builder.add_minting_script(
            self.minting_script_plutus_v2,
            redeemer=Redeemer(MintToken()),
        )

        # Set nft we want to mint
        builder.mint = c3_token

        # Set transaction metadata
        builder.auxiliary_data = auxiliary_data

        # Send the NFT to our own address
        nft_output = TransactionOutput(self.address, Value(2000000, c3_token))
        builder.add_output(nft_output)

        await self.chain_query.submit_tx_builder(
            builder, self.signing_key, self.address
        )
