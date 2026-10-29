from .. import wallet as keys
from ..api import call
from ..fmt import money, parse_money, table


def registered_key():
    key = keys.load_or_create()
    address = keys.address(key)
    if call("GET", "/me")["wallet"] != address:
        call("PUT", "/wallet", {"address": address})
    return key, address


def wallet(args):
    _, address = registered_key()
    print(table([["address", address], ["balance", money(call("GET", "/me")["balance"])]]))


def deposit(args):
    key, _ = registered_key()
    prepared = call("POST", "/deposits", {"amount": parse_money(args.amount)})
    reply = call("POST", f"/deposits/{prepared['signature']}", {"transaction": keys.sign(prepared["transaction"], key)})
    print(f"deposit {reply['status']}: {money(reply['amount'])}")


def withdraw(args):
    registered_key()
    reply = call("POST", "/withdrawals", {"amount": parse_money(args.amount)})
    print(f"withdrawal {reply['status']}: {money(reply['amount'])}")


def register(sub):
    sub.add_parser("wallet", help="your Solana wallet address and balance").set_defaults(run=wallet)
    for name, run in (("deposit", deposit), ("withdraw", withdraw)):
        p = sub.add_parser(name, help=f"{name} USDC, e.g. pb {name} 5")
        p.add_argument("amount", help="dollars")
        p.set_defaults(run=run)
