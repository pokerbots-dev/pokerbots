import base64

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from pokerbots_cli import wallet
from pokerbots_cli.fmt import money, parse_money


def test_sign_fills_our_slot_only():
    payer, me = Ed25519PrivateKey.generate(), Ed25519PrivateKey.generate()
    message = bytes([0x80, 2, 0, 1, 3]) + wallet.public(payer) + wallet.public(me) + bytes(32) + bytes(40)
    payer_signature = payer.sign(message)
    wire = bytes([2]) + payer_signature + bytes(64) + message
    signed = base64.b64decode(wallet.sign(base64.b64encode(wire).decode(), me))
    assert signed[1:65] == payer_signature
    me.public_key().verify(signed[65:129], message)
    assert signed[129:] == message


def test_b58_and_money():
    assert wallet.b58(bytes(32)) == "1" * 32
    assert wallet.b58(b"\x00\x01") == "12"
    assert [money(100_000), money(370_000), money(4_200_000), money(-1_100_000)] == ["10¢", "37¢", "$4.20", "-$1.10"]
    assert parse_money("$0.10") == 100_000
