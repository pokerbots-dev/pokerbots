import pydoc
import sys

from .. import wallet as keys
from ..api import call
from ..fmt import held, money, parse_money, signed, table, when


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


KINDS = {"deposit": "deposit", "withdrawal": "withdrawal", "buyin": "buy-in", "payout": "prize",
         "refund": "refund", "adjustment": "adjustment"}


def ledger(args):
    reply = call("GET", f"/ledger?limit={args.n}")
    balance, rows = reply["balance"], []
    cluster = "" if reply.get("cluster", "mainnet-beta") == "mainnet-beta" else f"?cluster={reply['cluster']}"
    for e in reply["entries"]:
        detail = e.get("note") or (f"solscan.io/tx/{e['tx']}{cluster}" if e.get("tx") else "")
        rows.append([when(e["created_at"]), KINDS.get(e["kind"], e["kind"]), signed(e["amount"], "money"), money(balance), detail])
        balance -= e["amount"]
    text = table([["time", "what", "amount", "balance", ""]] + rows, header=True) if rows else "no money movements yet"
    if sys.stdout.isatty():
        pydoc.pager(text)
    else:
        print(text)


def register(sub):
    sub.add_parser("wallet", help="your Solana wallet address and balance").set_defaults(run=wallet)
    for name, run in (("deposit", deposit), ("withdraw", withdraw)):
        p = sub.add_parser(name, help=f"{name} USDC, e.g. pb {name} 5")
        p.add_argument("amount", help="dollars")
        p.set_defaults(run=run)
    p = sub.add_parser("ledger", help="every deposit, withdrawal, buy-in and prize")
    p.add_argument("-n", type=int, default=100, help="how many, default 100")
    p.set_defaults(run=ledger)
