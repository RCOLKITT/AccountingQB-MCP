"""Getting-paid loop (Phase 5): send an invoice + chase overdue — real customer
emails, so both tools are confirm-gated and reminders default to a preview that
sends nothing."""

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "mcpb" / "src"))

import accountingqb.server as s  # noqa: E402


def _inv(id, doc, cust, total, bal, due, email="pat@acme.com"):
    d = {
        "Id": id,
        "DocNumber": doc,
        "CustomerRef": {"name": cust},
        "TotalAmt": total,
        "Balance": bal,
        "DueDate": due,
    }
    if email:
        d["BillEmail"] = {"Address": email}
    return d


def test_send_invoice_calls_send_endpoint(monkeypatch):
    calls = []

    async def fake_read(entity, eid):
        return {"Invoice": _inv("42", "1042", "Acme", 500, 500, "2026-08-01")}

    async def fake_request(method, endpoint, params=None, json_body=None):
        calls.append((method, endpoint, params))
        return {
            "Invoice": {
                "EmailStatus": "EmailSent",
                "BillEmail": {"Address": "pat@acme.com"},
            }
        }

    monkeypatch.setattr(s, "qb_read", fake_read)
    monkeypatch.setattr(s, "qb_request", fake_request)
    monkeypatch.setattr(s, "_demo_active", lambda: False)
    out = asyncio.run(s.qb_send_invoice("42"))
    assert calls == [("POST", "invoice/42/send", None)]
    assert "✅" in out and "EmailSent" in out and "pat@acme.com" in out


def test_send_invoice_override_recipient(monkeypatch):
    calls = []

    async def fake_read(entity, eid):
        return {"Invoice": _inv("42", "1042", "Acme", 500, 500, "2026-08-01", email="")}

    async def fake_request(method, endpoint, params=None, json_body=None):
        calls.append(params)
        return {"Invoice": {"EmailStatus": "EmailSent"}}

    monkeypatch.setattr(s, "qb_read", fake_read)
    monkeypatch.setattr(s, "qb_request", fake_request)
    monkeypatch.setattr(s, "_demo_active", lambda: False)
    out = asyncio.run(s.qb_send_invoice("42", send_to="new@acme.com"))
    assert calls == [{"sendTo": "new@acme.com"}]
    assert "new@acme.com" in out


def test_send_invoice_no_email_refuses(monkeypatch):
    async def fake_read(entity, eid):
        return {"Invoice": _inv("7", "1007", "Acme", 100, 100, "2026-08-01", email="")}

    monkeypatch.setattr(s, "qb_read", fake_read)
    monkeypatch.setattr(s, "_demo_active", lambda: False)
    out = asyncio.run(s.qb_send_invoice("7"))
    assert "no email on file" in out and "send_to" in out


def _overdue_world(monkeypatch, sent_spy=None):
    invoices = [
        _inv("1", "1001", "Acme", 500, 500, "2026-07-01"),  # overdue, emailable
        _inv("2", "1002", "Bramble", 800, 800, "2026-06-15"),  # overdue, emailable
        _inv(
            "3", "1003", "NoEmail Co", 300, 300, "2026-07-10", email=""
        ),  # overdue, no email
        _inv("4", "1004", "Future", 900, 900, "2099-01-01"),  # not overdue
        _inv("5", "1005", "Paid", 400, 0, "2026-01-01"),  # paid (Balance 0)
    ]

    async def fake_query_all(q, **kw):
        # tool queries Balance > 0, so drop the paid one like QBO would
        return {
            "QueryResponse": {
                "Invoice": [i for i in invoices if float(i["Balance"]) > 0]
            }
        }

    async def fake_request(method, endpoint, params=None, json_body=None):
        if sent_spy is not None and "/send" in endpoint:
            sent_spy.append(endpoint)
        return {"Invoice": {"EmailStatus": "EmailSent"}}

    monkeypatch.setattr(s, "qb_query_all", fake_query_all)
    monkeypatch.setattr(s, "qb_request", fake_request)
    monkeypatch.setattr(s, "_demo_active", lambda: False)


def test_reminders_preview_sends_nothing(monkeypatch):
    spy = []
    _overdue_world(monkeypatch, spy)
    out = asyncio.run(s.qb_send_payment_reminders(as_of_date="2026-09-01"))
    assert spy == []  # preview NEVER emails
    assert "Nothing sent yet" in out
    assert "Acme" in out and "Bramble" in out
    assert "$1,600.00 open" in out  # 500+800+300 overdue; future + paid excluded
    # no-email invoice surfaced separately, not emailed
    assert "No email on file (1)" in out and "NoEmail Co" in out
    assert "Future" not in out and "Paid" not in out


def test_reminders_apply_emails_only_overdue_with_email(monkeypatch):
    spy = []
    _overdue_world(monkeypatch, spy)
    out = asyncio.run(s.qb_send_payment_reminders(as_of_date="2026-09-01", apply=True))
    assert sorted(spy) == ["invoice/1/send", "invoice/2/send"]  # 3 skipped (no email)
    assert "Emailed: 2" in out and "Skipped (no email): 1" in out


def test_reminders_none_overdue(monkeypatch):
    _overdue_world(monkeypatch, [])
    out = asyncio.run(s.qb_send_payment_reminders(as_of_date="2020-01-01"))
    assert "No overdue invoices" in out
