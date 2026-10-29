import os
import sys
from datetime import datetime, timezone

MICRO = 1_000_000
INK, PAPER = "17;17;17", "244;243;239"


def colored():
    return sys.stdout.isatty() and not os.environ.get("NO_COLOR")


def bold(text):
    return f"\x1b[1m{text}\x1b[22m" if colored() else text


def table(rows, labels=False, header=False):
    """Aligned columns; bold the first column (labels) or first row (header)."""
    rows = [[str(c) for c in row] for row in rows]
    widths = [max(len(r[i]) for r in rows if i < len(r)) for i in range(max(map(len, rows)))]
    lines = []
    for n, r in enumerate(rows):
        cells = [c.ljust(w) for c, w in zip(r, widths)]
        if header and n == 0:
            cells = [bold(c) for c in cells]
        elif labels:
            cells[0] = bold(cells[0])
        lines.append("  ".join(cells).rstrip())
    return "\n".join(lines)


def money(micro):
    cents = round(micro / 10_000)
    sign = "-" if cents < 0 else ""
    return f"{cents}¢" if abs(cents) < 100 else f"{sign}${abs(cents) / 100:,.2f}"


def signed(value, unit=""):
    if value is None:
        return "-"
    return ("+" if value > 0 else "") + (money(value) if unit == "money" else f"{value:.0f}")


def when(utc):
    return datetime.fromisoformat(utc).replace(tzinfo=timezone.utc).astimezone().strftime("%m-%d %H:%M")


def parse_money(text):
    value = round(float(text.lstrip("$")) * MICRO)
    if value <= 0:
        raise ValueError("amount must be positive")
    return value


def place(n):
    return {1: "1st", 2: "2nd", 3: "3rd"}.get(n, f"{n}th") if n else "-"
