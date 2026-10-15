"""Specials ledger: parse bill / UB-04 / statement / EOB / record text, resolve providers, de-duplicate charges,
match to records, classify, total billed vs paid basis, list liens and requests. Every row cites its documents."""
import datetime as dt
import re

MONEY = r"-?\$[\d,]+\.\d{2}"
DATE = r"\d{2}/\d{2}/\d{4}"
INJURY_WORDS = re.compile(r"collision|mvc|mva|motor vehicle|car accident|crash|rear-?ended|whiplash|after (the )?accident|struck", re.I)
UNRELATED_ICD = re.compile(r"^(Z00|Z01|Z13|E11|E78|I10|J06|J45|K21|N39|F41)")
PREVENTIVE = re.compile(r"^993(8\d|9\d)$")
STOP = {"llc", "inc", "pc", "pa", "the", "of", "and", "group", "&"}
EXPAND = {"st": "saint", "ctr": "center", "med": "medical", "hosp": "hospital", "pt": "physical therapy", "assoc": "associates",
          "assocs": "associates", "ortho": "orthopedic", "orthopaedic": "orthopedic", "orthopaedics": "orthopedic", "orthopedics": "orthopedic",
          "chiro": "chiropractic", "rehab": "rehabilitation", "phys": "physicians", "dept": "department", "ems": "emergency medical services", "mt": "mount",
          "svc": "services", "svcs": "services", "rad": "radiology", "img": "imaging", "ctrs": "centers", "grp": "group"}


def m2f(s):
    return float(s.replace("$", "").replace(",", ""))


def s2d(s):
    return dt.datetime.strptime(s, "%m/%d/%Y").date()


def tokens(name):
    t = re.sub(r"[’'`.]", "", name.lower())
    t = re.sub(r"[^a-z0-9 ]", " ", t)
    out = []
    for w in t.split():
        w = EXPAND.get(w, w)
        out += [x for x in w.split() if x not in STOP]
    return out


def _tok_match(a, b):
    if a == b:
        return True
    if len(a) >= 3 and len(b) >= 3 and (a.startswith(b) or b.startswith(a)):
        return True
    if a.rstrip("s") == b.rstrip("s"):
        return True
    return len(a) > 4 and len(b) > 4 and _edit1(a, b)


def _edit1(a, b):
    if abs(len(a) - len(b)) > 1:
        return False
    i = j = d = 0
    while i < len(a) and j < len(b):
        if a[i] == b[j]:
            i += 1; j += 1
            continue
        d += 1
        if d > 1:
            return False
        if len(a) > len(b):
            i += 1
        elif len(b) > len(a):
            j += 1
        else:
            i += 1; j += 1
    return d + (len(a) - i) + (len(b) - j) <= 1


def _initials(ta, tb):
    """'uc' in one name standing for 'urgent care' in the other: replace it by those tokens."""
    out = []
    for x in ta:
        if 2 <= len(x) <= 4 and x.isalpha() and x not in tb:
            for i in range(len(tb) - len(x) + 1):
                if "".join(w[0] for w in tb[i:i + len(x)]) == x:
                    out += tb[i:i + len(x)]
                    break
            else:
                out.append(x)
        else:
            out.append(x)
    return out


def name_sim(a, b):
    ta, tb = tokens(a), tokens(b)
    ta, tb = _initials(ta, tb), _initials(tb, ta)
    if not ta or not tb:
        return 0.0
    hit_a = sum(any(_tok_match(x, y) for y in tb) for x in ta)
    hit_b = sum(any(_tok_match(y, x) for x in ta) for y in tb)
    short, hits = (ta, hit_a) if len(ta) <= len(tb) else (tb, hit_b)
    if len(short) >= 2 and hits == len(short):          # "CLEARVIEW IMAGING" inside "ClearView Imaging Center"
        return max(0.8, min(hit_a / len(ta), hit_b / len(tb)))
    return min(hit_a / len(ta), hit_b / len(tb))


def resolve(name, npi, known):
    if npi:
        for k, v in known.items():
            if v.get("npi") == npi:
                return k, "npi"
    best = max(known, key=lambda k: name_sim(name, k)) if known else None
    if best and name_sim(name, best) >= 0.75:
        return best, f"name {name_sim(name, best):.2f}"
    return f"UNKNOWN: {name}", "unresolved"


def parse(doc):
    t = doc["text"]
    lines = t.split("\n")
    head = lines[1] if lines[0].startswith("Received via") else lines[0]
    npi = (re.search(r"NPI:\s*(\d{10})", t) or [None, None])[1]
    out = {"id": doc["id"], "npi": npi, "provider": head}
    if "EXPLANATION OF BENEFITS" in t:
        out["type"] = "EOB"
        out["payer"] = re.search(r"EXPLANATION OF BENEFITS - (.+)", t).group(1).strip()
        out["provider"] = re.search(r"Provider:\s*(.+)", t).group(1).strip()
        out["lines"] = [{"dos": s2d(m[0]), "code": m[1], "billed": m2f(m[2]), "allowed": m2f(m[3]), "paid": m2f(m[4]), "adj": m2f(m[5]), "pr": m2f(m[6])}
                        for m in re.findall(rf"^({DATE})\s+(\S+)\s+({MONEY})\s+({MONEY})\s+({MONEY})\s+({MONEY})\s+({MONEY})", t, re.M)]
    elif "MEDICAL RECORD" in t:
        out["type"] = "RECORD"
        out["dos"] = s2d(re.search(rf"Date of service:\s*({DATE})", t).group(1))
        out["icd"] = re.search(r"Assessment:\s*(\S+)", t).group(1)
        out["cc"] = re.search(r"Chief complaint:\s*(.+)", t).group(1)
        out["codes"] = [c.strip() for c in re.search(r"Procedures:\s*(.*)", t).group(1).split(",") if c.strip()]
    elif "UB-04" in t:
        out["type"] = "UB04"
        f, th = re.search(rf"From ({DATE}) Through ({DATE})", t).groups()
        out["from"], out["through"] = s2d(f), s2d(th)
        out["revs"] = [(r, m2f(a)) for r, a in re.findall(rf"^Rev (\d{{4}})\s+({MONEY})", t, re.M)]
        out["total"] = m2f(re.search(rf"Total Charges ({MONEY})", t).group(1))
    elif "PATIENT STATEMENT" in t:
        out["type"] = "STATEMENT"
        rows = []
        for m in re.finditer(rf"^({DATE}) (.+?)\s+(-?\$[\d,]+\.\d{{2}})\s*$", t, re.M):
            dos, desc, amt = s2d(m[1]), m[2].strip(), m2f(m[3])
            code = (re.search(r"\((\w+)\)", desc) or [None, None])[1]
            if amt < 0 or "-$" in m[0]:
                kind = "PAY" if re.search(r"payment", desc, re.I) else "ADJ"
                rows.append({"kind": kind, "date": dos, "amount": abs(amt)})
            else:
                rows.append({"kind": "CHARGE", "dos": dos, "desc": desc, "code": code, "amount": amt})
        out["rows"] = rows
    elif "ITEMIZED BILL" in t:
        out["type"] = "ITEMIZED"
        out["lines"] = [{"dos": s2d(m[0]), "code": m[1], "desc": m[2].strip(), "amount": m2f(m[3])}
                        for m in re.findall(rf"^({DATE}) (\S+)\s+(.+?)\s+({MONEY})\s*$", t, re.M)]
        out["total"] = m2f(re.search(rf"TOTAL CHARGES ({MONEY})", t).group(1))
    else:
        out["type"] = "UNKNOWN"
    return out


def build_ledger(case, gap_days=30):
    acc, known = case["accident"], case["providers_known"]
    parsed = [parse(d) for d in case["docs"]]
    for p in parsed:
        p["prov"], p["how"] = resolve(p["provider"], p["npi"], known)
    charges, notes = [], []

    def add(prov, dos, code, amount, src, period=None):
        for c in charges:
            if c["prov"] == prov and c["dos"] == dos and abs(c["billed"] - amount) < 0.005 and (code is None or c["code"] in (None, code)):
                c["sources"].append(src)
                if code and not c["code"]:
                    c["code"] = code
                return c
        c = {"prov": prov, "dos": dos, "code": code, "billed": amount, "sources": [src], "period": period, "adj": None, "paid": None, "payer": None}
        charges.append(c)
        return c

    for p in [x for x in parsed if x["type"] == "ITEMIZED"]:
        for ln in p["lines"]:
            add(p["prov"], ln["dos"], ln["code"], ln["amount"], p["id"])
    stmt_credits, seen_stmt = [], set()
    for p in [x for x in parsed if x["type"] == "STATEMENT"]:
        sig = (p["prov"], tuple((r["kind"], r.get("dos") or r.get("date"), r["amount"]) for r in p["rows"]))
        if sig in seen_stmt:                       # a re-sent copy: its credits were already taken once
            notes.append(f"{p['id']}: same statement as one already read -> credits not applied twice")
            continue
        seen_stmt.add(sig)
        last = None
        for r in p["rows"]:
            if r["kind"] == "CHARGE":
                last = add(p["prov"], r["dos"], r["code"], r["amount"], p["id"])
            elif last is not None:
                stmt_credits.append((p["prov"], last["dos"], r["kind"], r["amount"], p["id"]))
    for p in [x for x in parsed if x["type"] == "UB04"]:
        inside = [c for c in charges if c["prov"] == p["prov"] and c["dos"] and p["from"] <= c["dos"] <= p["through"]]
        if inside and abs(sum(c["billed"] for c in inside) - p["total"]) < 0.01:
            notes.append(f"{p['id']}: UB-04 summary {p['total']:,.2f} = itemized charges already counted -> not added again")
            continue
        if inside:
            notes.append(f"{p['id']}: UB-04 total {p['total']:,.2f} differs from itemized {sum(c['billed'] for c in inside):,.2f} -> REVIEW")
        if p["from"] == p["through"]:
            for rev, amt in p["revs"]:
                add(p["prov"], p["from"], f"REV{rev}", amt, p["id"])
        else:
            add(p["prov"], p["from"], "UB04-PERIOD", p["total"], p["id"], period=(p["from"], p["through"]))
    records = [x for x in parsed if x["type"] == "RECORD"]
    eobs = [x for x in parsed if x["type"] == "EOB"]

    # payments
    for e in eobs:
        for ln in e["lines"]:
            for c in charges:
                if c["prov"] == e["prov"] and c["dos"] == ln["dos"] and abs(c["billed"] - ln["billed"]) < 0.005 and c["paid"] is None:
                    c.update(adj=ln["adj"], paid=ln["paid"], pr=ln["pr"], payer=e["payer"], eob=e["id"])
                    break
            else:
                pc = next((c for c in charges if c["prov"] == e["prov"] and c["period"] and c["period"][0] <= ln["dos"] <= c["period"][1]), None)
                if pc is not None:
                    pc["adj"] = (pc["adj"] or 0) + ln["adj"]
                    pc["paid"] = (pc["paid"] or 0) + ln["paid"]
                    pc["payer"], pc["eob"] = e["payer"], e["id"]
                if ln["code"] and not any(c["prov"] == e["prov"] and (c["dos"] == ln["dos"] or c["period"]) for c in charges):
                    notes.append(f"{e['id']}: EOB line {ln['dos']} {ln['code']} has no bill on file -> request bill")
    # facility summaries billed by revenue code: one rev line can hold several CPT lines of the EOB
    for e in eobs:
        left = [ln for ln in e["lines"] if not any(c.get("eob") == e["id"] and c["dos"] == ln["dos"] and abs(c["billed"] - ln["billed"]) < 0.005 for c in charges)]
        for dos in {ln["dos"] for ln in left}:
            revs = [c for c in charges if c["prov"] == e["prov"] and c["dos"] == dos and (c["code"] or "").startswith("REV") and c["paid"] is None]
            ls = [ln for ln in left if ln["dos"] == dos]
            if revs and abs(sum(c["billed"] for c in revs) - sum(ln["billed"] for ln in ls)) < 0.01:
                tot = sum(c["billed"] for c in revs)
                for c in revs:
                    f = c["billed"] / tot
                    c.update(adj=round(sum(ln["adj"] for ln in ls) * f, 2), paid=round(sum(ln["paid"] for ln in ls) * f, 2), payer=e["payer"], eob=e["id"])
    for prov, dos, kind, amt, src in stmt_credits:
        visit = [c for c in charges if c["prov"] == prov and c["dos"] == dos]
        if not visit or all(c["paid"] is not None for c in visit):
            continue
        tot = sum(c["billed"] for c in visit)
        for c in visit:
            share = amt * c["billed"] / tot if tot else 0
            if kind == "ADJ":
                c["s_adj"] = c.get("s_adj", 0) + share
            else:
                c["s_paid"] = c.get("s_paid", 0) + share
    for c in charges:
        if c["paid"] is None and "s_adj" in c:
            c["adj"], c["paid"], c["payer"] = round(c["s_adj"], 2), round(c.get("s_paid", 0), 2), "insurer (statement, payer not named)"

    # classify
    def rec_for(c):
        out = []
        for r in records:
            if r["prov"] != c["prov"]:
                continue
            if c["period"] and c["period"][0] <= r["dos"] <= c["period"][1]:
                out.append(r)
            elif c["dos"] and abs((r["dos"] - c["dos"]).days) <= 1:
                out.append(r)
        exact = [r for r in out if c["dos"] and r["dos"] == c["dos"]]
        # +-1 day only when no note has the exact date, and never borrow a note that is another charge's exact date
        return exact or [r for r in out if (r["prov"], r["dos"]) not in billed_dates]

    billed_dates = {(c["prov"], c["dos"]) for c in charges if c["dos"]}
    for c in charges:
        rs = rec_for(c)
        c["records"] = [r["id"] for r in rs]
        start = c["period"][0] if c["period"] else c["dos"]
        if start < acc:
            c["status"], c["why"] = "EXCLUDED_PRE_ACCIDENT", f"date of service {start} is before the accident {acc}"
        elif c["code"] and PREVENTIVE.match(c["code"]):
            c["status"], c["why"] = "REVIEW_UNRELATED", f"{c['code']} is a preventive-visit code"
        elif rs and all(UNRELATED_ICD.match(r["icd"]) or not INJURY_WORDS.search(r["cc"]) for r in rs):
            r = rs[0]
            c["status"], c["why"] = "REVIEW_UNRELATED", f"record {r['id']}: {r['icd']}, '{r['cc']}'"
        elif not rs:
            c["status"], c["why"] = "NEEDS_RECORD", "billed, no visit note on file (counted provisionally)"
        else:
            c["status"], c["why"] = "INCLUDED", f"record {rs[0]['id']}"
    counted = [c for c in charges if c["status"] in ("INCLUDED", "NEEDS_RECORD")]
    need_bill = []
    for r in records:
        if r["dos"] < acc or UNRELATED_ICD.match(r["icd"]) or not INJURY_WORDS.search(r["cc"]):
            continue
        if not any(c["prov"] == r["prov"] and ((c["dos"] and abs((c["dos"] - r["dos"]).days) <= 1) or (c["period"] and c["period"][0] <= r["dos"] <= c["period"][1])) for c in charges):
            need_bill.append((r["prov"], r["dos"], r["id"]))
    need_record = sorted({(c["prov"], c["dos"]) for c in charges if c["status"] == "NEEDS_RECORD"}, key=lambda x: (x[0], x[1]))
    dates = sorted({c["dos"] for c in counted if c["dos"]})
    gaps = [(a, b, (b - a).days) for a, b in zip(dates, dates[1:]) if (b - a).days > gap_days]
    if dates and (dates[0] - acc).days > 14:
        gaps.insert(0, (acc, dates[0], (dates[0] - acc).days))
    billed = round(sum(c["billed"] for c in counted), 2)
    known_adj = [c for c in counted if c["adj"] is not None]
    paid_basis = round(sum(c["billed"] - (c["adj"] or 0) for c in counted), 2)
    liens = {}
    for c in counted:
        if c["payer"] and c["paid"]:
            liens[c["payer"]] = round(liens.get(c["payer"], 0) + c["paid"], 2)
    return {"charges": charges, "billed": billed, "paid_basis": paid_basis, "paid_basis_complete": len(known_adj) == len(counted),
            "unpriced": [c for c in counted if c["adj"] is None], "liens": liens, "need_record": need_record, "need_bill": need_bill,
            "gaps": gaps, "notes": notes, "docs": parsed}
