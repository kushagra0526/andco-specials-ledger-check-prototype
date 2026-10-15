"""Synthetic PI case: visits, bills in several layouts, EOBs, records, noise — with the truth kept aside.

Truth (what a careful paralegal would put in the demand today):
  billed      sum of unique, related charges on bills received (DOS on/after the accident, related diagnosis)
  paid_basis  billed minus contractual adjustments on those charges (payer paid + patient responsibility)
  liens       payer paid on those charges, by payer
  need_record (provider, DOS) billed but no record received
  need_bill   (provider, DOS) in a record but no bill received
"""
import datetime as dt
import random


def d2s(d):
    return d.strftime("%m/%d/%Y")


def build(seed, B):
    rng = random.Random(seed)
    acc = dt.date(2026, rng.randint(1, 6), rng.randint(1, 28))
    patient = f"{rng.choice(B['first'])} {rng.choice(B['last'])}"
    provs = [p for p in B["providers"] if p["always"] or rng.random() < 0.6]
    visits = []                      # each: provider, dos, lines[(code, desc, amount)], icd, related, pre
    for p in provs:
        n = rng.randint(*p["visits"])
        day = acc + dt.timedelta(days=p["start"][0] if p["start"][0] == 0 else rng.randint(*p["start"]))
        for i in range(n):
            lines = [(c, desc, float(rng.randint(lo, hi))) for c, desc, lo, hi in rng.sample(p["codes"], k=min(len(p["codes"]), rng.randint(1, p["max_codes"])))]
            visits.append({"prov": p, "dos": day, "lines": lines, "icd": rng.choice(B["related_icd"]), "related": True, "pre": False})
            day += dt.timedelta(days=rng.choice(p["every"]))
    # noise visits
    office = [p for p in provs if p["kind"] == "office"]
    if office and rng.random() < B["p_pre"]:
        p = rng.choice(office)
        for k in range(rng.randint(1, 3)):
            dos = acc - dt.timedelta(days=rng.randint(20, 200))
            c, desc, lo, hi = p["codes"][0]
            visits.append({"prov": p, "dos": dos, "lines": [(c, desc, float(rng.randint(lo, hi)))], "icd": rng.choice(B["unrelated_icd"]), "related": False, "pre": True})
    if office and rng.random() < B["p_unrelated"]:
        p = rng.choice(office)
        dos = acc + dt.timedelta(days=rng.randint(10, 90))
        c, desc, lo, hi = rng.choice([p["codes"][0], B["preventive"]])
        visits.append({"prov": p, "dos": dos, "lines": [(c, desc, float(rng.randint(lo, hi)))], "icd": rng.choice(B["unrelated_icd"]), "related": False, "pre": False})
    visits.sort(key=lambda v: v["dos"])

    payer = rng.choice(B["payers"])
    for v in visits:
        v["eob"] = []
        for c, desc, amt in v["lines"]:
            allowed = round(amt * rng.uniform(*B["allowed_ratio"]), 2)
            pr = round(allowed * rng.choice([0, 0.1, 0.2]), 2)
            v["eob"].append((c, amt, allowed, round(allowed - pr, 2), round(amt - allowed, 2), pr))

    docs, truth = [], {"billed": 0.0, "paid_basis": 0.0, "liens": {}, "need_record": set(), "need_bill": set(), "pre_lines": 0, "unrelated_lines": 0}
    by_prov = {}
    for v in visits:
        by_prov.setdefault(v["prov"]["name"], []).append(v)
    for name, vs in by_prov.items():
        p = vs[0]["prov"]
        billed_visits = [v for v in vs if rng.random() > B["p_bill_missing"]]
        recorded = [v for v in vs if rng.random() > B["p_record_missing"]]
        alias = lambda: rng.choice(p["aliases"])  # noqa: E731
        layout = p["layout"]
        rel_billed = [v for v in billed_visits if v["related"] or not v["pre"]]
        # bill documents
        if billed_visits:
            if layout in ("itemized", "both"):
                docs.append(("BILL", itemized(p, alias(), patient, billed_visits, rng)))
            if layout in ("ub04", "both"):
                docs.append(("BILL", ub04(p, alias(), patient, billed_visits, rng)))
            if rng.random() < B["p_statement"] and p["kind"] == "office":
                docs.append(("BILL", statement(p, alias(), patient, billed_visits, rng)))
            if rng.random() < B["p_resend"]:
                kind, text = docs[-1]
                docs.append((kind, f"Received via {rng.choice(['fax', 'portal', 'mail scan'])} {d2s(acc + dt.timedelta(days=rng.randint(30, 120)))}\n" + text))
            if rng.random() < B["p_eob"]:
                docs.append(("EOB", eob(p, alias(), patient, billed_visits, payer)))
        for v in recorded:
            docs.append(("RECORD", record(p, alias(), patient, v, B, rng)))
        # truth
        for v in billed_visits:
            if v["pre"]:
                truth["pre_lines"] += len(v["lines"])
                continue
            if not v["related"]:
                truth["unrelated_lines"] += len(v["lines"])
                continue
            for c, amt, allowed, paid, adj, pr in v["eob"]:
                truth["billed"] += amt
                truth["paid_basis"] += amt - adj
                truth["liens"][payer] = truth["liens"].get(payer, 0.0) + paid
            if v not in recorded:
                truth["need_record"].add((p["name"], v["dos"]))
        for v in recorded:
            if v not in billed_visits and not v["pre"] and v["related"]:
                truth["need_bill"].add((p["name"], v["dos"]))
    rng.shuffle(docs)
    case = {"accident": acc, "patient": patient, "docs": [{"id": f"D{i + 1:02d}", "kind": k, "text": t} for i, (k, t) in enumerate(docs)],
            "providers_known": {p["name"]: {"npi": p["npi"]} for p in provs}}
    truth["billed"], truth["paid_basis"] = round(truth["billed"], 2), round(truth["paid_basis"], 2)
    truth["liens"] = {k: round(v, 2) for k, v in truth["liens"].items()}
    return case, truth


def money(x):
    return f"${x:,.2f}"


def itemized(p, alias, patient, vs, rng):
    lines = [f"{alias}", f"NPI: {p['npi']}" if rng.random() < 0.7 else "", f"Patient: {patient}", "ITEMIZED BILL", "DOS        CODE   DESCRIPTION                     CHARGE"]
    tot = 0
    for v in vs:
        for c, desc, amt in v["lines"]:
            lines.append(f"{d2s(v['dos'])} {c:6s} {desc:31s} {money(amt)}")
            tot += amt
    lines.append(f"TOTAL CHARGES {money(tot)}")
    return "\n".join(x for x in lines if x)


def ub04(p, alias, patient, vs, rng):
    by_rev = {}
    for v in vs:
        for c, desc, amt in v["lines"]:
            rev = p["rev"].get(c, "0001")
            by_rev[rev] = by_rev.get(rev, 0) + amt
    tot = sum(by_rev.values())
    lines = [f"{alias}", f"Patient: {patient}", "UB-04 CLAIM SUMMARY",
             f"Statement covers period: From {d2s(min(v['dos'] for v in vs))} Through {d2s(max(v['dos'] for v in vs))}"]
    lines += [f"Rev {r}  {money(a)}" for r, a in sorted(by_rev.items())]
    lines.append(f"Total Charges {money(tot)}")
    return "\n".join(lines)


def statement(p, alias, patient, vs, rng):
    lines = [f"{alias}", f"Patient: {patient}", "PATIENT STATEMENT", f"Previous balance {money(rng.choice([0, 0, 85.0, 140.0]))}",
             "DATE       DESCRIPTION                       CHARGES     CREDITS"]
    bal = 0
    for v in vs:
        for c, desc, amt in v["lines"]:
            code = f" ({c})" if rng.random() < 0.5 else ""
            lines.append(f"{d2s(v['dos'])} {(desc + code):33s} {money(amt):>10s}")
            bal += amt
        if v["eob"] and rng.random() < 0.6:
            paid = sum(e[3] for e in v["eob"])
            adj = sum(e[4] for e in v["eob"])
            lines.append(f"{d2s(v['dos'] + dt.timedelta(days=21))} Insurance payment{'':16s} {'':>10s} -{money(paid)}")
            lines.append(f"{d2s(v['dos'] + dt.timedelta(days=21))} Contractual adjustment{'':11s} {'':>10s} -{money(adj)}")
            bal -= paid + adj
    lines.append(f"BALANCE DUE {money(bal)}")
    return "\n".join(lines)


def eob(p, alias, patient, vs, payer):
    lines = [f"EXPLANATION OF BENEFITS - {payer}", f"Provider: {alias}", f"Member: {patient}",
             "DOS        CODE   BILLED     ALLOWED    PAID       ADJUSTMENT PT RESP"]
    for v in vs:
        for c, amt, allowed, paid, adj, pr in v["eob"]:
            lines.append(f"{d2s(v['dos'])} {c:6s} {money(amt):10s} {money(allowed):10s} {money(paid):10s} {money(adj):10s} {money(pr)}")
    return "\n".join(lines)


def record(p, alias, patient, v, B, rng):
    cc = rng.choice(B["cc_related"]) if v["related"] else rng.choice(B["cc_unrelated"])
    return "\n".join([f"{alias}", "MEDICAL RECORD - VISIT NOTE", f"Patient: {patient}", f"Date of service: {d2s(v['dos'])}",
                      f"Chief complaint: {cc}", f"Assessment: {v['icd']}", f"Procedures: {', '.join(c for c, _, _ in v['lines'])}"])
