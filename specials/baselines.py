"""Totals a quick tally would produce."""
from .ledger import parse


def sum_all(case):
    """Add up every bill document's total (statements: sum of charge lines)."""
    t = 0.0
    for d in case["docs"]:
        p = parse(d)
        if p["type"] in ("ITEMIZED", "UB04"):
            t += p["total"]
        elif p["type"] == "STATEMENT":
            t += sum(r["amount"] for r in p["rows"] if r["kind"] == "CHARGE")
    return round(t, 2)


def drop_resent(case):
    """Same, but identical documents (re-sent fax / portal copy) counted once."""
    seen, t = set(), 0.0
    for d in case["docs"]:
        body = d["text"].split("\n", 1)[1] if d["text"].startswith("Received via") else d["text"]
        if body in seen:
            continue
        seen.add(body)
        p = parse(d)
        if p["type"] in ("ITEMIZED", "UB04"):
            t += p["total"]
        elif p["type"] == "STATEMENT":
            t += sum(r["amount"] for r in p["rows"] if r["kind"] == "CHARGE")
    return round(t, 2)


def line_dedupe(case):
    """Charge lines de-duplicated on (date, amount) across all docs; UB-04 totals added unless equal to an itemized total;
    no provider resolution, no date or relatedness rules."""
    seen, t, item_totals = set(), 0.0, set()
    ps = [parse(d) for d in case["docs"]]
    for p in ps:
        if p["type"] == "ITEMIZED":
            item_totals.add(round(p["total"], 2))
            for ln in p["lines"]:
                k = (ln["dos"], ln["amount"])
                if k not in seen:
                    seen.add(k); t += ln["amount"]
    for p in ps:
        if p["type"] == "STATEMENT":
            for r in p["rows"]:
                if r["kind"] == "CHARGE" and (r["dos"], r["amount"]) not in seen:
                    seen.add((r["dos"], r["amount"])); t += r["amount"]
        elif p["type"] == "UB04" and round(p["total"], 2) not in item_totals:
            item_totals.add(round(p["total"], 2)); t += p["total"]
    return round(t, 2)
