"""send ADA to an address"""
from typing import List
from pycardano import (
    Network,
    Address,
    PaymentVerificationKey,
    ExtendedSigningKey,
    HDWallet,
    TransactionBuilder,
    TransactionOutput,
)
from charli3_offchain_core.chain_query import ChainQuery

# Add your mnemonic here
MNEMONIC_24 = ""

network = Network.MAINNET
chain_query = ChainQuery(
    "mainnetC1kgA6sHNIkRmjNA5jLCa8gUfKc8omBg",
    base_url="https://cardano-mainnet.blockfrost.io/api",
)


def send_ada_to(addresses: List[str], amount: int):
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
    chain_query.submit_tx_with_print(signed_tx)
    print(f"Sent {amount} ada to {len(addresses)} addresses")


if __name__ == "__main__":
    send_ada_to(
        [
            "addr1vxzq9lq33a5j65ajxlcrqyg9uqv3lwu7shlemc0qx0qtejqn4vx0w",
            "addr1vyvmjgwv45t62ptwru8t2aw5v4urhzau33g6dac7f7yvszck8vvd0",
        ],
        100,
    )
