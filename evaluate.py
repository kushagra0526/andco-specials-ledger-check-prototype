"""Score the ledger and baselines against generator truth.

python evaluate.py          # held-out
python evaluate.py --dev
"""
import collections
import json
import sys

from specials import baselines
from specials.ledger import build_ledger
from specials.synth import build


def run(B, seeds):
    agg = collections.Counter()
    err = {"ledger": [], "sum_all": [], "drop_resent": [], "line_dedupe": []}
    worst = []
    for seed in seeds:
        case, tr = build(seed, B)
        L = build_ledger(case)
        T = tr["billed"]
        for name, v in (("ledger", L["billed"]), ("sum_all", baselines.sum_all(case)), ("drop_resent", baselines.drop_resent(case)),
                        ("line_dedupe", baselines.line_dedupe(case))):
            e = round(v - T, 2)
            err[name].append(e)
            agg[f"{name}_exact"] += abs(e) < 0.01
        if abs(L["billed"] - T) >= 0.01:
            worst.append({"seed": seed, "truth": T, "ledger": L["billed"], "diff": round(L["billed"] - T, 2)})
        nr_t = {(p, d) for p, d in tr["need_record"]}
        nr_l = {(p, d) for p, d in L["need_record"]}
        nb_t = set(tr["need_bill"])
        nb_l = {(p, d) for p, d, _ in L["need_bill"]}
        agg["req_true"] += len(nr_t) + len(nb_t)
        agg["req_found"] += len(nr_t & nr_l) + len(nb_t & nb_l)
        agg["req_listed"] += len(nr_l) + len(nb_l)
        agg["req_wrong"] += len(nr_l - nr_t) + len(nb_l - nb_t)
        agg["pre_lines_true"] += tr["pre_lines"]
        agg["pre_lines_excluded"] += sum(len(c["sources"]) > 0 for c in L["charges"] if c["status"] == "EXCLUDED_PRE_ACCIDENT")
        agg["unrelated_lines_true"] += tr["unrelated_lines"]
        agg["unrelated_flagged"] += sum(1 for c in L["charges"] if c["status"] == "REVIEW_UNRELATED")
        agg["cases"] += 1
        if L["paid_basis_complete"]:
            agg["paid_complete"] += 1
            agg["paid_exact"] += abs(L["paid_basis"] - tr["paid_basis"]) < 0.05
            agg["liens_exact"] += all(abs(L["liens"].get(k, 0) - v) < 0.05 for k, v in tr["liens"].items())
        agg["unresolved_docs"] += sum(1 for d in L["docs"] if d["prov"].startswith("UNKNOWN"))
    summ = {}
    for name, es in err.items():
        summ[name] = {"exact_cases": agg[f"{name}_exact"], "overstated_total": round(sum(e for e in es if e > 0), 2),
                      "understated_total": round(-sum(e for e in es if e < 0), 2), "median_abs_error": sorted(abs(e) for e in es)[len(es) // 2],
                      "cases_over_1000": sum(e > 1000 for e in es)}
    summ["truth_total_billed"] = round(sum(build(s, B)[1]["billed"] for s in seeds), 2)
    summ["requests"] = {"true": agg["req_true"], "found": agg["req_found"], "listed": agg["req_listed"], "wrong": agg["req_wrong"]}
    summ["exclusions"] = {"pre_accident_lines_true": agg["pre_lines_true"], "pre_accident_excluded": agg["pre_lines_excluded"],
                          "unrelated_lines_true": agg["unrelated_lines_true"], "unrelated_flagged": agg["unrelated_flagged"]}
    summ["paid"] = {"cases_with_full_payment_data": agg["paid_complete"], "paid_basis_exact": agg["paid_exact"], "liens_exact": agg["liens_exact"]}
    summ["cases"], summ["unresolved_provider_docs"] = agg["cases"], agg["unresolved_docs"]
    return summ, worst


if __name__ == "__main__":
    if "--dev" in sys.argv:
        from specials.bank_dev import BANK
        seeds, name = range(1, 401), "dev"
    else:
        from eval.bank_heldout import BANK, SEEDS
        seeds, name = SEEDS, "heldout"
    summ, worst = run(BANK, seeds)
    json.dump({"summary": summ, "ledger_misses": worst[:100]}, open(f"out/{name}.json", "w"), indent=1, default=str)
    print(json.dumps(summ, indent=1))
    print(len(worst), "ledger misses:", worst[:8])
