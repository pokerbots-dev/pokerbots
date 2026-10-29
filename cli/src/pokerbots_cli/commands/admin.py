from ..api import admin
from ..fmt import money, table


def stats(args):
    s = admin("GET", "/stats")
    print(table([
        ["users", s["users"]],
        ["games today", s["games_today"]],
        ["owed to users", money(s["liabilities"])],
        ["hot wallet", f"{money(s['hot_usdc'])} USDC, {s['hot_sol']} SOL"],
        ["withdrawn today", money(s["withdrawn_today"])],
    ]))


def withdrawals(args):
    rows = admin("GET", "/withdrawals")
    print(table([["id", "user", "amount", "requested"]] + [
        [w["id"], w["login"], money(w["amount"]), w["created_at"]] for w in rows
    ]) if rows else "no pending withdrawals")


def decide(args):
    reply = admin("POST", f"/withdrawals/{args.id}", {"action": args.action})
    print(f"{args.id} {reply['status']}")


def register(sub):
    p = sub.add_parser("admin", help="operator commands")
    admin_sub = p.add_subparsers(metavar="command", required=True)
    admin_sub.add_parser("stats").set_defaults(run=stats)
    admin_sub.add_parser("withdrawals", help="pending withdrawals").set_defaults(run=withdrawals)
    for action in ("approve", "reject"):
        q = admin_sub.add_parser(action)
        q.add_argument("id")
        q.set_defaults(run=decide, action=action)
