"""accountingqb.tax_tables — the tax-data registry (L2 grounding layer).

Every jurisdiction-specific tax value the server ships lives here, with
provenance in TABLES and full history in tax_ledger.jsonl (L4 — append-only,
hash-chained). No value ships without a ledger row; deterministic policy
rules in tests/test_tax_data_policy.py (L3) gate every commit. A scheduled
research agent (L1) may PROPOSE changes via draft PR but never merges.
Constitution: "Every Encoded Rate Has a Source and a Review Date."
"""
from __future__ import annotations

import hashlib
import json
import pathlib
import re

TAX_DATA_VERSION = "2026.6"       # bumped by every approved rates PR
TAX_DATA_VERIFIED = "2026-08-03"  # date of the last full verification sweep


class TaxDataError(ValueError):
    """A requested tax value is unavailable for the year. The message is
    user-facing and safe to return directly from a tool."""


# =========================================================================
# US federal — quarterly estimator (moved from qb_estimate_quarterly_tax)
# =========================================================================

# Social Security wage base (OASDI cap). SSA COLA announcements.
_SS_WAGE_BASE = {2025: 176_100, 2026: 184_500}

# Federal bracket thresholds per Rev. Proc. 2024-40 (2025) and
# Rev. Proc. 2025-32 (2026, post-OBBBA). Review annually.
_FED_BRACKETS = {
    2025: {
        "single": [11_925, 48_475, 103_350, 197_300, 250_525, 626_350],
        "married_joint": [23_850, 96_950, 206_700, 394_600, 501_050, 752_600],
        "std_single": 15_750, "std_married": 31_500,  # OBBBA amounts
    },
    2026: {
        "single": [12_400, 50_400, 105_700, 201_775, 256_225, 640_600],
        "married_joint": [24_800, 100_800, 211_400, 403_550, 512_450, 768_700],
        "std_single": 16_100, "std_married": 32_200,
    },
}
_RATES = [0.10, 0.12, 0.22, 0.24, 0.32, 0.35, 0.37]

# Self-employment tax formula (IRC 1401/1402, stable statute)
_SE_NET_EARNINGS_FACTOR = 0.9235
_SE_SS_RATE = 0.124
_SE_MEDICARE_RATE = 0.029

# =========================================================================
# US federal — depreciation (moved from qb_vehicle_depreciation_calculator)
# =========================================================================

# TCJA bonus phase-down: applies ONLY to property acquired on/before
# Jan 19, 2025 (OBBBA made 100% permanent for later acquisitions).
# Statutory terminal value 0.0 for 2027+ (see TABLES terminal_value).
_TCJA_PHASE_DOWN = {2023: 0.80, 2024: 0.60, 2025: 0.40, 2026: 0.20}

# Heavy SUV (GVWR 6,001-14,000 lbs) Section 179 cap. Rev. Proc. annual.
_SUV_179_CAP = {2025: 31_300.0, 2026: 32_000.0}

# §280F luxury-auto caps (Rev. Proc. 2025-16 for 2025; 2026-15 for 2026)
_280F_LIMITS = {
    2025: {1: 20_200, 2: 19_600, 3: 11_800, 4: 7_060, "no_bonus_1": 12_200},
    2026: {1: 20_300, 2: 19_800, 3: 11_900, 4: 7_160, "no_bonus_1": 12_300},
}

# MACRS 5-year property (200% DB, half-year convention; Pub. 946)
_MACRS_5YR = [0.20, 0.32, 0.192, 0.1152, 0.1152, 0.0576]

# Section 179 general limits (OBBBA base $2.5M/$4M from 2025, indexed)
_SEC_179_LIMITS = {
    2025: {"limit": 2_500_000, "phaseout": 4_000_000},
    2026: {"limit": 2_560_000, "phaseout": 4_090_000},
}

# §195 startup costs (stable statute)
_SEC_195 = {"immediate": 5_000.0, "phaseout_start": 50_000.0, "months": 180}

# Home office simplified method (Rev. Proc. 2013-13, stable)
_HOME_OFFICE_SIMPLIFIED = {"rate_per_sqft": 5.0, "max_sqft": 300}

# IRS standard business mileage, cents/mile. 2026 is split: Notice 2026-10
# set 72.5c for Jan 1–Jun 30; Announcement 2026-11 (IRB 2026-29, Jul 13, 2026)
# raised it to 76.0c effective Jul 1 due to fuel-price increases. Table stores
# the currently applicable rate (76.0c) for mid-year onward planning; tools
# should note the H1 rate when computing full-year mileage costs.
_STD_MILEAGE_CENTS = {2025: 70.0, 2026: 76.0}

# Retirement plan limits (IRS COLA announcements)
_RETIREMENT_LIMITS = {
    2025: {"sep_max": 70_000, "solo_401k_deferral": 23_500},
    2026: {"sep_max": 72_000, "solo_401k_deferral": 24_500},
}

# 1099-NEC/MISC reporting threshold per payee (OBBBA: $2,000 for payments
# made on/after Jan 1 2026, inflation-indexed after; $600 before)
_1099_NEC_THRESHOLD = {2025: 600.0, 2026: 2_000.0}


# =========================================================================
# US state income tax (moved from module level)
# =========================================================================

# APPROXIMATE state income tax on pass-through/self-employment income, for
# quarterly planning only. (rate, kind): kind "none" = no tax on earned
# income, "flat" = statutory flat rate, "progressive_approx" = rough
# effective rate for a bracketed state. 2026 tax-year values — review
# annually (several flat states step their rate down each January).
# Source: Tax Foundation, "2026 State Income Tax Rates and Brackets".
_US_STATE_TAX = {
    "TX": (0.0, "none"), "FL": (0.0, "none"), "WA": (0.0, "none"),
    "NV": (0.0, "none"), "TN": (0.0, "none"), "SD": (0.0, "none"),
    "WY": (0.0, "none"), "AK": (0.0, "none"),
    "NH": (0.0, "none"),  # no tax on earned income (interest/dividends tax repealed 2025)
    "AZ": (0.025, "flat"), "CO": (0.044, "flat"),
    "GA": (0.0499, "flat"),  # HB 463 signed 2026-05-11; 4.99% retroactive Jan 1, 2026
    "ID": (0.053, "flat"), "IL": (0.0495, "flat"),
    "IN": (0.0295, "flat"),  # 2.95% flat effective Jan 1, 2026 (was 3.0%)
    "IA": (0.038, "flat"),
    "KY": (0.035, "flat"),   # 3.5% flat effective Jan 1, 2026 (was 4.0%)
    "LA": (0.03, "flat"),    # 3.0% flat since Jan 1, 2025 (Constitutional Amendment 2)
    "MA": (0.05, "flat"), "MI": (0.0425, "flat"),
    "MS": (0.04, "flat"),    # 4.0% flat effective Jan 1, 2026 (was 4.4%)
    "NC": (0.0399, "flat"),  # 3.99% flat effective Jan 1, 2026 (was 4.25%)
    "OH": (0.0275, "flat"),  # 2.75% flat effective Jan 1, 2026 (was progressive ~3.5%)
    "PA": (0.0307, "flat"), "UT": (0.045, "flat"),
    "AL": (0.05, "progressive_approx"), "AR": (0.039, "progressive_approx"),
    "CA": (0.093, "progressive_approx"), "CT": (0.055, "progressive_approx"),
    "DE": (0.055, "progressive_approx"), "DC": (0.065, "progressive_approx"),
    "HI": (0.079, "progressive_approx"), "KS": (0.0558, "progressive_approx"),
    "MD": (0.0475, "progressive_approx"),
    "ME": (0.0715, "progressive_approx"), "MN": (0.0785, "progressive_approx"),
    "MO": (0.047, "progressive_approx"),
    "MT": (0.0565, "progressive_approx"),  # top rate 5.65% effective Jan 1, 2026 (was 5.9%)
    "ND": (0.025, "progressive_approx"),
    "NE": (0.0455, "progressive_approx"),  # top rate 4.55% effective Jan 1, 2026 (was 5.2%)
    "NJ": (0.0637, "progressive_approx"), "NM": (0.049, "progressive_approx"),
    "NY": (0.065, "progressive_approx"),
    "OK": (0.045, "progressive_approx"),   # top rate 4.5% effective Jan 1, 2026 (was 4.75%)
    "OR": (0.0875, "progressive_approx"),
    "RI": (0.0475, "progressive_approx"), "SC": (0.062, "progressive_approx"),
    "VA": (0.0575, "progressive_approx"), "VT": (0.066, "progressive_approx"),
    "WI": (0.053, "progressive_approx"),
    "WV": (0.0458, "progressive_approx"),  # all rates reduced; top 4.58% effective Jan 1, 2026 (was 4.82%)
}

# Economic-nexus thresholds for STATE SALES TAX (post-Wayfair). Per state:
#   sales = gross/retail sales-dollar threshold; txns = transaction-count
#   threshold or None (many states dropped it in 2023-26); basis = "or" (either
#   trips nexus) | "and" (both required) | "only" (sales only). The measurement
#   window varies by state (prior/current calendar year or trailing 12 months) —
#   this is a SCREENING indicator; verify the exact window per state. NH/OR/MT/DE
#   have NO sales tax; AK has no *state* sales tax but local jurisdictions adopt
#   economic nexus ($100k) via the ARSSTC. Source: Sales Tax Institute Economic
#   Nexus State Guide (chart as of 2026-05-04), cross-checked to state DOR pages.
_US_SALES_TAX_NEXUS = {
    "AL": {"sales": 250_000, "txns": None, "basis": "only"},
    "AK": {"sales": 100_000, "txns": None, "basis": "only"},  # local only (ARSSTC)
    "AZ": {"sales": 100_000, "txns": None, "basis": "only"},
    "AR": {"sales": 100_000, "txns": 200, "basis": "or"},
    "CA": {"sales": 500_000, "txns": None, "basis": "only"},
    "CO": {"sales": 100_000, "txns": None, "basis": "only"},
    "CT": {"sales": 100_000, "txns": 200, "basis": "and"},
    "DC": {"sales": 100_000, "txns": 200, "basis": "or"},
    "FL": {"sales": 100_000, "txns": None, "basis": "only"},
    "GA": {"sales": 100_000, "txns": 200, "basis": "or"},
    "HI": {"sales": 100_000, "txns": 200, "basis": "or"},
    "ID": {"sales": 100_000, "txns": None, "basis": "only"},
    "IL": {"sales": 100_000, "txns": None, "basis": "only"},   # txns removed 2026-01-01
    "IN": {"sales": 100_000, "txns": None, "basis": "only"},
    "IA": {"sales": 100_000, "txns": None, "basis": "only"},
    "KS": {"sales": 100_000, "txns": None, "basis": "only"},
    "KY": {"sales": 100_000, "txns": None, "basis": "only"},   # txns removed 2026-08-01
    "LA": {"sales": 100_000, "txns": None, "basis": "only"},
    "ME": {"sales": 100_000, "txns": None, "basis": "only"},
    "MD": {"sales": 100_000, "txns": 200, "basis": "or"},
    "MA": {"sales": 100_000, "txns": None, "basis": "only"},
    "MI": {"sales": 100_000, "txns": 200, "basis": "or"},
    "MN": {"sales": 100_000, "txns": 200, "basis": "or"},
    "MS": {"sales": 250_000, "txns": None, "basis": "only"},
    "MO": {"sales": 100_000, "txns": None, "basis": "only"},
    "NE": {"sales": 100_000, "txns": 200, "basis": "or"},
    "NV": {"sales": 100_000, "txns": 200, "basis": "or"},
    "NJ": {"sales": 100_000, "txns": 200, "basis": "or"},
    "NM": {"sales": 100_000, "txns": None, "basis": "only"},
    "NY": {"sales": 500_000, "txns": 100, "basis": "and"},
    "NC": {"sales": 100_000, "txns": None, "basis": "only"},   # txns removed 2024-07-01
    "ND": {"sales": 100_000, "txns": None, "basis": "only"},
    "OH": {"sales": 100_000, "txns": 200, "basis": "or"},
    "OK": {"sales": 100_000, "txns": None, "basis": "only"},
    "PA": {"sales": 100_000, "txns": None, "basis": "only"},
    "RI": {"sales": 100_000, "txns": 200, "basis": "or"},
    "SC": {"sales": 100_000, "txns": None, "basis": "only"},
    "SD": {"sales": 100_000, "txns": None, "basis": "only"},   # txns removed 2023-07-01
    "TN": {"sales": 100_000, "txns": None, "basis": "only"},
    "TX": {"sales": 500_000, "txns": None, "basis": "only"},
    "UT": {"sales": 100_000, "txns": None, "basis": "only"},   # txns removed 2025-07-01
    "VT": {"sales": 100_000, "txns": 200, "basis": "or"},
    "VA": {"sales": 100_000, "txns": 200, "basis": "or"},
    "WA": {"sales": 100_000, "txns": None, "basis": "only"},
    "WV": {"sales": 100_000, "txns": 200, "basis": "or"},
    "WI": {"sales": 100_000, "txns": None, "basis": "only"},
    "WY": {"sales": 100_000, "txns": None, "basis": "only"},   # txns removed 2024-07-01
}
_NO_SALES_TAX_STATES = ("DE", "MT", "NH", "OR")  # AK: no state tax, local nexus applies


# =========================================================================
# Canada (moved from module level)
# =========================================================================

_GST_QUICK_METHOD_LIMIT = 400_000.0   # taxable supplies (tax incl.), prior 4 quarters
_GST_QUICK_METHOD_CREDIT_BASE = 30_000.0  # 1% credit on first $30k of supplies
_MEALS_ITC_FACTOR = 0.5               # ITA s.67.1 — 50% of GST/HST on meals claimable

_GST_WORKPAPER_FOOTER = (
    "This is a workpaper, not a filing. Verify against QuickBooks' "
    "Sales Tax Centre before filing with CRA."
)

# Provincial sales-tax regimes — rates in effect 2026. Review annually
# (CRA "GST/HST rates" table; NS dropped 15% -> 14% effective Apr 1, 2025).
# HST provinces file one GST34 with CRA; GST+PST/QST provinces file the
# provincial tax separately (QC files GST *and* QST with Revenu Québec).
_CA_SALES_TAX_REGIME = {
    "ON": {"regime": "HST", "hst": 0.13},
    "NB": {"regime": "HST", "hst": 0.15},
    "NL": {"regime": "HST", "hst": 0.15},
    "PE": {"regime": "HST", "hst": 0.15},
    "NS": {"regime": "HST", "hst": 0.14},
    "BC": {"regime": "GST_PST", "gst": 0.05, "pst": 0.07, "pst_name": "PST",
           "pst_agency": "BC Ministry of Finance"},
    "SK": {"regime": "GST_PST", "gst": 0.05, "pst": 0.06, "pst_name": "PST",
           "pst_agency": "Saskatchewan Ministry of Finance"},
    "MB": {"regime": "GST_PST", "gst": 0.05, "pst": 0.07, "pst_name": "RST",
           "pst_agency": "Manitoba Finance"},
    "QC": {"regime": "GST_QST", "gst": 0.05, "pst": 0.09975, "pst_name": "QST",
           "pst_agency": "Revenu Québec"},
    "AB": {"regime": "GST_ONLY", "gst": 0.05},
    "YT": {"regime": "GST_ONLY", "gst": 0.05},
    "NT": {"regime": "GST_ONLY", "gst": 0.05},
    "NU": {"regime": "GST_ONLY", "gst": 0.05},
}

# Keywords identifying provincial (non-GST34) tax agencies in TaxAgency
# DisplayNames, matched lowercased. " pst"/" qst"/" rst" keep the leading
# space so agency names like "BC PST" match without hitting substrings.
_CA_PROVINCIAL_AGENCY_HINTS = (
    "revenu québec", "revenu quebec", "ministère du revenu",
    "ministry of finance", "minister of finance", "manitoba finance",
    " pst", " qst", " rst",
)


def _ca_regime(prov: str) -> dict | None:
    return _CA_SALES_TAX_REGIME.get((prov or "").strip().upper())


def _ca_regime_describe(prov: str) -> str:
    """One-line description of a province's sales-tax regime, or ""."""
    r = _ca_regime(prov)
    if not r:
        return ""
    if r["regime"] == "HST":
        return f"{prov} — HST {r['hst'] * 100:g}% (single CRA GST34 filing)"
    if r["regime"] in ("GST_PST", "GST_QST"):
        return (
            f"{prov} — GST {r['gst'] * 100:g}% + {r['pst_name']} "
            f"{r['pst'] * 100:g}% ({r['pst_name']} filed separately with "
            f"{r['pst_agency']})"
        )
    return f"{prov} — GST {r['gst'] * 100:g}% only (no provincial sales tax)"


def _ca_agency_is_provincial(display_name: str) -> bool:
    name = f" {(display_name or '').lower()}"
    return any(hint in name for hint in _CA_PROVINCIAL_AGENCY_HINTS)

# (The former _T2125_LINE_MAP keyword table was folded into the canonical
# taxonomy below: subtype mappings in _ACCOUNT_TAXONOMY, the CA name fallback in
# _NAME_FALLBACK_CA, and the line catalog in _T2125_CATALOG.)

# ===================================================================
# CANONICAL ACCOUNT-CLASSIFICATION TAXONOMY (US Schedule C + CA T2125)
# ===================================================================
# Keyed on the QuickBooks AccountSubType enum — authoritative, stable, and
# locale-independent — so classification does not depend on free-text account
# names. Each entry names the destination line per jurisdiction; a line of
# None means "no mapping for that jurisdiction" (falls through to the name
# rules), and the special US line "NONDED" marks a book expense that is NOT
# deductible on Schedule C (e.g. entertainment, IRC §274(a)). Names remain a
# fallback for accounts with a blank/custom subtype (see _NAME_FALLBACK_*).

_ACCOUNT_TAXONOMY = {
    # --- Income (AccountType Income) --------------------------------
    "SalesOfProductIncome":     {"us": "1", "ca": "8000"},
    "ServiceFeeIncome":         {"us": "1", "ca": "8000"},
    "OtherPrimaryIncome":       {"us": "1", "ca": "8000"},
    "UnappliedCashPaymentIncome": {"us": "1", "ca": "8000"},
    "DiscountsRefundsGiven":    {"us": "2", "ca": "8000a"},   # returns & allowances
    # --- Other Income (AccountType Other Income) -> Line 6 / CA 8230 -
    "InterestEarned":           {"us": "6", "ca": "8230"},
    "DividendIncome":           {"us": "6", "ca": "8230"},
    "TaxExemptInterest":        {"us": "6", "ca": "8230"},
    "OtherMiscellaneousIncome": {"us": "6", "ca": "8230"},
    # --- Expenses (AccountType Expense) -----------------------------
    "AdvertisingPromotional":   {"us": "8",  "ca": "8521"},
    "Auto":                     {"us": "9",  "ca": "9281"},
    "CommissionsAndFees":       {"us": "10", "ca": "9270"},
    "PayrollExpenses":          {"us": "26", "ca": "9060"},
    "Insurance":                {"us": "15", "ca": "8690"},
    "InterestPaid":             {"us": "16b", "ca": "8710"},
    "FinanceCosts":             {"us": "16b", "ca": "8710"},
    "BankCharges":              {"us": "27a", "ca": "8710"},
    "BadDebts":                 {"us": "27a", "ca": "8590"},
    "LegalProfessionalFees":    {"us": "17", "ca": "8860"},
    "OfficeExpenses":           {"us": "18", "ca": "8810"},
    "OfficeGeneralAdministrativeExpenses": {"us": "18", "ca": "8810"},
    "DuesSubscriptions":        {"us": "27a", "ca": "8760"},
    "SuppliesMaterials":        {"us": "22", "ca": "8811"},
    "RentOrLeaseOfBuildings":   {"us": "20b", "ca": "8910"},
    "EquipmentRental":          {"us": "20a", "ca": "8910"},
    "RepairMaintenance":        {"us": "21", "ca": "8960"},
    "Travel":                   {"us": "24a", "ca": "9200"},
    "TravelMeals":              {"us": "24b", "ca": "8523"},
    "PromotionalMeals":         {"us": "24b", "ca": "8523"},
    "EntertainmentMeals":       {"us": "24b", "ca": "8523"},
    "Entertainment":            {"us": "NONDED_274", "ca": "8523"},  # §274: not deductible (US)
    "CharitableContributions":  {"us": "NONDED_170", "ca": "NONDED"},  # sole-prop: Sch A / T1, not the business
    "Utilities":                {"us": "25", "ca": "9220"},
    "ShippingFreightDelivery":  {"us": "27a", "ca": "9275"},
    "OtherMiscellaneousServiceCost": {"us": "27a", "ca": "9270"},
    "OtherBusinessExpenses":    {"us": "27a", "ca": "9270"},
}

# Authoritative line catalog per jurisdiction: the canonical ID + citation.
# The optional US "mef" slot is reserved for a later, verified population of
# IRS MeF XML element names (left None until each is checked against the
# schema). The taxonomy may only target lines that exist here (gate-enforced).
_IRS_SCHED_C = "https://www.irs.gov/instructions/i1040sc"
_CRA_T2125 = "https://www.canada.ca/en/revenue-agency/services/forms-publications/forms/t2125.html"

_SCHEDULE_C_CATALOG = {
    "1":   {"desc": "Gross receipts or sales", "mef": None},
    "2":   {"desc": "Returns and allowances", "mef": None},
    "6":   {"desc": "Other income", "mef": None},
    "8":   {"desc": "Advertising", "mef": None},
    "9":   {"desc": "Car and truck expenses", "mef": None},
    "10":  {"desc": "Commissions and fees", "mef": None},
    "11":  {"desc": "Contract labor", "mef": None},
    "12":  {"desc": "Depletion", "mef": None},
    "13":  {"desc": "Depreciation and section 179", "mef": None},
    "14":  {"desc": "Employee benefit programs", "mef": None},
    "15":  {"desc": "Insurance (other than health)", "mef": None},
    "16a": {"desc": "Mortgage interest", "mef": None},
    "16b": {"desc": "Other interest", "mef": None},
    "17":  {"desc": "Legal and professional services", "mef": None},
    "18":  {"desc": "Office expense", "mef": None},
    "19":  {"desc": "Pension and profit-sharing plans", "mef": None},
    "20a": {"desc": "Rent or lease (vehicles, machinery, equipment)", "mef": None},
    "20b": {"desc": "Rent or lease (other business property)", "mef": None},
    "21":  {"desc": "Repairs and maintenance", "mef": None},
    "22":  {"desc": "Supplies", "mef": None},
    "23":  {"desc": "Taxes and licenses", "mef": None},
    "24a": {"desc": "Travel", "mef": None},
    "24b": {"desc": "Deductible meals", "mef": None},
    "25":  {"desc": "Utilities", "mef": None},
    "26":  {"desc": "Wages", "mef": None},
    "27a": {"desc": "Other expenses", "mef": None},
    "NONDED_274": {"desc": "Entertainment — not deductible on Schedule C (IRC §274(a))", "mef": None},
    "NONDED_170": {"desc": "Charitable contributions — not a Schedule C deduction; a sole proprietor claims them on Schedule A (IRC §170)", "mef": None},
    "NONDED_162E": {"desc": "Political contributions & lobbying — not deductible (IRC §162(e))", "mef": None},
}
# authority + cite are uniform for the form, attach them once
for _k, _v in _SCHEDULE_C_CATALOG.items():
    _v["authority"], _v["cite"] = "IRS-Sch-C", _IRS_SCHED_C

_T2125_CATALOG = {
    "8000":  "Gross sales, commissions or fees",
    "8000a": "Returns, allowances & discounts",
    "8230":  "Other income (interest, etc.)",
    "8340":  "Subcontracts (Part 3)",
    "8521":  "Advertising",
    "8523":  "Meals & entertainment (50%)",
    "8590":  "Bad debts",
    "8690":  "Insurance",
    "8710":  "Interest & bank charges",
    "8760":  "Business taxes, licences, dues & memberships",
    "8810":  "Office expenses",
    "8811":  "Office stationery & supplies",
    "8860":  "Professional fees (incl. legal & accounting)",
    "8871":  "Management & administration fees",
    "8910":  "Rent",
    "8960":  "Repairs & maintenance",
    "9060":  "Salaries, wages & benefits",
    "9180":  "Property taxes",
    "9200":  "Travel expenses",
    "9220":  "Utilities",
    "9224":  "Fuel costs (except motor vehicles)",
    "9270":  "Other expenses",
    "9275":  "Delivery, freight & express",
    "9281":  "Motor vehicle expenses",
    "NONDED": "Not deductible on T2125 — personal/non-business (e.g. charitable donations claim a T1 credit)",
}
_T2125_CATALOG = {k: {"desc": v, "authority": "CRA-GIFI", "cite": _CRA_T2125}
                  for k, v in _T2125_CATALOG.items()}

# Name-based FALLBACK rules (used only when AccountSubType is blank/custom).
# BOTH jurisdictions compile with a leading word boundary so "Credit Card"
# never hits Line 9 and "overdue" never hits CA "due". First match wins;
# order = specific before generic.
_NAME_FALLBACK_US = [
    (r"mortgage", "16a"),
    (r"advertis|marketing", "8"),
    (r"cars?\b|truck|vehicle|automobile|mileage", "9"),
    (r"commission", "10"),
    (r"contract labou?r|subcontractor|contractor|freelancer", "11"),
    (r"pension|profit[- ]?sharing|401\(?k\)?|retirement plan|sep[- ]?ira|simple ira", "19"),
    (r"employee benefit|health benefit|group insurance", "14"),
    (r"depreciation|amortization", "13"),
    (r"insurance", "15"),
    (r"interest|finance charge", "16b"),
    (r"legal|professional|accounting|bookkeep|consult", "17"),
    (r"equipment (rent|lease)|vehicle (rent|lease)|machinery (rent|lease)|"
     r"(rent|lease).{0,12}(equipment|vehicle|machinery)", "20a"),
    (r"rent|lease", "20b"),
    (r"repair|maintenance", "21"),
    (r"office", "18"),
    (r"supplies|stationery", "22"),
    (r"tax(?:es)?\b|licen[cs]e|permit", "23"),
    (r"travel|hotel|lodging|airfare|airline|flight|taxi|rideshare|ride ?share|"
     r"uber|lyft", "24a"),
    # meals BEFORE entertainment: a combined "Meals & Entertainment" account maps
    # to deductible meals (50%); only a PURE entertainment account is §274 nondeductible
    (r"meals?|restaurant|dining", "24b"),
    (r"entertainment", "NONDED_274"),
    (r"charit|donation|contribution to", "NONDED_170"),
    (r"political contribution|lobbying", "NONDED_162E"),
    (r"utilit(y|ies)|electric|water|internet|phone|telephone|cell|communication", "25"),
    (r"wages?|salar|payroll", "26"),
    (r"software|subscription|hosting|cloud|saas|education|training|"
     r"bank (charge|fee)|processing|merchant|dues|shipping|postage|freight", "27a"),
]
_NAME_FALLBACK_CA = [
    (r"advertis|marketing", "8521"),
    (r"subcontract|contract labou?r", "8340"),
    (r"charit|donation", "NONDED"),
    (r"meal|entertain", "8523"),
    (r"bad debt", "8590"),
    (r"insurance", "8690"),
    (r"interest|bank", "8710"),
    (r"property tax", "9180"),
    (r"business tax|licen[cs]e|permit|membership|dues?", "8760"),
    (r"stationery|supplies", "8811"),
    (r"office", "8810"),
    (r"legal|accounting|bookkeep|professional", "8860"),
    (r"management fee|admin", "8871"),
    (r"rent|lease", "8910"),
    (r"repair|maintenance", "8960"),
    (r"salar|wages?|payroll", "9060"),
    (r"travel", "9200"),
    (r"utilit|phone|telephone|internet", "9220"),
    (r"fuel", "9224"),
    (r"delivery|freight|shipping", "9275"),
    (r"vehicle|automobile|auto\b|mileage|motor", "9281"),
    (r"software|subscription|hosting|education|training|tax(?:es)?\b", "9270"),
]
_NAME_FALLBACK_COMPILED = {
    "us": [(re.compile(r"\b(?:" + p + r")", re.I), line) for p, line in _NAME_FALLBACK_US],
    "ca": [(re.compile(r"\b(?:" + p + r")", re.I), line) for p, line in _NAME_FALLBACK_CA],
}
_CATCH_ALL = {"us": "27a", "ca": "9270"}
_CATALOG = {"us": _SCHEDULE_C_CATALOG, "ca": _T2125_CATALOG}
_HOME_8829 = re.compile(
    r"\b(home office|home-office|homeowner|home util\w*|home insurance)\b", re.I)


def classify_account(name: str, subtype: str, jurisdiction: str):
    """Map one account to its tax line. jurisdiction: 'US' or 'CA'.
    Returns (line, desc, flags). Prefers the authoritative AccountSubType;
    falls back to word-boundary name rules; else the jurisdiction catch-all.
    flags may include 'home_8829' (US, review on Form 8829) and 'nondeductible'.
    A line starting with "NONDED" marks a book expense that is NOT a deduction on
    the business return (entertainment §274, charitable §170, political §162(e))."""
    juris = "us" if str(jurisdiction).upper() == "US" else "ca"
    catalog = _CATALOG[juris]
    name = name or ""
    line = None
    tax = _ACCOUNT_TAXONOMY.get(subtype or "")
    if tax and tax.get(juris):
        line = tax[juris]
    else:
        for pat, cand in _NAME_FALLBACK_COMPILED[juris]:
            if pat.search(name):
                line = cand
                break
    if not line:
        line = _CATCH_ALL[juris]
    desc = catalog.get(line, {}).get("desc", "Other expenses")
    flags = []
    if line.startswith("NONDED"):
        flags.append("nondeductible")
    if juris == "us" and _HOME_8829.search(name):
        flags.append("home_8829")
    return line, desc, flags


# ===================================================================
# STATUTORY DEDUCTION LIMITS — percentage caps SET BY LAW (same for every
# taxpayer), so they belong in this ledgered control plane. This is distinct
# from a taxpayer's own ALLOCATION percentage (home-office %, vehicle %,
# internet %), which is per-realm taxpayer data and must NEVER live here.
# ===================================================================
_STATUTORY_LIMITS = {
    "meals_us": {"factor": 0.50, "line": "24b", "jurisdiction": "US",
                 "cite": "IRC §274(n)", "since": "2023-01-01",
                 "desc": "Business meals — 50% deductible"},
    "meals_ca": {"factor": 0.50, "line": "8523", "jurisdiction": "CA",
                 "cite": "ITA s.67.1", "since": None,
                 "desc": "Meals & entertainment — 50% deductible"},
    # NONDED_* lines are the degenerate case (factor 0.0); they are handled
    # separately (segregated + cited) rather than reduced in place.
}
_LINE_LIMIT_INDEX = {(v["jurisdiction"].lower(), v["line"]): v
                     for v in _STATUTORY_LIMITS.values()}


def line_limitation(line: str, jurisdiction: str):
    """Statutory deduction factor for a tax line: ``(factor, citation)``.
    Returns ``(1.0, "")`` when the line is fully deductible. LAW-set (same for
    every taxpayer) — NOT a taxpayer allocation percentage."""
    juris = "us" if str(jurisdiction).upper() == "US" else "ca"
    lim = _LINE_LIMIT_INDEX.get((juris, line))
    return (lim["factor"], lim["cite"]) if lim else (1.0, "")


# CCA declining-balance classes (Schedule II, Income Tax Regulations)
_CCA_CLASSES = {
    "8": (0.20, "Furniture, appliances, tools >= $500, misc. equipment"),
    "10": (0.30, "Motor vehicles / passenger vehicles within the cost ceiling"),
    "10.1": (0.30, "Passenger vehicles over the cost ceiling (one per class; "
                   "no terminal loss; half-year CCA allowed in year of sale)"),
    "12": (1.00, "Tools < $500, application software"),
    "14.1": (0.05, "Goodwill & intangibles"),
    "50": (0.55, "Computer hardware & systems software"),
    "53": (0.50, "Manufacturing & processing machinery"),
    "54": (0.30, "Zero-emission vehicles (ceiling $61,000 + tax)"),
}
# Class 10.1 passenger-vehicle cost ceiling by acquisition year (plus sales tax)
# Full acquisition-year history (CRA prescribed amounts): $30,000 for
# 2001-2021, then annual increases from 2022.
_CLASS_10_1_CEILING = {
    **{y: 30_000.0 for y in range(2001, 2022)},
    2022: 34_000.0, 2023: 36_000.0, 2024: 37_000.0,
    2025: 38_000.0, 2026: 39_000.0,
}
_CLASS_54_ZEV_CEILING = 61_000.0
_AII_START_YEAR = 2025       # Budget 2025 / Bill C-15 reinstatement
_AII_FIRST_YEAR_FACTOR = 1.5  # 1.5x first-year rate, half-year rule suspended

# T4A administrative practice: CRA commonly expects slips for service fees
# >= $500/vendor (box 048 has no legislated minimum).
_T4A_ADMIN_THRESHOLD = 500.0

# CPP self-employed parameters by year (CRA payroll tables)
_CPP_PARAMS = {
    2025: {"ympe": 71_300.0, "yampe": 81_200.0},
    2026: {"ympe": 74_600.0, "yampe": 85_000.0},
}
_CPP_BASIC_EXEMPTION = 3_500.0
_CPP_RATE_SELF = 0.119   # 5.95% employee + 5.95% employer
_CPP2_RATE_SELF = 0.08   # 4% employee + 4% employer

# APPROXIMATE federal brackets (2025 threshold values; Bill C-4 lowered the
# first rate — 14.5% blended for 2025, 14% for 2026; labelled approximate).
_CA_FED_BRACKETS_APPROX = [
    (57_375.0, 0.145),
    (114_750.0, 0.205),
    (177_882.0, 0.26),
    (253_414.0, 0.29),
    (float("inf"), 0.33),
]
_CA_BPA_APPROX = 16_000.0  # federal basic personal amount, rough

# APPROXIMATE flat provincial effective rates for planning only
_CA_PROV_FLAT_APPROX = {
    "ON": 0.07, "BC": 0.07, "AB": 0.10, "QC": 0.15, "MB": 0.12,
    "SK": 0.10, "NS": 0.13, "NB": 0.12, "PE": 0.13, "NL": 0.12,
    "YT": 0.07, "NT": 0.08, "NU": 0.06,
}

_CRA_INSTALMENT_DATES = ["Mar 15", "Jun 15", "Sep 15", "Dec 15"]
_CRA_INSTALMENT_THRESHOLD = 3_000.0  # net tax owing (QC: $1,800 federal)

# GST/HST Quick Method remittance rates for service businesses (CRA
# RC4058; rates depend on province of supply — planning figures only)
_QUICK_METHOD_REMITTANCE = {"gst_5pct_services": 0.036, "on_13pct_services": 0.088}


# =========================================================================
# TABLES — metadata registry (provenance layer). Every constant above has
# an entry; tests/test_tax_data_policy.py enforces completeness, freshness,
# ledger coverage, and sanity bounds.
# kind: exact (published figure) | approximation (planning estimate)
#       | stable_statute (formula/threshold set by statute, rarely moves)
# review: annual-december | annual-january | legislative-watch
# =========================================================================

TABLES: dict = {
    "SS_WAGE_BASE": dict(values=_SS_WAGE_BASE, year_keyed=True, jurisdiction="US-federal",
        kind="exact", description="Social Security wage base (SE tax OASDI cap)",
        source="SSA COLA fact sheet; Rev. Proc. 2025-32 context",
        source_url="https://www.ssa.gov/oact/cola/cbb.html",
        verified="2026-07-12", review="annual-december",
        sanity={"min": 100_000, "max": 500_000, "max_yoy_pct": 0.10}),
    "FED_BRACKETS": dict(values=_FED_BRACKETS, year_keyed=True, jurisdiction="US-federal",
        kind="exact", description="Federal income tax bracket thresholds + standard deduction",
        source="Rev. Proc. 2024-40 (2025); Rev. Proc. 2025-32 (2026, post-OBBBA)",
        source_url="https://www.irs.gov/pub/irs-drop/rp-25-32.pdf",
        verified="2026-07-12", review="annual-december", sanity={}),
    "FED_RATES": dict(values=_RATES, year_keyed=False, jurisdiction="US-federal",
        kind="stable_statute", description="Federal bracket rates (OBBBA made TCJA rates permanent)",
        source="IRC §1 as amended by OBBBA (2025)",
        source_url="https://www.congress.gov/bill/119th-congress/house-bill/1",
        verified="2026-07-12", review="legislative-watch",
        sanity={"min": 0.0, "max": 1.0}),
    "SE_TAX": dict(values={"net_earnings_factor": _SE_NET_EARNINGS_FACTOR,
                           "ss_rate": _SE_SS_RATE, "medicare_rate": _SE_MEDICARE_RATE},
        year_keyed=False, jurisdiction="US-federal", kind="stable_statute",
        description="Self-employment tax formula (IRC 1401/1402)",
        source="IRC §1401, §1402(a)(12)",
        source_url="https://www.irs.gov/businesses/small-businesses-self-employed/self-employment-tax-social-security-and-medicare-taxes",
        verified="2026-07-12", review="legislative-watch",
        sanity={"min": 0.0, "max": 1.0}),
    "US_STATE_TAX": dict(values=_US_STATE_TAX, year_keyed=False, jurisdiction="US-state",
        kind="approximation", description="State income tax on SE income (flat statutory or effective approx)",
        source="Tax Foundation, State Individual Income Tax Rates and Brackets, 2026; GA HB 463 (signed 2026-05-11, retroactive 2026-01-01)",
        source_url="https://taxfoundation.org/data/all/state/state-income-tax-rates-2026/",
        verified="2026-07-13", review="annual-january", sanity={"min": 0.0, "max": 1.0}),
    "US_SALES_TAX_NEXUS": dict(values=_US_SALES_TAX_NEXUS, year_keyed=False,
        jurisdiction="US-state", kind="exact",
        description="State sales-tax economic-nexus thresholds (post-Wayfair)",
        source="Sales Tax Institute Economic Nexus State Guide (chart as of 2026-05-04), cross-checked to state DOR pages",
        source_url="https://www.salestaxinstitute.com/resources/economic-nexus-state-guide",
        verified="2026-08-01", review="legislative-watch",
        sanity={"min": 0, "max": 1_000_000}),
    "TCJA_PHASE_DOWN": dict(values=_TCJA_PHASE_DOWN, year_keyed=True, terminal_value=0.0,
        jurisdiction="US-federal", kind="stable_statute",
        description="Bonus depreciation phase-down (property acquired on/before 2025-01-19)",
        source="IRC 168(k) (TCJA); OBBBA preserved phase-down for pre-1/19/25 acquisitions",
        source_url="https://www.irs.gov/newsroom/one-big-beautiful-bill-act-tax-provisions",
        verified="2026-07-12", review="legislative-watch", sanity={"min": 0.0, "max": 1.0}),
    "SUV_179_CAP": dict(values=_SUV_179_CAP, year_keyed=True, jurisdiction="US-federal",
        kind="exact", description="Heavy SUV (6,001-14,000 lbs GVWR) Section 179 cap",
        source="Rev. Proc. 2025-32 §179(b)(5) inflation adjustment",
        source_url="https://www.irs.gov/pub/irs-drop/rp-25-32.pdf",
        verified="2026-07-12", review="annual-december",
        sanity={"min": 20_000, "max": 60_000, "max_yoy_pct": 0.10}),
    "280F_LIMITS": dict(values=_280F_LIMITS, year_keyed=True, jurisdiction="US-federal",
        kind="exact", description="Luxury-auto (§280F) annual depreciation caps",
        source="Rev. Proc. 2025-16 (2025); Rev. Proc. 2026-15 (2026)",
        source_url="https://www.irs.gov/pub/irs-drop/rp-26-15.pdf",
        verified="2026-07-12", review="annual-january", sanity={}),
    "MACRS_5YR": dict(values=_MACRS_5YR, year_keyed=False, jurisdiction="US-federal",
        kind="stable_statute", description="MACRS 5-year property rates (200% DB, half-year)",
        source="IRS Publication 946, Table A-1",
        source_url="https://www.irs.gov/publications/p946",
        verified="2026-07-12", review="legislative-watch", sanity={"min": 0.0, "max": 1.0}),
    "SEC_179_LIMITS": dict(values=_SEC_179_LIMITS, year_keyed=True, jurisdiction="US-federal",
        kind="exact", description="Section 179 expensing limit + phase-out threshold",
        source="OBBBA (base $2.5M/$4M from 2025); Rev. Proc. 2025-32 (2026 indexed)",
        source_url="https://www.irs.gov/pub/irs-drop/rp-25-32.pdf",
        verified="2026-07-12", review="annual-december",
        sanity={"min": 1_000_000, "max": 10_000_000, "max_yoy_pct": 0.10}),
    "SEC_195": dict(values=_SEC_195, year_keyed=False, jurisdiction="US-federal",
        kind="stable_statute", description="Startup cost immediate deduction / phase-out / amortization",
        source="IRC §195(b)",
        source_url="https://www.law.cornell.edu/uscode/text/26/195",
        verified="2026-07-12", review="legislative-watch", sanity={}),
    "HOME_OFFICE_SIMPLIFIED": dict(values=_HOME_OFFICE_SIMPLIFIED, year_keyed=False,
        jurisdiction="US-federal", kind="stable_statute",
        description="Home office simplified method ($/sqft and cap)",
        source="Rev. Proc. 2013-13",
        source_url="https://www.irs.gov/businesses/small-businesses-self-employed/simplified-option-for-home-office-deduction",
        verified="2026-07-12", review="legislative-watch", sanity={}),
    "STD_MILEAGE_CENTS": dict(values=_STD_MILEAGE_CENTS, year_keyed=True,
        jurisdiction="US-federal", kind="exact",
        description="IRS standard business mileage rate (cents/mile); 2026 value is H2 rate (76.0c Jul 1+)",
        source="Notice 2025-5 (2025: 70c); Notice 2026-10 (H1 2026: 72.5c); Announcement 2026-11 in IRB 2026-29 (H2 2026: 76.0c, effective Jul 1)",
        source_url="https://www.irs.gov/pub/irs-irbs/irb26-29.pdf",
        verified="2026-07-13", review="annual-december",
        sanity={"min": 30.0, "max": 150.0, "max_yoy_pct": 0.15}),
    "RETIREMENT_LIMITS": dict(values=_RETIREMENT_LIMITS, year_keyed=True,
        jurisdiction="US-federal", kind="exact",
        description="SEP-IRA max and Solo 401(k) employee deferral",
        source="IRS COLA notice (2026: SEP $72,000, deferral $24,500)",
        source_url="https://www.irs.gov/retirement-plans/plan-participant-employee/retirement-topics-contributions",
        verified="2026-07-12", review="annual-december",
        sanity={"min": 10_000, "max": 200_000, "max_yoy_pct": 0.15}),
    "NEC_1099_THRESHOLD": dict(values=_1099_NEC_THRESHOLD, year_keyed=True,
        jurisdiction="US-federal", kind="exact",
        description="1099-NEC/MISC reporting threshold per payee",
        source="OBBBA §70433: $2,000 for payments on/after 2026-01-01, indexed after",
        source_url="https://www.irs.gov/newsroom/one-big-beautiful-bill-act-tax-provisions",
        verified="2026-07-12", review="legislative-watch",
        sanity={"min": 0, "max": 10_000}),
    "CA_SALES_TAX_REGIME": dict(values=_CA_SALES_TAX_REGIME, year_keyed=False,
        jurisdiction="CA-provincial", kind="exact",
        description="Per-province sales tax regime (HST/GST+PST/GST+QST/GST)",
        source="CRA GST/HST rates table (NS 15%->14% effective 2025-04-01)",
        source_url="https://www.canada.ca/en/revenue-agency/services/tax/businesses/topics/gst-hst-businesses/charge-collect-which-rate.html",
        verified="2026-07-12", review="annual-january", sanity={"min": 0.0, "max": 1.0}),
    "GST_QUICK_METHOD": dict(values={"limit": _GST_QUICK_METHOD_LIMIT,
                                     "credit_base": _GST_QUICK_METHOD_CREDIT_BASE,
                                     **_QUICK_METHOD_REMITTANCE},
        year_keyed=False, jurisdiction="CA-federal", kind="stable_statute",
        description="GST/HST Quick Method eligibility limit, 1% credit base, remittance rates",
        source="CRA RC4058 Quick Method of Accounting",
        source_url="https://www.canada.ca/en/revenue-agency/services/forms-publications/publications/rc4058.html",
        verified="2026-07-12", review="annual-january", sanity={}),
    "MEALS_ITC_FACTOR": dict(values=_MEALS_ITC_FACTOR, year_keyed=False,
        jurisdiction="CA-federal", kind="stable_statute",
        description="ITC restriction on meals & entertainment",
        source="Income Tax Act s.67.1",
        source_url="https://laws-lois.justice.gc.ca/eng/acts/i-3.3/section-67.1.html",
        verified="2026-07-12", review="legislative-watch", sanity={"min": 0.0, "max": 1.0}),
    "ACCOUNT_TAXONOMY": dict(values=_ACCOUNT_TAXONOMY, year_keyed=False,
        jurisdiction="US-federal", kind="stable_statute",
        description="QuickBooks AccountSubType -> IRS Schedule C line + CRA T2125/GIFI line",
        source="IRS Schedule C instructions (i1040sc) + CRA Form T2125",
        source_url="https://www.irs.gov/instructions/i1040sc",
        verified="2026-08-03", review="annual-january", sanity={}),
    "SCHEDULE_C_CATALOG": dict(values=_SCHEDULE_C_CATALOG, year_keyed=False,
        jurisdiction="US-federal", kind="stable_statute",
        description="Authoritative Schedule C line catalog (line -> desc + IRS citation)",
        source="IRS Schedule C instructions (i1040sc)",
        source_url="https://www.irs.gov/instructions/i1040sc",
        verified="2026-08-03", review="annual-january", sanity={}),
    "T2125_CATALOG": dict(values=_T2125_CATALOG, year_keyed=False,
        jurisdiction="CA-federal", kind="stable_statute",
        description="Authoritative T2125/GIFI line catalog (line -> desc + CRA citation)",
        source="CRA Form T2125 (Statement of Business or Professional Activities)",
        source_url="https://www.canada.ca/en/revenue-agency/services/forms-publications/forms/t2125.html",
        verified="2026-08-03", review="annual-january", sanity={}),
    "STATUTORY_LIMITS": dict(values=_STATUTORY_LIMITS, year_keyed=False,
        jurisdiction="US-federal", kind="stable_statute",
        description="Statutory deduction caps by tax line (e.g. meals 50%) — law-set, not taxpayer allocation",
        source="IRC §274(n) (US meals 50%); ITA s.67.1 (CA meals & entertainment 50%)",
        source_url="https://www.irs.gov/publications/p463",
        verified="2026-08-03", review="legislative-watch",
        sanity={"min": 0.0, "max": 1.0}),
    "CCA_CLASSES": dict(values=_CCA_CLASSES, year_keyed=False, jurisdiction="CA-federal",
        kind="stable_statute", description="CCA declining-balance classes and rates",
        source="Income Tax Regulations Schedule II",
        source_url="https://www.canada.ca/en/revenue-agency/services/tax/businesses/topics/sole-proprietorships-partnerships/report-business-income-expenses/claiming-capital-cost-allowance/classes-depreciable-property.html",
        verified="2026-07-12", review="legislative-watch", sanity={"min": 0.0, "max": 1.0}),
    "CLASS_10_1_CEILING": dict(values=_CLASS_10_1_CEILING, year_keyed=True,
        jurisdiction="CA-federal", kind="exact",
        description="Class 10.1 passenger-vehicle cost ceiling by acquisition year",
        source="CRA prescribed automobile amounts (announced each December)",
        source_url="https://www.canada.ca/en/department-finance/news/2025/12/automobile-deduction-limits.html",
        verified="2026-07-12", review="annual-december",
        sanity={"min": 20_000, "max": 100_000, "max_yoy_pct": 0.15}),
    "CLASS_54_ZEV_CEILING": dict(values=_CLASS_54_ZEV_CEILING, year_keyed=False,
        jurisdiction="CA-federal", kind="exact",
        description="Class 54 zero-emission vehicle cost ceiling",
        source="CRA prescribed amounts",
        source_url="https://www.canada.ca/en/revenue-agency/services/tax/businesses/topics/sole-proprietorships-partnerships/report-business-income-expenses/claiming-capital-cost-allowance/zero-emission-vehicles.html",
        verified="2026-07-12", review="annual-december",
        sanity={"min": 30_000, "max": 150_000}),
    "AII": dict(values={"start_year": _AII_START_YEAR, "first_year_factor": _AII_FIRST_YEAR_FACTOR},
        year_keyed=False, jurisdiction="CA-federal", kind="stable_statute",
        description="Accelerated Investment Incentive (Budget 2025 / Bill C-15)",
        source="Bill C-15 (2025); phase-out 2030-2033",
        source_url="https://www.canada.ca/en/department-finance/news/2025/11/accelerated-investment-incentive.html",
        verified="2026-07-12", review="legislative-watch", sanity={}),
    "T4A_ADMIN_THRESHOLD": dict(values=_T4A_ADMIN_THRESHOLD, year_keyed=False,
        jurisdiction="CA-federal", kind="approximation",
        description="T4A box 048 administrative reporting threshold (no legislated minimum)",
        source="CRA administrative practice",
        source_url="https://www.canada.ca/en/revenue-agency/services/tax/businesses/topics/payroll/completing-filing-information-returns/t4a-information-payers/t4a-slip.html",
        verified="2026-07-12", review="annual-january", sanity={"min": 0, "max": 10_000}),
    "CPP": dict(values={"params": _CPP_PARAMS, "basic_exemption": _CPP_BASIC_EXEMPTION,
                        "rate_self": _CPP_RATE_SELF, "cpp2_rate_self": _CPP2_RATE_SELF},
        year_keyed=True, jurisdiction="CA-federal", kind="exact",
        description="CPP/CPP2 self-employed parameters (YMPE/YAMPE by year)",
        source="CRA payroll deductions tables (2026: YMPE $74,600 / YAMPE $85,000)",
        source_url="https://www.canada.ca/en/revenue-agency/services/tax/businesses/topics/payroll/payroll-deductions-contributions/canada-pension-plan-cpp.html",
        verified="2026-07-12", review="annual-december",
        sanity={"max_yoy_pct": 0.10}),  # values mix rates and dollar ceilings
    "CA_FED_BRACKETS_APPROX": dict(values=_CA_FED_BRACKETS_APPROX, year_keyed=False,
        jurisdiction="CA-federal", kind="approximation",
        description="Approximate federal brackets for instalment planning (Bill C-4 blended first rate)",
        source="CRA 2025 thresholds; Bill C-4 (2025) rate cut",
        source_url="https://www.canada.ca/en/revenue-agency/services/tax/individuals/frequently-asked-questions-individuals/canadian-income-tax-rates-individuals-current-previous-years.html",
        verified="2026-07-12", review="annual-december",
        sanity={}),  # values mix bracket thresholds (dollars) and rates
    "CA_BPA_APPROX": dict(values=_CA_BPA_APPROX, year_keyed=False,
        jurisdiction="CA-federal", kind="approximation",
        description="Federal basic personal amount (rough, indexed annually)",
        source="CRA indexation adjustment",
        source_url="https://www.canada.ca/en/revenue-agency/services/tax/individuals/frequently-asked-questions-individuals/adjustment-personal-income-tax-benefit-amounts.html",
        verified="2026-07-12", review="annual-december",
        sanity={"min": 10_000, "max": 30_000}),
    "CA_PROV_FLAT_APPROX": dict(values=_CA_PROV_FLAT_APPROX, year_keyed=False,
        jurisdiction="CA-provincial", kind="approximation",
        description="Flat provincial effective income tax rates for planning",
        source="Provincial rate tables, blended estimate",
        source_url="https://www.canada.ca/en/revenue-agency/services/tax/individuals/frequently-asked-questions-individuals/canadian-income-tax-rates-individuals-current-previous-years.html",
        verified="2026-07-12", review="annual-december", sanity={"min": 0.0, "max": 1.0}),
    "CRA_INSTALMENTS": dict(values={"dates": _CRA_INSTALMENT_DATES,
                                    "threshold": _CRA_INSTALMENT_THRESHOLD},
        year_keyed=False, jurisdiction="CA-federal", kind="stable_statute",
        description="CRA instalment due dates and $3,000 threshold ($1,800 QC)",
        source="Income Tax Act s.156.1",
        source_url="https://www.canada.ca/en/revenue-agency/services/tax/individuals/topics/about-your-tax-return/making-payments-individuals/paying-your-income-tax-instalments.html",
        verified="2026-07-12", review="legislative-watch", sanity={}),
}


# =========================================================================
# Access helpers (L2 — fail-closed)
# =========================================================================

def tax_value(table: str, year: int):
    """Exact-year lookup. Missing year -> TaxDataError (fail-closed)."""
    entry = TABLES[table]
    values = entry["values"]
    if year in values:
        return values[year]
    if "terminal_value" in entry and year > max(values):
        return entry["terminal_value"]
    known = sorted(k for k in values if isinstance(k, int))
    raise TaxDataError(
        f"{entry['description']}: no figures loaded for {year} "
        f"(tables cover {known[0]}-{known[-1]}, verified {entry['verified']}, "
        f"TAX_DATA v{TAX_DATA_VERSION}). For future years, tables load once "
        f"official figures publish."
    )


def tax_value_or_latest(table: str, year: int):
    """(value, note). Known year -> (value, ""). Future year -> latest
    year's value plus a mandatory user-facing note (Constitution: never
    silently reuse stale rates — always say which year's figures were
    used). Past years below coverage -> TaxDataError (later-year figures
    are never applied backward)."""
    entry = TABLES[table]
    values = entry["values"]
    if year in values:
        return values[year], ""
    if "terminal_value" in entry and year > max(values):
        return entry["terminal_value"], ""
    years = sorted(k for k in values if isinstance(k, int))
    if year > years[-1]:
        return values[years[-1]], (
            f"Note: using {years[-1]} figures — {year} tables not yet loaded "
            f"(verified through {years[-1]}, TAX_DATA v{TAX_DATA_VERSION})."
        )
    raise TaxDataError(
        f"{entry['description']}: no figures for {year} — tables begin at "
        f"{years[0]} and later-year figures are never applied backward."
    )


def tax_data_footer(vintage_year=None) -> str:
    """Provenance + point-of-use liability footer for tax tool outputs."""
    vintage = f"{vintage_year} tables" if vintage_year else "current tables"
    return ("\n\n---\n"
            f"*Rates: {vintage} · verified {TAX_DATA_VERIFIED} · "
            f"TAX_DATA v{TAX_DATA_VERSION} · details: qb_tax_data_info*\n"
            "*Informational workpaper only — not tax, legal, or accounting "
            "advice. Rates and rules change and may not fit your situation. "
            "Verify against official IRS/CRA/state sources and confirm with a "
            "qualified tax professional before filing or relying on these "
            "figures; you are responsible for the accuracy and compliance of "
            "your filings.*")


# =========================================================================
# L4 ledger access
# =========================================================================

_LEDGER_GENESIS_SEED = "accountingqb-tax-ledger-genesis-v1"


def iter_table_rows(name: str, entry: dict):
    """Yield (key, value) ledger-row pairs for one TABLES entry — the same
    decomposition the genesis seeder used, shared so tests can't drift."""
    v = entry["values"]
    if entry.get("year_keyed") and isinstance(v, dict) and all(isinstance(k, int) for k in v):
        for year in sorted(v):
            yield str(year), v[year]
    elif name == "CPP":
        for year in sorted(v["params"]):
            yield f"{year}:params", v["params"][year]
        for k in ("basic_exemption", "rate_self", "cpp2_rate_self"):
            yield k, v[k]
    else:
        yield "-", v


def table_year_keys(entry: dict) -> list:
    """Year keys covered by a year_keyed table (handles CPP-style nesting)."""
    v = entry["values"]
    if isinstance(v, dict) and all(isinstance(k, int) for k in v):
        return sorted(v)
    if isinstance(v, dict) and isinstance(v.get("params"), dict):
        return sorted(v["params"])
    return []


def canonical_value(value):
    """JSON-normalize a registry value for ledger storage/comparison:
    dict keys become strings (JSON has no int keys), tuples become lists."""
    if isinstance(value, dict):
        return {str(k): canonical_value(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [canonical_value(v) for v in value]
    return value


def ledger_path() -> pathlib.Path:
    return pathlib.Path(__file__).parent / "tax_ledger.jsonl"


def load_ledger() -> list:
    """Parse the ledger. Returns [] if the file is missing (pre-genesis)."""
    p = ledger_path()
    if not p.exists():
        return []
    return [json.loads(line) for line in p.read_text().splitlines() if line.strip()]


def verify_ledger_chain(rows=None) -> bool:
    """Append-only by math: each row's prev_hash must equal the SHA-256 of
    the previous row's canonical line (genesis hashes the fixed seed)."""
    if rows is None:
        rows = load_ledger()
    prev = hashlib.sha256(_LEDGER_GENESIS_SEED.encode()).hexdigest()
    for row in rows:
        if row.get("prev_hash") != f"sha256:{prev}":
            return False
        canonical = json.dumps(row, sort_keys=True, separators=(",", ":"))
        prev = hashlib.sha256(canonical.encode()).hexdigest()
    return True
