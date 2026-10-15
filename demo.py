"""One held-out case: documents in, specials ledger out (with what a quick tally would have said)."""
import collections

from eval.bank_heldout import BANK
from specials import baselines
from specials.ledger import build_ledger
from specials.synth import build

SEED = 90011


def main(seed=SEED):
    case, truth = build(seed, BANK)
    L = build_ledger(case)
    kinds = collections.Counter(d["type"] for d in L["docs"])
    print(f"Case {seed}: {case['patient']}, accident {case['accident']}, {len(case['docs'])} documents {dict(kinds)}")
    print("\nSPECIALS LEDGER (unique charges)")
    by = collections.defaultdict(list)
    for c in L["charges"]:
        by[c["prov"]].append(c)
    for prov, cs in by.items():
        print(f"  {prov}")
        for c in sorted(cs, key=lambda c: c["dos"]):
            pay = f"paid {c['paid']:>8,.2f} adj {c['adj']:>8,.2f}" if c["adj"] is not None else "no payment data"
            print(f"    {c['dos']} {str(c['code']):8s} {c['billed']:>9,.2f}  {c['status']:22s} src {','.join(c['sources']):12s} {pay}")
            if c["status"] not in ("INCLUDED",):
                print(f"        - {c['why']}")
    print("\nNOTES")
    for n in L["notes"]:
        print("  -", n)
    print("\nREQUESTS")
    for p, d in L["need_record"]:
        print(f"  records: {p}, DOS {d}")
    for p, d, rid in L["need_bill"]:
        print(f"  bill   : {p}, DOS {d} (seen in {rid})")
    for a, b, n in L["gaps"]:
        print(f"  gap    : {n} days between {a} and {b} (expect the adjuster to raise it)")
    print("\nTOTALS")
    print(f"  billed specials        {L['billed']:>12,.2f}   (truth {truth['billed']:,.2f})")
    print(f"  paid basis             {L['paid_basis']:>12,.2f}   {'complete' if L['paid_basis_complete'] else str(len(L['unpriced'])) + ' charges without payment data counted at billed'}")
    print(f"  liens                  {L['liens']}")
    print(f"  quick tallies          add every bill {baselines.sum_all(case):,.2f} | drop re-sent copies {baselines.drop_resent(case):,.2f} | de-dupe lines on date+amount {baselines.line_dedupe(case):,.2f}")


if __name__ == "__main__":
    main()
