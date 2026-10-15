#!/usr/bin/env python3
"""Build the fictional expense-review fixtures and deterministic input PDFs.

No model, service, approval or payment operation is performed. The expected
outcomes are author-prepared test labels, never measured results.
"""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
from pathlib import Path
import zipfile

import reportlab
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.pdfbase.pdfmetrics import registerFont, stringWidth
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen import canvas


ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "app" / "fixtures" / "expense_review"
COMPANY = "Cedarline Services"
DOMAIN_ID = "expense_review"
FONT_DIR = Path(reportlab.__file__).parent / "fonts"
registerFont(TTFont("ExpenseSans", str(FONT_DIR / "Vera.ttf")))
registerFont(TTFont("ExpenseSans-Bold", str(FONT_DIR / "VeraBd.ttf")))

POLICY_LINES = [
    "Cedarline Services | Accommodation reimbursement precheck | Initial procedure",
    "Fictional company policy for a six-case demonstration. This is not tax or legal guidance.",
    "Scope: check the submitted claim and hotel payment evidence before a manager's business approval.",
    "Only update the isolated review status. Never approve expenditure, send a message or execute payment.",
    "Use the approved stay dates recorded on the claim form. If either hotel stay date differs, hold for a manager's decision on the changed stay; matching amounts do not resolve this exception.",
    "The hotel guest must match the claimant. A known guest-name mismatch is returned for correction.",
    "For a receipt addressed to the claimant, use the explicitly stated employee-paid amount marked PAID. Compare the claim with that amount, not with a total that includes another payer.",
    "For an accepted receipt with an identified employee payment marked PAID, a known amount mismatch is returned for correction.",
    "Mark the documentary precheck complete only when claimant and guest match, both stay dates match the approved dates, the receipt is accepted, and the claimed amount equals the stated employee-paid amount marked PAID.",
    "The acceptance conditions for a company-addressed hotel folio are not recorded here, including how to use its payer allocation. Ask the expense task owner before treating that arrangement as accepted evidence.",
    "If a required value, payer allocation or payment status is missing, hold and request the specific missing evidence. Do not subtract a company payment from a total, reverse-calculate from the claim, or infer who paid.",
    "Changed-trip necessity and exceptions to the approved stay remain a manager's business decision. A task-owner clarification of document checks does not grant that approval.",
    "READY_FOR_BUSINESS_APPROVAL means only that this documentary precheck is complete. RETURNED_FOR_CORRECTION and HELD are isolated simulation states, not communications or payment instructions.",
]

TEACHING_LINES = [
    "DRAFT FOR TASK-OWNER REVIEW | Company-addressed hotel folios",
    "This proposed explanation is not approved and must not activate rules until the task owner reviews and explicitly approves it.",
    "A folio addressed to Cedarline Services may be accepted for this precheck when the named guest matches the claimant, the employee-paid amount is explicitly identified, and that employee payment is marked PAID.",
    "Compare the claimed amount directly with that stated employee-paid amount, not the total lodging charge. A known mismatch is returned for correction.",
    "The company prepayment is not reimbursed to the employee. Its presence does not replace evidence of the employee's own payment.",
    "Do not calculate or infer a missing payment allocation. Hold and request evidence that explicitly identifies the employee-paid amount and its payment status.",
    "Both hotel stay dates must match the approved stay dates. A changed stay still requires a manager's decision; this clarification does not approve an extension.",
    "Matching evidence permits only READY_FOR_BUSINESS_APPROVAL in the isolated simulation, never final expense approval or payment.",
]

# These are fictional transactions, not observations of a real organization.
RECORDS = [
    dict(suffix="dev_01", claim="EXP-261001", split="dev", stratum="normal", name="Mika Sato", start="2026-09-03", end="2026-09-05", actual_end="2026-09-05", amount=26800, total=26800, company_paid=0, employee_paid=26800, payment="PAID", recipient="Mika Sato", document="RECEIPT-H4101", hotel="Willowmere House Hotel", issued="2026-09-05", submitted="2026-09-06", note="Accommodation cost for the approved trip."),
    dict(suffix="dev_02", claim="EXP-261002", split="dev", stratum="transfer", name="Aya Mori", start="2026-09-08", end="2026-09-10", actual_end="2026-09-10", amount=34800, total=52800, company_paid=18000, employee_paid=34800, payment="PAID", recipient=COMPANY, document="FOLIO-H4102", hotel="Aster Quay Lodge", issued="2026-09-10", submitted="2026-09-11", note="The attached folio records the company prepayment and my card payment."),
    dict(suffix="dev_03", claim="EXP-261003", split="dev", stratum="must_hold", name="Jun Aoki", start="2026-09-12", end="2026-09-14", actual_end="2026-09-14", amount=31200, total=49200, company_paid=None, employee_paid=None, payment=None, recipient=COMPANY, document="FOLIO-H4103", hotel="Birchhaven Court Hotel", issued="2026-09-14", submitted="2026-09-15", note="The hotel supplied a statement showing only the total payment."),
    dict(suffix="dev_04", claim="EXP-261004", split="dev", stratum="must_hold", name="Ren Kato", start="2026-09-18", end="2026-09-19", actual_end="2026-09-20", amount=39600, total=39600, company_paid=0, employee_paid=39600, payment="PAID", recipient="Ren Kato", document="RECEIPT-H4104", hotel="Linden Crest Inn", issued="2026-09-20", submitted="2026-09-21", note="An additional night was needed after the meeting was rescheduled. Approval for the extension is pending."),
    dict(suffix="holdout_01", claim="EXP-261005", split="holdout", stratum="transfer", name="Nao Ito", start="2026-09-23", end="2026-09-25", actual_end="2026-09-25", amount=27600, total=47600, company_paid=20000, employee_paid=27600, payment="PAID", recipient=COMPANY, document="FOLIO-H4105", hotel="Cloverstone Rooms", issued="2026-09-25", submitted="2026-09-26", note="My card payment is listed separately from the company prepayment."),
    dict(suffix="holdout_02", claim="EXP-261006", split="holdout", stratum="transfer", name="Yui Ono", start="2026-09-27", end="2026-09-29", actual_end="2026-09-29", amount=42400, total=42400, company_paid=16000, employee_paid=26400, payment="PAID", recipient=COMPANY, document="FOLIO-H4106", hotel="Mapleford Terrace Hotel", issued="2026-09-29", submitted="2026-09-30", note="The requested amount was entered from the total lodging charge."),
]

FIELD_DEFINITIONS = [
    ("claimant_name", "Claimant", "string", "Employee name on the reimbursement request."),
    ("claimed_amount_jpy", "Claimed amount (JPY)", "number", "Amount entered on the claim; do not replace it with a corrected amount."),
    ("approved_stay_start", "Approved stay start", "string", "Approved trip start date as written on the claim, in YYYY-MM-DD format."),
    ("approved_stay_end", "Approved stay end", "string", "Approved trip end date as written on the claim, in YYYY-MM-DD format."),
    ("receipt_addressee_name", "Receipt addressee", "string", "Exact Bill to name on the hotel payment document."),
    ("receipt_guest_name", "Hotel guest", "string", "Exact guest name on the hotel payment document."),
    ("receipt_stay_start", "Hotel stay start", "string", "Actual stay start stated on the hotel document, in YYYY-MM-DD format."),
    ("receipt_stay_end", "Hotel stay end", "string", "Actual stay end stated on the hotel document, in YYYY-MM-DD format."),
    ("employee_payment_amount_jpy", "Employee-paid amount (JPY)", "number", "Employee card payment explicitly stated by the hotel; null if not stated. Never derive it by subtraction."),
    ("employee_payment_status", "Employee payment status", "string", "Status of the employee payment, not the overall bill. Null when not stated."),
    ("receipt_total_jpy", "Total lodging charge (JPY)", "number", "Hotel total, which may include payments by different payers."),
    ("company_payment_amount_jpy", "Company prepayment (JPY)", "number", "Company payment explicitly stated by the hotel; null when not stated."),
    ("exception_note", "Employee note", "string", "Verbatim employee note. A note is not a manager's approval."),
]


def sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def text_bytes(lines):
    return ("\n".join(lines) + "\n").encode("utf-8")


def write_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def condition(field, op, value=None, rhs=None):
    return {"field_id": field, "operator": op, **({"rhs_field_id": rhs} if rhs else {"value": value})}


def source_ref(source_id, lines, line):
    return {"source_id": source_id, "version_hash": sha(text_bytes(lines)), "locator": f"line:{line}", "quote": lines[line - 1]}


def rule(rule_id, priority, statement, all_conditions, action, policy_lines, any_conditions=None, teaching_lines=None):
    refs = [source_ref("expense_sop", POLICY_LINES, n) for n in policy_lines]
    refs += [source_ref("expense_teaching_draft", TEACHING_LINES, n) for n in teaching_lines or []]
    return {"rule_id": rule_id, "priority": priority, "statement": statement,
            "when": {"all": all_conditions, "any": any_conditions or []}, "action_id": action,
            "source_refs": refs, "approved_by": None}


def make_domains():
    same_guest = condition("receipt_guest_name", "eq", rhs="claimant_name")
    same_dates = [condition("receipt_stay_start", "eq", rhs="approved_stay_start"), condition("receipt_stay_end", "eq", rhs="approved_stay_end")]
    paid = condition("employee_payment_status", "eq", "PAID")
    personal = condition("receipt_addressee_name", "eq", rhs="claimant_name")
    company = condition("receipt_addressee_name", "eq", COMPANY)
    rules = [
        rule("expense_changed_stay", 10, "A stay outside the recorded approved dates requires a manager's decision.", [], "hold_case", [5, 12], [condition("receipt_stay_start", "ne", rhs="approved_stay_start"), condition("receipt_stay_end", "ne", rhs="approved_stay_end")]),
        rule("expense_guest_mismatch", 20, "Return a known mismatch between the claimant and the hotel guest.", [condition("receipt_guest_name", "ne", rhs="claimant_name")], "return_for_correction", [6]),
        rule("expense_personal_amount_mismatch", 30, "Return a personal receipt when the stated paid employee amount differs from the claim.", [personal, same_guest, paid, condition("claimed_amount_jpy", "ne", rhs="employee_payment_amount_jpy")], "return_for_correction", [7, 8]),
        rule("expense_personal_complete", 90, "Complete the documentary precheck for a matching personal receipt with an explicitly stated paid employee amount.", [personal, same_guest, *same_dates, paid, condition("claimed_amount_jpy", "eq", rhs="employee_payment_amount_jpy")], "ready_for_approval", [7, 9, 13]),
    ]
    actions = []
    for aid, label, state, description in [
        ("ready_for_approval", "Complete documentary precheck", "READY_FOR_BUSINESS_APPROVAL", "Mark this isolated case ready for a manager's business approval. This is not expense approval or payment."),
        ("return_for_correction", "Mark for correction", "RETURNED_FOR_CORRECTION", "Record a known document mismatch in this isolated case. Do not contact the claimant or change a payment."),
        ("hold_case", "Hold for clarification or review", "HELD", "Keep incomplete evidence or a business exception for human review in this isolated simulation."),
    ]:
        actions.append({"action_id": aid, "label": label, "description": description, "effects": [{"field_id": "status", "value": state}], "terminal": True})
    domain = {"schema_version": "1.0", "domain_id": DOMAIN_ID, "version": 0,
              "title": "Accommodation reimbursement precheck",
              "goal": "Check fictional reimbursement documents, identify missing evidence or business exceptions, and record only an isolated precheck status before human expense approval.",
              "input_fields": [{"field_id": fid, "label": label, "type": kind, "description": desc, "required": True} for fid, label, kind, desc in FIELD_DEFINITIONS],
              "state_fields": [{"field_id": "status", "label": "Review status", "type": "string", "description": "Isolated documentary precheck status; never a payment status.", "required": True}],
              "actions": actions, "rules": rules, "default_action_id": "hold_case",
              "source_hashes": {"expense_sop": sha(text_bytes(POLICY_LINES))}}
    clarified = copy.deepcopy(domain)
    clarified["version"] = 1
    clarified["source_hashes"]["expense_teaching_draft"] = sha(text_bytes(TEACHING_LINES))
    clarified["rules"].extend([
        rule("expense_company_amount_mismatch", 30, "Return a company-addressed folio when its explicitly stated paid employee amount differs from the claim.", [company, same_guest, paid, condition("claimed_amount_jpy", "ne", rhs="employee_payment_amount_jpy")], "return_for_correction", [8, 11], teaching_lines=[3, 4, 6]),
        rule("expense_company_complete", 90, "Complete the precheck for an accepted company-addressed folio only when identity, approved stay dates and the explicitly stated paid employee amount match.", [company, same_guest, *same_dates, paid, condition("claimed_amount_jpy", "eq", rhs="employee_payment_amount_jpy")], "ready_for_approval", [9, 11, 12, 13], teaching_lines=[3, 4, 6, 7, 8]),
    ])
    return domain, clarified


def display(value):
    return "Not stated" if value is None else f"{value:,}" if isinstance(value, int) else str(value)


def make_documents(record):
    r = record
    facts = dict(claimant_name=r["name"], claimed_amount_jpy=r["amount"], approved_stay_start=r["start"], approved_stay_end=r["end"],
                 receipt_addressee_name=r["recipient"], receipt_guest_name=r["name"], receipt_stay_start=r["start"], receipt_stay_end=r["actual_end"],
                 employee_payment_amount_jpy=r["employee_paid"], employee_payment_status=r["payment"], receipt_total_jpy=r["total"], company_payment_amount_jpy=r["company_paid"], exception_note=r["note"])
    claim_rows = [
        (None, "Claim ID", r["claim"]), (None, "Submitted", r["submitted"]),
        ("claimant_name", "Claimant", r["name"]), (None, "Expense category", "Business-trip accommodation"),
        (None, "Business purpose", "Internal process planning meeting"), (None, "Approved trip reference", "TRIP-" + r["claim"].split("-")[1]),
        ("approved_stay_start", "Approved stay start", r["start"]), ("approved_stay_end", "Approved stay end", r["end"]),
        ("claimed_amount_jpy", "Claimed amount (JPY)", r["amount"]), (None, "Attached payment document", r["document"]),
        ("exception_note", "Employee note", r["note"]),
    ]
    hotel_rows = [
        (None, "Document ID", r["document"]), (None, "Issued", r["issued"]),
        ("receipt_addressee_name", "Bill to", r["recipient"]), ("receipt_guest_name", "Guest", r["name"]),
        ("receipt_stay_start", "Stay start", r["start"]), ("receipt_stay_end", "Stay end", r["actual_end"]),
        ("receipt_total_jpy", "Total lodging charge (JPY)", r["total"]), ("company_payment_amount_jpy", "Company prepayment (JPY)", r["company_paid"]),
        ("employee_payment_amount_jpy", "Employee card payment (JPY)", r["employee_paid"]),
        ("employee_payment_status", "Employee card payment status", r["payment"]), (None, "Total settlement status", "PAID"),
    ]
    pages = []
    field_map = {}
    for page_number, organization, title, rows in [(1, COMPANY, "Expense reimbursement request", claim_rows), (2, r["hotel"], "Hotel payment statement", hotel_rows)]:
        lines = [f"{label}: {display(value)}" for _, label, value in rows]
        pages.append({"page": page_number, "organization": organization, "title": title, "lines": lines})
        for line_number, ((fid, _, value), line) in enumerate(zip(rows, lines), 1):
            if fid:
                field_map[fid] = {"value": value, "status": "UNRESOLVED" if value is None else "OBSERVED", "page": page_number, "content_line": line_number, "quote": line}
    return facts, pages, field_map


def wrapped(text, font, size, width):
    lines, current = [], ""
    for word in text.split():
        candidate = current + (" " if current else "") + word
        if stringWidth(candidate, font, size) > width and current:
            lines.append(current)
            current = word
        else:
            current = candidate
    return lines + ([current] if current else [])


def render_pdf(path, record, pages):
    path.parent.mkdir(parents=True, exist_ok=True)
    c = canvas.Canvas(str(path), pagesize=A4, invariant=1, pageCompression=1)
    c.setTitle(record["claim"] + " | Fictional accommodation reimbursement documents")
    c.setAuthor("Cedarline Services - fictional demonstration")
    c.setSubject("Synthetic input documents; no actual expense, approval or payment")
    c.setCreator("Expense demo material generator")
    w, h = A4
    ink, green, muted = colors.HexColor("#173b31"), colors.HexColor("#176b57"), colors.HexColor("#61756c")
    for page in pages:
        c.setFillColor(colors.white)
        c.rect(0, 0, w, h, fill=1, stroke=0)
        c.setFillColor(green)
        c.rect(42, h - 56, 32, 4, fill=1, stroke=0)
        c.setFont("ExpenseSans-Bold", 10)
        c.setFillColor(ink)
        c.drawString(42, h - 80, page["organization"])
        c.setFont("ExpenseSans-Bold", 22)
        c.drawString(42, h - 113, page["title"])
        c.setFont("ExpenseSans", 9)
        c.setFillColor(muted)
        c.drawString(42, h - 135, "FICTIONAL INPUT DOCUMENT  |  " + record["claim"])
        c.setStrokeColor(colors.HexColor("#d9e2dc"))
        c.line(42, h - 153, w - 42, h - 153)
        y = h - 185
        for line in page["lines"]:
            fragments = wrapped(line, "ExpenseSans", 11, w - 84)
            c.setFont("ExpenseSans", 11)
            c.setFillColor(ink)
            for fragment in fragments:
                c.drawString(42, y, fragment)
                y -= 16
            y -= 15
        if y < 158:
            raise ValueError("PDF content overflow: " + record["claim"])
        c.setFillColor(colors.HexColor("#f2f6f2"))
        c.roundRect(42, 98, w - 84, 53, 6, fill=1, stroke=0)
        c.setFillColor(muted)
        c.setFont("ExpenseSans", 9)
        note = ("Documentary precheck only. A manager still decides business approval." if page["page"] == 1 else "Payment entries describe this fictional hotel's record. Missing allocations remain unstated.")
        for n, line in enumerate(wrapped(note, "ExpenseSans", 9, w - 110)):
            c.drawString(55, 130 - n * 13, line)
        c.setFont("ExpenseSans", 8)
        c.drawString(42, 62, "All organizations, people and transactions in this document are fictional.")
        c.drawRightString(w - 42, 42, f"{page['page']} / 2")
        c.showPage()
    c.save()


def build(output):
    FIXTURE.mkdir(parents=True, exist_ok=True)
    output.mkdir(parents=True, exist_ok=True)
    domain, clarified = make_domains()
    (FIXTURE / "source_sop.txt").write_bytes(text_bytes(POLICY_LINES))
    (FIXTURE / "expert_teaching_reference.txt").write_bytes(text_bytes(TEACHING_LINES))
    write_json(FIXTURE / "domain_v0.json", domain)
    write_json(FIXTURE / "rules_v1_reference.json", clarified)
    cases, documents, expected, test_plan = [], [], [], []
    full_actions = ["ready_for_approval", "ready_for_approval", "hold_case", "hold_case", "ready_for_approval", "return_for_correction"]
    initial_actions = ["ready_for_approval", "hold_case", "hold_case", "hold_case", "hold_case", "hold_case"]
    rationales = [
        "Personal receipt, guest, approved stay dates and explicitly paid employee amount match.",
        "Under the reviewed company-folio acceptance condition, the stated employee payment of JPY 34,800 matches the claim. The company prepayment is not claimed.",
        "The employee payment amount and its payment status are not stated. Neither the claim nor the total establishes who paid; do not calculate an allocation.",
        "The hotel stay ends on 2026-09-20 but the approved stay ends on 2026-09-19. The extension is awaiting a manager's decision, despite matching payment and claim amounts.",
        "An unused company-addressed folio independently states a paid employee amount of JPY 27,600 matching the claim, guest and approved dates.",
        "The claim is JPY 42,400 but the explicitly paid employee amount is JPY 26,400. Return the mismatch; the company-folio acceptance condition does not authorize claiming the total.",
    ]
    state_by_action = {a["action_id"]: a["effects"][0]["value"] for a in domain["actions"]}
    for index, record in enumerate(RECORDS):
        cid = DOMAIN_ID + "_" + record["suffix"]
        facts, pages, field_map = make_documents(record)
        filename = record["claim"] + ".pdf"
        relative_path = Path("case_inputs") / record["split"] / filename
        pdf = output / relative_path
        render_pdf(pdf, record, pages)
        pdf_hash = sha(pdf.read_bytes())
        source_id = "expense_document_" + record["claim"].split("-")[1]
        evidence = {}
        for fid, mapping in field_map.items():
            rendered_quote = "\n".join(wrapped(mapping["quote"], "ExpenseSans", 11, A4[0] - 84))
            evidence[fid] = {"value": mapping["value"], "status": mapping["status"], "source_refs": [{"source_id": source_id, "version_hash": pdf_hash, "locator": f"page:{mapping['page']}", "quote": rendered_quote}], "content_line": mapping["content_line"]}
        documents.append({"case_id": cid, "claim_id": record["claim"], "source_id": source_id, "filename": filename, "relative_path": relative_path.as_posix(), "version_hash": pdf_hash, "pages": pages, "field_evidence": evidence})
        raw_text = "\n\n".join(f"Page {p['page']}: {p['organization']} | {p['title']}\n" + "\n".join(p["lines"]) for p in pages)
        cases.append({"case_id": cid, "domain_id": DOMAIN_ID, "split": record["split"], "stratum": record["stratum"], "facts": facts, "raw_text": raw_text, "initial_state": {"status": "NEW"}})
        action = full_actions[index]
        expected.append({"case_id": cid, "expected_action_id": action, "expected_state": {"status": state_by_action[action]}, "critical_wrong_actions": ["ready_for_approval"] if action != "ready_for_approval" else [], "rationale": "Private author-prepared label for the complete reviewed policy; not a run result. " + rationales[index]})
        test_plan.append({"case_id": cid, "split": record["split"], "initial_policy_expected_action_id": initial_actions[index], "reviewed_policy_expected_action_id": action, "measured_result": None})
    write_json(FIXTURE / "cases.json", cases)
    write_json(FIXTURE / "expected_private_to_scorer.json", expected)
    write_json(FIXTURE / "case_documents.json", {"schema_version": "1.0", "fictional": True, "case_field_origin": "Author-prepared transcription of the exact generated document lines; not model extraction.", "documents": documents})
    (output / "policy").mkdir(exist_ok=True)
    (output / "owner_review").mkdir(exist_ok=True)
    (output / "policy" / "source_sop.txt").write_bytes(text_bytes(POLICY_LINES))
    (output / "owner_review" / "expert_teaching_draft.txt").write_bytes(text_bytes(TEACHING_LINES))
    write_json(output / "evaluation" / "expected_private_to_scorer.json", expected)
    write_json(output / "evaluation" / "test_plan_private.json", {"status": "NOT_EXECUTED", "approval": "All supplied rule versions and the owner explanation are drafts.", "cases": test_plan})
    write_json(output / "evaluation" / "case_field_evidence_private.json", {"case_field_origin": "Author-prepared transcription; not model extraction.", "documents": documents})
    readme = """FICTIONAL EXPENSE REVIEW INPUT PACK

Purpose
Test a documentary precheck for business-trip accommodation reimbursement.
The only actions update an isolated case status. No expense is approved and
no payment or message is sent.

Contents
policy/source_sop.txt: initial procedure, including its recorded evidence gap.
case_inputs/dev/: four development cases, two pages each (claim and hotel).
case_inputs/holdout/: two cases to keep out of task-owner teaching.
owner_review/expert_teaching_draft.txt: proposed clarification; not approved.
evaluation/: private author-prepared labels, field evidence and test plan.
Never upload evaluation files as model sources or include them in prompts.

Review and comparison
Review the initial procedure and extracted fields before approving a workflow.
Run the initial conditions from NEW. Use development cases to ask the task
owner what is missing. Review the proposed explanation and derived conditions
before explicitly approving them. Compare the same cases from the same NEW
state, then check the two cases not used for the explanation.
The field evidence map is an author transcription of the supplied documents;
it is not evidence that a model has extracted those fields.

Boundaries
READY_FOR_BUSINESS_APPROVAL means documentary precheck complete, not approval
of an expense. HELD can mean missing evidence or a manager's business decision.
RETURNED_FOR_CORRECTION records a known mismatch without sending anything.
The private expected outcomes are planned labels, not observed AI results.
This six-case set does not establish general accuracy or whole-job automation.
All company policies, organizations, people and transactions are fictional.
"""
    (output / "README.txt").write_text(readme, encoding="utf-8")
    (FIXTURE / "README.txt").write_text(readme + "\nBuild: python3 tools/build_expense_demo_materials.py\n", encoding="utf-8")
    archive = output.with_suffix(".zip")
    with zipfile.ZipFile(archive, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for file in sorted(output.rglob("*")):
            if file.is_file():
                zi = zipfile.ZipInfo((Path(output.name) / file.relative_to(output)).as_posix(), date_time=(2026, 10, 1, 0, 0, 0))
                zi.compress_type = zipfile.ZIP_DEFLATED
                zi.external_attr = 0o100644 << 16
                zf.writestr(zi, file.read_bytes())
    return {"fixture": str(FIXTURE), "output": str(output), "archive": str(archive), "cases": len(cases), "pdf_pages": len(cases) * 2, "status": "INPUTS_CREATED_NOT_EXECUTED"}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=ROOT / "output" / "Expense_Demo_Data")
    args = parser.parse_args()
    print(json.dumps(build(args.output.resolve()), indent=2))


if __name__ == "__main__":
    main()
