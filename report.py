"""out/report.html: held-out first run vs after fixes."""
import json

F = json.load(open("out/heldout_first_run.json"))["summary"]
A = json.load(open("out/heldout.json"))["summary"]
N = {"sum_all": "Add every bill document", "drop_resent": "…minus re-sent copies", "line_dedupe": "De-dupe lines on date + amount", "ledger": "Specials ledger"}
rows = ""
for k in ("sum_all", "drop_resent", "line_dedupe", "ledger"):
    rows += (f"<tr class={'g' if k == 'ledger' else ''}><td>{N[k]}</td><td>{F[k]['exact_cases']}</td><td>{A[k]['exact_cases']}</td>"
             f"<td>${A[k]['overstated_total']:,.0f}</td><td>{A[k]['cases_over_1000']}</td></tr>")
html = f"""<!doctype html><meta charset=utf-8><title>specials ledger</title>
<style>body{{font:16px system-ui;margin:28px;max-width:1000px}}table{{border-collapse:collapse}}td,th{{border:1px solid #ccc;padding:8px 12px;text-align:right}}td:first-child,th:first-child{{text-align:left}}.g td{{background:#eaf7ee;font-weight:600}}</style>
<h2>Medical specials: held-out bank, 1,000 synthetic PI cases</h2>
<p>Bills in 3 layouts + EOBs + visit notes per case; truth = unique, related charges billed (from the generator). Unofficial prototype, not affiliated with Andco.</p>
<table><tr><th>Method</th><th>Exact specials, first run</th><th>Exact, after fixes</th><th>$ overstated (all cases)</th><th>Cases off by &gt;$1,000</th></tr>{rows}</table>
<p>Pre-accident lines excluded {A['exclusions']['pre_accident_excluded']}/{A['exclusions']['pre_accident_lines_true']} ·
unrelated flagged {A['exclusions']['unrelated_flagged']}/{A['exclusions']['unrelated_lines_true']} ·
requests found {A['requests']['found']}/{A['requests']['true']} with {A['requests']['wrong']} wrong ·
paid basis exact {A['paid']['paid_basis_exact']}/{A['paid']['cases_with_full_payment_data']} cases with full payment data.</p>
<p>First run: 839/1000 — "Northgate UC Grp" did not resolve (UC = Urgent Care). Fix: abbreviation-by-initials + "grp"; plus re-sent statements applying credits twice (paid basis). Remaining 18 misses: 17 are visits billed with no note yet (counted provisionally, on the request list) that turned out unrelated; 1 other.</p>"""
open("out/report.html", "w", encoding="utf-8").write(html)
