MICRO = 1_000_000


def table(rows):
    rows = [[str(c) for c in row] for row in rows]
    widths = [max(len(r[i]) for r in rows if i < len(r)) for i in range(max(map(len, rows)))]
    return "\n".join("  ".join(c.ljust(w) for c, w in zip(r, widths)).rstrip() for r in rows)


def money(micro):
    cents = round(micro / 10_000)
    return f"{cents}¢" if abs(cents) < 100 else f"${cents / 100:,.2f}"


def parse_money(text):
    value = round(float(text.lstrip("$")) * MICRO)
    if value <= 0:
        raise ValueError("amount must be positive")
    return value


def place(n):
    return {1: "1st", 2: "2nd", 3: "3rd"}.get(n, f"{n}th") if n else "-"
