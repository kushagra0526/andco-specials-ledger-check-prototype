import datetime as dt
import sys, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

from specials.ledger import build_ledger, name_sim, resolve
from specials.synth import build
from specials.bank_dev import BANK

ACC = dt.date(2026, 3, 1)
KNOWN = {"Coastal Physical Therapy": {"npi": "1295847361"}, "St. Mary's Medical Center": {"npi": "1730192837"}}
ITEM = "Coastal PT\nPatient: A B\nITEMIZED BILL\nDOS        CODE   DESCRIPTION   CHARGE\n03/05/2026 97110  Therapeutic exercise $120.00\n03/05/2026 97140  Manual therapy $90.00\nTOTAL CHARGES $210.00"
STMT = ("COASTAL PHYSICAL THERAPY & REHAB\nPatient: A B\nPATIENT STATEMENT\nPrevious balance $0.00\nDATE DESCRIPTION CHARGES CREDITS\n"
        "01/10/2026 Therapeutic exercise (97110) $110.00\n03/05/2026 Therapeutic exercise (97110) $120.00\n03/05/2026 Manual therapy $90.00\n"
        "03/26/2026 Insurance payment -$100.00\n03/26/2026 Contractual adjustment -$60.00\nBALANCE DUE $160.00")
REC = "Coastal Physical Therapy\nMEDICAL RECORD - VISIT NOTE\nPatient: A B\nDate of service: {d}\nChief complaint: {cc}\nAssessment: {icd}\nProcedures: 97110"


def case(*docs):
    return {"accident": ACC, "patient": "A B", "providers_known": KNOWN, "docs": [{"id": f"D{i}", "kind": "", "text": t} for i, t in enumerate(docs, 1)]}


def test_provider_aliases_resolve():
    assert resolve("COASTAL PHYSICAL THERAPY & REHAB", None, KNOWN)[0] == "Coastal Physical Therapy"
    assert resolve("Saint Marys Med Ctr", None, KNOWN)[0] == "St. Mary's Medical Center"
    assert name_sim("Northgate UC Grp", "Northgate Urgent Care") >= 0.75
    assert resolve("Totally Different Clinic", None, KNOWN)[0].startswith("UNKNOWN")


def test_statement_and_resent_copy_do_not_double_count():
    L = build_ledger(case(ITEM, "Received via fax 04/01/2026\n" + ITEM, STMT, REC.format(d="03/05/2026", cc="Neck pain after MVC", icd="S13.4XXA")))
    assert L["billed"] == 210.00
    pre = [c for c in L["charges"] if c["status"] == "EXCLUDED_PRE_ACCIDENT"]
    assert len(pre) == 1 and pre[0]["billed"] == 110.00


def test_statement_credits_give_paid_basis_once():
    L = build_ledger(case(ITEM, STMT, "Received via portal 04/02/2026\n" + STMT, REC.format(d="03/05/2026", cc="Neck pain after MVC", icd="S13.4XXA")))
    assert abs(L["paid_basis"] - 150.00) < 0.01      # 210 billed - 60 contractual adjustment


def test_unrelated_record_flags_and_missing_record_requested():
    L = build_ledger(case(ITEM, REC.format(d="03/05/2026", cc="Annual physical", icd="Z00.00")))
    assert {c["status"] for c in L["charges"]} == {"REVIEW_UNRELATED"} and L["billed"] == 0
    L2 = build_ledger(case(ITEM))
    assert L2["need_record"] == [("Coastal Physical Therapy", dt.date(2026, 3, 5))] and L2["billed"] == 210.00


def test_record_without_bill_requests_bill():
    L = build_ledger(case(ITEM, REC.format(d="03/12/2026", cc="Neck pain after MVC", icd="S13.4XXA")))
    assert [(p, d) for p, d, _ in L["need_bill"]] == [("Coastal Physical Therapy", dt.date(2026, 3, 12))]


def test_ub04_summary_matching_itemized_not_added():
    ub = "St. Mary's Medical Center\nPatient: A B\nUB-04 CLAIM SUMMARY\nStatement covers period: From 03/01/2026 Through 03/01/2026\nRev 0450  $2,000.00\nTotal Charges $2,000.00"
    it = "Saint Marys Med Ctr\nNPI: 1730192837\nPatient: A B\nITEMIZED BILL\nDOS CODE DESCRIPTION CHARGE\n03/01/2026 99284  ED visit $2,000.00\nTOTAL CHARGES $2,000.00"
    L = build_ledger(case(ub, it))
    assert L["billed"] == 2000.00 and any("not added again" in n for n in L["notes"])


def test_dev_bank_mostly_exact():
    exact = sum(abs(build_ledger(c)["billed"] - t["billed"]) < 0.01 for c, t in (build(s, BANK) for s in range(1, 61)))
    assert exact >= 57
