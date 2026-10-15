"""Held-out bank. Committed to git before the first run; never tuned against.

Different providers, alias styles the dev expansions don't list (Univ, Hlth, Grp, Ctr., Mt., "&" vs "and"), other CPT
codes and rev codes, other payers incl. Medicaid, higher noise (pre-accident visits, re-sent copies, statements,
missing bills/records), and an urgent-care + pain-management path instead of ER-only.
"""

BANK = {
    "first": ["Maria", "Kevin", "Aisha", "Robert", "Hannah", "Luis", "Grace", "Omar"],
    "last": ["Garcia", "Nguyen", "Martin", "Clark", "Lewis", "Walker", "Young", "Hernandez"],
    "payers": ["Cigna", "Humana", "Medicaid (state plan)", "Kaiser Permanente", "Medicare"],
    "allowed_ratio": (0.25, 0.85),
    "related_icd": ["S13.4XXA", "S39.012A", "M54.2", "M50.20", "S23.3XXA", "S06.0X0A", "M25.511"],
    "unrelated_icd": ["Z00.01", "E78.5", "J45.909", "K21.9", "Z13.220"],
    "cc_related": ["Right shoulder pain since the crash", "Mid back pain after being rear-ended", "Concussion symptoms after motor vehicle accident",
                   "Neck and arm numbness following the collision", "Whiplash, follow-up"],
    "cc_unrelated": ["Wellness exam", "Cholesterol recheck", "Asthma refill", "Heartburn"],
    "preventive": ("99395", "Preventive visit est 18-39", 160, 300),
    "p_pre": 0.45, "p_unrelated": 0.3, "p_bill_missing": 0.08, "p_record_missing": 0.1, "p_statement": 0.6, "p_resend": 0.4, "p_eob": 0.5,
    "providers": [
        {"name": "Lakeshore Fire Rescue Ambulance", "aliases": ["Lakeshore Fire Rescue Ambulance", "LAKESHORE FIRE & RESCUE AMB", "Lakeshore Fire and Rescue Ambulance Svc"],
         "npi": "1023948576", "kind": "transport", "layout": "itemized", "always": False, "visits": (1, 1), "start": (0, 0), "every": [1], "max_codes": 2, "rev": {},
         "codes": [("A0429", "BLS emergency transport", 700, 1300), ("A0425", "Mileage", 90, 300)]},
        {"name": "University Health Medical Center", "aliases": ["University Health Medical Center", "Univ Health Med Ctr", "UNIVERSITY HLTH MEDICAL CENTER"],
         "npi": "1184756302", "kind": "facility", "layout": "both", "always": True, "visits": (1, 1), "start": (0, 0), "every": [1], "max_codes": 3,
         "rev": {"99283": "0450", "72040": "0320", "73030": "0320", "96372": "0510"},
         "codes": [("99283", "ED visit level 3", 1200, 2600), ("72040", "X-ray cervical spine 2-3 views", 300, 700),
                   ("73030", "X-ray shoulder 2+ views", 250, 650), ("96372", "Injection IM/SQ", 60, 180)]},
        {"name": "Northgate Urgent Care", "aliases": ["Northgate Urgent Care", "NORTHGATE URGENT CARE CTR.", "Northgate UC Grp"], "npi": "1376450928",
         "kind": "office", "layout": "itemized", "always": False, "visits": (1, 2), "start": (0, 3), "every": [3, 5], "max_codes": 2, "rev": {},
         "codes": [("99214", "Office visit est moderate", 180, 320), ("72100", "X-ray lumbar spine", 150, 400)]},
        {"name": "Mount Hope Pain Management", "aliases": ["Mount Hope Pain Management", "Mt. Hope Pain Mgmt", "MT HOPE PAIN MANAGEMENT GRP"], "npi": "1665029384",
         "kind": "office", "layout": "itemized", "always": False, "visits": (1, 3), "start": (30, 70), "every": [21, 28], "max_codes": 2, "rev": {},
         "codes": [("64483", "Transforaminal epidural injection", 1800, 4200), ("99204", "New patient consult", 300, 520), ("77003", "Fluoroscopic guidance", 250, 600)]},
        {"name": "Riverside Advanced Imaging", "aliases": ["Riverside Advanced Imaging", "RIVERSIDE ADV IMAGING", "Riverside Adv. Img Ctr"], "npi": "1937465012",
         "kind": "facility", "layout": "ub04", "always": False, "visits": (1, 3), "start": (7, 40), "every": [5, 9], "max_codes": 1,
         "rev": {"72141": "0610", "73221": "0610", "70551": "0610"},
         "codes": [("72141", "MRI cervical spine", 1400, 3800), ("73221", "MRI shoulder", 1300, 3200), ("70551", "MRI brain", 1600, 3900)]},
        {"name": "Peak Performance Physical Therapy", "aliases": ["Peak Performance Physical Therapy", "Peak Perf PT", "PEAK PERFORMANCE PHYSICAL THERAPY & SPORTS REHAB"],
         "npi": "1450396728", "kind": "office", "layout": "itemized", "always": False, "visits": (8, 22), "start": (4, 25), "every": [2, 3, 4, 7], "max_codes": 3, "rev": {},
         "codes": [("97110", "Therapeutic exercises", 85, 190), ("97530", "Therapeutic activities", 90, 200), ("97112", "Neuromuscular re-education", 80, 170),
                   ("G0283", "E-stim unattended", 25, 60)]},
        {"name": "Valley Family Chiropractic", "aliases": ["Valley Family Chiropractic", "Valley Family Chiro & Wellness", "VALLEY FAMILY CHIROPRACTIC PC"],
         "npi": "1592837460", "kind": "office", "layout": "itemized", "always": False, "visits": (5, 14), "start": (1, 12), "every": [2, 3, 7], "max_codes": 2, "rev": {},
         "codes": [("98940", "Chiropractic manipulation 1-2 regions", 50, 100), ("97140", "Manual therapy", 60, 120)]},
    ],
}
SEEDS = range(90_001, 91_001)   # 1,000 cases
