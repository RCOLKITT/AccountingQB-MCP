"""
QuickBooks Online MCP Server — Production Edition

A comprehensive MCP server for sole proprietors and small businesses.
Covers all QuickBooks Online entity types: transactions (purchases, deposits,
transfers, journal entries, bills, payments), reports (P&L, balance sheet,
cash flow, general ledger, AP/AR aging, trial balance), and entity management
(vendors, customers, accounts, items).

Built with FastMCP using flat parameters (required for Claude Desktop compatibility).
"""

import os
import json
import httpx
from datetime import datetime, timedelta
from typing import Optional
from mcp.server.fastmcp import FastMCP

mcp = FastMCP("quickbooks")

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
QB_CLIENT_ID = os.environ.get("QB_CLIENT_ID", "")
QB_CLIENT_SECRET = os.environ.get("QB_CLIENT_SECRET", "")
QB_REDIRECT_URI = os.environ.get("QB_REDIRECT_URI", "http://localhost:8080/callback")
QB_REALM_ID = os.environ.get("QB_REALM_ID", "")
QB_REFRESH_TOKEN = os.environ.get("QB_REFRESH_TOKEN", "")
# Prefer persisted refresh token (auto-saved after each OAuth exchange)
_token_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".qb_refresh_token")
if os.path.exists(_token_file):
    try:
        with open(_token_file) as _f:
            _saved = _f.read().strip()
        if _saved:
            QB_REFRESH_TOKEN = _saved
    except OSError:
        pass
QB_ENVIRONMENT = os.environ.get("QB_ENVIRONMENT", "production")

BASE_URL = (
    "https://quickbooks.api.intuit.com" if QB_ENVIRONMENT == "production"
    else "https://sandbox-quickbooks.api.intuit.com"
)
AUTH_URL = "https://oauth.platform.intuit.com/oauth2/v1/tokens/bearer"

_access_token = None
_token_expiry = None


# ---------------------------------------------------------------------------
# Auth & HTTP helpers
# ---------------------------------------------------------------------------
async def get_access_token() -> str:
    global _access_token, _token_expiry
    if _access_token and _token_expiry and datetime.now() < _token_expiry:
        return _access_token

    if not QB_CLIENT_ID or not QB_CLIENT_SECRET or not QB_REFRESH_TOKEN:
        raise ValueError(
            "QuickBooks credentials not configured. Set QB_CLIENT_ID, "
            "QB_CLIENT_SECRET, and QB_REFRESH_TOKEN environment variables."
        )

    async with httpx.AsyncClient() as client:
        resp = await client.post(AUTH_URL, data={
            "grant_type": "refresh_token",
            "refresh_token": QB_REFRESH_TOKEN,
            "client_id": QB_CLIENT_ID,
            "client_secret": QB_CLIENT_SECRET,
        }, headers={"Accept": "application/json"})
        resp.raise_for_status()
        data = resp.json()

    _access_token = data["access_token"]
    _token_expiry = datetime.now() + timedelta(seconds=data.get("expires_in", 3600) - 60)
    new_refresh = data.get("refresh_token")
    if new_refresh and new_refresh != QB_REFRESH_TOKEN:
        # Persist the new refresh token so restarts don't lose it.
        # Save to a file next to server.py; also update the in-memory global.
        global QB_REFRESH_TOKEN
        QB_REFRESH_TOKEN = new_refresh
        os.environ["QB_REFRESH_TOKEN"] = new_refresh
        token_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".qb_refresh_token")
        try:
            with open(token_path, "w") as f:
                f.write(new_refresh)
        except OSError:
            pass  # best-effort; token is still in memory for this session
    return _access_token


async def qb_request(method: str, endpoint: str, params: dict = None, json_body: dict = None) -> dict:
    token = await get_access_token()
    url = f"{BASE_URL}/v3/company/{QB_REALM_ID}/{endpoint}"
    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/json",
        "Content-Type": "application/json",
    }
    async with httpx.AsyncClient(timeout=30.0) as client:
        resp = await client.request(method, url, params=params, json=json_body, headers=headers)
        if resp.status_code == 401:
            global _access_token
            _access_token = None
            token = await get_access_token()
            headers["Authorization"] = f"Bearer {token}"
            resp = await client.request(method, url, params=params, json=json_body, headers=headers)
        resp.raise_for_status()
        return resp.json()


async def qb_query(query: str) -> dict:
    return await qb_request("GET", "query", params={"query": query})


async def qb_read(entity: str, entity_id: str) -> dict:
    return await qb_request("GET", f"{entity}/{entity_id}")


def fmt(amount) -> str:
    if amount is None:
        return "$0.00"
    return f"${float(amount):,.2f}"


def _parse_report_rows(rows, lines, indent=0):
    """Recursively parse QuickBooks report row structure."""
    for section in rows:
        header_data = section.get("Header", {})
        if header_data:
            cols = header_data.get("ColData", [])
            if cols:
                prefix = "###" if indent == 0 else "####"
                lines.append(f"\n{prefix} {cols[0].get('value', '')}")

        # Handle rows with ColData directly (leaf rows)
        col_data = section.get("ColData", [])
        if len(col_data) >= 2:
            rname = col_data[0].get("value", "")
            amount = col_data[-1].get("value", "0")
            pad = "  " * (indent + 1)
            try:
                lines.append(f"{pad}{rname}: {fmt(float(amount))}")
            except (ValueError, TypeError):
                lines.append(f"{pad}{rname}: {amount}")

        # Recurse into nested rows
        nested = section.get("Rows", {}).get("Row", [])
        if nested:
            _parse_report_rows(nested, lines, indent + 1)

        summary = section.get("Summary", {})
        if summary:
            cols = summary.get("ColData", [])
            if len(cols) >= 2:
                try:
                    lines.append(f"**{cols[0].get('value', '')}: {fmt(float(cols[-1].get('value', '0')))}**")
                except (ValueError, TypeError):
                    lines.append(f"**{cols[0].get('value', '')}: {cols[-1].get('value', '')}**")


# ===================================================================
# COMPANY INFO
# ===================================================================

@mcp.tool()
async def qb_company_info() -> str:
    """Get QuickBooks company information including name, address, fiscal year, and subscription status."""
    result = await qb_query("SELECT * FROM CompanyInfo")
    info = result.get("QueryResponse", {}).get("CompanyInfo", [{}])[0]
    lines = ["## QuickBooks Company Info\n"]
    lines.append(f"- **Company:** {info.get('CompanyName', 'N/A')}")
    lines.append(f"- **Legal Name:** {info.get('LegalName', 'N/A')}")
    lines.append(f"- **EIN:** {info.get('EIN', 'N/A')}")
    lines.append(f"- **Industry:** {info.get('IndustryType', 'N/A')}")
    lines.append(f"- **Fiscal Year Start:** {info.get('FiscalYearStartMonth', 'N/A')}")
    addr = info.get("CompanyAddr", {})
    if addr:
        lines.append(f"- **Address:** {addr.get('Line1', '')} {addr.get('City', '')}, {addr.get('CountrySubDivisionCode', '')} {addr.get('PostalCode', '')}")
    email = info.get("Email", {}).get("Address", "")
    if email:
        lines.append(f"- **Email:** {email}")
    phone = info.get("PrimaryPhone", {}).get("FreeFormNumber", "")
    if phone:
        lines.append(f"- **Phone:** {phone}")
    return "\n".join(lines)


# ===================================================================
# TRANSACTION QUERIES — Purchases / Expenses
# ===================================================================

@mcp.tool()
async def qb_list_transactions(start_date: str, end_date: str, vendor_name: str = "", min_amount: float = 0, max_amount: float = 0, max_results: int = 100) -> str:
    """List QuickBooks transactions (purchases, expenses) within a date range. Dates in YYYY-MM-DD format. Optionally filter by vendor_name, min_amount, max_amount."""
    query = (
        f"SELECT * FROM Purchase WHERE TxnDate >= '{start_date}' "
        f"AND TxnDate <= '{end_date}' MAXRESULTS {max_results}"
    )
    result = await qb_query(query)
    purchases = result.get("QueryResponse", {}).get("Purchase", [])

    if not purchases:
        return f"No transactions found between {start_date} and {end_date}."

    lines = [f"## Transactions: {start_date} to {end_date}\n"]
    total = 0.0
    count = 0
    for p in purchases:
        amt = float(p.get("TotalAmt", 0))
        vendor = p.get("EntityRef", {}).get("name", "Unknown")
        date = p.get("TxnDate", "N/A")
        memo = p.get("PrivateNote", "")
        pay_type = p.get("PaymentType", "")
        acct = p.get("AccountRef", {}).get("name", "")

        if min_amount and amt < min_amount:
            continue
        if max_amount and amt > max_amount:
            continue
        if vendor_name and vendor_name.lower() not in vendor.lower():
            continue

        total += amt
        count += 1
        detail_lines = []
        for line in p.get("Line", []):
            if line.get("DetailType") == "AccountBasedExpenseLineDetail":
                cat = line.get("AccountBasedExpenseLineDetail", {}).get("AccountRef", {}).get("name", "")
                detail_lines.append(f"  - {cat}: {fmt(line.get('Amount'))}")

        lines.append(f"**{date}** | {vendor} | {fmt(amt)} | ID: {p.get('Id', '')}")
        if pay_type or acct:
            lines.append(f"  Payment: {pay_type} via {acct}")
        if memo:
            lines.append(f"  Memo: {memo}")
        lines.extend(detail_lines)
        lines.append("")

    lines.append(f"\n**Total: {fmt(total)} ({count} transactions)**")
    return "\n".join(lines)


# ===================================================================
# TRANSACTION QUERIES — Deposits
# ===================================================================

@mcp.tool()
async def qb_list_deposits(start_date: str, end_date: str, max_results: int = 100) -> str:
    """List deposits (income, owner investments, bank deposits) within a date range. Dates in YYYY-MM-DD format. Use this to find income or money deposited into business accounts."""
    query = (
        f"SELECT * FROM Deposit WHERE TxnDate >= '{start_date}' "
        f"AND TxnDate <= '{end_date}' MAXRESULTS {max_results}"
    )
    result = await qb_query(query)
    deposits = result.get("QueryResponse", {}).get("Deposit", [])

    if not deposits:
        return f"No deposits found between {start_date} and {end_date}."

    lines = [f"## Deposits: {start_date} to {end_date}\n"]
    total = 0.0
    for d in deposits:
        amt = float(d.get("TotalAmt", 0))
        date = d.get("TxnDate", "N/A")
        acct = d.get("DepositToAccountRef", {}).get("name", "Unknown")
        memo = d.get("PrivateNote", "")
        total += amt

        detail_lines = []
        for line in d.get("Line", []):
            detail = line.get("DepositLineDetail", {})
            from_acct = detail.get("AccountRef", {}).get("name", "")
            from_name = detail.get("Entity", {}).get("name", "")
            line_amt = line.get("Amount", 0)
            desc = line.get("Description", "")
            source = from_name or from_acct or "Unknown source"
            detail_lines.append(f"  - {source}: {fmt(line_amt)}" + (f" ({desc})" if desc else ""))

        lines.append(f"**{date}** | {fmt(amt)} → {acct} | ID: {d.get('Id', '')}")
        if memo:
            lines.append(f"  Memo: {memo}")
        lines.extend(detail_lines)
        lines.append("")

    lines.append(f"\n**Total Deposits: {fmt(total)} ({len(deposits)} deposits)**")
    return "\n".join(lines)


# ===================================================================
# TRANSACTION QUERIES — Transfers
# ===================================================================

@mcp.tool()
async def qb_list_transfers(start_date: str, end_date: str, max_results: int = 100) -> str:
    """List transfers between accounts within a date range. Dates in YYYY-MM-DD format. Use this to see money moved between business bank accounts or credit cards."""
    query = (
        f"SELECT * FROM Transfer WHERE TxnDate >= '{start_date}' "
        f"AND TxnDate <= '{end_date}' MAXRESULTS {max_results}"
    )
    result = await qb_query(query)
    transfers = result.get("QueryResponse", {}).get("Transfer", [])

    if not transfers:
        return f"No transfers found between {start_date} and {end_date}."

    lines = [f"## Transfers: {start_date} to {end_date}\n"]
    total = 0.0
    for t in transfers:
        amt = float(t.get("Amount", 0))
        date = t.get("TxnDate", "N/A")
        from_acct = t.get("FromAccountRef", {}).get("name", "Unknown")
        to_acct = t.get("ToAccountRef", {}).get("name", "Unknown")
        memo = t.get("PrivateNote", "")
        total += amt

        lines.append(f"**{date}** | {fmt(amt)} | {from_acct} → {to_acct} | ID: {t.get('Id', '')}")
        if memo:
            lines.append(f"  Memo: {memo}")
        lines.append("")

    lines.append(f"\n**Total Transfers: {fmt(total)} ({len(transfers)} transfers)**")
    return "\n".join(lines)


# ===================================================================
# TRANSACTION QUERIES — Journal Entries
# ===================================================================

@mcp.tool()
async def qb_list_journal_entries(start_date: str, end_date: str, max_results: int = 100) -> str:
    """List journal entries (adjustments, reclassifications) within a date range. Dates in YYYY-MM-DD format. Useful for finding accounting adjustments, corrections, and manual entries."""
    query = (
        f"SELECT * FROM JournalEntry WHERE TxnDate >= '{start_date}' "
        f"AND TxnDate <= '{end_date}' MAXRESULTS {max_results}"
    )
    result = await qb_query(query)
    entries = result.get("QueryResponse", {}).get("JournalEntry", [])

    if not entries:
        return f"No journal entries found between {start_date} and {end_date}."

    lines = [f"## Journal Entries: {start_date} to {end_date}\n"]
    for je in entries:
        date = je.get("TxnDate", "N/A")
        total = float(je.get("TotalAmt", 0))
        memo = je.get("PrivateNote", "")
        doc = je.get("DocNumber", "")
        adj = je.get("Adjustment", False)

        lines.append(f"**{date}** | {fmt(total)} | ID: {je.get('Id', '')}" + (f" | Doc#: {doc}" if doc else "") + (" [ADJUSTMENT]" if adj else ""))
        if memo:
            lines.append(f"  Memo: {memo}")

        for line in je.get("Line", []):
            detail = line.get("JournalEntryLineDetail", {})
            acct = detail.get("AccountRef", {}).get("name", "")
            posting = detail.get("PostingType", "")
            amt = line.get("Amount", 0)
            desc = line.get("Description", "")
            entity = detail.get("Entity", {}).get("name", "")
            lines.append(f"  - {posting} {acct}: {fmt(amt)}" + (f" ({entity})" if entity else "") + (f" — {desc}" if desc else ""))
        lines.append("")

    lines.append(f"**{len(entries)} journal entries found**")
    return "\n".join(lines)


# ===================================================================
# TRANSACTION QUERIES — Bills (Accounts Payable)
# ===================================================================

@mcp.tool()
async def qb_list_bills(start_date: str, end_date: str, vendor_name: str = "", max_results: int = 100) -> str:
    """List bills (accounts payable) within a date range. Dates in YYYY-MM-DD. Optionally filter by vendor_name. Shows what you owe to vendors."""
    query = f"SELECT * FROM Bill WHERE TxnDate >= '{start_date}' AND TxnDate <= '{end_date}'"
    if vendor_name:
        query += f" AND VendorRef LIKE '%{vendor_name}%'"
    query += f" MAXRESULTS {max_results}"

    result = await qb_query(query)
    bills = result.get("QueryResponse", {}).get("Bill", [])

    if not bills:
        return f"No bills found between {start_date} and {end_date}."

    lines = [f"## Bills: {start_date} to {end_date}\n"]
    total = 0.0
    total_balance = 0.0
    for b in bills:
        amt = float(b.get("TotalAmt", 0))
        balance = float(b.get("Balance", 0))
        vendor = b.get("VendorRef", {}).get("name", "Unknown")
        date = b.get("TxnDate", "N/A")
        due = b.get("DueDate", "N/A")
        memo = b.get("PrivateNote", "")
        total += amt
        total_balance += balance

        status = "PAID" if balance == 0 else f"DUE: {fmt(balance)}"
        lines.append(f"**{date}** | {vendor} | {fmt(amt)} | {status} | Due: {due} | ID: {b.get('Id', '')}")
        if memo:
            lines.append(f"  Memo: {memo}")

        for line in b.get("Line", []):
            if line.get("DetailType") == "AccountBasedExpenseLineDetail":
                cat = line.get("AccountBasedExpenseLineDetail", {}).get("AccountRef", {}).get("name", "")
                lines.append(f"  - {cat}: {fmt(line.get('Amount'))}")
        lines.append("")

    lines.append(f"\n**Total Billed: {fmt(total)} | Outstanding: {fmt(total_balance)} ({len(bills)} bills)**")
    return "\n".join(lines)


# ===================================================================
# TRANSACTION QUERIES — Bill Payments
# ===================================================================

@mcp.tool()
async def qb_list_bill_payments(start_date: str, end_date: str, max_results: int = 100) -> str:
    """List bill payments within a date range. Dates in YYYY-MM-DD. Shows payments made against bills (accounts payable)."""
    query = (
        f"SELECT * FROM BillPayment WHERE TxnDate >= '{start_date}' "
        f"AND TxnDate <= '{end_date}' MAXRESULTS {max_results}"
    )
    result = await qb_query(query)
    payments = result.get("QueryResponse", {}).get("BillPayment", [])

    if not payments:
        return f"No bill payments found between {start_date} and {end_date}."

    lines = [f"## Bill Payments: {start_date} to {end_date}\n"]
    total = 0.0
    for bp in payments:
        amt = float(bp.get("TotalAmt", 0))
        vendor = bp.get("VendorRef", {}).get("name", "Unknown")
        date = bp.get("TxnDate", "N/A")
        pay_type = bp.get("PayType", "")
        total += amt

        acct_name = ""
        if pay_type == "Check":
            acct_name = bp.get("CheckPayment", {}).get("BankAccountRef", {}).get("name", "")
        elif pay_type == "CreditCard":
            acct_name = bp.get("CreditCardPayment", {}).get("CCAccountRef", {}).get("name", "")

        lines.append(f"**{date}** | {vendor} | {fmt(amt)} | {pay_type} via {acct_name} | ID: {bp.get('Id', '')}")
        lines.append("")

    lines.append(f"\n**Total Paid: {fmt(total)} ({len(payments)} payments)**")
    return "\n".join(lines)


# ===================================================================
# TRANSACTION QUERIES — Sales Receipts
# ===================================================================

@mcp.tool()
async def qb_list_sales_receipts(start_date: str, end_date: str, max_results: int = 100) -> str:
    """List sales receipts (direct sales, not invoiced) within a date range. Dates in YYYY-MM-DD."""
    query = (
        f"SELECT * FROM SalesReceipt WHERE TxnDate >= '{start_date}' "
        f"AND TxnDate <= '{end_date}' MAXRESULTS {max_results}"
    )
    result = await qb_query(query)
    receipts = result.get("QueryResponse", {}).get("SalesReceipt", [])

    if not receipts:
        return f"No sales receipts found between {start_date} and {end_date}."

    lines = [f"## Sales Receipts: {start_date} to {end_date}\n"]
    total = 0.0
    for sr in receipts:
        amt = float(sr.get("TotalAmt", 0))
        customer = sr.get("CustomerRef", {}).get("name", "Walk-in")
        date = sr.get("TxnDate", "N/A")
        doc = sr.get("DocNumber", "")
        total += amt

        lines.append(f"**{date}** | {customer} | {fmt(amt)} | ID: {sr.get('Id', '')}" + (f" | #{doc}" if doc else ""))
        for line in sr.get("Line", []):
            desc = line.get("Description", "")
            line_amt = line.get("Amount", 0)
            if desc and line_amt:
                lines.append(f"  - {desc}: {fmt(line_amt)}")
        lines.append("")

    lines.append(f"\n**Total Sales: {fmt(total)} ({len(receipts)} receipts)**")
    return "\n".join(lines)


# ===================================================================
# TRANSACTION QUERIES — Customer Payments
# ===================================================================

@mcp.tool()
async def qb_list_payments(start_date: str, end_date: str, max_results: int = 100) -> str:
    """List customer payments received within a date range. Dates in YYYY-MM-DD. Shows payments applied against invoices."""
    query = (
        f"SELECT * FROM Payment WHERE TxnDate >= '{start_date}' "
        f"AND TxnDate <= '{end_date}' MAXRESULTS {max_results}"
    )
    result = await qb_query(query)
    payments = result.get("QueryResponse", {}).get("Payment", [])

    if not payments:
        return f"No customer payments found between {start_date} and {end_date}."

    lines = [f"## Customer Payments: {start_date} to {end_date}\n"]
    total = 0.0
    for p in payments:
        amt = float(p.get("TotalAmt", 0))
        customer = p.get("CustomerRef", {}).get("name", "Unknown")
        date = p.get("TxnDate", "N/A")
        deposit_acct = p.get("DepositToAccountRef", {}).get("name", "Undeposited")
        total += amt

        lines.append(f"**{date}** | {customer} | {fmt(amt)} → {deposit_acct} | ID: {p.get('Id', '')}")
        lines.append("")

    lines.append(f"\n**Total Received: {fmt(total)} ({len(payments)} payments)**")
    return "\n".join(lines)


# ===================================================================
# TRANSACTION QUERIES — Invoices
# ===================================================================

@mcp.tool()
async def qb_list_invoices(start_date: str, end_date: str, customer_name: str = "", status: str = "", max_results: int = 100) -> str:
    """List invoices within a date range. Dates in YYYY-MM-DD. Filter by customer_name and/or status (Paid, Unpaid, Overdue). Shows accounts receivable."""
    query = f"SELECT * FROM Invoice WHERE TxnDate >= '{start_date}' AND TxnDate <= '{end_date}'"
    query += f" MAXRESULTS {max_results}"

    result = await qb_query(query)
    invoices = result.get("QueryResponse", {}).get("Invoice", [])

    if not invoices:
        return f"No invoices found between {start_date} and {end_date}."

    lines = [f"## Invoices: {start_date} to {end_date}\n"]
    total = 0.0
    total_balance = 0.0
    count = 0
    for inv in invoices:
        customer = inv.get("CustomerRef", {}).get("name", "Unknown")
        if customer_name and customer_name.lower() not in customer.lower():
            continue

        amt = float(inv.get("TotalAmt", 0))
        balance = float(inv.get("Balance", 0))
        date = inv.get("TxnDate", "N/A")
        due = inv.get("DueDate", "N/A")
        doc = inv.get("DocNumber", "")

        inv_status = "PAID" if balance == 0 else "UNPAID"
        if balance > 0 and due != "N/A":
            try:
                if datetime.strptime(due, "%Y-%m-%d") < datetime.now():
                    inv_status = "OVERDUE"
            except ValueError:
                pass

        if status and status.lower() != inv_status.lower():
            continue

        total += amt
        total_balance += balance
        count += 1

        lines.append(f"**{date}** | #{doc} | {customer} | {fmt(amt)} | {inv_status} | Due: {due} | ID: {inv.get('Id', '')}")
        lines.append("")

    lines.append(f"\n**Total Invoiced: {fmt(total)} | Outstanding: {fmt(total_balance)} ({count} invoices)**")
    return "\n".join(lines)


# ===================================================================
# UNIVERSAL TRANSACTION SEARCH
# ===================================================================

@mcp.tool()
async def qb_search_transactions(start_date: str, end_date: str, search_term: str = "", max_results: int = 50) -> str:
    """Search across ALL transaction types (purchases, deposits, transfers, journal entries, bills, payments, invoices, sales receipts) in a date range. Optionally filter by search_term (matches vendor, customer, memo, account names). Dates in YYYY-MM-DD."""
    all_txns = []
    term = search_term.lower()

    entity_configs = [
        ("Purchase", "Purchase", lambda p: {
            "type": "Purchase", "id": p.get("Id"), "date": p.get("TxnDate", ""),
            "amount": float(p.get("TotalAmt", 0)),
            "entity": p.get("EntityRef", {}).get("name", ""),
            "memo": p.get("PrivateNote", ""),
            "account": p.get("AccountRef", {}).get("name", ""),
        }),
        ("Deposit", "Deposit", lambda d: {
            "type": "Deposit", "id": d.get("Id"), "date": d.get("TxnDate", ""),
            "amount": float(d.get("TotalAmt", 0)),
            "entity": ", ".join(
                line.get("DepositLineDetail", {}).get("Entity", {}).get("name", "")
                for line in d.get("Line", []) if line.get("DepositLineDetail", {}).get("Entity", {}).get("name")
            ) or "N/A",
            "memo": d.get("PrivateNote", ""),
            "account": d.get("DepositToAccountRef", {}).get("name", ""),
        }),
        ("Transfer", "Transfer", lambda t: {
            "type": "Transfer", "id": t.get("Id"), "date": t.get("TxnDate", ""),
            "amount": float(t.get("Amount", 0)),
            "entity": f"{t.get('FromAccountRef', {}).get('name', '')} → {t.get('ToAccountRef', {}).get('name', '')}",
            "memo": t.get("PrivateNote", ""),
            "account": "",
        }),
        ("JournalEntry", "JournalEntry", lambda j: {
            "type": "Journal Entry", "id": j.get("Id"), "date": j.get("TxnDate", ""),
            "amount": float(j.get("TotalAmt", 0)),
            "entity": ", ".join(
                line.get("JournalEntryLineDetail", {}).get("AccountRef", {}).get("name", "")
                for line in j.get("Line", []) if line.get("JournalEntryLineDetail", {}).get("AccountRef", {}).get("name")
            ),
            "memo": j.get("PrivateNote", ""),
            "account": "",
        }),
        ("Bill", "Bill", lambda b: {
            "type": "Bill", "id": b.get("Id"), "date": b.get("TxnDate", ""),
            "amount": float(b.get("TotalAmt", 0)),
            "entity": b.get("VendorRef", {}).get("name", ""),
            "memo": b.get("PrivateNote", ""),
            "account": "",
        }),
        ("Invoice", "Invoice", lambda i: {
            "type": "Invoice", "id": i.get("Id"), "date": i.get("TxnDate", ""),
            "amount": float(i.get("TotalAmt", 0)),
            "entity": i.get("CustomerRef", {}).get("name", ""),
            "memo": i.get("PrivateNote", ""),
            "account": "",
        }),
        ("Payment", "Payment", lambda p: {
            "type": "Payment", "id": p.get("Id"), "date": p.get("TxnDate", ""),
            "amount": float(p.get("TotalAmt", 0)),
            "entity": p.get("CustomerRef", {}).get("name", ""),
            "memo": p.get("PrivateNote", ""),
            "account": p.get("DepositToAccountRef", {}).get("name", ""),
        }),
        ("SalesReceipt", "SalesReceipt", lambda s: {
            "type": "Sales Receipt", "id": s.get("Id"), "date": s.get("TxnDate", ""),
            "amount": float(s.get("TotalAmt", 0)),
            "entity": s.get("CustomerRef", {}).get("name", ""),
            "memo": s.get("PrivateNote", ""),
            "account": "",
        }),
    ]

    for qb_entity, response_key, transform in entity_configs:
        try:
            q = f"SELECT * FROM {qb_entity} WHERE TxnDate >= '{start_date}' AND TxnDate <= '{end_date}' MAXRESULTS {max_results}"
            res = await qb_query(q)
            items = res.get("QueryResponse", {}).get(response_key, [])
            for item in items:
                txn = transform(item)
                if not term or any(term in str(v).lower() for v in txn.values()):
                    all_txns.append(txn)
        except Exception:
            pass  # Some entity types may not be available

    all_txns.sort(key=lambda x: x.get("date", ""), reverse=True)

    if not all_txns:
        msg = f"No transactions found between {start_date} and {end_date}"
        if search_term:
            msg += f" matching '{search_term}'"
        return msg + "."

    lines = [f"## All Transactions: {start_date} to {end_date}"]
    if search_term:
        lines[0] += f" (filter: '{search_term}')"
    lines.append("")

    total = sum(t["amount"] for t in all_txns)
    for txn in all_txns[:max_results]:
        lines.append(f"**{txn['date']}** | [{txn['type']}] {txn['entity']} | {fmt(txn['amount'])} | ID: {txn['id']}")
        if txn.get("memo"):
            lines.append(f"  Memo: {txn['memo']}")

    lines.append(f"\n**{len(all_txns)} transactions | Total: {fmt(total)}**")
    return "\n".join(lines)


# ===================================================================
# EXPENSE SUMMARY
# ===================================================================

@mcp.tool()
async def qb_expense_summary(start_date: str, end_date: str) -> str:
    """Get expenses grouped by category/account for a date range. Useful for Schedule C and tax deduction tracking. Dates in YYYY-MM-DD format."""
    query = (
        f"SELECT * FROM Purchase WHERE TxnDate >= '{start_date}' "
        f"AND TxnDate <= '{end_date}' MAXRESULTS 1000"
    )
    result = await qb_query(query)
    purchases = result.get("QueryResponse", {}).get("Purchase", [])

    categories = {}
    vendor_totals = {}
    grand_total = 0.0

    for p in purchases:
        vendor = p.get("EntityRef", {}).get("name", "Unknown")
        for line in p.get("Line", []):
            if line.get("DetailType") == "AccountBasedExpenseLineDetail":
                acct = line.get("AccountBasedExpenseLineDetail", {}).get("AccountRef", {}).get("name", "Uncategorized")
                amt = float(line.get("Amount", 0))
                categories.setdefault(acct, 0.0)
                categories[acct] += amt
                vendor_totals.setdefault(vendor, 0.0)
                vendor_totals[vendor] += amt
                grand_total += amt

    lines = [f"## Expense Summary: {start_date} to {end_date}\n"]
    lines.append("### By Category")
    for cat in sorted(categories, key=categories.get, reverse=True):
        lines.append(f"- **{cat}**: {fmt(categories[cat])}")

    lines.append(f"\n### Top Vendors")
    for v in sorted(vendor_totals, key=vendor_totals.get, reverse=True)[:20]:
        lines.append(f"- {v}: {fmt(vendor_totals[v])}")

    lines.append(f"\n**Grand Total: {fmt(grand_total)}**")
    return "\n".join(lines)


# ===================================================================
# REPORTS — Profit & Loss
# ===================================================================

@mcp.tool()
async def qb_profit_loss(start_date: str, end_date: str, summarize_by: str = "Total") -> str:
    """Generate a Profit & Loss (Income Statement) report. Dates in YYYY-MM-DD. summarize_by: Total, Month, Quarter, Year."""
    report = await qb_request("GET", "reports/ProfitAndLoss", params={
        "start_date": start_date,
        "end_date": end_date,
        "summarize_column_by": summarize_by,
    })

    header = report.get("Header", {})
    lines = [f"## Profit & Loss: {header.get('StartPeriod', '')} to {header.get('EndPeriod', '')}\n"]
    rows = report.get("Rows", {}).get("Row", [])
    _parse_report_rows(rows, lines)
    return "\n".join(lines)


# ===================================================================
# REPORTS — Balance Sheet
# ===================================================================

@mcp.tool()
async def qb_balance_sheet(as_of_date: str) -> str:
    """Generate a Balance Sheet report as of a specific date. Date in YYYY-MM-DD format."""
    report = await qb_request("GET", "reports/BalanceSheet", params={
        "date_macro": "",
        "start_date": as_of_date,
        "end_date": as_of_date,
    })

    lines = [f"## Balance Sheet as of {as_of_date}\n"]
    rows = report.get("Rows", {}).get("Row", [])
    _parse_report_rows(rows, lines)
    return "\n".join(lines)


# ===================================================================
# REPORTS — Cash Flow Statement
# ===================================================================

@mcp.tool()
async def qb_cash_flow(start_date: str, end_date: str) -> str:
    """Generate a Statement of Cash Flows report. Dates in YYYY-MM-DD. Shows operating, investing, and financing cash activities."""
    report = await qb_request("GET", "reports/CashFlow", params={
        "start_date": start_date,
        "end_date": end_date,
    })

    header = report.get("Header", {})
    lines = [f"## Statement of Cash Flows: {header.get('StartPeriod', '')} to {header.get('EndPeriod', '')}\n"]
    rows = report.get("Rows", {}).get("Row", [])
    _parse_report_rows(rows, lines)
    return "\n".join(lines)


# ===================================================================
# REPORTS — General Ledger
# ===================================================================

@mcp.tool()
async def qb_general_ledger(start_date: str, end_date: str, account_name: str = "") -> str:
    """Generate a General Ledger report showing all transactions by account. Dates in YYYY-MM-DD. Optionally filter by account_name."""
    params = {
        "start_date": start_date,
        "end_date": end_date,
    }
    if account_name:
        accounts = await qb_query(f"SELECT * FROM Account WHERE Name LIKE '%{account_name}%' MAXRESULTS 1")
        acct_list = accounts.get("QueryResponse", {}).get("Account", [])
        if acct_list:
            params["account"] = acct_list[0]["Id"]

    report = await qb_request("GET", "reports/GeneralLedger", params=params)

    header = report.get("Header", {})
    lines = [f"## General Ledger: {header.get('StartPeriod', '')} to {header.get('EndPeriod', '')}\n"]
    if account_name:
        lines.append(f"Filtered: {account_name}\n")

    rows = report.get("Rows", {}).get("Row", [])
    _parse_report_rows(rows, lines)
    return "\n".join(lines)


# ===================================================================
# REPORTS — Trial Balance
# ===================================================================

@mcp.tool()
async def qb_trial_balance(start_date: str, end_date: str) -> str:
    """Generate a Trial Balance report. Dates in YYYY-MM-DD. Shows all account debits and credits to verify books are balanced."""
    report = await qb_request("GET", "reports/TrialBalance", params={
        "start_date": start_date,
        "end_date": end_date,
    })

    header = report.get("Header", {})
    lines = [f"## Trial Balance: {header.get('StartPeriod', '')} to {header.get('EndPeriod', '')}\n"]
    rows = report.get("Rows", {}).get("Row", [])
    _parse_report_rows(rows, lines)
    return "\n".join(lines)


# ===================================================================
# REPORTS — Accounts Receivable Aging
# ===================================================================

@mcp.tool()
async def qb_ar_aging(as_of_date: str) -> str:
    """Generate an Accounts Receivable Aging report. Date in YYYY-MM-DD. Shows what customers owe you, grouped by how overdue."""
    report = await qb_request("GET", "reports/AgedReceivables", params={
        "date_macro": "",
        "start_date": as_of_date,
        "end_date": as_of_date,
    })

    lines = [f"## Accounts Receivable Aging as of {as_of_date}\n"]
    rows = report.get("Rows", {}).get("Row", [])
    _parse_report_rows(rows, lines)
    return "\n".join(lines)


# ===================================================================
# REPORTS — Accounts Payable Aging
# ===================================================================

@mcp.tool()
async def qb_ap_aging(as_of_date: str) -> str:
    """Generate an Accounts Payable Aging report. Date in YYYY-MM-DD. Shows what you owe vendors, grouped by how overdue."""
    report = await qb_request("GET", "reports/AgedPayables", params={
        "date_macro": "",
        "start_date": as_of_date,
        "end_date": as_of_date,
    })

    lines = [f"## Accounts Payable Aging as of {as_of_date}\n"]
    rows = report.get("Rows", {}).get("Row", [])
    _parse_report_rows(rows, lines)
    return "\n".join(lines)


# ===================================================================
# REPORTS — Tax Summary (Schedule C)
# ===================================================================

@mcp.tool()
async def qb_tax_summary(start_date: str, end_date: str) -> str:
    """Generate a tax-oriented summary mapping QuickBooks data to Schedule C lines. Dates in YYYY-MM-DD."""
    report = await qb_request("GET", "reports/ProfitAndLoss", params={
        "start_date": start_date,
        "end_date": end_date,
        "summarize_column_by": "Total",
    })

    schedule_c_map = {
        "Advertising": "Line 8 - Advertising",
        "Marketing": "Line 8 - Advertising",
        "Car and Truck": "Line 9 - Car and truck",
        "Automobile": "Line 9 - Car and truck",
        "Commissions": "Line 10 - Commissions",
        "Contract Labor": "Line 11 - Contract labor",
        "Depreciation": "Line 13 - Depreciation",
        "Insurance": "Line 15 - Insurance",
        "Interest": "Line 16 - Interest",
        "Legal": "Line 17 - Legal & professional",
        "Professional": "Line 17 - Legal & professional",
        "Accounting": "Line 17 - Legal & professional",
        "Bookkeeper": "Line 17 - Legal & professional",
        "Office": "Line 18 - Office expense",
        "Software": "Line 18 - Office expense",
        "Subscriptions": "Line 18 - Office expense",
        "Equipment": "Line 18 - Office expense",
        "Rent": "Line 20b - Rent",
        "Repairs": "Line 21 - Repairs",
        "Maintenance": "Line 21 - Repairs",
        "Supplies": "Line 22 - Supplies",
        "Taxes": "Line 23 - Taxes & licenses",
        "Travel": "Line 24a - Travel",
        "Meals": "Line 24b - Meals",
        "Utilities": "Line 25 - Utilities",
        "Telephone": "Line 25 - Utilities",
        "Internet": "Line 25 - Utilities",
        "Home Office": "Line 30 - Home office",
        "Mortgage": "Line 30 - Home office",
    }

    lines = [f"## Tax Summary (Schedule C): {start_date} to {end_date}\n"]
    schedule_c = {}

    rows = report.get("Rows", {}).get("Row", [])
    for section in rows:
        for row in section.get("Rows", {}).get("Row", []):
            col_data = row.get("ColData", [])
            if len(col_data) >= 2:
                rname = col_data[0].get("value", "")
                try:
                    amount = float(col_data[-1].get("value", "0"))
                except (ValueError, TypeError):
                    continue
                if amount == 0:
                    continue

                mapped = "Line 27 - Other expenses"
                for keyword, sc_line in schedule_c_map.items():
                    if keyword.lower() in rname.lower():
                        mapped = sc_line
                        break

                schedule_c.setdefault(mapped, [])
                schedule_c[mapped].append((rname, amount))

    for sc_line in sorted(schedule_c.keys()):
        items = schedule_c[sc_line]
        total = sum(a for _, a in items)
        lines.append(f"### {sc_line}: {fmt(total)}")
        for rname, a in items:
            lines.append(f"  - {rname}: {fmt(a)}")
        lines.append("")

    grand = sum(sum(a for _, a in items) for items in schedule_c.values())
    lines.append(f"\n**Total Deductible Expenses: {fmt(grand)}**")
    return "\n".join(lines)


# ===================================================================
# ENTITY MANAGEMENT — Accounts
# ===================================================================

@mcp.tool()
async def qb_list_accounts(max_results: int = 100) -> str:
    """List all chart of accounts (expense categories, income accounts, etc.) in QuickBooks."""
    query = f"SELECT * FROM Account MAXRESULTS {max_results}"
    result = await qb_query(query)
    accounts = result.get("QueryResponse", {}).get("Account", [])

    if not accounts:
        return "No accounts found."

    grouped = {}
    for a in accounts:
        atype = a.get("AccountType", "Other")
        grouped.setdefault(atype, []).append(a)

    lines = ["## Chart of Accounts\n"]
    for atype in sorted(grouped.keys()):
        lines.append(f"### {atype}")
        for a in grouped[atype]:
            aname = a.get("FullyQualifiedName", a.get("Name", "Unknown"))
            balance = fmt(a.get("CurrentBalance", 0))
            sub = a.get("AccountSubType", "")
            lines.append(f"- {aname} (ID: {a.get('Id')}) | {sub} | Balance: {balance}")
        lines.append("")
    return "\n".join(lines)


# ===================================================================
# ENTITY MANAGEMENT — Vendors
# ===================================================================

@mcp.tool()
async def qb_list_vendors(name: str = "", max_results: int = 50) -> str:
    """List vendors/suppliers in QuickBooks. Optionally filter by name."""
    query = "SELECT * FROM Vendor"
    if name:
        query += f" WHERE DisplayName LIKE '%{name}%'"
    query += f" MAXRESULTS {max_results}"

    result = await qb_query(query)
    vendors = result.get("QueryResponse", {}).get("Vendor", [])

    if not vendors:
        return "No vendors found."

    lines = [f"## Vendors ({len(vendors)} found)\n"]
    for v in vendors:
        vname = v.get("DisplayName", "Unknown")
        balance = fmt(v.get("Balance", 0))
        active = "Active" if v.get("Active", True) else "Inactive"
        email = v.get("PrimaryEmailAddr", {}).get("Address", "")
        lines.append(f"- **{vname}** (ID: {v.get('Id')}) | Balance: {balance} | {active}" + (f" | {email}" if email else ""))
    return "\n".join(lines)


@mcp.tool()
async def qb_create_vendor(display_name: str, email: str = "", phone: str = "", company_name: str = "") -> str:
    """Create a new vendor/supplier in QuickBooks. display_name is required. Optionally include email, phone, company_name."""
    vendor_body = {"DisplayName": display_name}
    if email:
        vendor_body["PrimaryEmailAddr"] = {"Address": email}
    if phone:
        vendor_body["PrimaryPhone"] = {"FreeFormNumber": phone}
    if company_name:
        vendor_body["CompanyName"] = company_name

    result = await qb_request("POST", "vendor", json_body=vendor_body)
    v = result.get("Vendor", {})
    return (
        f"Vendor created!\n"
        f"- Name: {v.get('DisplayName')}\n"
        f"- ID: {v.get('Id')}\n"
        f"- Balance: {fmt(v.get('Balance', 0))}"
    )


# ===================================================================
# ENTITY MANAGEMENT — Customers
# ===================================================================

@mcp.tool()
async def qb_list_customers(name: str = "", max_results: int = 50) -> str:
    """List customers in QuickBooks. Optionally filter by name."""
    query = "SELECT * FROM Customer"
    if name:
        query += f" WHERE DisplayName LIKE '%{name}%'"
    query += f" MAXRESULTS {max_results}"

    result = await qb_query(query)
    customers = result.get("QueryResponse", {}).get("Customer", [])

    if not customers:
        return "No customers found."

    lines = [f"## Customers ({len(customers)} found)\n"]
    for c in customers:
        cname = c.get("DisplayName", "Unknown")
        balance = fmt(c.get("Balance", 0))
        active = "Active" if c.get("Active", True) else "Inactive"
        email = c.get("PrimaryEmailAddr", {}).get("Address", "")
        lines.append(f"- **{cname}** (ID: {c.get('Id')}) | Balance: {balance} | {active}" + (f" | {email}" if email else ""))
    return "\n".join(lines)


@mcp.tool()
async def qb_create_customer(display_name: str, email: str = "", phone: str = "", company_name: str = "") -> str:
    """Create a new customer in QuickBooks. display_name is required. Optionally include email, phone, company_name."""
    customer_body = {"DisplayName": display_name}
    if email:
        customer_body["PrimaryEmailAddr"] = {"Address": email}
    if phone:
        customer_body["PrimaryPhone"] = {"FreeFormNumber": phone}
    if company_name:
        customer_body["CompanyName"] = company_name

    result = await qb_request("POST", "customer", json_body=customer_body)
    c = result.get("Customer", {})
    return (
        f"Customer created!\n"
        f"- Name: {c.get('DisplayName')}\n"
        f"- ID: {c.get('Id')}\n"
        f"- Balance: {fmt(c.get('Balance', 0))}"
    )


# ===================================================================
# ENTITY MANAGEMENT — Items / Products & Services
# ===================================================================

@mcp.tool()
async def qb_list_items(name: str = "", max_results: int = 100) -> str:
    """List products and services (items) in QuickBooks. Optionally filter by name. Items are used on invoices and sales receipts."""
    query = "SELECT * FROM Item"
    if name:
        query += f" WHERE Name LIKE '%{name}%'"
    query += f" MAXRESULTS {max_results}"

    result = await qb_query(query)
    items = result.get("QueryResponse", {}).get("Item", [])

    if not items:
        return "No items found."

    lines = [f"## Items/Products ({len(items)} found)\n"]
    for item in items:
        iname = item.get("Name", "Unknown")
        itype = item.get("Type", "")
        price = fmt(item.get("UnitPrice", 0))
        active = "Active" if item.get("Active", True) else "Inactive"
        income_acct = item.get("IncomeAccountRef", {}).get("name", "")
        expense_acct = item.get("ExpenseAccountRef", {}).get("name", "")

        lines.append(f"- **{iname}** (ID: {item.get('Id')}) | {itype} | Price: {price} | {active}")
        if income_acct:
            lines.append(f"  Income account: {income_acct}")
        if expense_acct:
            lines.append(f"  Expense account: {expense_acct}")
    return "\n".join(lines)


# ===================================================================
# TRANSACTION CREATION — Expenses / Purchases
# ===================================================================

@mcp.tool()
async def qb_create_expense(vendor_name: str, amount: float, account_name: str, date: str, description: str = "", payment_method: str = "") -> str:
    """Create a new expense/purchase in QuickBooks. vendor_name: payee, amount: total, account_name: expense category, date: YYYY-MM-DD, description: memo, payment_method: bank/card account name."""
    vendors = await qb_query(f"SELECT * FROM Vendor WHERE DisplayName LIKE '%{vendor_name}%' MAXRESULTS 1")
    vendor_list = vendors.get("QueryResponse", {}).get("Vendor", [])
    if not vendor_list:
        return f"Vendor '{vendor_name}' not found. Use qb_list_vendors to find existing vendors, or qb_create_vendor to create one."
    vendor = vendor_list[0]

    accounts = await qb_query(f"SELECT * FROM Account WHERE Name LIKE '%{account_name}%' AND AccountType = 'Expense' MAXRESULTS 1")
    account_list = accounts.get("QueryResponse", {}).get("Account", [])
    if not account_list:
        return f"Expense account '{account_name}' not found. Use qb_list_accounts to see available accounts."
    account = account_list[0]

    purchase_body = {
        "PaymentType": "Cash",
        "TxnDate": date,
        "EntityRef": {"value": vendor["Id"], "name": vendor["DisplayName"]},
        "Line": [{
            "DetailType": "AccountBasedExpenseLineDetail",
            "Amount": amount,
            "AccountBasedExpenseLineDetail": {
                "AccountRef": {"value": account["Id"], "name": account["Name"]}
            },
            "Description": description or ""
        }],
    }
    if description:
        purchase_body["PrivateNote"] = description

    if payment_method:
        pay_accounts = await qb_query(f"SELECT * FROM Account WHERE Name LIKE '%{payment_method}%' MAXRESULTS 1")
        pay_list = pay_accounts.get("QueryResponse", {}).get("Account", [])
        if pay_list:
            purchase_body["AccountRef"] = {"value": pay_list[0]["Id"], "name": pay_list[0]["Name"]}

    result = await qb_request("POST", "purchase", json_body=purchase_body)
    p = result.get("Purchase", {})
    return (
        f"Expense created!\n"
        f"- ID: {p.get('Id')}\n"
        f"- Vendor: {vendor['DisplayName']}\n"
        f"- Amount: {fmt(amount)}\n"
        f"- Category: {account['Name']}\n"
        f"- Date: {date}"
    )


# ===================================================================
# TRANSACTION CREATION — Invoices
# ===================================================================

@mcp.tool()
async def qb_create_invoice(customer_name: str, line_items: str, due_date: str = "", memo: str = "") -> str:
    """Create a customer invoice. line_items is a JSON string: [{"description": "...", "amount": 100}]. due_date in YYYY-MM-DD."""
    customers = await qb_query(f"SELECT * FROM Customer WHERE DisplayName LIKE '%{customer_name}%' MAXRESULTS 1")
    customer_list = customers.get("QueryResponse", {}).get("Customer", [])
    if not customer_list:
        return f"Customer '{customer_name}' not found. Use qb_list_customers or qb_create_customer."
    customer = customer_list[0]

    items = json.loads(line_items) if isinstance(line_items, str) else line_items
    inv_lines = []
    for item in items:
        inv_lines.append({
            "DetailType": "SalesItemLineDetail",
            "Amount": item.get("amount", 0),
            "Description": item.get("description", ""),
            "SalesItemLineDetail": {
                "Qty": item.get("quantity", 1),
                "UnitPrice": item.get("amount", 0) / max(item.get("quantity", 1), 1),
            }
        })

    invoice_body = {
        "CustomerRef": {"value": customer["Id"]},
        "Line": inv_lines,
    }
    if due_date:
        invoice_body["DueDate"] = due_date
    if memo:
        invoice_body["CustomerMemo"] = {"value": memo}

    result = await qb_request("POST", "invoice", json_body=invoice_body)
    inv = result.get("Invoice", {})
    return (
        f"Invoice created!\n"
        f"- Invoice #: {inv.get('DocNumber', 'N/A')}\n"
        f"- Customer: {customer['DisplayName']}\n"
        f"- Total: {fmt(inv.get('TotalAmt'))}\n"
        f"- Due: {inv.get('DueDate', 'N/A')}"
    )


# ===================================================================
# TRANSACTION CREATION — Journal Entries (Reclassify)
# ===================================================================

@mcp.tool()
async def qb_create_journal_entry(date: str, lines_json: str, memo: str = "") -> str:
    """Create a journal entry for reclassifications or adjustments. date: YYYY-MM-DD. lines_json is a JSON string: [{"account_name": "...", "amount": 100.00, "type": "Debit"}, {"account_name": "...", "amount": 100.00, "type": "Credit"}]. Debits and credits must balance."""
    entries = json.loads(lines_json) if isinstance(lines_json, str) else lines_json

    je_lines = []
    total_debit = 0.0
    total_credit = 0.0

    for entry in entries:
        acct_name = entry.get("account_name", "")
        amount = float(entry.get("amount", 0))
        posting_type = entry.get("type", "Debit")

        accounts = await qb_query(f"SELECT * FROM Account WHERE Name LIKE '%{acct_name}%' MAXRESULTS 1")
        acct_list = accounts.get("QueryResponse", {}).get("Account", [])
        if not acct_list:
            return f"Account '{acct_name}' not found. Use qb_list_accounts to see available accounts."
        acct = acct_list[0]

        if posting_type == "Debit":
            total_debit += amount
        else:
            total_credit += amount

        je_lines.append({
            "DetailType": "JournalEntryLineDetail",
            "Amount": amount,
            "Description": entry.get("description", ""),
            "JournalEntryLineDetail": {
                "PostingType": posting_type,
                "AccountRef": {"value": acct["Id"], "name": acct["Name"]},
            }
        })

    if abs(total_debit - total_credit) > 0.01:
        return f"Journal entry does not balance. Debits: {fmt(total_debit)}, Credits: {fmt(total_credit)}. They must be equal."

    je_body = {
        "TxnDate": date,
        "Line": je_lines,
    }
    if memo:
        je_body["PrivateNote"] = memo

    result = await qb_request("POST", "journalentry", json_body=je_body)
    je = result.get("JournalEntry", {})
    return (
        f"Journal entry created!\n"
        f"- ID: {je.get('Id')}\n"
        f"- Date: {date}\n"
        f"- Total: {fmt(je.get('TotalAmt'))}\n"
        f"- Lines: {len(je_lines)}" +
        (f"\n- Memo: {memo}" if memo else "")
    )


# ===================================================================
# TRANSACTION CREATION — Deposits
# ===================================================================

@mcp.tool()
async def qb_create_deposit(date: str, deposit_to_account: str, lines_json: str, memo: str = "") -> str:
    """Create a bank deposit. date: YYYY-MM-DD. deposit_to_account: name of bank account receiving deposit. lines_json: JSON string [{"account_name": "...", "amount": 100.00, "description": "..."}]."""
    dep_accounts = await qb_query(f"SELECT * FROM Account WHERE Name LIKE '%{deposit_to_account}%' MAXRESULTS 1")
    dep_list = dep_accounts.get("QueryResponse", {}).get("Account", [])
    if not dep_list:
        return f"Account '{deposit_to_account}' not found. Use qb_list_accounts to see available accounts."

    entries = json.loads(lines_json) if isinstance(lines_json, str) else lines_json
    dep_lines = []
    for entry in entries:
        acct_name = entry.get("account_name", "")
        amount = float(entry.get("amount", 0))
        desc = entry.get("description", "")

        accounts = await qb_query(f"SELECT * FROM Account WHERE Name LIKE '%{acct_name}%' MAXRESULTS 1")
        acct_list = accounts.get("QueryResponse", {}).get("Account", [])
        if not acct_list:
            return f"Account '{acct_name}' not found."
        acct = acct_list[0]

        dep_lines.append({
            "DetailType": "DepositLineDetail",
            "Amount": amount,
            "Description": desc,
            "DepositLineDetail": {
                "AccountRef": {"value": acct["Id"], "name": acct["Name"]},
            }
        })

    deposit_body = {
        "TxnDate": date,
        "DepositToAccountRef": {"value": dep_list[0]["Id"], "name": dep_list[0]["Name"]},
        "Line": dep_lines,
    }
    if memo:
        deposit_body["PrivateNote"] = memo

    result = await qb_request("POST", "deposit", json_body=deposit_body)
    dep = result.get("Deposit", {})
    return (
        f"Deposit created!\n"
        f"- ID: {dep.get('Id')}\n"
        f"- Date: {date}\n"
        f"- Total: {fmt(dep.get('TotalAmt'))}\n"
        f"- Deposited to: {dep_list[0]['Name']}"
    )


# ===================================================================
# TRANSACTION CREATION — Transfers
# ===================================================================

@mcp.tool()
async def qb_create_transfer(date: str, from_account: str, to_account: str, amount: float, memo: str = "") -> str:
    """Create a transfer between two accounts. date: YYYY-MM-DD. from_account and to_account are account names. amount is the transfer amount."""
    from_accts = await qb_query(f"SELECT * FROM Account WHERE Name LIKE '%{from_account}%' MAXRESULTS 1")
    from_list = from_accts.get("QueryResponse", {}).get("Account", [])
    if not from_list:
        return f"From account '{from_account}' not found."

    to_accts = await qb_query(f"SELECT * FROM Account WHERE Name LIKE '%{to_account}%' MAXRESULTS 1")
    to_list = to_accts.get("QueryResponse", {}).get("Account", [])
    if not to_list:
        return f"To account '{to_account}' not found."

    transfer_body = {
        "TxnDate": date,
        "Amount": amount,
        "FromAccountRef": {"value": from_list[0]["Id"], "name": from_list[0]["Name"]},
        "ToAccountRef": {"value": to_list[0]["Id"], "name": to_list[0]["Name"]},
    }
    if memo:
        transfer_body["PrivateNote"] = memo

    result = await qb_request("POST", "transfer", json_body=transfer_body)
    t = result.get("Transfer", {})
    return (
        f"Transfer created!\n"
        f"- ID: {t.get('Id')}\n"
        f"- Date: {date}\n"
        f"- Amount: {fmt(amount)}\n"
        f"- From: {from_list[0]['Name']} → To: {to_list[0]['Name']}"
    )


# ===================================================================
# TRANSACTION UPDATE — Generic entity updater
# ===================================================================

@mcp.tool()
async def qb_update_transaction(entity_type: str, entity_id: str, updates_json: str) -> str:
    """Update an existing transaction. entity_type: Purchase, Deposit, Transfer, JournalEntry, Bill, Invoice, etc. entity_id: the transaction ID. updates_json: JSON string of fields to update (e.g., {"PrivateNote": "new memo", "TxnDate": "2025-01-15"}). Fetches current version first to ensure SyncToken is correct."""
    entity_lower = entity_type.lower()
    current = await qb_read(entity_lower, entity_id)
    entity_data = current.get(entity_type, {})

    if not entity_data:
        return f"{entity_type} with ID {entity_id} not found."

    updates = json.loads(updates_json) if isinstance(updates_json, str) else updates_json
    entity_data.update(updates)

    result = await qb_request("POST", entity_lower, json_body=entity_data)
    updated = result.get(entity_type, {})
    return (
        f"{entity_type} updated!\n"
        f"- ID: {updated.get('Id')}\n"
        f"- SyncToken: {updated.get('SyncToken')}\n"
        f"- Updated fields: {', '.join(updates.keys())}"
    )


# ===================================================================
# TRANSACTION VOID
# ===================================================================

@mcp.tool()
async def qb_void_transaction(entity_type: str, entity_id: str) -> str:
    """Void a transaction (keeps it in records but zeroes the amount). entity_type: Purchase, Invoice, Payment, SalesReceipt, BillPayment, etc. entity_id: the transaction ID. Note: not all entity types support void."""
    entity_lower = entity_type.lower()
    current = await qb_read(entity_lower, entity_id)
    entity_data = current.get(entity_type, {})

    if not entity_data:
        return f"{entity_type} with ID {entity_id} not found."

    void_body = {
        "Id": entity_data["Id"],
        "SyncToken": entity_data["SyncToken"],
    }

    try:
        result = await qb_request("POST", f"{entity_lower}?operation=void", json_body=void_body)
        voided = result.get(entity_type, {})
        return f"{entity_type} voided!\n- ID: {voided.get('Id')}\n- Original amount: {fmt(entity_data.get('TotalAmt', entity_data.get('Amount')))}"
    except Exception as e:
        return f"Could not void {entity_type} {entity_id}: {str(e)}. Not all transaction types support void."


# ===================================================================
# RECONCILIATION
# ===================================================================

@mcp.tool()
async def qb_reconcile_invoices(start_date: str, end_date: str, invoice_data: str) -> str:
    """Compare email-extracted invoices against QuickBooks transactions. invoice_data is a JSON string: [{"vendor": "...", "amount": 100.00, "date": "2025-01-15"}]. Dates in YYYY-MM-DD."""
    query = (
        f"SELECT * FROM Purchase WHERE TxnDate >= '{start_date}' "
        f"AND TxnDate <= '{end_date}' MAXRESULTS 1000"
    )
    result = await qb_query(query)
    qb_purchases = result.get("QueryResponse", {}).get("Purchase", [])

    qb_by_vendor = {}
    for p in qb_purchases:
        vendor = p.get("EntityRef", {}).get("name", "Unknown").lower()
        qb_by_vendor.setdefault(vendor, []).append({
            "amount": float(p.get("TotalAmt", 0)),
            "date": p.get("TxnDate", ""),
            "id": p.get("Id", ""),
        })

    invoices = json.loads(invoice_data) if isinstance(invoice_data, str) else invoice_data
    matched = []
    missing = []
    mismatched = []

    for inv in invoices:
        vendor = inv.get("vendor", "").lower()
        amount = float(inv.get("amount", 0))
        date = inv.get("date", "")

        found = False
        for key in qb_by_vendor:
            if vendor in key or key in vendor:
                for qb_txn in qb_by_vendor[key]:
                    if abs(qb_txn["amount"] - amount) < 0.02:
                        matched.append({"vendor": inv["vendor"], "amount": amount, "qb_id": qb_txn["id"]})
                        found = True
                        break
                if not found:
                    qb_total = sum(t["amount"] for t in qb_by_vendor[key])
                    mismatched.append({"vendor": inv["vendor"], "invoice_amount": amount, "qb_total": qb_total})
                    found = True
                break

        if not found:
            missing.append({"vendor": inv["vendor"], "amount": amount, "date": date})

    lines = [f"## Reconciliation: {start_date} to {end_date}\n"]
    lines.append(f"**Matched:** {len(matched)} | **Missing from QB:** {len(missing)} | **Mismatched:** {len(mismatched)}\n")

    if missing:
        lines.append("### Missing from QuickBooks")
        for m in missing:
            lines.append(f"- {m['vendor']}: {fmt(m['amount'])} ({m['date']})")

    if mismatched:
        lines.append("\n### Amount Mismatches")
        for m in mismatched:
            lines.append(f"- {m['vendor']}: Invoice {fmt(m['invoice_amount'])} vs QB {fmt(m['qb_total'])}")

    if matched:
        lines.append(f"\n### Matched ({len(matched)})")
        for m in matched[:10]:
            lines.append(f"- {m['vendor']}: {fmt(m['amount'])}")
        if len(matched) > 10:
            lines.append(f"  ... and {len(matched) - 10} more")

    return "\n".join(lines)


# ===================================================================
# ACCOUNT BALANCE LOOKUP
# ===================================================================

@mcp.tool()
async def qb_account_balance(account_name: str) -> str:
    """Get the current balance of a specific account by name. Returns account details and balance."""
    accounts = await qb_query(f"SELECT * FROM Account WHERE Name LIKE '%{account_name}%' MAXRESULTS 5")
    acct_list = accounts.get("QueryResponse", {}).get("Account", [])

    if not acct_list:
        return f"No account matching '{account_name}' found."

    lines = [f"## Account Balance: '{account_name}'\n"]
    for a in acct_list:
        lines.append(f"- **{a.get('Name')}** (ID: {a.get('Id')})")
        lines.append(f"  Type: {a.get('AccountType')} / {a.get('AccountSubType', '')}")
        lines.append(f"  Balance: {fmt(a.get('CurrentBalance', 0))}")
        lines.append("")
    return "\n".join(lines)


# ===================================================================
# SMART FEATURES — Uncategorized / Duplicates / Auto-Categorize
# ===================================================================

@mcp.tool()
async def qb_uncategorized_transactions(start_date: str = "", end_date: str = "", max_results: int = 100) -> str:
    """Find transactions that are uncategorized or booked to 'Uncategorized Expense/Income/Asset'.
    Useful for cleaning up books. Dates in YYYY-MM-DD format. If omitted, searches all time."""
    # Find uncategorized accounts
    accts = await qb_query("SELECT Id, Name FROM Account WHERE Name LIKE '%ncategorized%' MAXRESULTS 10")
    acct_list = accts.get("QueryResponse", {}).get("Account", [])
    if not acct_list:
        return "No uncategorized accounts found — your books look clean!"

    acct_ids = [a["Id"] for a in acct_list]
    acct_names = {a["Id"]: a["Name"] for a in acct_list}

    # Query purchases hitting those accounts
    date_filter = ""
    if start_date:
        date_filter += f" AND TxnDate >= '{start_date}'"
    if end_date:
        date_filter += f" AND TxnDate <= '{end_date}'"

    all_uncategorized = []
    for acct_id in acct_ids:
        q = f"SELECT * FROM Purchase WHERE AccountRef = '{acct_id}'{date_filter} MAXRESULTS {max_results}"
        try:
            result = await qb_query(q)
            purchases = result.get("QueryResponse", {}).get("Purchase", [])
            for p in purchases:
                all_uncategorized.append({
                    "id": p.get("Id"),
                    "date": p.get("TxnDate"),
                    "amount": float(p.get("TotalAmt", 0)),
                    "vendor": p.get("EntityRef", {}).get("name", "Unknown"),
                    "account": acct_names.get(acct_id, "Uncategorized"),
                    "memo": p.get("PrivateNote", ""),
                })
        except Exception:
            continue

    if not all_uncategorized:
        return "No uncategorized transactions found — everything is categorized!"

    all_uncategorized.sort(key=lambda x: x["date"] or "", reverse=True)
    lines = [f"## Uncategorized Transactions ({len(all_uncategorized)} found)\n"]
    total = 0.0
    for t in all_uncategorized:
        lines.append(f"- **{t['date']}** | {t['vendor']} | {fmt(t['amount'])} | {t['account']} | ID: {t['id']}")
        if t["memo"]:
            lines.append(f"  Memo: {t['memo']}")
        total += t["amount"]
    lines.append(f"\n**Total uncategorized: {fmt(total)}**")
    return "\n".join(lines)


@mcp.tool()
async def qb_find_duplicates(start_date: str, end_date: str, tolerance_days: int = 3, max_results: int = 200) -> str:
    """Find potential duplicate transactions within a date range. Matches by amount and vendor within tolerance_days window. Dates in YYYY-MM-DD."""
    result = await qb_query(
        f"SELECT * FROM Purchase WHERE TxnDate >= '{start_date}' AND TxnDate <= '{end_date}' MAXRESULTS {max_results}"
    )
    purchases = result.get("QueryResponse", {}).get("Purchase", [])
    if not purchases:
        return f"No transactions found between {start_date} and {end_date}."

    from collections import defaultdict
    groups = defaultdict(list)
    for p in purchases:
        key = (
            round(float(p.get("TotalAmt", 0)), 2),
            (p.get("EntityRef", {}).get("name", "") or "").lower().strip(),
        )
        groups[key].append(p)

    dupes = []
    for key, txns in groups.items():
        if len(txns) < 2:
            continue
        txns.sort(key=lambda x: x.get("TxnDate", ""))
        for i in range(len(txns)):
            for j in range(i + 1, len(txns)):
                d1 = datetime.strptime(txns[i]["TxnDate"], "%Y-%m-%d")
                d2 = datetime.strptime(txns[j]["TxnDate"], "%Y-%m-%d")
                if abs((d2 - d1).days) <= tolerance_days:
                    dupes.append((txns[i], txns[j]))

    if not dupes:
        return f"No potential duplicates found between {start_date} and {end_date}. Books look clean!"

    lines = [f"## Potential Duplicates ({len(dupes)} pairs found)\n"]
    for a, b in dupes:
        lines.append(f"**{a.get('EntityRef', {}).get('name', 'Unknown')}** — {fmt(float(a.get('TotalAmt', 0)))}:")
        lines.append(f"  1. {a['TxnDate']} (ID: {a['Id']}) — {a.get('PrivateNote', '') or 'no memo'}")
        lines.append(f"  2. {b['TxnDate']} (ID: {b['Id']}) — {b.get('PrivateNote', '') or 'no memo'}")
        lines.append("")
    lines.append("Review each pair and void the duplicate using `qb_void_transaction`.")
    return "\n".join(lines)


@mcp.tool()
async def qb_auto_categorize_suggestions(start_date: str, end_date: str, max_results: int = 100) -> str:
    """Suggest categories for uncategorized transactions based on vendor history.
    Analyzes past categorization patterns to recommend correct accounts. Dates in YYYY-MM-DD."""
    # Get uncategorized purchases
    accts = await qb_query("SELECT Id FROM Account WHERE Name LIKE '%ncategorized%' MAXRESULTS 10")
    acct_list = accts.get("QueryResponse", {}).get("Account", [])
    if not acct_list:
        return "No uncategorized accounts found."

    uncategorized = []
    for acct in acct_list:
        q = (f"SELECT * FROM Purchase WHERE AccountRef = '{acct['Id']}' "
             f"AND TxnDate >= '{start_date}' AND TxnDate <= '{end_date}' MAXRESULTS {max_results}")
        try:
            result = await qb_query(q)
            uncategorized.extend(result.get("QueryResponse", {}).get("Purchase", []))
        except Exception:
            continue

    if not uncategorized:
        return "No uncategorized transactions found to categorize."

    # Build vendor → account history from categorized purchases
    all_purchases = await qb_query(f"SELECT * FROM Purchase WHERE TxnDate >= '{start_date}' AND TxnDate <= '{end_date}' MAXRESULTS 500")
    categorized = all_purchases.get("QueryResponse", {}).get("Purchase", [])

    from collections import Counter
    vendor_history = {}
    for p in categorized:
        vendor = (p.get("EntityRef", {}).get("name", "") or "").lower().strip()
        if not vendor:
            continue
        line_items = p.get("Line", [])
        for li in line_items:
            detail = li.get("AccountBasedExpenseLineDetail", {})
            acct_name = detail.get("AccountRef", {}).get("name", "")
            if acct_name and "uncategorized" not in acct_name.lower():
                if vendor not in vendor_history:
                    vendor_history[vendor] = Counter()
                vendor_history[vendor][acct_name] += 1

    lines = [f"## Auto-Categorize Suggestions ({len(uncategorized)} transactions)\n"]
    for p in uncategorized:
        vendor = (p.get("EntityRef", {}).get("name", "") or "").lower().strip()
        date = p.get("TxnDate", "")
        amt = float(p.get("TotalAmt", 0))
        suggestion = "No history — manual review needed"
        if vendor in vendor_history:
            top = vendor_history[vendor].most_common(1)
            if top:
                suggestion = f"→ **{top[0][0]}** (based on {top[0][1]} past transactions)"

        lines.append(f"- {date} | {p.get('EntityRef', {}).get('name', 'Unknown')} | {fmt(amt)} | {suggestion} | ID: {p.get('Id')}")

    lines.append("\nUse `qb_update_transaction` to apply the suggested categories.")
    return "\n".join(lines)


# ===================================================================
# BATCH OPERATIONS
# ===================================================================

@mcp.tool()
async def qb_batch_create_expenses(expenses_json: str) -> str:
    """Create multiple expenses in one call. expenses_json is a JSON array of objects:
    [{"vendor_name": "...", "amount": 100, "account_name": "...", "date": "YYYY-MM-DD", "description": "..."}].
    Useful for importing invoices or bulk expense entry."""
    try:
        expenses = json.loads(expenses_json)
    except json.JSONDecodeError:
        return "Error: Invalid JSON. Provide a JSON array of expense objects."

    if not isinstance(expenses, list):
        return "Error: expenses_json must be a JSON array."

    results = []
    errors = []
    for i, exp in enumerate(expenses):
        try:
            vendor_name = exp.get("vendor_name", "Unknown")
            amount = float(exp.get("amount", 0))
            account_name = exp.get("account_name", "")
            date = exp.get("date", datetime.now().strftime("%Y-%m-%d"))
            description = exp.get("description", "")
            payment_method = exp.get("payment_method", "")

            # Look up vendor
            vendors = await qb_query(f"SELECT Id, DisplayName FROM Vendor WHERE DisplayName LIKE '%{vendor_name}%' MAXRESULTS 1")
            vendor_list = vendors.get("QueryResponse", {}).get("Vendor", [])
            if not vendor_list:
                # Create vendor
                new_vendor = await qb_request("POST", "vendor", json_body={"DisplayName": vendor_name})
                vendor_ref = {"value": new_vendor["Vendor"]["Id"], "name": vendor_name}
            else:
                vendor_ref = {"value": vendor_list[0]["Id"], "name": vendor_list[0]["DisplayName"]}

            # Look up expense account
            accounts = await qb_query(f"SELECT Id, Name FROM Account WHERE Name LIKE '%{account_name}%' MAXRESULTS 1")
            acct_list = accounts.get("QueryResponse", {}).get("Account", [])
            if not acct_list:
                errors.append(f"#{i+1}: Account '{account_name}' not found")
                continue
            acct_ref = {"value": acct_list[0]["Id"], "name": acct_list[0]["Name"]}

            # Look up payment account if specified
            pay_ref = None
            if payment_method:
                pay_accts = await qb_query(f"SELECT Id, Name FROM Account WHERE Name LIKE '%{payment_method}%' MAXRESULTS 1")
                pay_list = pay_accts.get("QueryResponse", {}).get("Account", [])
                if pay_list:
                    pay_ref = {"value": pay_list[0]["Id"], "name": pay_list[0]["Name"]}

            body = {
                "PaymentType": "Cash",
                "TxnDate": date,
                "EntityRef": vendor_ref,
                "Line": [{
                    "Amount": amount,
                    "DetailType": "AccountBasedExpenseLineDetail",
                    "AccountBasedExpenseLineDetail": {"AccountRef": acct_ref},
                    "Description": description,
                }],
            }
            if pay_ref:
                body["AccountRef"] = pay_ref

            resp = await qb_request("POST", "purchase", json_body=body)
            txn_id = resp.get("Purchase", {}).get("Id", "?")
            results.append(f"#{i+1}: ✅ {date} | {vendor_name} | {fmt(amount)} → {account_name} (ID: {txn_id})")

        except Exception as e:
            errors.append(f"#{i+1}: ❌ {exp.get('vendor_name', '?')} — {str(e)}")

    lines = [f"## Batch Expense Creation Results\n"]
    lines.append(f"**Succeeded:** {len(results)} | **Failed:** {len(errors)}\n")
    if results:
        lines.append("### Created:")
        lines.extend(results)
    if errors:
        lines.append("\n### Errors:")
        lines.extend(errors)
    return "\n".join(lines)


@mcp.tool()
async def qb_batch_create_bills(bills_json: str) -> str:
    """Create multiple bills (accounts payable) in one call. bills_json is a JSON array:
    [{"vendor_name": "...", "amount": 100, "account_name": "...", "date": "YYYY-MM-DD", "due_date": "YYYY-MM-DD", "description": "..."}].
    Useful for importing vendor invoices from email extraction."""
    try:
        bills = json.loads(bills_json)
    except json.JSONDecodeError:
        return "Error: Invalid JSON. Provide a JSON array of bill objects."

    results = []
    errors = []
    for i, bill in enumerate(bills):
        try:
            vendor_name = bill.get("vendor_name", "Unknown")
            amount = float(bill.get("amount", 0))
            account_name = bill.get("account_name", "")
            date = bill.get("date", datetime.now().strftime("%Y-%m-%d"))
            due_date = bill.get("due_date", date)
            description = bill.get("description", "")

            # Look up or create vendor
            vendors = await qb_query(f"SELECT Id, DisplayName FROM Vendor WHERE DisplayName LIKE '%{vendor_name}%' MAXRESULTS 1")
            vendor_list = vendors.get("QueryResponse", {}).get("Vendor", [])
            if not vendor_list:
                new_vendor = await qb_request("POST", "vendor", json_body={"DisplayName": vendor_name})
                vendor_ref = {"value": new_vendor["Vendor"]["Id"], "name": vendor_name}
            else:
                vendor_ref = {"value": vendor_list[0]["Id"], "name": vendor_list[0]["DisplayName"]}

            # Look up expense account
            accounts = await qb_query(f"SELECT Id, Name FROM Account WHERE Name LIKE '%{account_name}%' MAXRESULTS 1")
            acct_list = accounts.get("QueryResponse", {}).get("Account", [])
            if not acct_list:
                errors.append(f"#{i+1}: Account '{account_name}' not found")
                continue
            acct_ref = {"value": acct_list[0]["Id"], "name": acct_list[0]["Name"]}

            body = {
                "VendorRef": vendor_ref,
                "TxnDate": date,
                "DueDate": due_date,
                "Line": [{
                    "Amount": amount,
                    "DetailType": "AccountBasedExpenseLineDetail",
                    "AccountBasedExpenseLineDetail": {"AccountRef": acct_ref},
                    "Description": description,
                }],
            }

            resp = await qb_request("POST", "bill", json_body=body)
            bill_id = resp.get("Bill", {}).get("Id", "?")
            results.append(f"#{i+1}: ✅ {date} | {vendor_name} | {fmt(amount)} → {account_name} (Bill ID: {bill_id})")

        except Exception as e:
            errors.append(f"#{i+1}: ❌ {bill.get('vendor_name', '?')} — {str(e)}")

    lines = [f"## Batch Bill Creation Results\n"]
    lines.append(f"**Succeeded:** {len(results)} | **Failed:** {len(errors)}\n")
    if results:
        lines.append("### Created:")
        lines.extend(results)
    if errors:
        lines.append("\n### Errors:")
        lines.extend(errors)
    return "\n".join(lines)


# ===================================================================
# ADVANCED REPORTS — Period Comparison, Runway, Burn Rate
# ===================================================================

@mcp.tool()
async def qb_compare_periods(report_type: str, period1_start: str, period1_end: str, period2_start: str, period2_end: str) -> str:
    """Compare two time periods side-by-side. report_type: 'ProfitAndLoss' or 'BalanceSheet'.
    Shows each period's totals and the dollar/percentage change. Dates in YYYY-MM-DD."""
    if report_type not in ("ProfitAndLoss", "BalanceSheet"):
        return "Error: report_type must be 'ProfitAndLoss' or 'BalanceSheet'."

    def extract_rows(report_data):
        rows = {}
        def _walk(row_list, prefix=""):
            for section in row_list:
                col_data = section.get("ColData", [])
                if len(col_data) >= 2:
                    name = col_data[0].get("value", "")
                    try:
                        val = float(col_data[-1].get("value", "0"))
                    except (ValueError, TypeError):
                        val = 0
                    full_name = f"{prefix}{name}" if prefix else name
                    rows[full_name] = val
                summary = section.get("Summary", {})
                if summary:
                    cols = summary.get("ColData", [])
                    if len(cols) >= 2:
                        try:
                            rows[cols[0].get("value", "")] = float(cols[-1].get("value", "0"))
                        except (ValueError, TypeError):
                            pass
                nested = section.get("Rows", {}).get("Row", [])
                if nested:
                    header = section.get("Header", {}).get("ColData", [{}])
                    group_name = header[0].get("value", "") if header else ""
                    _walk(nested, f"{group_name} > " if group_name else prefix)
            return rows
        report_rows = report_data.get("Rows", {}).get("Row", [])
        _walk(report_rows)
        return rows

    r1 = await qb_request("GET", f"reports/{report_type}", params={
        "start_date": period1_start, "end_date": period1_end
    })
    r2 = await qb_request("GET", f"reports/{report_type}", params={
        "start_date": period2_start, "end_date": period2_end
    })

    rows1 = extract_rows(r1)
    rows2 = extract_rows(r2)
    all_keys = sorted(set(list(rows1.keys()) + list(rows2.keys())))

    lines = [f"## {report_type} Period Comparison\n"]
    lines.append(f"| Account | {period1_start}→{period1_end} | {period2_start}→{period2_end} | Change | % Change |")
    lines.append("|---|---|---|---|---|")

    for key in all_keys:
        v1 = rows1.get(key, 0)
        v2 = rows2.get(key, 0)
        change = v2 - v1
        pct = (change / abs(v1) * 100) if v1 != 0 else 0
        sign = "+" if change >= 0 else ""
        lines.append(f"| {key} | {fmt(v1)} | {fmt(v2)} | {sign}{fmt(change)} | {sign}{pct:.1f}% |")

    return "\n".join(lines)


@mcp.tool()
async def qb_monthly_burn_rate(months_back: int = 6) -> str:
    """Calculate monthly burn rate based on the last N months of expenses.
    Returns monthly totals, average burn, and trend. Useful for runway planning."""
    from datetime import date
    today = date.today()
    monthly_data = []

    for i in range(months_back, 0, -1):
        # Calculate month start/end
        m = today.month - i
        y = today.year
        while m <= 0:
            m += 12
            y -= 1
        month_start = f"{y}-{m:02d}-01"
        if m == 12:
            month_end = f"{y}-12-31"
        else:
            next_m_start = date(y if m < 12 else y + 1, (m % 12) + 1, 1)
            month_end = (next_m_start - timedelta(days=1)).strftime("%Y-%m-%d")

        result = await qb_request("GET", "reports/ProfitAndLoss", params={
            "start_date": month_start, "end_date": month_end
        })

        # Extract total expenses
        total_expense = 0
        total_income = 0
        report_rows = result.get("Rows", {}).get("Row", [])
        for section in report_rows:
            summary = section.get("Summary", {})
            cols = summary.get("ColData", [])
            if len(cols) >= 2:
                label = cols[0].get("value", "").lower()
                try:
                    val = float(cols[-1].get("value", "0"))
                except (ValueError, TypeError):
                    val = 0
                if "expense" in label:
                    total_expense = abs(val)
                elif "income" in label:
                    total_income = val

        from calendar import month_abbr
        monthly_data.append({
            "month": f"{month_abbr[m]} {y}",
            "expenses": total_expense,
            "income": total_income,
            "net": total_income - total_expense,
        })

    avg_burn = sum(d["expenses"] for d in monthly_data) / len(monthly_data) if monthly_data else 0
    avg_income = sum(d["income"] for d in monthly_data) / len(monthly_data) if monthly_data else 0
    avg_net = sum(d["net"] for d in monthly_data) / len(monthly_data) if monthly_data else 0

    lines = ["## Monthly Burn Rate Analysis\n"]
    lines.append("| Month | Income | Expenses | Net |")
    lines.append("|---|---|---|---|")
    for d in monthly_data:
        lines.append(f"| {d['month']} | {fmt(d['income'])} | {fmt(d['expenses'])} | {fmt(d['net'])} |")
    lines.append(f"\n**Average Monthly Burn:** {fmt(avg_burn)}")
    lines.append(f"**Average Monthly Income:** {fmt(avg_income)}")
    lines.append(f"**Average Monthly Net:** {fmt(avg_net)}")

    # Trend (is burn increasing or decreasing?)
    if len(monthly_data) >= 3:
        first_half = sum(d["expenses"] for d in monthly_data[:len(monthly_data)//2])
        second_half = sum(d["expenses"] for d in monthly_data[len(monthly_data)//2:])
        if second_half > first_half * 1.1:
            lines.append("\n⚠️ **Trend: Expenses increasing** — burn rate growing over time.")
        elif second_half < first_half * 0.9:
            lines.append("\n✅ **Trend: Expenses decreasing** — spending is tightening.")
        else:
            lines.append("\n📊 **Trend: Stable** — expenses roughly consistent.")

    return "\n".join(lines)


@mcp.tool()
async def qb_runway_calculator(current_cash: float = 0, monthly_revenue: float = 0, monthly_expenses: float = 0) -> str:
    """Calculate runway (months until cash runs out). If amounts are 0, auto-calculates from last 3 months of QB data.
    Returns months of runway and recommendations."""
    if current_cash == 0:
        # Auto-detect from balance sheet
        bs = await qb_request("GET", "reports/BalanceSheet", params={
            "date_macro": "Today"
        })
        report_rows = bs.get("Rows", {}).get("Row", [])
        for section in report_rows:
            header = section.get("Header", {}).get("ColData", [{}])
            if header and "bank" in header[0].get("value", "").lower():
                summary = section.get("Summary", {})
                cols = summary.get("ColData", [])
                if len(cols) >= 2:
                    try:
                        current_cash = float(cols[-1].get("value", "0"))
                    except (ValueError, TypeError):
                        pass

    if monthly_expenses == 0 or monthly_revenue == 0:
        from datetime import date
        today = date.today()
        start_3mo = (today - timedelta(days=90)).strftime("%Y-%m-%d")
        end = today.strftime("%Y-%m-%d")
        result = await qb_request("GET", "reports/ProfitAndLoss", params={
            "start_date": start_3mo, "end_date": end
        })
        report_rows = result.get("Rows", {}).get("Row", [])
        for section in report_rows:
            summary = section.get("Summary", {})
            cols = summary.get("ColData", [])
            if len(cols) >= 2:
                label = cols[0].get("value", "").lower()
                try:
                    val = float(cols[-1].get("value", "0"))
                except (ValueError, TypeError):
                    val = 0
                if "expense" in label:
                    monthly_expenses = abs(val) / 3
                elif "income" in label:
                    monthly_revenue = val / 3

    net_burn = monthly_expenses - monthly_revenue
    if net_burn <= 0:
        return (f"## Runway Calculator\n\n"
                f"**Cash on hand:** {fmt(current_cash)}\n"
                f"**Monthly revenue:** {fmt(monthly_revenue)}\n"
                f"**Monthly expenses:** {fmt(monthly_expenses)}\n\n"
                f"✅ **Cash-flow positive!** Revenue exceeds expenses by {fmt(abs(net_burn))}/month.")

    runway_months = current_cash / net_burn if net_burn > 0 else float('inf')

    lines = ["## Runway Calculator\n"]
    lines.append(f"**Cash on hand:** {fmt(current_cash)}")
    lines.append(f"**Monthly revenue:** {fmt(monthly_revenue)}")
    lines.append(f"**Monthly expenses:** {fmt(monthly_expenses)}")
    lines.append(f"**Net monthly burn:** {fmt(net_burn)}")
    lines.append(f"\n### 🏃 Runway: {runway_months:.1f} months")

    if runway_months < 3:
        lines.append("\n🔴 **CRITICAL** — Less than 3 months of runway. Immediate action needed.")
    elif runway_months < 6:
        lines.append("\n🟡 **WARNING** — Less than 6 months. Begin fundraising or cost-cutting.")
    elif runway_months < 12:
        lines.append("\n🟢 **OK** — 6-12 months of runway. Plan ahead for sustainability.")
    else:
        lines.append("\n✅ **HEALTHY** — 12+ months of runway.")

    return "\n".join(lines)


# ===================================================================
# TAX TOOLS — Schedule C, Quarterly Estimates, Deductions, Depreciation
# ===================================================================

@mcp.tool()
async def qb_schedule_c(tax_year: str = "2024") -> str:
    """Generate IRS Schedule C (Profit or Loss from Business) line-by-line mapping.
    Maps QuickBooks expense categories to Schedule C lines for tax filing. tax_year: YYYY format."""
    start = f"{tax_year}-01-01"
    end = f"{tax_year}-12-31"

    result = await qb_request("GET", "reports/ProfitAndLoss", params={
        "start_date": start, "end_date": end,
        "summarize_column_by": "Total"
    })

    # Schedule C line mapping
    schedule_c_map = {
        "advertising": {"line": "8", "desc": "Advertising"},
        "marketing": {"line": "8", "desc": "Advertising"},
        "automobile": {"line": "9", "desc": "Car and truck expenses"},
        "vehicle": {"line": "9", "desc": "Car and truck expenses"},
        "mileage": {"line": "9", "desc": "Car and truck expenses"},
        "commission": {"line": "10", "desc": "Commissions and fees"},
        "contract": {"line": "11", "desc": "Contract labor"},
        "freelancer": {"line": "11", "desc": "Contract labor"},
        "depreciation": {"line": "13", "desc": "Depreciation and Sec 179"},
        "insurance": {"line": "15", "desc": "Insurance (other than health)"},
        "interest": {"line": "16a", "desc": "Mortgage interest"},
        "legal": {"line": "17", "desc": "Legal and professional services"},
        "professional": {"line": "17", "desc": "Legal and professional services"},
        "accounting": {"line": "17", "desc": "Legal and professional services"},
        "office": {"line": "18", "desc": "Office expense"},
        "supplies": {"line": "22", "desc": "Supplies"},
        "rent": {"line": "20b", "desc": "Rent (other business property)"},
        "repair": {"line": "21", "desc": "Repairs and maintenance"},
        "tax": {"line": "23", "desc": "Taxes and licenses"},
        "license": {"line": "23", "desc": "Taxes and licenses"},
        "travel": {"line": "24a", "desc": "Travel"},
        "meals": {"line": "24b", "desc": "Deductible meals (50%)"},
        "utilities": {"line": "25", "desc": "Utilities"},
        "phone": {"line": "25", "desc": "Utilities"},
        "internet": {"line": "25", "desc": "Utilities"},
        "wage": {"line": "26", "desc": "Wages"},
        "salary": {"line": "26", "desc": "Wages"},
        "software": {"line": "27a", "desc": "Other expenses"},
        "subscription": {"line": "27a", "desc": "Other expenses"},
        "hosting": {"line": "27a", "desc": "Other expenses"},
        "cloud": {"line": "27a", "desc": "Other expenses"},
        "education": {"line": "27a", "desc": "Other expenses"},
        "training": {"line": "27a", "desc": "Other expenses"},
        "bank": {"line": "27a", "desc": "Other expenses"},
        "processing": {"line": "27a", "desc": "Other expenses"},
    }

    # Parse P&L rows into account → amount
    def extract_expenses(rows, result_dict, parent=""):
        for section in rows:
            col_data = section.get("ColData", [])
            if len(col_data) >= 2:
                name = col_data[0].get("value", "")
                try:
                    val = float(col_data[-1].get("value", "0"))
                except (ValueError, TypeError):
                    val = 0
                if val != 0:
                    result_dict[name] = val
            nested = section.get("Rows", {}).get("Row", [])
            if nested:
                extract_expenses(nested, result_dict)

    expense_dict = {}
    report_rows = result.get("Rows", {}).get("Row", [])
    for section in report_rows:
        header = section.get("Header", {}).get("ColData", [{}])
        if header and "expense" in header[0].get("value", "").lower():
            nested = section.get("Rows", {}).get("Row", [])
            if nested:
                extract_expenses(nested, expense_dict)

    # Also get income
    total_income = 0
    total_expenses = 0
    for section in report_rows:
        summary = section.get("Summary", {})
        cols = summary.get("ColData", [])
        if len(cols) >= 2:
            label = cols[0].get("value", "").lower()
            try:
                val = float(cols[-1].get("value", "0"))
            except (ValueError, TypeError):
                val = 0
            if "income" in label and "net" not in label:
                total_income = val
            elif "expense" in label:
                total_expenses = abs(val)

    # Map expenses to Schedule C lines
    from collections import defaultdict
    sc_lines = defaultdict(lambda: {"amount": 0, "accounts": []})
    unmapped = []

    for acct_name, amount in expense_dict.items():
        mapped = False
        for keyword, info in schedule_c_map.items():
            if keyword in acct_name.lower():
                line_key = f"Line {info['line']}: {info['desc']}"
                sc_lines[line_key]["amount"] += abs(amount)
                sc_lines[line_key]["accounts"].append(f"{acct_name}: {fmt(abs(amount))}")
                mapped = True
                break
        if not mapped and abs(amount) > 0:
            unmapped.append(f"{acct_name}: {fmt(abs(amount))}")

    lines = [f"## IRS Schedule C — {tax_year}\n"]
    lines.append(f"**Line 1 — Gross receipts:** {fmt(total_income)}")
    lines.append(f"**Line 7 — Gross income:** {fmt(total_income)}\n")

    lines.append("### Expenses:")
    sorted_lines = sorted(sc_lines.items(), key=lambda x: x[0])
    total_mapped = 0
    for line_name, data in sorted_lines:
        lines.append(f"\n**{line_name}: {fmt(data['amount'])}**")
        for acct in data["accounts"]:
            lines.append(f"  - {acct}")
        total_mapped += data["amount"]

    if unmapped:
        lines.append(f"\n### Unmapped (need manual review):")
        for u in unmapped:
            lines.append(f"  - {u}")

    lines.append(f"\n**Line 28 — Total expenses: {fmt(total_mapped)}**")
    net_profit = total_income - total_mapped
    lines.append(f"**Line 31 — Net profit (loss): {fmt(net_profit)}**")

    if net_profit < 0:
        lines.append(f"\n📋 **NOL:** This {fmt(abs(net_profit))} loss can be carried forward to offset future income.")

    return "\n".join(lines)


@mcp.tool()
async def qb_estimate_quarterly_tax(tax_year: str = "2025", filing_status: str = "single", state: str = "MA") -> str:
    """Estimate quarterly tax payments (federal + state) based on YTD P&L.
    filing_status: single, married_joint, married_separate. state: two-letter code (MA, CA, etc.)."""
    from datetime import date
    today = date.today()
    year = int(tax_year)
    start = f"{year}-01-01"
    end = min(today.strftime("%Y-%m-%d"), f"{year}-12-31")

    result = await qb_request("GET", "reports/ProfitAndLoss", params={
        "start_date": start, "end_date": end
    })

    total_income = 0
    total_expenses = 0
    report_rows = result.get("Rows", {}).get("Row", [])
    for section in report_rows:
        summary = section.get("Summary", {})
        cols = summary.get("ColData", [])
        if len(cols) >= 2:
            label = cols[0].get("value", "").lower()
            try:
                val = float(cols[-1].get("value", "0"))
            except (ValueError, TypeError):
                val = 0
            if "income" in label and "net" not in label:
                total_income = val
            elif "expense" in label:
                total_expenses = abs(val)

    net_income = total_income - total_expenses

    # Self-employment tax (15.3% on 92.35% of net income)
    se_base = net_income * 0.9235 if net_income > 0 else 0
    se_tax = se_base * 0.153

    # Federal income tax (rough brackets for 2024/2025)
    adjusted_income = net_income - (se_tax / 2)  # SE deduction
    standard_deduction = 14600 if filing_status == "single" else 29200

    taxable = max(0, adjusted_income - standard_deduction)
    federal_tax = 0
    if filing_status in ("single", "married_separate"):
        brackets = [(11600, 0.10), (47150 - 11600, 0.12), (100525 - 47150, 0.22),
                     (191950 - 100525, 0.24), (243725 - 191950, 0.32), (609350 - 243725, 0.35), (float('inf'), 0.37)]
    else:
        brackets = [(23200, 0.10), (94300 - 23200, 0.12), (201050 - 94300, 0.22),
                     (383900 - 201050, 0.24), (487450 - 383900, 0.32), (731200 - 487450, 0.35), (float('inf'), 0.37)]

    remaining = taxable
    for bracket_size, rate in brackets:
        if remaining <= 0:
            break
        amount = min(remaining, bracket_size)
        federal_tax += amount * rate
        remaining -= amount

    # State tax estimate
    state_tax = 0
    state_rate_desc = ""
    if state.upper() == "MA":
        state_tax = max(0, net_income) * 0.05  # MA flat 5% income tax
        state_rate_desc = "MA flat 5% income tax"
    elif state.upper() == "CA":
        state_tax = max(0, net_income) * 0.093  # CA rough avg
        state_rate_desc = "CA ~9.3% avg rate"
    else:
        state_tax = max(0, net_income) * 0.05  # Generic estimate
        state_rate_desc = f"{state} estimated ~5%"

    total_annual = federal_tax + se_tax + state_tax
    quarterly = total_annual / 4

    # Determine which quarters remain
    quarter_due = {1: "Apr 15", 2: "Jun 15", 3: "Sep 15", 4: "Jan 15 (next year)"}
    current_quarter = (today.month - 1) // 3 + 1

    lines = [f"## Estimated Quarterly Tax — {tax_year}\n"]
    lines.append(f"**YTD Net Income:** {fmt(net_income)} ({start} to {end})")
    lines.append(f"**Filing Status:** {filing_status}")
    lines.append(f"**State:** {state.upper()}\n")

    lines.append("### Tax Breakdown:")
    lines.append(f"- Federal income tax: {fmt(federal_tax)}")
    lines.append(f"- Self-employment tax: {fmt(se_tax)}")
    lines.append(f"  (Social Security: {fmt(min(se_base, 168600) * 0.124)}, Medicare: {fmt(se_base * 0.029)})")
    lines.append(f"- {state_rate_desc}: {fmt(state_tax)}")
    lines.append(f"\n**Total estimated annual tax: {fmt(total_annual)}**")
    lines.append(f"**Each quarterly payment: {fmt(quarterly)}**")

    lines.append(f"\n### Quarterly Due Dates:")
    for q, due in quarter_due.items():
        status = "✅ Past" if q < current_quarter else ("⏳ Current" if q == current_quarter else "📅 Upcoming")
        lines.append(f"  Q{q}: {due} — {fmt(quarterly)} ({status})")

    if net_income <= 0:
        lines.append(f"\n📋 **Note:** With a net loss, no estimated payments are due. You may carry forward this NOL.")

    return "\n".join(lines)


@mcp.tool()
async def qb_deduction_finder(tax_year: str = "2024") -> str:
    """Analyze books for commonly missed tax deductions. Checks for home office,
    vehicle expenses, health insurance, retirement contributions, startup costs,
    Section 179, and more. Returns suggestions with estimated savings."""
    start = f"{tax_year}-01-01"
    end = f"{tax_year}-12-31"

    result = await qb_request("GET", "reports/ProfitAndLoss", params={
        "start_date": start, "end_date": end
    })

    expense_dict = {}
    total_income = 0
    total_expenses = 0
    report_rows = result.get("Rows", {}).get("Row", [])

    def extract_all(rows, out):
        for section in rows:
            col_data = section.get("ColData", [])
            if len(col_data) >= 2:
                name = col_data[0].get("value", "")
                try:
                    val = float(col_data[-1].get("value", "0"))
                except (ValueError, TypeError):
                    val = 0
                if val != 0:
                    out[name] = val
            nested = section.get("Rows", {}).get("Row", [])
            if nested:
                extract_all(nested, out)

    for section in report_rows:
        summary = section.get("Summary", {})
        cols = summary.get("ColData", [])
        if len(cols) >= 2:
            label = cols[0].get("value", "").lower()
            try:
                val = float(cols[-1].get("value", "0"))
            except (ValueError, TypeError):
                val = 0
            if "income" in label and "net" not in label:
                total_income = val
            elif "expense" in label:
                total_expenses = abs(val)
        nested = section.get("Rows", {}).get("Row", [])
        if nested:
            extract_all(nested, expense_dict)

    findings = []
    estimated_savings = 0

    # Check for home office
    has_home_office = any("home" in k.lower() and "office" in k.lower() for k in expense_dict)
    has_rent = any("rent" in k.lower() for k in expense_dict)
    if not has_home_office and not has_rent:
        findings.append({
            "deduction": "Home Office Deduction (IRS Form 8829)",
            "status": "🔴 NOT CLAIMED",
            "details": "Simplified: $5/sq ft up to 300 sq ft = $1,500. Regular method may be higher with mortgage interest, property taxes, utilities, insurance.",
            "estimate": 1500,
        })
        estimated_savings += 1500

    # Check for vehicle expenses
    has_vehicle = any("auto" in k.lower() or "vehicle" in k.lower() or "car" in k.lower() or "mileage" in k.lower() for k in expense_dict)
    if not has_vehicle:
        findings.append({
            "deduction": "Vehicle Expenses (Standard Mileage or Actual)",
            "status": "🔴 NOT CLAIMED",
            "details": "2024 rate: 67¢/mile. Track business miles for meetings, supply runs, etc.",
            "estimate": 1000,
        })
        estimated_savings += 1000

    # Check for health insurance
    has_health = any("health" in k.lower() or "medical" in k.lower() or "dental" in k.lower() for k in expense_dict)
    if not has_health:
        findings.append({
            "deduction": "Self-Employed Health Insurance (Schedule 1, Line 17)",
            "status": "🟡 CHECK IF APPLICABLE",
            "details": "100% of health/dental/vision premiums deductible above-the-line. Must not have employer coverage.",
            "estimate": 6000,
        })
        estimated_savings += 6000

    # Check for retirement contributions
    has_retirement = any("retire" in k.lower() or "401k" in k.lower() or "sep" in k.lower() or "ira" in k.lower() for k in expense_dict)
    if not has_retirement:
        findings.append({
            "deduction": "Retirement Contributions (SEP-IRA / Solo 401k)",
            "status": "🟡 OPPORTUNITY",
            "details": "SEP-IRA: up to 25% of net SE income (max $69,000 for 2024). Solo 401k: $23,000 employee + 25% employer.",
            "estimate": 0,
        })

    # Check for depreciation
    has_depreciation = any("deprec" in k.lower() or "section 179" in k.lower() for k in expense_dict)
    if not has_depreciation:
        # Check if there are asset purchases
        findings.append({
            "deduction": "Section 179 / Depreciation",
            "status": "🟡 CHECK ASSETS",
            "details": "Equipment, computers, furniture purchased for business can be expensed immediately under Section 179.",
            "estimate": 0,
        })

    # Check for education/training
    has_education = any("education" in k.lower() or "training" in k.lower() or "course" in k.lower() for k in expense_dict)
    if not has_education:
        findings.append({
            "deduction": "Education & Training",
            "status": "🟡 CHECK",
            "details": "Courses, certifications, books, conferences related to your business are deductible.",
            "estimate": 500,
        })
        estimated_savings += 500

    # Check for startup costs
    net_income = total_income - total_expenses
    if net_income < 0 and total_income == 0:
        findings.append({
            "deduction": "Section 195 Startup Costs",
            "status": "🟡 MAY APPLY",
            "details": "First $5,000 of startup costs deductible in year 1 (if total < $50K). Remainder amortized over 180 months.",
            "estimate": 5000,
        })
        estimated_savings += 5000

    # R&D Tax Credit check (for tech/AI companies)
    has_software = any("software" in k.lower() or "cloud" in k.lower() or "hosting" in k.lower() for k in expense_dict)
    if has_software:
        sw_total = sum(abs(v) for k, v in expense_dict.items() if any(kw in k.lower() for kw in ["software", "cloud", "hosting", "api"]))
        findings.append({
            "deduction": "R&D Tax Credit (Form 6765)",
            "status": "🟡 LIKELY ELIGIBLE",
            "details": f"Software/cloud/API spend of {fmt(sw_total)} suggests R&D activity. Credit = ~10% of qualified research expenses. Startups can offset payroll taxes up to $500K/year.",
            "estimate": sw_total * 0.10,
        })
        estimated_savings += sw_total * 0.10

    # NOL carryforward
    if net_income < 0:
        findings.append({
            "deduction": "Net Operating Loss (NOL) Carryforward",
            "status": "📋 AVAILABLE",
            "details": f"NOL of {fmt(abs(net_income))} can offset up to 80% of future taxable income. Carries forward indefinitely (federal) or 20 years (MA).",
            "estimate": 0,
        })

    lines = [f"## Deduction Finder — {tax_year}\n"]
    lines.append(f"**Total Income:** {fmt(total_income)} | **Total Expenses:** {fmt(total_expenses)} | **Net:** {fmt(net_income)}\n")

    for f in findings:
        lines.append(f"### {f['status']} {f['deduction']}")
        lines.append(f"{f['details']}")
        if f['estimate'] > 0:
            lines.append(f"**Estimated value: {fmt(f['estimate'])}**")
        lines.append("")

    if estimated_savings > 0:
        lines.append(f"\n### 💰 Total Estimated Unclaimed Deductions: {fmt(estimated_savings)}")
        # Rough tax savings at 30% effective rate
        lines.append(f"**Potential tax savings: ~{fmt(estimated_savings * 0.30)}** (at ~30% effective rate)")

    return "\n".join(lines)


@mcp.tool()
async def qb_depreciation_schedule(tax_year: str = "2024") -> str:
    """Generate a depreciation schedule for all fixed assets. Shows Section 179,
    MACRS, and accumulated depreciation for tax year. Pulls from QB asset accounts."""
    # Get fixed asset accounts
    assets = await qb_query("SELECT * FROM Account WHERE AccountType = 'Fixed Asset' MAXRESULTS 50")
    acct_list = assets.get("QueryResponse", {}).get("Account", [])

    if not acct_list:
        return f"No fixed asset accounts found for {tax_year}."

    lines = [f"## Depreciation Schedule — {tax_year}\n"]
    lines.append("| Asset Account | Balance | Useful Life | Method | Annual Depreciation |")
    lines.append("|---|---|---|---|---|")

    total_depreciation = 0
    for a in acct_list:
        name = a.get("Name", "")
        balance = float(a.get("CurrentBalance", 0))
        if abs(balance) < 1:
            continue

        # Determine method/life based on asset type
        if "computer" in name.lower() or "laptop" in name.lower() or "tablet" in name.lower():
            useful_life = 5
            method = "Section 179 / MACRS 5-yr"
            annual = balance  # Full Section 179
        elif "furniture" in name.lower():
            useful_life = 7
            method = "MACRS 7-year"
            annual = balance / 7
        elif "vehicle" in name.lower() or "auto" in name.lower():
            useful_life = 5
            method = "MACRS 5-year"
            annual = balance / 5
        elif "building" in name.lower() or "improvement" in name.lower():
            useful_life = 39
            method = "Straight-line 39-yr"
            annual = balance / 39
        else:
            useful_life = 5
            method = "MACRS 5-year (default)"
            annual = balance / 5

        lines.append(f"| {name} | {fmt(balance)} | {useful_life} yr | {method} | {fmt(annual)} |")
        total_depreciation += annual

    lines.append(f"\n**Total Annual Depreciation: {fmt(total_depreciation)}**")
    lines.append(f"\nNote: Section 179 allows full first-year deduction for qualifying assets up to $1,220,000 (2024 limit).")

    return "\n".join(lines)


# ===================================================================
# RECONCILIATION & MATCHING
# ===================================================================

@mcp.tool()
async def qb_match_invoices_to_transactions(invoices_json: str, start_date: str, end_date: str, tolerance: float = 2.0) -> str:
    """Match extracted invoices against QuickBooks transactions. invoices_json is a JSON array:
    [{"vendor": "...", "amount": 100, "date": "YYYY-MM-DD", "description": "..."}].
    tolerance: dollar amount for fuzzy matching. Returns matched, unmatched, and suggestions."""
    try:
        invoices = json.loads(invoices_json)
    except json.JSONDecodeError:
        return "Error: Invalid JSON for invoices."

    # Get all transactions in range
    purchases = await qb_query(
        f"SELECT * FROM Purchase WHERE TxnDate >= '{start_date}' AND TxnDate <= '{end_date}' MAXRESULTS 500"
    )
    txns = purchases.get("QueryResponse", {}).get("Purchase", [])

    matched = []
    unmatched_invoices = []
    used_txn_ids = set()

    for inv in invoices:
        inv_vendor = (inv.get("vendor", "") or "").lower().strip()
        inv_amount = float(inv.get("amount", 0))
        inv_date = inv.get("date", "")
        best_match = None
        best_score = 0

        for txn in txns:
            if txn["Id"] in used_txn_ids:
                continue
            txn_vendor = (txn.get("EntityRef", {}).get("name", "") or "").lower().strip()
            txn_amount = float(txn.get("TotalAmt", 0))
            txn_date = txn.get("TxnDate", "")

            # Score the match
            score = 0
            if abs(txn_amount - inv_amount) <= tolerance:
                score += 50
            if inv_vendor and txn_vendor and (inv_vendor in txn_vendor or txn_vendor in inv_vendor):
                score += 30
            if inv_date == txn_date:
                score += 20
            elif inv_date and txn_date:
                try:
                    d1 = datetime.strptime(inv_date, "%Y-%m-%d")
                    d2 = datetime.strptime(txn_date, "%Y-%m-%d")
                    if abs((d2 - d1).days) <= 7:
                        score += 10
                except (ValueError, TypeError):
                    pass

            if score > best_score and score >= 50:
                best_score = score
                best_match = txn

        if best_match:
            used_txn_ids.add(best_match["Id"])
            matched.append({
                "invoice": inv,
                "transaction": best_match,
                "score": best_score,
            })
        else:
            unmatched_invoices.append(inv)

    lines = [f"## Invoice Matching Results\n"]
    lines.append(f"**Matched:** {len(matched)} | **Unmatched:** {len(unmatched_invoices)} | **Total invoices:** {len(invoices)}\n")

    if matched:
        lines.append("### Matched Invoices:")
        for m in matched:
            inv = m["invoice"]
            txn = m["transaction"]
            lines.append(f"- ✅ {inv.get('vendor', '?')} | Invoice: {fmt(inv.get('amount', 0))} ({inv.get('date', '?')}) → QB: {fmt(float(txn.get('TotalAmt', 0)))} ({txn.get('TxnDate', '?')}) [Score: {m['score']}]")

    if unmatched_invoices:
        lines.append(f"\n### Unmatched Invoices ({len(unmatched_invoices)} — need to be created):")
        total_unmatched = 0
        for inv in unmatched_invoices:
            amt = float(inv.get("amount", 0))
            lines.append(f"- ❌ {inv.get('vendor', '?')} | {fmt(amt)} | {inv.get('date', '?')} | {inv.get('description', '')}")
            total_unmatched += amt
        lines.append(f"\n**Total unmatched: {fmt(total_unmatched)}**")
        lines.append("\nUse `qb_batch_create_expenses` or `qb_batch_create_bills` to import these.")

    return "\n".join(lines)


# ===================================================================
# UTILITIES — Account Management, Vendor Merge, Fiscal Year Close
# ===================================================================

@mcp.tool()
async def qb_inactivate_account(account_name: str) -> str:
    """Inactivate a QuickBooks account (hide it from active lists without deleting).
    Useful for cleaning up unused or personal accounts. Requires exact account name."""
    accounts = await qb_query(f"SELECT * FROM Account WHERE Name = '{account_name}' MAXRESULTS 1")
    acct_list = accounts.get("QueryResponse", {}).get("Account", [])

    if not acct_list:
        return f"No account matching '{account_name}' found."

    acct = acct_list[0]
    if not acct.get("Active", True):
        return f"Account '{account_name}' is already inactive."

    balance = float(acct.get("CurrentBalance", 0))
    if abs(balance) > 0.01:
        return f"Cannot inactivate '{account_name}' — it has a balance of {fmt(balance)}. Zero it out first with a journal entry."

    body = {
        "Id": acct["Id"],
        "SyncToken": acct["SyncToken"],
        "Active": False,
        "Name": acct["Name"],
        "AccountType": acct["AccountType"],
    }
    if "AccountSubType" in acct:
        body["AccountSubType"] = acct["AccountSubType"]

    result = await qb_request("POST", "account", json_body=body)
    return f"✅ Account '{account_name}' (ID: {acct['Id']}) has been inactivated."


@mcp.tool()
async def qb_create_account(name: str, account_type: str, account_sub_type: str = "", description: str = "") -> str:
    """Create a new account in the chart of accounts.
    account_type: Bank, Accounts Receivable, Other Current Asset, Fixed Asset, Other Asset,
    Accounts Payable, Credit Card, Other Current Liability, Long Term Liability, Equity,
    Income, Cost of Goods Sold, Expense, Other Income, Other Expense.
    account_sub_type: varies by type (e.g., 'Checking' for Bank, 'OfficeGeneralAdministrativeExpenses' for Expense)."""
    body = {
        "Name": name,
        "AccountType": account_type,
    }
    if account_sub_type:
        body["AccountSubType"] = account_sub_type
    if description:
        body["Description"] = description

    result = await qb_request("POST", "account", json_body=body)
    new_acct = result.get("Account", {})
    return (f"✅ Created account '{new_acct.get('Name')}' (ID: {new_acct.get('Id')})\n"
            f"  Type: {new_acct.get('AccountType')} / {new_acct.get('AccountSubType', '')}")


@mcp.tool()
async def qb_vendor_summary(start_date: str, end_date: str, top_n: int = 20) -> str:
    """Rank vendors by total spend within a date range. Shows top N vendors with
    transaction count and total amount. Useful for negotiation and cost analysis."""
    result = await qb_query(
        f"SELECT * FROM Purchase WHERE TxnDate >= '{start_date}' AND TxnDate <= '{end_date}' MAXRESULTS 500"
    )
    purchases = result.get("QueryResponse", {}).get("Purchase", [])

    if not purchases:
        return f"No transactions found between {start_date} and {end_date}."

    from collections import defaultdict
    vendor_totals = defaultdict(lambda: {"count": 0, "total": 0.0})
    for p in purchases:
        vendor = p.get("EntityRef", {}).get("name", "Unknown")
        amt = float(p.get("TotalAmt", 0))
        vendor_totals[vendor]["count"] += 1
        vendor_totals[vendor]["total"] += amt

    sorted_vendors = sorted(vendor_totals.items(), key=lambda x: x[1]["total"], reverse=True)[:top_n]

    lines = [f"## Top Vendors by Spend: {start_date} to {end_date}\n"]
    lines.append("| Rank | Vendor | Transactions | Total Spend |")
    lines.append("|---|---|---|---|")
    grand_total = 0
    for i, (vendor, data) in enumerate(sorted_vendors, 1):
        lines.append(f"| {i} | {vendor} | {data['count']} | {fmt(data['total'])} |")
        grand_total += data["total"]

    lines.append(f"\n**Total across top {len(sorted_vendors)} vendors: {fmt(grand_total)}**")
    lines.append(f"**Total vendors in period: {len(vendor_totals)}**")
    return "\n".join(lines)


@mcp.tool()
async def qb_create_bill(vendor_name: str, amount: float, account_name: str, date: str, due_date: str = "", description: str = "") -> str:
    """Create a single bill (accounts payable) in QuickBooks.
    vendor_name: payee, amount: total, account_name: expense category, date: YYYY-MM-DD.
    due_date: when payment is due (defaults to date if empty)."""
    if not due_date:
        due_date = date

    # Look up or create vendor
    vendors = await qb_query(f"SELECT Id, DisplayName FROM Vendor WHERE DisplayName LIKE '%{vendor_name}%' MAXRESULTS 1")
    vendor_list = vendors.get("QueryResponse", {}).get("Vendor", [])
    if not vendor_list:
        new_vendor = await qb_request("POST", "vendor", json_body={"DisplayName": vendor_name})
        vendor_ref = {"value": new_vendor["Vendor"]["Id"], "name": vendor_name}
    else:
        vendor_ref = {"value": vendor_list[0]["Id"], "name": vendor_list[0]["DisplayName"]}

    # Look up expense account
    accounts = await qb_query(f"SELECT Id, Name FROM Account WHERE Name LIKE '%{account_name}%' MAXRESULTS 1")
    acct_list = accounts.get("QueryResponse", {}).get("Account", [])
    if not acct_list:
        return f"Error: Account '{account_name}' not found. Use `qb_list_accounts` to see available accounts."
    acct_ref = {"value": acct_list[0]["Id"], "name": acct_list[0]["Name"]}

    body = {
        "VendorRef": vendor_ref,
        "TxnDate": date,
        "DueDate": due_date,
        "Line": [{
            "Amount": amount,
            "DetailType": "AccountBasedExpenseLineDetail",
            "AccountBasedExpenseLineDetail": {"AccountRef": acct_ref},
            "Description": description,
        }],
    }

    resp = await qb_request("POST", "bill", json_body=body)
    bill = resp.get("Bill", {})
    return (f"✅ Created bill #{bill.get('Id')}\n"
            f"  Vendor: {vendor_name} | Amount: {fmt(amount)} | Due: {due_date}\n"
            f"  Category: {acct_list[0]['Name']}")


@mcp.tool()
async def qb_profit_loss_by_class(start_date: str, end_date: str) -> str:
    """Generate P&L report broken down by class/department. Useful for multi-segment businesses.
    Dates in YYYY-MM-DD. Returns nothing if classes aren't used."""
    result = await qb_request("GET", "reports/ProfitAndLoss", params={
        "start_date": start_date, "end_date": end_date,
        "summarize_column_by": "Class"
    })

    header = result.get("Header", {})
    columns = result.get("Columns", {}).get("Column", [])
    col_names = [c.get("ColTitle", "") for c in columns]

    if len(col_names) <= 2:
        return "No class data found. This report requires QuickBooks classes to be enabled."

    lines = [f"## Profit & Loss by Class: {start_date} to {end_date}\n"]
    report_rows = result.get("Rows", {}).get("Row", [])
    _parse_report_rows(report_rows, lines)
    return "\n".join(lines)


@mcp.tool()
async def qb_income_summary(start_date: str, end_date: str) -> str:
    """Get income grouped by source/category for a date range. Complements qb_expense_summary.
    Shows all income accounts and their totals. Dates in YYYY-MM-DD."""
    result = await qb_request("GET", "reports/ProfitAndLoss", params={
        "start_date": start_date, "end_date": end_date
    })

    income_items = {}
    report_rows = result.get("Rows", {}).get("Row", [])

    def extract_income(rows, out):
        for section in rows:
            col_data = section.get("ColData", [])
            if len(col_data) >= 2:
                name = col_data[0].get("value", "")
                try:
                    val = float(col_data[-1].get("value", "0"))
                except (ValueError, TypeError):
                    val = 0
                if val != 0:
                    out[name] = val
            nested = section.get("Rows", {}).get("Row", [])
            if nested:
                extract_income(nested, out)

    for section in report_rows:
        header = section.get("Header", {}).get("ColData", [{}])
        label = header[0].get("value", "").lower() if header else ""
        if "income" in label and "net" not in label:
            nested = section.get("Rows", {}).get("Row", [])
            if nested:
                extract_income(nested, income_items)

    if not income_items:
        return f"No income found between {start_date} and {end_date}."

    lines = [f"## Income Summary: {start_date} to {end_date}\n"]
    total = 0
    for name, amount in sorted(income_items.items(), key=lambda x: x[1], reverse=True):
        lines.append(f"- **{name}:** {fmt(amount)}")
        total += amount
    lines.append(f"\n**Total Income: {fmt(total)}**")
    return "\n".join(lines)


@mcp.tool()
async def qb_fiscal_year_close_checklist(tax_year: str = "2024") -> str:
    """Generate a year-end close checklist with status checks against QuickBooks data.
    Verifies key items are in order for tax filing: uncategorized transactions, open invoices,
    undeposited funds, equity cleanup, and more."""
    start = f"{tax_year}-01-01"
    end = f"{tax_year}-12-31"

    checks = []

    # 1. Check for uncategorized transactions
    accts = await qb_query("SELECT Id, Name FROM Account WHERE Name LIKE '%ncategorized%' MAXRESULTS 10")
    uncat_accts = accts.get("QueryResponse", {}).get("Account", [])
    uncat_total = 0
    for a in uncat_accts:
        uncat_total += abs(float(a.get("CurrentBalance", 0)))
    if uncat_total > 0:
        checks.append(f"🔴 **Uncategorized transactions:** {fmt(uncat_total)} needs categorization")
    else:
        checks.append("✅ **No uncategorized transactions**")

    # 2. Check for open invoices
    open_invoices = await qb_query(f"SELECT * FROM Invoice WHERE Balance > '0' MAXRESULTS 100")
    inv_list = open_invoices.get("QueryResponse", {}).get("Invoice", [])
    open_balance = sum(float(i.get("Balance", 0)) for i in inv_list)
    if open_balance > 0:
        checks.append(f"🟡 **Open invoices:** {len(inv_list)} invoices, {fmt(open_balance)} outstanding")
    else:
        checks.append("✅ **No open invoices**")

    # 3. Check for undeposited funds
    udf = await qb_query("SELECT * FROM Account WHERE Name = 'Undeposited Funds' MAXRESULTS 1")
    udf_accts = udf.get("QueryResponse", {}).get("Account", [])
    if udf_accts:
        udf_balance = float(udf_accts[0].get("CurrentBalance", 0))
        if abs(udf_balance) > 0:
            checks.append(f"🟡 **Undeposited funds:** {fmt(udf_balance)} — should be deposited or cleared")
        else:
            checks.append("✅ **Undeposited funds: $0.00**")

    # 4. Check Opening Balance Equity
    obe = await qb_query("SELECT * FROM Account WHERE Name = 'Opening Balance Equity' MAXRESULTS 1")
    obe_accts = obe.get("QueryResponse", {}).get("Account", [])
    if obe_accts:
        obe_balance = float(obe_accts[0].get("CurrentBalance", 0))
        if abs(obe_balance) > 0:
            checks.append(f"🟡 **Opening Balance Equity:** {fmt(obe_balance)} — CPA should close to Retained Earnings")
        else:
            checks.append("✅ **Opening Balance Equity: $0.00**")

    # 5. Check for personal accounts still active
    personal_keywords = ["personal", "mortgage", "student loan"]
    all_accts = await qb_query("SELECT * FROM Account WHERE Active = true MAXRESULTS 200")
    all_list = all_accts.get("QueryResponse", {}).get("Account", [])
    personal_active = [a for a in all_list if any(kw in a.get("Name", "").lower() for kw in personal_keywords)]
    if personal_active:
        names = ", ".join(a["Name"] for a in personal_active)
        checks.append(f"🟡 **Personal accounts still active:** {names}")
    else:
        checks.append("✅ **No personal accounts active**")

    # 6. P&L summary
    pnl = await qb_request("GET", "reports/ProfitAndLoss", params={
        "start_date": start, "end_date": end
    })
    net_income = 0
    for section in pnl.get("Rows", {}).get("Row", []):
        summary = section.get("Summary", {})
        cols = summary.get("ColData", [])
        if len(cols) >= 2 and "net" in cols[0].get("value", "").lower():
            try:
                net_income = float(cols[-1].get("value", "0"))
            except (ValueError, TypeError):
                pass
    checks.append(f"📊 **{tax_year} Net Income (Loss):** {fmt(net_income)}")

    lines = [f"## Fiscal Year-End Close Checklist — {tax_year}\n"]
    for c in checks:
        lines.append(c)

    lines.append(f"\n### Recommended Next Steps:")
    lines.append("1. Resolve any 🔴 items immediately")
    lines.append("2. Address 🟡 items before filing taxes")
    lines.append("3. Run `qb_schedule_c` for Schedule C line mapping")
    lines.append("4. Run `qb_deduction_finder` for missed deductions")
    lines.append("5. Send CPA handoff package with all reports")

    return "\n".join(lines)


# ===================================================================
# ATTACHMENT / RECEIPT UPLOAD
# ===================================================================

@mcp.tool()
async def qb_upload_receipt(entity_type: str, entity_id: str, file_name: str, file_url: str, content_type: str = "image/jpeg") -> str:
    """Attach a receipt or document to a QuickBooks transaction.
    entity_type: Purchase, Bill, Invoice, etc. entity_id: transaction ID.
    file_url: public URL of the receipt image/PDF. content_type: MIME type."""
    token = await get_access_token()
    url = f"{BASE_URL}/v3/company/{QB_REALM_ID}/upload"

    # Download the file first
    async with httpx.AsyncClient(timeout=30.0) as client:
        file_resp = await client.get(file_url)
        if file_resp.status_code != 200:
            return f"Error: Could not download file from {file_url} (status {file_resp.status_code})"
        file_data = file_resp.content

    # Upload as multipart
    import io
    boundary = "----QuickBooksAttachment"
    metadata = json.dumps({
        "AttachableRef": [{"EntityRef": {"type": entity_type, "value": entity_id}}],
        "FileName": file_name,
        "ContentType": content_type,
    })

    body = (
        f"--{boundary}\r\n"
        f"Content-Disposition: form-data; name=\"file_metadata_0\"\r\n"
        f"Content-Type: application/json\r\n\r\n"
        f"{metadata}\r\n"
        f"--{boundary}\r\n"
        f"Content-Disposition: form-data; name=\"file_content_0\"; filename=\"{file_name}\"\r\n"
        f"Content-Type: {content_type}\r\n\r\n"
    ).encode() + file_data + f"\r\n--{boundary}--\r\n".encode()

    async with httpx.AsyncClient(timeout=60.0) as client:
        resp = await client.post(url, content=body, headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": f"multipart/form-data; boundary={boundary}",
            "Accept": "application/json",
        })
        resp.raise_for_status()
        result = resp.json()

    attachable = result.get("AttachableResponse", [{}])[0].get("Attachable", {})
    return (f"✅ Receipt attached to {entity_type} #{entity_id}\n"
            f"  File: {file_name}\n"
            f"  Attachment ID: {attachable.get('Id', '?')}")


@mcp.tool()
async def qb_list_attachments(entity_type: str = "", entity_id: str = "", max_results: int = 25) -> str:
    """List attachments/receipts. Filter by entity_type and entity_id to see attachments
    for a specific transaction, or leave empty to list all recent attachments."""
    if entity_type and entity_id:
        query = (f"SELECT * FROM Attachable WHERE AttachableRef.EntityRef.Type = '{entity_type}' "
                 f"AND AttachableRef.EntityRef.Value = '{entity_id}' MAXRESULTS {max_results}")
    else:
        query = f"SELECT * FROM Attachable MAXRESULTS {max_results}"

    result = await qb_query(query)
    attachments = result.get("QueryResponse", {}).get("Attachable", [])

    if not attachments:
        return "No attachments found."

    lines = [f"## Attachments ({len(attachments)} found)\n"]
    for a in attachments:
        refs = a.get("AttachableRef", [])
        ref_str = ", ".join(f"{r.get('EntityRef', {}).get('type', '?')} #{r.get('EntityRef', {}).get('value', '?')}" for r in refs)
        lines.append(f"- **{a.get('FileName', 'Unknown')}** (ID: {a.get('Id')})")
        lines.append(f"  Size: {a.get('Size', '?')} bytes | Type: {a.get('ContentType', '?')}")
        if ref_str:
            lines.append(f"  Linked to: {ref_str}")
        lines.append("")
    return "\n".join(lines)


# ===================================================================
# RECURRING TRANSACTIONS
# ===================================================================

@mcp.tool()
async def qb_list_recurring_transactions(max_results: int = 50) -> str:
    """List all recurring transactions (templates) in QuickBooks.
    Shows recurring bills, invoices, and expenses with their schedules."""
    # QB API uses RecurringTransaction endpoint
    try:
        result = await qb_query(f"SELECT * FROM RecurringTransaction MAXRESULTS {max_results}")
        recurrings = result.get("QueryResponse", {}).get("RecurringTransaction", [])
    except Exception:
        # Recurring transactions may not be queryable via SQL in all QBO versions
        return "Recurring transactions query not available in this QuickBooks plan."

    if not recurrings:
        return "No recurring transactions found."

    lines = [f"## Recurring Transactions ({len(recurrings)} found)\n"]
    for r in recurrings:
        rtype = r.get("RecurringInfo", {}).get("RecurType", "?")
        name = r.get("RecurringInfo", {}).get("Name", "?")
        schedule = r.get("RecurringInfo", {}).get("ScheduleInfo", {})
        interval = schedule.get("IntervalType", "?")
        next_date = schedule.get("NextDate", "?")
        lines.append(f"- **{name}** ({rtype})")
        lines.append(f"  Schedule: Every {interval} | Next: {next_date}")
        lines.append("")
    return "\n".join(lines)


# ===================================================================
# SECURITY & AUDIT LOGGING
# ===================================================================

import logging
import re
from functools import wraps

# Configure audit logger — writes to file for compliance trail
_audit_logger = logging.getLogger("qb_audit")
_audit_logger.setLevel(logging.INFO)
_audit_handler = logging.StreamHandler()
_audit_handler.setFormatter(logging.Formatter(
    "%(asctime)s | %(levelname)s | %(message)s", datefmt="%Y-%m-%d %H:%M:%S"
))
_audit_logger.addHandler(_audit_handler)

# Try to add file handler for persistent audit trail
try:
    _file_handler = logging.FileHandler(
        os.path.join(os.path.dirname(os.path.abspath(__file__)), "audit.log"),
        encoding="utf-8"
    )
    _file_handler.setFormatter(logging.Formatter(
        "%(asctime)s | %(levelname)s | %(message)s", datefmt="%Y-%m-%d %H:%M:%S"
    ))
    _audit_logger.addHandler(_file_handler)
except Exception:
    pass  # File logging optional — stderr still captures audit events


def _sanitize_input(value: str, field_name: str = "input") -> str:
    """Sanitize string inputs to prevent SQL injection in QB queries.
    QuickBooks uses its own query language, but we still validate inputs."""
    if not isinstance(value, str):
        return str(value)
    # Block common injection patterns
    dangerous_patterns = [
        r";\s*(DROP|DELETE|UPDATE|INSERT|ALTER|CREATE|EXEC)",
        r"--\s*$",
        r"/\*.*\*/",
        r"'\s*(OR|AND)\s+'",
    ]
    for pattern in dangerous_patterns:
        if re.search(pattern, value, re.IGNORECASE):
            raise ValueError(f"Invalid characters in {field_name}: potential injection detected")
    # Strip control characters
    value = re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f]', '', value)
    return value


def _validate_date(date_str: str, field_name: str = "date") -> str:
    """Validate date format is YYYY-MM-DD."""
    if not re.match(r'^\d{4}-\d{2}-\d{2}$', date_str):
        raise ValueError(f"Invalid {field_name} format: '{date_str}'. Use YYYY-MM-DD.")
    try:
        datetime.strptime(date_str, "%Y-%m-%d")
    except ValueError:
        raise ValueError(f"Invalid {field_name}: '{date_str}' is not a real date.")
    return date_str


def _validate_amount(amount: float, field_name: str = "amount") -> float:
    """Validate monetary amounts are reasonable."""
    if amount < 0:
        raise ValueError(f"{field_name} cannot be negative: {amount}")
    if amount > 10_000_000:
        raise ValueError(f"{field_name} exceeds safety limit ($10M): {amount}")
    return round(amount, 2)


def _audit_log(action: str, details: str):
    """Log an auditable action for compliance."""
    _audit_logger.info(f"ACTION={action} | {details}")


# ===================================================================
# NEW TOOL 1: Reclassify Transaction
# ===================================================================

@mcp.tool()
async def qb_reclassify_transaction(entity_type: str, entity_id: str, new_account_name: str, memo: str = "") -> str:
    """Reclassify a transaction to a different expense/income account. Simpler than manual update.
    entity_type: Purchase, Deposit, Bill, etc. entity_id: the transaction ID.
    new_account_name: name of the account to reclassify to."""
    entity_type = _sanitize_input(entity_type, "entity_type")
    entity_id = _sanitize_input(entity_id, "entity_id")
    new_account_name = _sanitize_input(new_account_name, "new_account_name")

    _audit_log("RECLASSIFY_START", f"type={entity_type} id={entity_id} new_acct={new_account_name}")

    # Find the new account
    acct_result = await qb_query(f"SELECT * FROM Account WHERE Name LIKE '%{new_account_name}%' MAXRESULTS 5")
    accounts = acct_result.get("QueryResponse", {}).get("Account", [])
    if not accounts:
        return f"Account '{new_account_name}' not found. Use qb_list_accounts to see available accounts."
    if len(accounts) > 1:
        names = ", ".join(a["Name"] for a in accounts)
        return f"Multiple accounts match '{new_account_name}': {names}. Please be more specific."
    target_acct = accounts[0]

    # Read the existing transaction
    txn = await qb_read(entity_type, entity_id)
    entity_data = txn.get(entity_type, {})
    if not entity_data:
        return f"{entity_type} #{entity_id} not found."

    old_lines_info = []
    # Update all AccountBasedExpenseLineDetail lines
    for line in entity_data.get("Line", []):
        if line.get("DetailType") == "AccountBasedExpenseLineDetail":
            old_acct = line.get("AccountBasedExpenseLineDetail", {}).get("AccountRef", {}).get("name", "?")
            old_lines_info.append(f"{old_acct}: {fmt(line.get('Amount'))}")
            line["AccountBasedExpenseLineDetail"]["AccountRef"] = {
                "value": target_acct["Id"],
                "name": target_acct["Name"]
            }

    if memo:
        entity_data["PrivateNote"] = memo

    # Sparse update — include SyncToken
    result = await qb_request("POST", entity_type.lower(), json_body=entity_data)
    updated = result.get(entity_type, {})

    _audit_log("RECLASSIFY_DONE", f"type={entity_type} id={entity_id} new_acct={target_acct['Name']} (ID:{target_acct['Id']})")

    return (
        f"✅ Reclassified {entity_type} #{entity_id}\n"
        f"  From: {'; '.join(old_lines_info)}\n"
        f"  To: {target_acct['Name']}\n"
        f"  SyncToken: {updated.get('SyncToken', '?')}"
    )


# ===================================================================
# NEW TOOL 2: Batch Create Journal Entries
# ===================================================================

@mcp.tool()
async def qb_batch_create_journal_entries(entries_json: str) -> str:
    """Create multiple journal entries in one call. entries_json is a JSON array:
    [{"date": "YYYY-MM-DD", "memo": "...", "lines": [{"account_name": "...", "amount": 100.00, "type": "Debit"}, ...]}].
    Each entry must have balanced debits and credits. Returns summary of created JEs."""
    entries = json.loads(entries_json) if isinstance(entries_json, str) else entries_json

    if not isinstance(entries, list) or len(entries) == 0:
        return "Error: entries_json must be a non-empty JSON array of journal entries."
    if len(entries) > 25:
        return "Error: Maximum 25 journal entries per batch. Split into multiple calls."

    _audit_log("BATCH_JE_START", f"count={len(entries)}")

    results = []
    errors = []

    for i, entry in enumerate(entries):
        try:
            date = _validate_date(entry.get("date", ""), f"entry[{i}].date")
            memo = entry.get("memo", "")
            lines = entry.get("lines", [])

            if not lines or len(lines) < 2:
                errors.append(f"Entry {i+1}: Must have at least 2 lines (debit + credit)")
                continue

            je_lines = []
            total_debit = 0.0
            total_credit = 0.0

            for line in lines:
                acct_name = _sanitize_input(line.get("account_name", ""), "account_name")
                amount = _validate_amount(float(line.get("amount", 0)), "amount")
                posting_type = line.get("type", "Debit")

                if posting_type not in ("Debit", "Credit"):
                    errors.append(f"Entry {i+1}: Invalid posting type '{posting_type}'. Use 'Debit' or 'Credit'.")
                    break

                acct_result = await qb_query(f"SELECT * FROM Account WHERE Name LIKE '%{acct_name}%' MAXRESULTS 1")
                acct_list = acct_result.get("QueryResponse", {}).get("Account", [])
                if not acct_list:
                    errors.append(f"Entry {i+1}: Account '{acct_name}' not found.")
                    break
                acct = acct_list[0]

                if posting_type == "Debit":
                    total_debit += amount
                else:
                    total_credit += amount

                je_lines.append({
                    "DetailType": "JournalEntryLineDetail",
                    "Amount": amount,
                    "Description": line.get("description", ""),
                    "JournalEntryLineDetail": {
                        "PostingType": posting_type,
                        "AccountRef": {"value": acct["Id"], "name": acct["Name"]},
                    }
                })

            if len(je_lines) != len(lines):
                continue  # An error was recorded above

            if abs(total_debit - total_credit) > 0.01:
                errors.append(f"Entry {i+1}: Does not balance. Debits={fmt(total_debit)}, Credits={fmt(total_credit)}")
                continue

            je_body = {"TxnDate": date, "Line": je_lines}
            if memo:
                je_body["PrivateNote"] = memo

            result = await qb_request("POST", "journalentry", json_body=je_body)
            je = result.get("JournalEntry", {})
            results.append(f"  ✅ JE #{je.get('Id')} | {date} | {fmt(je.get('TotalAmt'))} | {memo[:50]}")

            _audit_log("BATCH_JE_CREATED", f"id={je.get('Id')} date={date} amount={fmt(je.get('TotalAmt'))}")

        except Exception as e:
            errors.append(f"Entry {i+1}: {str(e)}")

    output = [f"## Batch Journal Entry Results\n"]
    if results:
        output.append(f"**Created: {len(results)} journal entries**")
        output.extend(results)
    if errors:
        output.append(f"\n**Errors: {len(errors)}**")
        output.extend(f"  ❌ {e}" for e in errors)

    _audit_log("BATCH_JE_DONE", f"created={len(results)} errors={len(errors)}")
    return "\n".join(output)


# ===================================================================
# NEW TOOL 3: Home Office Calculator (Form 8829)
# ===================================================================

@mcp.tool()
async def qb_home_office_calculator(
    home_sqft: float,
    office_sqft: float,
    home_value: float,
    land_value: float = 0,
    annual_mortgage_interest: float = 0,
    annual_property_tax: float = 0,
    annual_insurance: float = 0,
    annual_utilities: float = 0,
    annual_repairs: float = 0,
    depreciation_years: float = 39,
    tax_year: str = "2025"
) -> str:
    """Calculate home office deduction using the regular method (Form 8829).
    Returns deduction breakdown by category with IRS line mappings.
    home_sqft: total home square footage. office_sqft: dedicated office square footage.
    home_value: fair market value or purchase price. land_value: land portion (not depreciable).
    All annual amounts are the full household totals — business % is calculated automatically."""
    home_sqft = _validate_amount(home_sqft, "home_sqft")
    office_sqft = _validate_amount(office_sqft, "office_sqft")
    if office_sqft > home_sqft:
        return "Error: Office square footage cannot exceed home square footage."

    biz_pct = round(office_sqft / home_sqft, 4)
    biz_pct_display = f"{biz_pct * 100:.2f}%"

    building_value = home_value - land_value
    annual_depreciation = building_value / depreciation_years

    deductions = {
        "Mortgage interest": annual_mortgage_interest * biz_pct,
        "Property taxes": annual_property_tax * biz_pct,
        "Homeowner insurance": annual_insurance * biz_pct,
        "Utilities": annual_utilities * biz_pct,
        "Repairs & maintenance": annual_repairs * biz_pct,
        "Depreciation": annual_depreciation * biz_pct,
    }

    total = sum(deductions.values())

    lines = [
        f"## Home Office Deduction — {tax_year} (Form 8829)\n",
        f"**Business Use Percentage:** {office_sqft:.0f} sq ft / {home_sqft:.0f} sq ft = **{biz_pct_display}**\n",
        f"### Deduction Breakdown",
    ]
    for category, amount in deductions.items():
        if amount > 0:
            lines.append(f"  {category}: **{fmt(amount)}**")

    lines.extend([
        f"\n### **TOTAL HOME OFFICE DEDUCTION: {fmt(total)}**",
        f"\n### Calculation Details",
        f"  Building value: {fmt(building_value)} (home {fmt(home_value)} - land {fmt(land_value)})",
        f"  Annual depreciation: {fmt(annual_depreciation)} ({fmt(building_value)} / {depreciation_years:.0f} years)",
        f"  Business %: {biz_pct_display}",
        f"\n### Schedule C Mapping",
        f"  Line 18 (Office expense): $0 — using Form 8829 instead",
        f"  Line 30 (Business use of home): **{fmt(total)}** — attach Form 8829",
        f"\n*Note: Regular method used. Simplified method ($5/sqft, max 300 sqft = $1,500) available as alternative.*",
    ])

    _audit_log("HOME_OFFICE_CALC", f"year={tax_year} biz_pct={biz_pct_display} total={fmt(total)}")
    return "\n".join(lines)


# ===================================================================
# NEW TOOL 4: Vehicle Depreciation Calculator
# ===================================================================

@mcp.tool()
async def qb_vehicle_depreciation_calculator(
    purchase_price: float,
    purchase_date: str,
    business_use_pct: float,
    vehicle_weight_lbs: float = 6001,
    is_new: bool = True,
    tax_year: str = "2025"
) -> str:
    """Calculate vehicle depreciation deduction using Section 179, bonus depreciation, and MACRS.
    purchase_price: total vehicle cost. purchase_date: YYYY-MM-DD.
    business_use_pct: decimal (0.50 = 50%). vehicle_weight_lbs: GVWR for SUV classification.
    is_new: whether vehicle is new (affects bonus depreciation eligibility).
    Returns first-year and multi-year depreciation schedule."""
    purchase_price = _validate_amount(purchase_price, "purchase_price")
    _validate_date(purchase_date, "purchase_date")

    if business_use_pct <= 0 or business_use_pct > 1:
        return "Error: business_use_pct must be between 0.01 and 1.00 (e.g., 0.50 for 50%)."

    biz_basis = purchase_price * business_use_pct
    is_heavy_suv = vehicle_weight_lbs > 6000

    lines = [
        f"## Vehicle Depreciation — {tax_year}\n",
        f"**Purchase Price:** {fmt(purchase_price)}",
        f"**Purchase Date:** {purchase_date}",
        f"**Business Use:** {business_use_pct*100:.0f}%",
        f"**Business Basis:** {fmt(biz_basis)}",
        f"**GVWR:** {vehicle_weight_lbs:,.0f} lbs ({'Heavy SUV > 6,000 lbs' if is_heavy_suv else 'Standard vehicle'})",
        f"**New/Used:** {'New' if is_new else 'Used'}",
    ]

    if is_heavy_suv:
        # Heavy SUV: Section 179 up to $30,500 (2025), then bonus depreciation, then MACRS
        sec179_limit = 30500  # 2025 limit for heavy SUVs
        sec179 = min(biz_basis, sec179_limit)
        remaining_after_179 = biz_basis - sec179

        # Bonus depreciation (40% for 2025 under phase-down)
        bonus_rate = 0.40 if is_new else 0.0
        bonus = remaining_after_179 * bonus_rate
        remaining_after_bonus = remaining_after_179 - bonus

        # MACRS 5-year, first year rate = 20%
        macrs_yr1 = remaining_after_bonus * 0.20
        total_yr1 = sec179 + bonus + macrs_yr1

        lines.extend([
            f"\n### First-Year Deduction Breakdown",
            f"  Section 179: **{fmt(sec179)}** (heavy SUV limit: {fmt(sec179_limit)})",
            f"  Bonus depreciation ({bonus_rate*100:.0f}%): **{fmt(bonus)}**",
            f"  MACRS Year 1 (20%): **{fmt(macrs_yr1)}**",
            f"  **TOTAL FIRST-YEAR DEDUCTION: {fmt(total_yr1)}**",
            f"\n### Remaining MACRS Schedule (5-year property)",
        ])

        # MACRS 5-year rates: 20%, 32%, 19.2%, 11.52%, 11.52%, 5.76%
        macrs_rates = [0.20, 0.32, 0.192, 0.1152, 0.1152, 0.0576]
        remaining_macrs = remaining_after_bonus
        for yr, rate in enumerate(macrs_rates):
            yr_deduction = remaining_macrs * rate
            year_num = int(tax_year) + yr
            marker = " ← (included above)" if yr == 0 else ""
            lines.append(f"  Year {yr+1} ({year_num}): {fmt(yr_deduction)} ({rate*100:.1f}%){marker}")

    else:
        # Standard vehicle: IRS annual limits apply
        # 2025 limits (estimated)
        limits = {1: 20200, 2: 19500, 3: 11700, 4: 6960}
        yr1_deduction = min(biz_basis, limits[1])

        lines.extend([
            f"\n### Standard Vehicle (≤ 6,000 lbs GVWR)",
            f"  Year 1 limit: **{fmt(yr1_deduction)}** (IRS max: {fmt(limits[1])})",
            f"  Year 2 limit: {fmt(limits[2])}",
            f"  Year 3 limit: {fmt(limits[3])}",
            f"  Year 4+: {fmt(limits[4])}/year until fully depreciated",
        ])

    lines.extend([
        f"\n### Schedule C Mapping",
        f"  Line 13 (Depreciation / Form 4562): report vehicle depreciation",
        f"\n*⚠️ CPA should verify: bonus depreciation rate, Section 179 limits, and business use substantiation.*",
        f"*Mileage log required to support business use percentage.*",
    ])

    _audit_log("VEHICLE_DEPR_CALC", f"year={tax_year} price={fmt(purchase_price)} biz_pct={business_use_pct}")
    return "\n".join(lines)


# ===================================================================
# NEW TOOL 5: List Journal Entries by Memo
# ===================================================================

@mcp.tool()
async def qb_list_journal_entries_by_memo(search_text: str, max_results: int = 50) -> str:
    """Search journal entries by memo/private note text. Useful for finding specific
    JEs by description (e.g., 'home office', 'depreciation', 'reclassify').
    search_text: text to search for in memo field (case-insensitive partial match)."""
    search_text = _sanitize_input(search_text, "search_text")

    # QB query doesn't support LIKE on PrivateNote, so we fetch all and filter
    result = await qb_query(f"SELECT * FROM JournalEntry MAXRESULTS 500")
    all_jes = result.get("QueryResponse", {}).get("JournalEntry", [])

    if not all_jes:
        return "No journal entries found."

    matches = []
    for je in all_jes:
        memo = je.get("PrivateNote", "")
        if search_text.lower() in memo.lower():
            matches.append(je)

    if not matches:
        return f"No journal entries found matching '{search_text}'."

    matches = matches[:max_results]

    lines = [f"## Journal Entries matching '{search_text}' ({len(matches)} found)\n"]
    for je in matches:
        je_id = je.get("Id", "?")
        date = je.get("TxnDate", "?")
        memo = je.get("PrivateNote", "")
        total = je.get("TotalAmt", 0)

        lines.append(f"**{date}** | ID: {je_id} | {fmt(float(total))}")
        if memo:
            lines.append(f"  Memo: {memo[:100]}{'...' if len(memo) > 100 else ''}")

        for line in je.get("Line", []):
            detail = line.get("JournalEntryLineDetail", {})
            acct = detail.get("AccountRef", {}).get("name", "?")
            posting = detail.get("PostingType", "?")
            amt = line.get("Amount", 0)
            lines.append(f"  - {posting} {acct}: {fmt(float(amt))}")
        lines.append("")

    return "\n".join(lines)


# ===================================================================
# NEW TOOL 6: Account Transactions
# ===================================================================

@mcp.tool()
async def qb_account_transactions(account_name: str, start_date: str, end_date: str, max_results: int = 100) -> str:
    """Get all transactions for a specific account within a date range.
    Shows every debit and credit hitting the account. Useful for account reconciliation
    and verifying balances. account_name: exact or partial account name."""
    account_name = _sanitize_input(account_name, "account_name")
    start_date = _validate_date(start_date, "start_date")
    end_date = _validate_date(end_date, "end_date")

    # Find the account
    acct_result = await qb_query(f"SELECT * FROM Account WHERE Name LIKE '%{account_name}%' MAXRESULTS 5")
    accounts = acct_result.get("QueryResponse", {}).get("Account", [])
    if not accounts:
        return f"Account '{account_name}' not found."
    if len(accounts) > 1:
        names = ", ".join(f"{a['Name']} (ID:{a['Id']})" for a in accounts)
        return f"Multiple accounts match: {names}. Please be more specific."
    acct = accounts[0]

    # Use the General Ledger report filtered by account
    params = {
        "start_date": start_date,
        "end_date": end_date,
        "account": acct["Id"],
    }
    result = await qb_request("GET", "reports/GeneralLedger", params=params)

    report = result
    rows = report.get("Rows", {}).get("Row", [])

    lines = [
        f"## Account Transactions: {acct['Name']} (ID: {acct['Id']})",
        f"**Period:** {start_date} to {end_date}",
        f"**Type:** {acct.get('AccountType', '?')} / {acct.get('AccountSubType', '')}",
        f"**Current Balance:** {fmt(float(acct.get('CurrentBalance', 0)))}",
        "",
    ]

    _parse_report_rows(rows, lines)

    if len(lines) <= 5:
        lines.append("No transactions found for this account in the date range.")

    return "\n".join(lines)


# ===================================================================
# NEW TOOL 7: Schedule C Detailed
# ===================================================================

@mcp.tool()
async def qb_schedule_c_detailed(tax_year: str = "2025") -> str:
    """Generate a detailed Schedule C (Profit or Loss from Business) mapping with
    QuickBooks account-level detail for each line. More granular than qb_schedule_c —
    shows which QB accounts feed each Schedule C line. tax_year in YYYY format."""
    start = f"{tax_year}-01-01"
    end = f"{tax_year}-12-31"

    # Get P&L for the year
    params = {"start_date": start, "end_date": end, "summarize_by": "Total"}
    result = await qb_request("GET", "reports/ProfitAndLoss", params=params)

    # Get all accounts for mapping
    accts_result = await qb_query("SELECT * FROM Account MAXRESULTS 200")
    all_accounts = accts_result.get("QueryResponse", {}).get("Account", [])

    # Build account balance lookup
    acct_balances = {}
    for a in all_accounts:
        name = a.get("Name", "")
        bal = float(a.get("CurrentBalance", 0))
        acct_type = a.get("AccountType", "")
        acct_balances[name] = {"balance": bal, "type": acct_type, "id": a.get("Id", "")}

    # Schedule C line mapping
    line_map = {
        "Line 1 - Gross receipts": ["Sales of Product Income", "Service/Fee Income", "Other Income"],
        "Line 6 - Other income": ["Other income", "Interest income"],
        "Line 8 - Advertising": ["Advertising", "Marketing"],
        "Line 9 - Car/truck expenses": ["Business Vehicles", "Auto", "Car", "Vehicle"],
        "Line 10 - Commissions": ["Commissions"],
        "Line 11 - Contract labor": ["Contract labor", "Contractors", "Subcontractors"],
        "Line 13 - Depreciation": ["Depreciation"],
        "Line 15 - Insurance": ["Insurance", "Homeowner & rental insurance"],
        "Line 16a - Mortgage interest": ["Mortgage interest"],
        "Line 17 - Legal/professional": ["Legal", "Professional", "Accounting", "Tax"],
        "Line 18 - Office expense": ["Office", "Supplies", "Stationery"],
        "Line 20a - Rent (vehicles)": [],
        "Line 20b - Rent (other)": ["Rent"],
        "Line 21 - Repairs": ["Repairs & maintenance"],
        "Line 22 - Supplies": ["Supplies"],
        "Line 23 - Taxes/licenses": ["Property taxes", "Taxes", "Licenses"],
        "Line 24a - Travel": ["Travel"],
        "Line 24b - Meals": ["Meals"],
        "Line 25 - Utilities": ["Utilities", "Home utilities", "Electric", "Gas", "Water", "Internet", "Cell phone", "Communications"],
        "Line 27a - Other expenses": ["Subscriptions", "Software", "Training", "Education", "Bank charges", "Fees"],
        "Line 30 - Business use of home": [],
    }

    lines = [
        f"## Schedule C Detail — {tax_year}\n",
        f"**Vaspera Capital LLC / NutriFitAI LLC**",
        f"**EIN:** Check QB Company Info",
        f"**Period:** {start} to {end}\n",
    ]

    total_income = 0.0
    total_expenses = 0.0

    for sched_line, keywords in line_map.items():
        matching_accounts = []
        line_total = 0.0

        for acct_name, info in acct_balances.items():
            for kw in keywords:
                if kw.lower() in acct_name.lower():
                    bal = abs(info["balance"])
                    if bal > 0:
                        matching_accounts.append((acct_name, bal, info["id"]))
                        line_total += bal
                    break

        if matching_accounts or "Line 1" in sched_line or "Line 30" in sched_line:
            lines.append(f"### {sched_line}: **{fmt(line_total)}**")
            for name, bal, aid in matching_accounts:
                lines.append(f"  - {name} (#{aid}): {fmt(bal)}")
            if not matching_accounts:
                lines.append(f"  - (no matching accounts)")
            lines.append("")

            if "Line 1" in sched_line or "Line 6" in sched_line:
                total_income += line_total
            else:
                total_expenses += line_total

    net = total_income - total_expenses
    lines.extend([
        f"\n---",
        f"### **Summary**",
        f"  Total Income (Lines 1-6): {fmt(total_income)}",
        f"  Total Expenses (Lines 8-27): {fmt(total_expenses)}",
        f"  **Net Profit/Loss (Line 31): {fmt(net)}**",
        f"\n*Note: Line 30 (Business use of home) calculated separately via Form 8829.*",
        f"*CPA should verify account-to-line mappings match actual filing.*",
    ])

    _audit_log("SCHEDULE_C_DETAIL", f"year={tax_year} income={fmt(total_income)} expenses={fmt(total_expenses)}")
    return "\n".join(lines)


# ===================================================================
# NEW TOOL 8: Create Sub-Account
# ===================================================================

@mcp.tool()
async def qb_create_sub_account(name: str, parent_account_name: str, account_type: str = "", account_sub_type: str = "", description: str = "") -> str:
    """Create a sub-account under an existing parent account. Simpler than qb_create_account
    for building account hierarchies. name: new sub-account name.
    parent_account_name: name of existing parent account.
    account_type/account_sub_type: inherited from parent if not specified."""
    name = _sanitize_input(name, "name")
    parent_account_name = _sanitize_input(parent_account_name, "parent_account_name")

    # Find parent account
    parent_result = await qb_query(f"SELECT * FROM Account WHERE Name = '{parent_account_name}' MAXRESULTS 5")
    parents = parent_result.get("QueryResponse", {}).get("Account", [])
    if not parents:
        # Try partial match
        parent_result = await qb_query(f"SELECT * FROM Account WHERE Name LIKE '%{parent_account_name}%' MAXRESULTS 5")
        parents = parent_result.get("QueryResponse", {}).get("Account", [])
    if not parents:
        return f"Parent account '{parent_account_name}' not found."
    if len(parents) > 1:
        names = ", ".join(f"{a['Name']} (ID:{a['Id']})" for a in parents)
        return f"Multiple accounts match: {names}. Please be more specific."
    parent = parents[0]

    body = {
        "Name": name,
        "SubAccount": True,
        "ParentRef": {"value": parent["Id"], "name": parent["Name"]},
        "AccountType": account_type or parent.get("AccountType", "Expense"),
        "AccountSubType": account_sub_type or parent.get("AccountSubType", ""),
    }
    if description:
        body["Description"] = description

    result = await qb_request("POST", "account", json_body=body)
    new_acct = result.get("Account", {})

    _audit_log("CREATE_SUB_ACCOUNT", f"name={name} parent={parent['Name']} id={new_acct.get('Id')}")

    return (
        f"✅ Created sub-account '{new_acct.get('FullyQualifiedName', name)}' (ID: {new_acct.get('Id')})\n"
        f"  Parent: {parent['Name']} (ID: {parent['Id']})\n"
        f"  Type: {new_acct.get('AccountType', '?')} / {new_acct.get('AccountSubType', '')}"
    )


# ===================================================================
# NEW TOOL 9: Transaction Detail
# ===================================================================

@mcp.tool()
async def qb_transaction_detail(entity_type: str, entity_id: str) -> str:
    """Get complete details for a single transaction. entity_type: Purchase, Deposit,
    Transfer, JournalEntry, Bill, Invoice, Payment, SalesReceipt, BillPayment, etc.
    entity_id: the transaction ID. Returns all fields including line items, memo, metadata."""
    entity_type = _sanitize_input(entity_type, "entity_type")
    entity_id = _sanitize_input(entity_id, "entity_id")

    valid_types = [
        "Purchase", "Deposit", "Transfer", "JournalEntry", "Bill",
        "Invoice", "Payment", "SalesReceipt", "BillPayment", "Estimate",
        "CreditMemo", "RefundReceipt", "VendorCredit"
    ]
    if entity_type not in valid_types:
        return f"Invalid entity_type '{entity_type}'. Valid types: {', '.join(valid_types)}"

    txn = await qb_read(entity_type, entity_id)
    entity_data = txn.get(entity_type, {})
    if not entity_data:
        return f"{entity_type} #{entity_id} not found."

    lines = [f"## {entity_type} #{entity_id} — Full Detail\n"]

    # Common fields
    for field, label in [
        ("TxnDate", "Date"), ("TotalAmt", "Total"), ("PrivateNote", "Memo"),
        ("DocNumber", "Doc Number"), ("TxnStatus", "Status"),
    ]:
        val = entity_data.get(field)
        if val is not None:
            if field == "TotalAmt":
                lines.append(f"**{label}:** {fmt(float(val))}")
            else:
                lines.append(f"**{label}:** {val}")

    # Entity references
    for ref_field, label in [
        ("EntityRef", "Vendor/Customer"), ("AccountRef", "Account"),
        ("DepositToAccountRef", "Deposit To"), ("FromAccountRef", "From Account"),
        ("ToAccountRef", "To Account"),
    ]:
        ref = entity_data.get(ref_field, {})
        if ref:
            lines.append(f"**{label}:** {ref.get('name', '?')} (ID: {ref.get('value', '?')})")

    # Line items
    txn_lines = entity_data.get("Line", [])
    if txn_lines:
        lines.append(f"\n### Line Items ({len(txn_lines)})")
        for i, line in enumerate(txn_lines, 1):
            detail_type = line.get("DetailType", "?")
            amount = line.get("Amount", 0)
            desc = line.get("Description", "")

            lines.append(f"\n**Line {i}:** {fmt(float(amount))} ({detail_type})")
            if desc:
                lines.append(f"  Description: {desc}")

            # Parse detail based on type
            if detail_type == "AccountBasedExpenseLineDetail":
                detail = line.get("AccountBasedExpenseLineDetail", {})
                lines.append(f"  Account: {detail.get('AccountRef', {}).get('name', '?')}")
            elif detail_type == "JournalEntryLineDetail":
                detail = line.get("JournalEntryLineDetail", {})
                lines.append(f"  Account: {detail.get('AccountRef', {}).get('name', '?')}")
                lines.append(f"  Posting: {detail.get('PostingType', '?')}")
            elif detail_type == "ItemBasedExpenseLineDetail":
                detail = line.get("ItemBasedExpenseLineDetail", {})
                lines.append(f"  Item: {detail.get('ItemRef', {}).get('name', '?')}")

    # Metadata
    meta = entity_data.get("MetaData", {})
    if meta:
        lines.append(f"\n### Metadata")
        lines.append(f"  Created: {meta.get('CreateTime', '?')}")
        lines.append(f"  Updated: {meta.get('LastUpdatedTime', '?')}")
    lines.append(f"  SyncToken: {entity_data.get('SyncToken', '?')}")

    return "\n".join(lines)


# ===================================================================
# NEW TOOL 10: Delete Journal Entry
# ===================================================================

@mcp.tool()
async def qb_delete_journal_entry(journal_entry_id: str, confirm: bool = False) -> str:
    """Delete a journal entry. Use for removing draft, duplicate, or test JEs.
    journal_entry_id: the JE ID to delete. confirm: must be True to execute deletion.
    ⚠️ This is PERMANENT. Use qb_void_transaction to void instead of delete when possible."""
    journal_entry_id = _sanitize_input(journal_entry_id, "journal_entry_id")

    if not confirm:
        # Read the JE first to show what would be deleted
        txn = await qb_read("JournalEntry", journal_entry_id)
        je = txn.get("JournalEntry", {})
        if not je:
            return f"Journal entry #{journal_entry_id} not found."

        memo = je.get("PrivateNote", "(no memo)")
        date = je.get("TxnDate", "?")
        total = je.get("TotalAmt", 0)

        return (
            f"⚠️ **Confirm Deletion**\n"
            f"  JE #{journal_entry_id} | {date} | {fmt(float(total))}\n"
            f"  Memo: {memo[:100]}\n\n"
            f"To delete, call again with confirm=True.\n"
            f"Consider using qb_void_transaction instead (keeps audit trail)."
        )

    _audit_log("DELETE_JE_START", f"id={journal_entry_id}")

    # Read to get SyncToken
    txn = await qb_read("JournalEntry", journal_entry_id)
    je = txn.get("JournalEntry", {})
    if not je:
        return f"Journal entry #{journal_entry_id} not found."

    # QB delete: POST with ?operation=delete
    delete_body = {"Id": journal_entry_id, "SyncToken": je["SyncToken"]}
    result = await qb_request("POST", "journalentry?operation=delete", json_body=delete_body)

    _audit_log("DELETE_JE_DONE", f"id={journal_entry_id} memo={je.get('PrivateNote', '')[:50]}")

    return f"✅ Journal entry #{journal_entry_id} permanently deleted."


# ===================================================================
# NEW: 1099 Contractor Reporting
# ===================================================================

@mcp.tool()
async def qb_1099_contractor_report(tax_year: str = "2025", threshold: float = 600.0) -> str:
    """Generate 1099-NEC contractor reporting data for a tax year.
    Lists all vendors paid >= threshold (default $600) via non-employee compensation.
    Shows vendor name, total paid, TIN status, and address.
    Useful for year-end tax filing prep and 1099-NEC generation.
    tax_year: YYYY format. threshold: minimum payment amount to include (IRS default $600)."""
    start = f"{tax_year}-01-01"
    end = f"{tax_year}-12-31"
    threshold = _validate_amount(threshold, "threshold")

    # Get all vendors
    vendor_result = await qb_query("SELECT * FROM Vendor MAXRESULTS 500")
    vendors = vendor_result.get("QueryResponse", {}).get("Vendor", [])
    if not vendors:
        return "No vendors found."

    # Get all purchases for the year
    purchase_result = await qb_query(
        f"SELECT * FROM Purchase WHERE TxnDate >= '{start}' AND TxnDate <= '{end}' MAXRESULTS 1000"
    )
    purchases = purchase_result.get("QueryResponse", {}).get("Purchase", [])

    # Get all bill payments for the year
    billpay_result = await qb_query(
        f"SELECT * FROM BillPayment WHERE TxnDate >= '{start}' AND TxnDate <= '{end}' MAXRESULTS 1000"
    )
    bill_payments = billpay_result.get("QueryResponse", {}).get("BillPayment", [])

    # Get all bills for the year (for bill-based payments)
    bill_result = await qb_query(
        f"SELECT * FROM Bill WHERE TxnDate >= '{start}' AND TxnDate <= '{end}' MAXRESULTS 1000"
    )
    bills = bill_result.get("QueryResponse", {}).get("Bill", [])

    # Build vendor lookup
    vendor_map = {}
    for v in vendors:
        vid = v.get("Id", "")
        vendor_map[vid] = {
            "name": v.get("DisplayName", "?"),
            "company": v.get("CompanyName", ""),
            "tin": v.get("TaxIdentifier", ""),
            "vendor1099": v.get("Vendor1099", False),
            "email": v.get("PrimaryEmailAddr", {}).get("Address", ""),
            "address": "",
            "total_paid": 0.0,
            "payment_count": 0,
        }
        addr = v.get("BillAddr", {})
        if addr:
            parts = [addr.get("Line1", ""), addr.get("City", ""),
                     addr.get("CountrySubDivisionCode", ""), addr.get("PostalCode", "")]
            vendor_map[vid]["address"] = ", ".join(p for p in parts if p)

    # Tally from purchases (direct payments)
    for p in purchases:
        entity_ref = p.get("EntityRef", {})
        vid = entity_ref.get("value", "")
        if vid in vendor_map:
            amount = float(p.get("TotalAmt", 0))
            vendor_map[vid]["total_paid"] += amount
            vendor_map[vid]["payment_count"] += 1

    # Tally from bills
    for b in bills:
        entity_ref = b.get("VendorRef", {})
        vid = entity_ref.get("value", "")
        if vid in vendor_map:
            amount = float(b.get("TotalAmt", 0))
            vendor_map[vid]["total_paid"] += amount
            vendor_map[vid]["payment_count"] += 1

    # Filter vendors above threshold
    reportable = []
    for vid, info in vendor_map.items():
        if info["total_paid"] >= threshold:
            reportable.append(info)

    reportable.sort(key=lambda x: x["total_paid"], reverse=True)

    lines = [
        f"## 1099-NEC Contractor Report — {tax_year}",
        f"**Threshold:** {fmt(threshold)}",
        f"**Reportable Vendors:** {len(reportable)}\n",
    ]

    grand_total = 0.0
    missing_tin = 0
    missing_addr = 0

    for i, v in enumerate(reportable, 1):
        grand_total += v["total_paid"]
        tin_status = "✅ On file" if v["tin"] else "⚠️ MISSING"
        flag_1099 = "Yes" if v["vendor1099"] else "No"

        if not v["tin"]:
            missing_tin += 1
        if not v["address"]:
            missing_addr += 1

        lines.append(f"### {i}. {v['name']}")
        lines.append(f"  **Total Paid:** {fmt(v['total_paid'])} ({v['payment_count']} payments)")
        lines.append(f"  **1099 Vendor Flag:** {flag_1099}")
        lines.append(f"  **TIN Status:** {tin_status}")
        if v["company"]:
            lines.append(f"  **Company:** {v['company']}")
        if v["address"]:
            lines.append(f"  **Address:** {v['address']}")
        else:
            lines.append(f"  **Address:** ⚠️ MISSING — needed for 1099-NEC filing")
        if v["email"]:
            lines.append(f"  **Email:** {v['email']}")
        lines.append("")

    lines.extend([
        f"---",
        f"### Summary",
        f"  Total reportable payments: {fmt(grand_total)}",
        f"  Vendors requiring 1099-NEC: {len(reportable)}",
        f"  Missing TIN: {missing_tin}",
        f"  Missing address: {missing_addr}",
        "",
    ])

    if missing_tin > 0 or missing_addr > 0:
        lines.append("### ⚠️ Action Items")
        if missing_tin > 0:
            lines.append(f"  - Collect W-9 from {missing_tin} vendor(s) to get TIN")
        if missing_addr > 0:
            lines.append(f"  - Collect mailing address from {missing_addr} vendor(s)")
        lines.append(f"  - 1099-NEC filing deadline: January 31, {int(tax_year)+1}")
        lines.append(f"  - Use IRS FIRE system or approved e-file provider")

    _audit_log("1099_REPORT", f"year={tax_year} vendors={len(reportable)} total={fmt(grand_total)}")
    return "\n".join(lines)


# ===================================================================
# NEW: Anomaly Detection
# ===================================================================

@mcp.tool()
async def qb_anomaly_detection(start_date: str, end_date: str, sensitivity: str = "medium") -> str:
    """Analyze transactions for anomalies and unusual patterns.
    Detects: unusually large transactions, duplicate payments, weekend/holiday activity,
    round-number payments, vendor concentration risk, and statistical outliers.
    sensitivity: low (flag only extreme), medium (balanced), high (flag more).
    start_date/end_date in YYYY-MM-DD format."""
    start_date = _validate_date(start_date, "start_date")
    end_date = _validate_date(end_date, "end_date")
    sensitivity = _sanitize_input(sensitivity, "sensitivity")

    if sensitivity not in ("low", "medium", "high"):
        sensitivity = "medium"

    # Set z-score thresholds based on sensitivity
    z_thresholds = {"low": 3.0, "medium": 2.0, "high": 1.5}
    z_limit = z_thresholds[sensitivity]

    # Fetch all purchases
    purchase_result = await qb_query(
        f"SELECT * FROM Purchase WHERE TxnDate >= '{start_date}' AND TxnDate <= '{end_date}' MAXRESULTS 1000"
    )
    purchases = purchase_result.get("QueryResponse", {}).get("Purchase", [])

    # Fetch bills
    bill_result = await qb_query(
        f"SELECT * FROM Bill WHERE TxnDate >= '{start_date}' AND TxnDate <= '{end_date}' MAXRESULTS 1000"
    )
    bills = bill_result.get("QueryResponse", {}).get("Bill", [])

    # Equity/owner account keywords — these are personal transfers (CC payments,
    # owner draws, personal expenses), NOT vendor payments. We exclude them from
    # round-number, outlier, and weekend checks to reduce false positives.
    EQUITY_KEYWORDS = {
        "owner investment", "owner draw", "personal expense", "personal healthcare",
        "opening balance equity", "federal estimated tax", "state tax",
        "owner retirement", "health insurance premium", "hsa contribution",
    }

    def _is_equity_txn(txn):
        """Check if a transaction is an owner/equity transfer (not a real vendor payment)."""
        acct = txn.get("account_category", "").lower()
        memo = txn.get("memo", "").lower()
        for kw in EQUITY_KEYWORDS:
            if kw in acct or kw in memo:
                return True
        # Also catch common CC payment memos from bank imports
        if "mobile payment" in memo and "thank you" in memo:
            return True
        if "online transfer" in memo and ("payment" in memo or "debit" in memo):
            return True
        return False

    # Combine into unified transaction list
    all_txns = []
    for p in purchases:
        # Extract expense category from line items for equity detection
        line_categories = []
        for line in p.get("Line", []):
            detail = line.get("AccountBasedExpenseLineDetail", {})
            acct_name = detail.get("AccountRef", {}).get("name", "")
            if acct_name:
                line_categories.append(acct_name)
        all_txns.append({
            "type": "Purchase",
            "id": p.get("Id", "?"),
            "date": p.get("TxnDate", "?"),
            "amount": float(p.get("TotalAmt", 0)),
            "vendor": p.get("EntityRef", {}).get("name", "Unknown"),
            "memo": p.get("PrivateNote", p.get("Memo", "")),
            "account": p.get("AccountRef", {}).get("name", "?"),
            "account_category": ", ".join(line_categories),
            "is_equity": False,  # set below
        })
    for b in bills:
        line_categories = []
        for line in b.get("Line", []):
            detail = line.get("AccountBasedExpenseLineDetail", {})
            acct_name = detail.get("AccountRef", {}).get("name", "")
            if acct_name:
                line_categories.append(acct_name)
        all_txns.append({
            "type": "Bill",
            "id": b.get("Id", "?"),
            "date": b.get("TxnDate", "?"),
            "amount": float(b.get("TotalAmt", 0)),
            "vendor": b.get("VendorRef", {}).get("name", "Unknown"),
            "memo": b.get("PrivateNote", ""),
            "account": "",
            "account_category": ", ".join(line_categories),
            "is_equity": False,
        })

    # Tag equity transactions
    for t in all_txns:
        t["is_equity"] = _is_equity_txn(t)

    if not all_txns:
        return "No transactions found in the date range."

    # Use only non-equity, business transactions for statistical baseline
    biz_txns = [t for t in all_txns if not t["is_equity"]]
    amounts = [t["amount"] for t in biz_txns if t["amount"] > 0]
    equity_count = sum(1 for t in all_txns if t["is_equity"])
    if not amounts:
        return "No non-zero transactions found."

    # Statistical analysis
    import statistics
    mean_amt = statistics.mean(amounts)
    stdev_amt = statistics.stdev(amounts) if len(amounts) > 1 else 0
    median_amt = statistics.median(amounts)

    anomalies = []

    # 1. Statistical outliers (z-score) — skip equity/owner transfers
    for t in biz_txns:
        if stdev_amt > 0 and t["amount"] > 0:
            z = (t["amount"] - mean_amt) / stdev_amt
            if z > z_limit:
                anomalies.append({
                    "category": "Statistical Outlier",
                    "severity": "HIGH" if z > 3 else "MEDIUM",
                    "detail": f"{t['type']} #{t['id']} on {t['date']}: {fmt(t['amount'])} to {t['vendor']} (z-score: {z:.1f})",
                    "txn": t,
                })

    # 2. Duplicate detection (same vendor + similar amount within 3 days)
    # Skip equity transactions — CC payment on credit card + bank debit are two
    # legs of the same transfer, not duplicates.
    from datetime import timedelta
    non_equity_txns = [t for t in all_txns if not t["is_equity"]]
    sorted_txns = sorted(non_equity_txns, key=lambda x: (x["vendor"], x["date"]))
    for i in range(len(sorted_txns) - 1):
        a = sorted_txns[i]
        b = sorted_txns[i + 1]
        if a["vendor"] == b["vendor"] and a["vendor"] != "Unknown":
            try:
                date_a = datetime.strptime(a["date"], "%Y-%m-%d")
                date_b = datetime.strptime(b["date"], "%Y-%m-%d")
                day_diff = abs((date_b - date_a).days)
                amt_diff = abs(a["amount"] - b["amount"])
                if day_diff <= 3 and amt_diff < 0.01 and a["amount"] > 0:
                    anomalies.append({
                        "category": "Potential Duplicate",
                        "severity": "HIGH",
                        "detail": f"{a['vendor']}: {fmt(a['amount'])} on {a['date']} & {b['date']} ({a['type']} #{a['id']} & #{b['id']})",
                        "txn": a,
                    })
            except ValueError:
                pass

    # 3. Round-number payments — skip equity (CC payments are naturally round)
    for t in biz_txns:
        if t["amount"] >= 1000 and t["amount"] == round(t["amount"], -2):
            anomalies.append({
                "category": "Round Number",
                "severity": "LOW",
                "detail": f"{t['type']} #{t['id']}: {fmt(t['amount'])} to {t['vendor']} on {t['date']}",
                "txn": t,
            })

    # 4. Weekend transactions — skip equity (people pay CC bills on weekends)
    for t in biz_txns:
        try:
            d = datetime.strptime(t["date"], "%Y-%m-%d")
            if d.weekday() >= 5:  # Saturday=5, Sunday=6
                day_name = "Saturday" if d.weekday() == 5 else "Sunday"
                anomalies.append({
                    "category": "Weekend Transaction",
                    "severity": "LOW",
                    "detail": f"{t['type']} #{t['id']}: {fmt(t['amount'])} to {t['vendor']} on {t['date']} ({day_name})",
                    "txn": t,
                })
        except ValueError:
            pass

    # 5. Vendor concentration risk — use business txns only for accurate %
    vendor_totals = {}
    total_spend = sum(amounts) if amounts else 0
    for t in biz_txns:
        v = t["vendor"]
        vendor_totals[v] = vendor_totals.get(v, 0) + t["amount"]
    for v, total in vendor_totals.items():
        pct = (total / total_spend * 100) if total_spend > 0 else 0
        if pct > 30 and v != "Unknown":
            anomalies.append({
                "category": "Vendor Concentration",
                "severity": "MEDIUM",
                "detail": f"{v}: {fmt(total)} = {pct:.1f}% of total spend",
                "txn": None,
            })

    # Deduplicate
    seen = set()
    unique_anomalies = []
    for a in anomalies:
        key = a["detail"]
        if key not in seen:
            seen.add(key)
            unique_anomalies.append(a)

    # Sort by severity
    sev_order = {"HIGH": 0, "MEDIUM": 1, "LOW": 2}
    unique_anomalies.sort(key=lambda x: sev_order.get(x["severity"], 3))

    lines = [
        f"## Transaction Anomaly Report",
        f"**Period:** {start_date} to {end_date}",
        f"**Total Transactions:** {len(all_txns)} ({equity_count} owner/equity transfers excluded from checks)",
        f"**Business Transactions Analyzed:** {len(biz_txns)}",
        f"**Sensitivity:** {sensitivity} (z-score threshold: {z_limit})",
        f"**Anomalies Found:** {len(unique_anomalies)}\n",
        f"### Statistics (business transactions only)",
        f"  Mean transaction: {fmt(mean_amt)}",
        f"  Median transaction: {fmt(median_amt)}",
        f"  Std deviation: {fmt(stdev_amt)}",
        f"  Total business spend: {fmt(total_spend)}\n",
    ]

    if not unique_anomalies:
        lines.append("✅ No anomalies detected at this sensitivity level.")
    else:
        # Group by category
        from collections import defaultdict
        by_cat = defaultdict(list)
        for a in unique_anomalies:
            by_cat[a["category"]].append(a)

        for cat, items in by_cat.items():
            lines.append(f"### {cat} ({len(items)})")
            for a in items:
                icon = "🔴" if a["severity"] == "HIGH" else "🟡" if a["severity"] == "MEDIUM" else "🟢"
                lines.append(f"  {icon} [{a['severity']}] {a['detail']}")
            lines.append("")

    _audit_log("ANOMALY_DETECTION", f"period={start_date}/{end_date} txns={len(all_txns)} anomalies={len(unique_anomalies)}")
    return "\n".join(lines)


# ===================================================================
# NEW: Credit Memo Management
# ===================================================================

@mcp.tool()
async def qb_list_credit_memos(start_date: str, end_date: str, customer_name: str = "", max_results: int = 100) -> str:
    """List credit memos (customer credits/refunds) within a date range.
    Credit memos reduce what a customer owes. Optionally filter by customer_name.
    start_date/end_date in YYYY-MM-DD format."""
    start_date = _validate_date(start_date, "start_date")
    end_date = _validate_date(end_date, "end_date")

    query = f"SELECT * FROM CreditMemo WHERE TxnDate >= '{start_date}' AND TxnDate <= '{end_date}'"
    if customer_name:
        customer_name = _sanitize_input(customer_name, "customer_name")
        # Look up customer first
        cust_result = await qb_query(f"SELECT * FROM Customer WHERE DisplayName LIKE '%{customer_name}%' MAXRESULTS 5")
        customers = cust_result.get("QueryResponse", {}).get("Customer", [])
        if customers:
            cust_id = customers[0]["Id"]
            query += f" AND CustomerRef = '{cust_id}'"
    query += f" MAXRESULTS {max_results}"

    result = await qb_query(query)
    memos = result.get("QueryResponse", {}).get("CreditMemo", [])

    if not memos:
        return "No credit memos found in the date range."

    total = 0.0
    lines = [f"## Credit Memos ({start_date} to {end_date})\n"]
    for cm in memos:
        cm_id = cm.get("Id", "?")
        date = cm.get("TxnDate", "?")
        cust = cm.get("CustomerRef", {}).get("name", "?")
        amount = float(cm.get("TotalAmt", 0))
        balance = float(cm.get("RemainingCredit", 0))
        memo = cm.get("PrivateNote", "")
        doc_num = cm.get("DocNumber", "")
        total += amount

        lines.append(f"**#{doc_num or cm_id}** | {date} | {cust}")
        lines.append(f"  Amount: {fmt(amount)} | Remaining: {fmt(balance)}")
        if memo:
            lines.append(f"  Memo: {memo[:80]}")
        lines.append("")

    lines.append(f"---\n**Total Credit Memos:** {fmt(total)} ({len(memos)} memos)")
    return "\n".join(lines)


@mcp.tool()
async def qb_create_credit_memo(customer_name: str, line_items: str, date: str = "", memo: str = "") -> str:
    """Create a credit memo for a customer. Reduces what the customer owes.
    customer_name: customer to credit. line_items: JSON string array
    [{\"description\": \"Returned item\", \"amount\": 50.00}].
    date: YYYY-MM-DD (defaults to today). memo: internal note."""
    customer_name = _sanitize_input(customer_name, "customer_name")
    import json as _json

    # Find customer
    cust_result = await qb_query(f"SELECT * FROM Customer WHERE DisplayName LIKE '%{customer_name}%' MAXRESULTS 5")
    customers = cust_result.get("QueryResponse", {}).get("Customer", [])
    if not customers:
        return f"Customer '{customer_name}' not found."
    if len(customers) > 1:
        names = ", ".join(f"{c['DisplayName']} (ID:{c['Id']})" for c in customers)
        return f"Multiple customers match: {names}. Be more specific."
    customer = customers[0]

    try:
        items = _json.loads(line_items)
    except _json.JSONDecodeError:
        return "Invalid line_items JSON. Use format: [{\"description\": \"...\", \"amount\": 100}]"

    cm_lines = []
    for item in items:
        amt = _validate_amount(float(item.get("amount", 0)), "line amount")
        cm_lines.append({
            "Amount": amt,
            "Description": item.get("description", ""),
            "DetailType": "SalesItemLineDetail",
            "SalesItemLineDetail": {
                "ItemRef": {"value": "1", "name": "Services"},
            },
        })

    body = {
        "CustomerRef": {"value": customer["Id"]},
        "Line": cm_lines,
    }
    if date:
        body["TxnDate"] = _validate_date(date, "date")
    if memo:
        body["PrivateNote"] = memo

    result = await qb_request("POST", "creditmemo", json_body=body)
    cm = result.get("CreditMemo", {})

    _audit_log("CREATE_CREDIT_MEMO", f"customer={customer['DisplayName']} amount={fmt(float(cm.get('TotalAmt', 0)))}")
    return (
        f"✅ Credit memo created\n"
        f"  ID: {cm.get('Id')}\n"
        f"  Customer: {customer['DisplayName']}\n"
        f"  Amount: {fmt(float(cm.get('TotalAmt', 0)))}\n"
        f"  Date: {cm.get('TxnDate', 'today')}"
    )


# ===================================================================
# NEW: Vendor Credit Management
# ===================================================================

@mcp.tool()
async def qb_list_vendor_credits(start_date: str, end_date: str, vendor_name: str = "", max_results: int = 100) -> str:
    """List vendor credits within a date range. Vendor credits reduce what you owe a vendor.
    Optionally filter by vendor_name. start_date/end_date in YYYY-MM-DD format."""
    start_date = _validate_date(start_date, "start_date")
    end_date = _validate_date(end_date, "end_date")

    query = f"SELECT * FROM VendorCredit WHERE TxnDate >= '{start_date}' AND TxnDate <= '{end_date}'"
    if vendor_name:
        vendor_name = _sanitize_input(vendor_name, "vendor_name")
        vend_result = await qb_query(f"SELECT * FROM Vendor WHERE DisplayName LIKE '%{vendor_name}%' MAXRESULTS 5")
        vendors = vend_result.get("QueryResponse", {}).get("Vendor", [])
        if vendors:
            vend_id = vendors[0]["Id"]
            query += f" AND VendorRef = '{vend_id}'"
    query += f" MAXRESULTS {max_results}"

    result = await qb_query(query)
    credits = result.get("QueryResponse", {}).get("VendorCredit", [])

    if not credits:
        return "No vendor credits found in the date range."

    total = 0.0
    lines = [f"## Vendor Credits ({start_date} to {end_date})\n"]
    for vc in credits:
        vc_id = vc.get("Id", "?")
        date = vc.get("TxnDate", "?")
        vend = vc.get("VendorRef", {}).get("name", "?")
        amount = float(vc.get("TotalAmt", 0))
        memo = vc.get("PrivateNote", "")
        total += amount

        lines.append(f"**#{vc_id}** | {date} | {vend} | {fmt(amount)}")
        if memo:
            lines.append(f"  Memo: {memo[:80]}")

        for line in vc.get("Line", []):
            acct = line.get("AccountBasedExpenseLineDetail", {}).get("AccountRef", {}).get("name", "")
            if acct:
                lines.append(f"  - {acct}: {fmt(float(line.get('Amount', 0)))}")
        lines.append("")

    lines.append(f"---\n**Total Vendor Credits:** {fmt(total)} ({len(credits)} credits)")
    return "\n".join(lines)


@mcp.tool()
async def qb_create_vendor_credit(vendor_name: str, amount: float, account_name: str, date: str = "", description: str = "") -> str:
    """Create a vendor credit. Reduces what you owe a vendor (e.g., refund, return, pricing adjustment).
    vendor_name: vendor issuing the credit. amount: credit amount.
    account_name: expense account to reduce. date: YYYY-MM-DD (defaults to today)."""
    vendor_name = _sanitize_input(vendor_name, "vendor_name")
    account_name = _sanitize_input(account_name, "account_name")
    amount = _validate_amount(amount, "amount")

    # Find vendor
    vend_result = await qb_query(f"SELECT * FROM Vendor WHERE DisplayName LIKE '%{vendor_name}%' MAXRESULTS 5")
    vendors = vend_result.get("QueryResponse", {}).get("Vendor", [])
    if not vendors:
        return f"Vendor '{vendor_name}' not found."
    if len(vendors) > 1:
        names = ", ".join(f"{v['DisplayName']} (ID:{v['Id']})" for v in vendors)
        return f"Multiple vendors match: {names}. Be more specific."
    vendor = vendors[0]

    # Find account
    acct_result = await qb_query(f"SELECT * FROM Account WHERE Name LIKE '%{account_name}%' MAXRESULTS 5")
    accounts = acct_result.get("QueryResponse", {}).get("Account", [])
    if not accounts:
        return f"Account '{account_name}' not found."
    account = accounts[0]

    body = {
        "VendorRef": {"value": vendor["Id"]},
        "Line": [{
            "Amount": amount,
            "Description": description,
            "DetailType": "AccountBasedExpenseLineDetail",
            "AccountBasedExpenseLineDetail": {
                "AccountRef": {"value": account["Id"], "name": account["Name"]},
            },
        }],
    }
    if date:
        body["TxnDate"] = _validate_date(date, "date")

    result = await qb_request("POST", "vendorcredit", json_body=body)
    vc = result.get("VendorCredit", {})

    _audit_log("CREATE_VENDOR_CREDIT", f"vendor={vendor['DisplayName']} amount={fmt(amount)}")
    return (
        f"✅ Vendor credit created\n"
        f"  ID: {vc.get('Id')}\n"
        f"  Vendor: {vendor['DisplayName']}\n"
        f"  Amount: {fmt(amount)}\n"
        f"  Account: {account['Name']}\n"
        f"  Date: {vc.get('TxnDate', 'today')}"
    )


# ===================================================================
# NEW: Sales Tax Summary
# ===================================================================

@mcp.tool()
async def qb_sales_tax_summary(start_date: str, end_date: str) -> str:
    """Generate a sales tax summary report for a date range.
    Shows taxable sales, tax collected, tax rates, and liability by jurisdiction.
    Useful for state/local sales tax filing. start_date/end_date in YYYY-MM-DD."""
    start_date = _validate_date(start_date, "start_date")
    end_date = _validate_date(end_date, "end_date")

    # Get invoices and sales receipts with tax
    inv_result = await qb_query(
        f"SELECT * FROM Invoice WHERE TxnDate >= '{start_date}' AND TxnDate <= '{end_date}' MAXRESULTS 500"
    )
    invoices = inv_result.get("QueryResponse", {}).get("Invoice", [])

    sr_result = await qb_query(
        f"SELECT * FROM SalesReceipt WHERE TxnDate >= '{start_date}' AND TxnDate <= '{end_date}' MAXRESULTS 500"
    )
    sales_receipts = sr_result.get("QueryResponse", {}).get("SalesReceipt", [])

    # Try to get the TaxAgency / TaxCode info
    tax_code_result = await qb_query("SELECT * FROM TaxCode MAXRESULTS 50")
    tax_codes = tax_code_result.get("QueryResponse", {}).get("TaxCode", [])

    tax_rate_result = await qb_query("SELECT * FROM TaxRate MAXRESULTS 50")
    tax_rates = tax_rate_result.get("QueryResponse", {}).get("TaxRate", [])

    # Build tax rate lookup
    rate_map = {}
    for tr in tax_rates:
        rate_map[tr.get("Id", "")] = {
            "name": tr.get("Name", "?"),
            "rate": float(tr.get("RateValue", 0)),
            "agency": tr.get("AgencyRef", {}).get("name", "?"),
        }

    total_taxable = 0.0
    total_tax = 0.0
    total_exempt = 0.0
    total_gross = 0.0
    tax_by_rate = {}

    for txn_list in [invoices, sales_receipts]:
        for txn in txn_list:
            total_amt = float(txn.get("TotalAmt", 0))
            tax_amt = float(txn.get("TxnTaxDetail", {}).get("TotalTax", 0))
            total_gross += total_amt
            total_tax += tax_amt

            if tax_amt > 0:
                total_taxable += (total_amt - tax_amt)
            else:
                total_exempt += total_amt

            # Parse tax detail lines
            tax_lines = txn.get("TxnTaxDetail", {}).get("TaxLine", [])
            for tl in tax_lines:
                detail = tl.get("TaxLineDetail", {})
                rate_id = detail.get("TaxRateRef", {}).get("value", "")
                tax_on = float(detail.get("NetAmountTaxable", 0))
                tax_charged = float(tl.get("Amount", 0))
                rate_info = rate_map.get(rate_id, {"name": f"Rate#{rate_id}", "rate": 0, "agency": "?"})

                key = rate_info["name"]
                if key not in tax_by_rate:
                    tax_by_rate[key] = {
                        "rate": rate_info["rate"],
                        "agency": rate_info["agency"],
                        "taxable_amount": 0.0,
                        "tax_collected": 0.0,
                    }
                tax_by_rate[key]["taxable_amount"] += tax_on
                tax_by_rate[key]["tax_collected"] += tax_charged

    lines = [
        f"## Sales Tax Summary",
        f"**Period:** {start_date} to {end_date}",
        f"**Invoices:** {len(invoices)} | **Sales Receipts:** {len(sales_receipts)}\n",
        f"### Totals",
        f"  Gross Sales: {fmt(total_gross)}",
        f"  Taxable Sales: {fmt(total_taxable)}",
        f"  Tax-Exempt Sales: {fmt(total_exempt)}",
        f"  **Total Tax Collected: {fmt(total_tax)}**\n",
    ]

    if tax_by_rate:
        lines.append(f"### Tax Breakdown by Rate")
        for name, info in sorted(tax_by_rate.items()):
            lines.append(f"  **{name}** ({info['rate']}%) — Agency: {info['agency']}")
            lines.append(f"    Taxable: {fmt(info['taxable_amount'])} | Tax: {fmt(info['tax_collected'])}")
            lines.append("")

    if tax_codes:
        lines.append(f"### Active Tax Codes ({len(tax_codes)})")
        for tc in tax_codes:
            active = "Active" if tc.get("Active") else "Inactive"
            taxable = "Taxable" if tc.get("Taxable") else "Non-Taxable"
            lines.append(f"  - {tc.get('Name', '?')} ({active}, {taxable})")

    lines.extend([
        f"\n---",
        f"*Note: Verify totals against QB Sales Tax Liability report before filing.*",
        f"*File frequency depends on your state registration.*",
    ])

    _audit_log("SALES_TAX_SUMMARY", f"period={start_date}/{end_date} tax_collected={fmt(total_tax)}")
    return "\n".join(lines)


# ===================================================================
# NEW: Multi-Period Cash Flow Forecast
# ===================================================================

@mcp.tool()
async def qb_cash_flow_forecast(months_forward: int = 6, base_months: int = 6) -> str:
    """Forecast future cash flow based on historical patterns.
    Analyzes the last base_months of income/expenses and projects months_forward.
    Shows projected monthly cash balance, burn rate trends, and runway.
    months_forward: how many months to project (1-24).
    base_months: historical months to base projections on (3-12)."""
    months_forward = max(1, min(24, months_forward))
    base_months = max(3, min(12, base_months))

    from datetime import timedelta
    from collections import defaultdict

    today = datetime.now()
    start = (today - timedelta(days=base_months * 30)).strftime("%Y-%m-%d")
    end = today.strftime("%Y-%m-%d")

    # Get P&L by month for base period
    params = {"start_date": start, "end_date": end, "summarize_by": "Month"}
    result = await qb_request("GET", "reports/ProfitAndLoss", params=params)

    # Parse the report
    rows = result.get("Rows", {}).get("Row", [])
    columns = result.get("Columns", {}).get("Column", [])
    month_labels = [c.get("ColTitle", "") for c in columns if c.get("ColTitle", "") != ""]

    # Extract income and expense totals per month.
    # P&L by month may have separate "Income" and "Other Income" sections
    # (and "Expenses" / "Other Expenses"), so we accumulate into dicts
    # keyed by column index, then convert to lists at the end.
    # We ignore summary rows like "Net Income", "Gross Profit", etc.
    income_by_month = defaultdict(float)
    expense_by_month = defaultdict(float)
    num_month_cols = len(month_labels)

    for row in rows:
        if row.get("type") != "Section":
            continue
        header = row.get("Header", {})
        group = header.get("ColData", [{}])[0].get("value", "") if header.get("ColData") else ""
        group_lower = group.lower().strip()

        is_income = group_lower in ("income", "other income")
        is_expense = group_lower in ("expenses", "other expenses")
        if not is_income and not is_expense:
            continue

        summary = row.get("Summary", {}).get("ColData", [])
        if not summary:
            continue

        # Summary ColData has one entry per month column plus a "Total" column.
        # The first element is the label (e.g. "Total Income"), so skip it.
        numeric_cols = summary[1:] if len(summary) > num_month_cols else summary
        for idx, col in enumerate(numeric_cols):
            val_str = col.get("value", "0").replace(",", "")
            try:
                val = float(val_str)
            except ValueError:
                continue
            if is_income:
                income_by_month[idx] += val
            else:
                expense_by_month[idx] += abs(val)

    monthly_income = [income_by_month[i] for i in sorted(income_by_month)] if income_by_month else []
    monthly_expenses = [expense_by_month[i] for i in sorted(expense_by_month)] if expense_by_month else []

    # Fallback: use P&L total approach
    if not monthly_income and not monthly_expenses:
        pl_params = {"start_date": start, "end_date": end, "summarize_by": "Total"}
        pl_result = await qb_request("GET", "reports/ProfitAndLoss", params=pl_params)
        pl_rows = pl_result.get("Rows", {}).get("Row", [])
        total_income = 0.0
        total_expenses = 0.0
        for row in pl_rows:
            row_data = row.get("Summary", {}).get("ColData", [])
            if row_data:
                label = row.get("Header", {}).get("ColData", [{}])[0].get("value", "")
                val_str = row_data[-1].get("value", "0").replace(",", "") if row_data else "0"
                try:
                    val = float(val_str)
                except ValueError:
                    val = 0
                label_lower = label.lower().strip()
                # Only match actual revenue/expense buckets, not "Net Income" etc.
                if label_lower in ("income", "other income"):
                    total_income += val
                elif label_lower in ("expenses", "other expenses"):
                    total_expenses += abs(val)
        avg_income = total_income / base_months
        avg_expenses = total_expenses / base_months
    else:
        import statistics
        avg_income = statistics.mean(monthly_income) if monthly_income else 0
        avg_expenses = statistics.mean(monthly_expenses) if monthly_expenses else 0

    # Get current cash position
    accts_result = await qb_query("SELECT * FROM Account WHERE AccountType = 'Bank' MAXRESULTS 20")
    bank_accounts = accts_result.get("QueryResponse", {}).get("Account", [])
    current_cash = sum(float(a.get("CurrentBalance", 0)) for a in bank_accounts)

    # Project forward
    lines = [
        f"## Cash Flow Forecast",
        f"**Based on:** Last {base_months} months of data",
        f"**Projecting:** {months_forward} months forward\n",
        f"### Current Position",
        f"  Cash on hand: {fmt(current_cash)}",
        f"  Avg monthly income: {fmt(avg_income)}",
        f"  Avg monthly expenses: {fmt(avg_expenses)}",
        f"  Net monthly: {fmt(avg_income - avg_expenses)}\n",
        f"### Monthly Projections",
        f"{'Month':<15} {'Income':>12} {'Expenses':>12} {'Net':>12} {'Balance':>14}",
        f"{'-'*65}",
    ]

    balance = current_cash
    months_to_zero = None

    for m in range(1, months_forward + 1):
        future_date = today + timedelta(days=m * 30)
        month_label = future_date.strftime("%b %Y")
        net = avg_income - avg_expenses
        balance += net

        lines.append(
            f"{month_label:<15} {fmt(avg_income):>12} {fmt(avg_expenses):>12} {fmt(net):>12} {fmt(balance):>14}"
        )
        if balance <= 0 and months_to_zero is None:
            months_to_zero = m

    lines.extend([
        "",
        f"### Runway Analysis",
    ])

    if avg_expenses > avg_income and avg_expenses > 0:
        runway_months = current_cash / (avg_expenses - avg_income)
        lines.append(f"  ⚠️ **Burn rate:** {fmt(avg_expenses - avg_income)}/month")
        lines.append(f"  **Runway:** {runway_months:.1f} months")
        if runway_months < 6:
            lines.append(f"  🔴 **CRITICAL:** Less than 6 months of runway")
        elif runway_months < 12:
            lines.append(f"  🟡 **CAUTION:** Less than 12 months of runway")
    elif avg_income > avg_expenses:
        lines.append(f"  ✅ **Positive cash flow:** {fmt(avg_income - avg_expenses)}/month")
        lines.append(f"  Cash position growing — no runway concerns")
    else:
        lines.append(f"  Break-even: income ≈ expenses")

    lines.append(f"\n*Forecast assumes constant rates. Actual results will vary.*")

    _audit_log("CASH_FLOW_FORECAST", f"months={months_forward} cash={fmt(current_cash)} net={fmt(avg_income - avg_expenses)}")
    return "\n".join(lines)


# ===================================================================
# NEW: Profit Margin by Customer/Item
# ===================================================================

@mcp.tool()
async def qb_profit_margin_analysis(start_date: str, end_date: str, group_by: str = "customer") -> str:
    """Analyze profit margins by customer or item/product.
    Shows revenue, COGS (if tracked), and margin for each customer or item.
    group_by: 'customer' or 'item'. start_date/end_date in YYYY-MM-DD."""
    start_date = _validate_date(start_date, "start_date")
    end_date = _validate_date(end_date, "end_date")
    group_by = _sanitize_input(group_by, "group_by").lower()

    if group_by not in ("customer", "item"):
        return "group_by must be 'customer' or 'item'."

    # Get invoices and sales receipts
    inv_result = await qb_query(
        f"SELECT * FROM Invoice WHERE TxnDate >= '{start_date}' AND TxnDate <= '{end_date}' MAXRESULTS 500"
    )
    invoices = inv_result.get("QueryResponse", {}).get("Invoice", [])

    sr_result = await qb_query(
        f"SELECT * FROM SalesReceipt WHERE TxnDate >= '{start_date}' AND TxnDate <= '{end_date}' MAXRESULTS 500"
    )
    sales_receipts = sr_result.get("QueryResponse", {}).get("SalesReceipt", [])

    from collections import defaultdict
    groups = defaultdict(lambda: {"revenue": 0.0, "cogs": 0.0, "count": 0})

    for txn_list in [invoices, sales_receipts]:
        for txn in txn_list:
            if group_by == "customer":
                key = txn.get("CustomerRef", {}).get("name", "Unknown")
                groups[key]["revenue"] += float(txn.get("TotalAmt", 0))
                groups[key]["count"] += 1
            else:
                for line in txn.get("Line", []):
                    detail = line.get("SalesItemLineDetail", {})
                    item_name = detail.get("ItemRef", {}).get("name", "")
                    if item_name:
                        amt = float(line.get("Amount", 0))
                        groups[item_name]["revenue"] += amt
                        groups[item_name]["count"] += 1

    # Try to get COGS from P&L
    params = {"start_date": start_date, "end_date": end_date, "summarize_by": "Total"}
    pl_result = await qb_request("GET", "reports/ProfitAndLoss", params=params)
    pl_rows = pl_result.get("Rows", {}).get("Row", [])

    total_cogs = 0.0
    total_revenue = 0.0
    for row in pl_rows:
        header = row.get("Header", {}).get("ColData", [{}])[0].get("value", "")
        summary = row.get("Summary", {}).get("ColData", [])
        if summary:
            val_str = summary[-1].get("value", "0").replace(",", "")
            try:
                val = float(val_str)
            except ValueError:
                val = 0
            if "cost of goods" in header.lower():
                total_cogs = abs(val)
            elif "income" in header.lower() and "other" not in header.lower():
                total_revenue = val

    # Distribute COGS proportionally if we have it
    if total_cogs > 0 and total_revenue > 0:
        for key, data in groups.items():
            proportion = data["revenue"] / total_revenue if total_revenue > 0 else 0
            data["cogs"] = total_cogs * proportion

    # Sort by revenue
    sorted_groups = sorted(groups.items(), key=lambda x: x[1]["revenue"], reverse=True)

    lines = [
        f"## Profit Margin Analysis by {group_by.title()}",
        f"**Period:** {start_date} to {end_date}",
        f"**{group_by.title()}s:** {len(sorted_groups)}\n",
    ]

    if total_cogs > 0:
        lines.append(f"*COGS distributed proportionally to revenue (total COGS: {fmt(total_cogs)})*\n")
    else:
        lines.append(f"*No COGS tracked — margins show gross revenue only*\n")

    lines.append(f"{'Name':<30} {'Revenue':>12} {'COGS':>12} {'Margin':>12} {'%':>8} {'Txns':>6}")
    lines.append(f"{'-'*80}")

    grand_revenue = 0.0
    grand_cogs = 0.0
    for name, data in sorted_groups:
        rev = data["revenue"]
        cogs = data["cogs"]
        margin = rev - cogs
        pct = (margin / rev * 100) if rev > 0 else 0
        grand_revenue += rev
        grand_cogs += cogs

        display_name = name[:28] if len(name) > 28 else name
        lines.append(f"{display_name:<30} {fmt(rev):>12} {fmt(cogs):>12} {fmt(margin):>12} {pct:>7.1f}% {data['count']:>6}")

    grand_margin = grand_revenue - grand_cogs
    grand_pct = (grand_margin / grand_revenue * 100) if grand_revenue > 0 else 0
    lines.extend([
        f"{'-'*80}",
        f"{'TOTAL':<30} {fmt(grand_revenue):>12} {fmt(grand_cogs):>12} {fmt(grand_margin):>12} {grand_pct:>7.1f}%",
    ])

    _audit_log("PROFIT_MARGIN", f"group={group_by} period={start_date}/{end_date} revenue={fmt(grand_revenue)}")
    return "\n".join(lines)


# ===================================================================
# NEW: Budget vs Actual
# ===================================================================

@mcp.tool()
async def qb_budget_vs_actual(fiscal_year: str = "2025") -> str:
    """Compare budgeted amounts vs actual spending for a fiscal year.
    Requires budgets to be set up in QuickBooks. Shows variance by account
    and highlights over/under-budget items. fiscal_year in YYYY format."""
    start = f"{fiscal_year}-01-01"
    end = f"{fiscal_year}-12-31"

    # Try to get budgets
    budget_result = await qb_query("SELECT * FROM Budget MAXRESULTS 10")
    budgets = budget_result.get("QueryResponse", {}).get("Budget", [])

    if not budgets:
        return (
            f"No budgets found in QuickBooks.\n\n"
            f"To use this tool, create a budget in QuickBooks:\n"
            f"  1. Go to Settings > Budgeting\n"
            f"  2. Create a budget for fiscal year {fiscal_year}\n"
            f"  3. Enter budget amounts by account/month\n"
            f"  4. Run this tool again"
        )

    # Get actual P&L
    params = {"start_date": start, "end_date": end, "summarize_by": "Total"}
    pl_result = await qb_request("GET", "reports/ProfitAndLoss", params=params)

    # Get Budget Summary report
    budget_params = {"start_date": start, "end_date": end, "summarize_by": "Total"}
    try:
        bva_result = await qb_request("GET", "reports/BudgetVsActual", params=budget_params)
    except Exception:
        # Fall back to manual comparison
        bva_result = None

    if bva_result and bva_result.get("Rows"):
        # Parse the QB Budget vs Actual report
        rows = bva_result.get("Rows", {}).get("Row", [])
        lines = [
            f"## Budget vs Actual — {fiscal_year}",
            f"**Period:** {start} to {end}\n",
        ]
        _parse_report_rows(rows, lines)
        _audit_log("BUDGET_VS_ACTUAL", f"year={fiscal_year}")
        return "\n".join(lines)

    # Manual fallback: compare budget entity to P&L
    budget = budgets[0]
    budget_lines_data = budget.get("BudgetDetail", [])

    from collections import defaultdict
    budget_by_acct = defaultdict(float)
    for bd in budget_lines_data:
        acct_name = bd.get("AccountRef", {}).get("name", "?")
        amount = float(bd.get("Amount", 0))
        budget_by_acct[acct_name] += amount

    # Get actual account balances
    actual_by_acct = {}
    accts_result = await qb_query("SELECT * FROM Account MAXRESULTS 200")
    for a in accts_result.get("QueryResponse", {}).get("Account", []):
        actual_by_acct[a["Name"]] = float(a.get("CurrentBalance", 0))

    lines = [
        f"## Budget vs Actual — {fiscal_year}",
        f"**Budget:** {budget.get('Name', 'Default')}",
        f"**Period:** {start} to {end}\n",
        f"{'Account':<35} {'Budget':>12} {'Actual':>12} {'Variance':>12} {'%':>8}",
        f"{'-'*80}",
    ]

    total_budget = 0.0
    total_actual = 0.0
    over_budget = []

    for acct, budg_amt in sorted(budget_by_acct.items()):
        act_amt = abs(actual_by_acct.get(acct, 0))
        variance = budg_amt - act_amt
        pct = (act_amt / budg_amt * 100) if budg_amt > 0 else 0
        total_budget += budg_amt
        total_actual += act_amt

        flag = " ⚠️" if act_amt > budg_amt * 1.1 else ""
        if act_amt > budg_amt * 1.1:
            over_budget.append((acct, budg_amt, act_amt, variance))

        display_name = acct[:33] if len(acct) > 33 else acct
        lines.append(f"{display_name:<35} {fmt(budg_amt):>12} {fmt(act_amt):>12} {fmt(variance):>12} {pct:>7.1f}%{flag}")

    total_variance = total_budget - total_actual
    lines.extend([
        f"{'-'*80}",
        f"{'TOTAL':<35} {fmt(total_budget):>12} {fmt(total_actual):>12} {fmt(total_variance):>12}",
    ])

    if over_budget:
        lines.append(f"\n### ⚠️ Over Budget ({len(over_budget)} accounts)")
        for acct, b, a, v in over_budget:
            lines.append(f"  - {acct}: {fmt(a)} actual vs {fmt(b)} budget ({fmt(abs(v))} over)")

    _audit_log("BUDGET_VS_ACTUAL", f"year={fiscal_year} budget={fmt(total_budget)} actual={fmt(total_actual)}")
    return "\n".join(lines)


# ===================================================================
# NEW: Estimate to Invoice Conversion
# ===================================================================

@mcp.tool()
async def qb_list_estimates(start_date: str = "", end_date: str = "", customer_name: str = "", status: str = "", max_results: int = 50) -> str:
    """List estimates/quotes. Optionally filter by date range, customer, or status.
    status: Pending, Accepted, Closed, Rejected (leave empty for all).
    start_date/end_date in YYYY-MM-DD format."""
    query = "SELECT * FROM Estimate"
    conditions = []

    if start_date:
        start_date = _validate_date(start_date, "start_date")
        conditions.append(f"TxnDate >= '{start_date}'")
    if end_date:
        end_date = _validate_date(end_date, "end_date")
        conditions.append(f"TxnDate <= '{end_date}'")

    if conditions:
        query += " WHERE " + " AND ".join(conditions)
    query += f" MAXRESULTS {max_results}"

    result = await qb_query(query)
    estimates = result.get("QueryResponse", {}).get("Estimate", [])

    if not estimates:
        return "No estimates found."

    # Filter by customer and status in-memory (QB query limitations)
    if customer_name:
        customer_name = _sanitize_input(customer_name, "customer_name").lower()
        estimates = [e for e in estimates if customer_name in e.get("CustomerRef", {}).get("name", "").lower()]
    if status:
        status = _sanitize_input(status, "status")
        estimates = [e for e in estimates if e.get("TxnStatus", "").lower() == status.lower()]

    lines = [f"## Estimates ({len(estimates)} found)\n"]
    total = 0.0
    for est in estimates:
        est_id = est.get("Id", "?")
        date = est.get("TxnDate", "?")
        cust = est.get("CustomerRef", {}).get("name", "?")
        amount = float(est.get("TotalAmt", 0))
        est_status = est.get("TxnStatus", "?")
        doc_num = est.get("DocNumber", "")
        expiry = est.get("ExpirationDate", "")
        total += amount

        lines.append(f"**#{doc_num or est_id}** | {date} | {cust} | {fmt(amount)} | {est_status}")
        if expiry:
            lines.append(f"  Expires: {expiry}")
        line_count = len([l for l in est.get("Line", []) if l.get("DetailType") != "SubTotalLineDetail"])
        lines.append(f"  Line items: {line_count}")
        lines.append("")

    lines.append(f"---\n**Total:** {fmt(total)}")
    lines.append(f"\nUse qb_convert_estimate_to_invoice to convert an accepted estimate.")
    return "\n".join(lines)


@mcp.tool()
async def qb_convert_estimate_to_invoice(estimate_id: str) -> str:
    """Convert an estimate/quote into an invoice. Copies all line items, customer,
    and details from the estimate. estimate_id: the estimate's ID."""
    estimate_id = _sanitize_input(estimate_id, "estimate_id")

    # Read the estimate
    est_data = await qb_read("Estimate", estimate_id)
    estimate = est_data.get("Estimate", {})
    if not estimate:
        return f"Estimate #{estimate_id} not found."

    customer_ref = estimate.get("CustomerRef", {})
    if not customer_ref:
        return "Estimate has no customer reference."

    # Build invoice from estimate lines
    invoice_lines = []
    for line in estimate.get("Line", []):
        detail_type = line.get("DetailType", "")
        if detail_type == "SubTotalLineDetail":
            continue
        invoice_lines.append({
            "Amount": line.get("Amount", 0),
            "Description": line.get("Description", ""),
            "DetailType": detail_type,
        })
        # Copy the detail object
        if detail_type == "SalesItemLineDetail":
            invoice_lines[-1]["SalesItemLineDetail"] = line.get("SalesItemLineDetail", {})
        elif detail_type == "GroupLineDetail":
            invoice_lines[-1]["GroupLineDetail"] = line.get("GroupLineDetail", {})

    body = {
        "CustomerRef": customer_ref,
        "Line": invoice_lines,
        "PrivateNote": f"Converted from Estimate #{estimate.get('DocNumber', estimate_id)}",
    }

    # Copy optional fields
    if estimate.get("BillEmail"):
        body["BillEmail"] = estimate["BillEmail"]
    if estimate.get("ShipAddr"):
        body["ShipAddr"] = estimate["ShipAddr"]
    if estimate.get("BillAddr"):
        body["BillAddr"] = estimate["BillAddr"]

    result = await qb_request("POST", "invoice", json_body=body)
    invoice = result.get("Invoice", {})

    _audit_log("ESTIMATE_TO_INVOICE", f"estimate={estimate_id} invoice={invoice.get('Id')}")

    return (
        f"✅ Invoice created from Estimate #{estimate.get('DocNumber', estimate_id)}\n"
        f"  Invoice ID: {invoice.get('Id')}\n"
        f"  Invoice #: {invoice.get('DocNumber', 'auto')}\n"
        f"  Customer: {customer_ref.get('name', '?')}\n"
        f"  Amount: {fmt(float(invoice.get('TotalAmt', 0)))}\n"
        f"  Date: {invoice.get('TxnDate', 'today')}\n\n"
        f"*The original estimate remains unchanged. Update its status manually if needed.*"
    )


# ===================================================================
# ENTRY POINT
# ===================================================================

if __name__ == "__main__":
    mcp.run()
