from ..api import admin
from ..fmt import MICRO, money, table


def stats(args):
    s = admin("GET", "/stats")
    print(table([
        ["users", s["users"]],
        ["games today", s["games_today"]],
        ["owed to users", money(s["liabilities"])],
        ["hot wallet", f"{money(s['hot_usdc'])} USDC, {s['hot_sol']} SOL"],
        ["withdrawn today", money(s["withdrawn_today"])],
        ["paused", ", ".join(s["paused"]) or "nothing"],
    ]))


def withdrawals(args):
    rows = admin("GET", "/withdrawals")
    print(table([["id", "user", "amount", "requested"]] + [
        [w["id"], w["login"], money(w["amount"]), w["created_at"]] for w in rows
    ]) if rows else "no pending withdrawals")


def decide(args):
    reply = admin("POST", f"/withdrawals/{args.id}", {"action": args.action})
    print(f"{args.id} {reply['status']}")


def test_alert(args):
    print("sent" if admin("POST", "/test-alert")["sent"] else "not sent: ALERT_EMAIL is not set")


def pause(args):
    print("paused:", ", ".join(admin("POST", f"/{args.action}/{args.what}")["paused"]) or "nothing")


def suspend(args):
    reply = admin("POST", f"/users/{args.login}/{args.action}")
    print(f"{args.login} {'suspended' if reply['suspended'] else 'active'}")


def adjust(args):
    reply = admin("POST", f"/users/{args.login}/adjust", {"amount": round(float(args.dollars) * MICRO), "reason": " ".join(args.reason)})
    print(f"{args.login} balance {money(reply['balance'])}")


def register(sub):
    p = sub.add_parser("admin")
    admin_sub = p.add_subparsers(metavar="command", required=True)
    admin_sub.add_parser("stats").set_defaults(run=stats)
    admin_sub.add_parser("withdrawals", help="pending withdrawals").set_defaults(run=withdrawals)
    admin_sub.add_parser("test-alert", help="email a test alert").set_defaults(run=test_alert)
    for action in ("pause", "resume"):
        q = admin_sub.add_parser(action, help=f"{action} live play, deposits, withdrawals or all")
        q.add_argument("what", choices=["live", "deposits", "withdrawals", "all"])
        q.set_defaults(run=pause, action=action)
    for action in ("suspend", "unsuspend"):
        q = admin_sub.add_parser(action, help="suspended users can only withdraw" if action == "suspend" else None)
        q.add_argument("login")
        q.set_defaults(run=suspend, action=action)
    q = admin_sub.add_parser("adjust", help="credit (+) or debit (-) a balance, e.g. adjust alice -0.10 duplicate payout")
    q.add_argument("login")
    q.add_argument("dollars")
    q.add_argument("reason", nargs="+")
    q.set_defaults(run=adjust)
    for action in ("approve", "reject"):
        q = admin_sub.add_parser(action)
        q.add_argument("id")
        q.set_defaults(run=decide, action=action)
