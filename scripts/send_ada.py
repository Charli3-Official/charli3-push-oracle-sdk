"""send ADA to an address"""

import asyncio
from typing import List

from pycardano import (
    Address,
    BlockFrostChainContext,
    ExtendedSigningKey,
    HDWallet,
    Network,
    PaymentVerificationKey,
    TransactionBuilder,
    TransactionOutput,
)

from charli3_offchain_core.chain_query import ChainQuery

# Add your mnemonic here
MNEMONIC_24 = ""

network = Network.MAINNET
blockfrost_base_url = "base_url"
blockfrost_project_id = "project_id"
blockfrost_context = BlockFrostChainContext(
    blockfrost_project_id,
    base_url=blockfrost_base_url,
)

chain_query = ChainQuery(
    blockfrost_context,
)


async def send_ada_to(addresses: List[str], amount: int):
    """Send ADA to a list of addresses."""
    hdwallet = HDWallet.from_mnemonic(MNEMONIC_24)
    hdwallet_spend = hdwallet.derive_from_path("m/1852'/1815'/0'/0/0")
    spend_public_key = hdwallet_spend.public_key
    sender_verification_key = PaymentVerificationKey.from_primitive(spend_public_key)
    sender_pub_key_hash = sender_verification_key.hash()

    sender_signing_key = ExtendedSigningKey.from_hdwallet(hdwallet_spend)
    sender_address = Address(sender_pub_key_hash, network=network)
    topup_amount = amount * 1000000

    builder = TransactionBuilder(context=chain_query.context)

    for address in addresses:
        builder.add_output(
            TransactionOutput(
                address=Address.from_primitive(address), amount=topup_amount
            )
        )

    builder.add_input_address(sender_address)
    signed_tx = builder.build_and_sign(
        signing_keys=[sender_signing_key],
        change_address=sender_address,
    )
    await chain_query.submit_tx_with_print(signed_tx)
    print(f"Sent {amount} ada to {len(addresses)} addresses")


if __name__ == "__main__":
    asyncio.run(
        send_ada_to(
            [
                "addr1vxzq9lq33a5j65ajxlcrqyg9uqv3lwu7shlemc0qx0qtejqn4vx0w",
                "addr1vyvmjgwv45t62ptwru8t2aw5v4urhzau33g6dac7f7yvszck8vvd0",
            ],
            100,
        )
    )
