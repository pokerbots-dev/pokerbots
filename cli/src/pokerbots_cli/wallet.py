import base64
import json

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat

from .auth import credentials_path

ALPHABET = "123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz"


def b58(data):
    n = int.from_bytes(data, "big")
    out = ""
    while n:
        n, r = divmod(n, 58)
        out = ALPHABET[r] + out
    return "1" * (len(data) - len(data.lstrip(b"\0"))) + out


def path():
    return credentials_path().with_name("wallet.json")


def public(key):
    return key.public_key().public_bytes(Encoding.Raw, PublicFormat.Raw)


def load_or_create():
    """Solana keypair file format: JSON array of 64 bytes, secret seed then public key."""
    p = path()
    if p.exists():
        return Ed25519PrivateKey.from_private_bytes(bytes(json.loads(p.read_text())[:32]))
    key = Ed25519PrivateKey.generate()
    seed = key.private_bytes_raw()
    p.parent.mkdir(parents=True, exist_ok=True)
    p.touch(mode=0o600)
    p.write_text(json.dumps(list(seed + public(key))))
    return key


def address(key):
    return b58(public(key))


def shortvec(data, i):
    value = shift = 0
    while True:
        byte = data[i]
        i += 1
        value |= (byte & 0x7F) << shift
        shift += 7
        if byte < 0x80:
            return value, i


def sign(transaction_b64, key):
    """Adds our signature to a partially signed wire transaction."""
    wire = base64.b64decode(transaction_b64)
    count, start = shortvec(wire, 0)
    message = wire[start + 64 * count:]
    versioned = message[0] & 0x80
    signers = message[1 if versioned else 0]
    _, offset = shortvec(message, (1 if versioned else 0) + 3)
    keys = [message[offset + 32 * i: offset + 32 * (i + 1)] for i in range(signers)]
    at = start + 64 * keys.index(public(key))
    return base64.b64encode(wire[:at] + key.sign(message) + wire[at + 64:]).decode()
