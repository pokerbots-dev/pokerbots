import sys

from .. import wallet as keys
from ..api import call
from ..fmt import held, money, parse_money, table


def registered_key():
    key = keys.load_or_create()
    address = keys.address(key)
    me = call("GET", "/me")
    if me["wallet"] != address:
        call("PUT", "/wallet", {"address": address})
    return key, address, me


def wallet(args):
    _, address, me = registered_key()
    me = call("GET", "/me")
    yours = [["address", address], ["send", "USDC on Solana only (not SOL)"], ["wallet", held(me)]]
    ours = [["balance", f"{money(me['balance'])} on pokerbots, for live buy-ins"]]
    if me["withdraw_to"] and me["withdraw_to"] != address:
        ours.append(["withdraws to", me["withdraw_to"]])
    print(table(yours, labels=True) + "\n" + "-" * 3 + "\n" + table(ours, labels=True))


def deposit(args):
    key, _, _ = registered_key()
    prepared = call("POST", "/deposits", {"amount": parse_money(args.amount)})
    reply = call("POST", f"/deposits/{prepared['signature']}", {"transaction": keys.sign(prepared["transaction"], key)})
    print(f"deposit {reply['status']}: {money(reply['amount'])}")


def withdraw(args):
    _, address, me = registered_key()
    if me["withdraw_to"] and me["withdraw_to"] != address:
        sys.exit(f"withdrawals go to {me['withdraw_to']}, the wallet you last deposited from.\n"
                 f"to use this wallet instead, deposit from it once: pb deposit 0.10")
    reply = call("POST", "/withdrawals", {"amount": parse_money(args.amount)})
    print(f"withdrawal {reply['status']}: {money(reply['amount'])}")


def register(sub):
    sub.add_parser("wallet", help="your Solana wallet address and balance").set_defaults(run=wallet)
    for name, run in (("deposit", deposit), ("withdraw", withdraw)):
        p = sub.add_parser(name, help=f"{name} USDC, e.g. pb {name} 5")
        p.add_argument("amount", help="dollars")
        p.set_defaults(run=run)
