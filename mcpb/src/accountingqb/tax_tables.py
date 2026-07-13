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

TAX_DATA_VERSION = "2026.2"       # bumped by every approved rates PR
TAX_DATA_VERIFIED = "2026-07-12"  # date of the last full verification sweep


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

# IRS standard business mileage, cents/mile (Notice 2026-10 for 2026)
_STD_MILEAGE_CENTS = {2025: 70.0, 2026: 72.5}

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
# effective rate for a bracketed state. 2025 tax-year values — review
# annually (several flat states step their rate down each January).
# Source: Tax Foundation, "2025 State Income Tax Rates and Brackets".
_US_STATE_TAX = {
    "TX": (0.0, "none"), "FL": (0.0, "none"), "WA": (0.0, "none"),
    "NV": (0.0, "none"), "TN": (0.0, "none"), "SD": (0.0, "none"),
    "WY": (0.0, "none"), "AK": (0.0, "none"),
    "NH": (0.0, "none"),  # no tax on earned income (interest/dividends tax repealed 2025)
    "AZ": (0.025, "flat"), "CO": (0.044, "flat"), "GA": (0.0519, "flat"),
    "ID": (0.053, "flat"), "IL": (0.0495, "flat"), "IN": (0.03, "flat"),
    "IA": (0.038, "flat"), "KY": (0.04, "flat"), "MA": (0.05, "flat"),
    "MI": (0.0425, "flat"), "MS": (0.044, "flat"), "NC": (0.0425, "flat"),
    "PA": (0.0307, "flat"), "UT": (0.045, "flat"),
    "AL": (0.05, "progressive_approx"), "AR": (0.039, "progressive_approx"),
    "CA": (0.093, "progressive_approx"), "CT": (0.055, "progressive_approx"),
    "DE": (0.055, "progressive_approx"), "DC": (0.065, "progressive_approx"),
    "HI": (0.079, "progressive_approx"), "KS": (0.0558, "progressive_approx"),
    "LA": (0.03, "progressive_approx"), "MD": (0.0475, "progressive_approx"),
    "ME": (0.0715, "progressive_approx"), "MN": (0.0785, "progressive_approx"),
    "MO": (0.047, "progressive_approx"), "MT": (0.059, "progressive_approx"),
    "ND": (0.025, "progressive_approx"), "NE": (0.052, "progressive_approx"),
    "NJ": (0.0637, "progressive_approx"), "NM": (0.049, "progressive_approx"),
    "NY": (0.065, "progressive_approx"), "OH": (0.035, "progressive_approx"),
    "OK": (0.0475, "progressive_approx"), "OR": (0.0875, "progressive_approx"),
    "RI": (0.0475, "progressive_approx"), "SC": (0.062, "progressive_approx"),
    "VA": (0.0575, "progressive_approx"), "VT": (0.066, "progressive_approx"),
    "WI": (0.053, "progressive_approx"), "WV": (0.0482, "progressive_approx"),
}


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

# T2125 Part 4 line numbers — QB account-name keyword -> (line, description).
# Insertion order matters: more specific keywords must precede generic ones
# (e.g. "property tax" before "business tax", "stationery" before "office").
_T2125_LINE_MAP = {
    "advertis": ("8521", "Advertising"),
    "marketing": ("8521", "Advertising"),
    "meal": ("8523", "Meals & entertainment (50% deductible)"),
    "entertain": ("8523", "Meals & entertainment (50% deductible)"),
    "bad debt": ("8590", "Bad debts"),
    "insurance": ("8690", "Insurance"),
    "interest": ("8710", "Interest & bank charges"),
    "bank": ("8710", "Interest & bank charges"),
    "property tax": ("9180", "Property taxes"),
    "business tax": ("8760", "Business taxes, licences & memberships"),
    "licence": ("8760", "Business taxes, licences & memberships"),
    "license": ("8760", "Business taxes, licences & memberships"),
    "membership": ("8760", "Business taxes, licences & memberships"),
    "due": ("8760", "Business taxes, licences & memberships"),
    "stationery": ("8811", "Office stationery & supplies"),
    "supplies": ("8811", "Office stationery & supplies"),
    "office": ("8810", "Office expenses"),
    "legal": ("8860", "Professional fees (incl. legal & accounting)"),
    "accounting": ("8860", "Professional fees (incl. legal & accounting)"),
    "bookkeep": ("8860", "Professional fees (incl. legal & accounting)"),
    "professional": ("8860", "Professional fees (incl. legal & accounting)"),
    "management fee": ("8871", "Management & administration fees"),
    "admin": ("8871", "Management & administration fees"),
    "rent": ("8910", "Rent"),
    "repair": ("8960", "Repairs & maintenance"),
    "maintenance": ("8960", "Repairs & maintenance"),
    "salar": ("9060", "Salaries, wages & benefits"),
    "wage": ("9060", "Salaries, wages & benefits"),
    "payroll": ("9060", "Salaries, wages & benefits"),
    "travel": ("9200", "Travel expenses"),
    "utilit": ("9220", "Utilities"),
    "phone": ("9220", "Utilities"),
    "telephone": ("9220", "Utilities"),
    "internet": ("9220", "Utilities"),
    "fuel": ("9224", "Fuel costs (except motor vehicles)"),
    "delivery": ("9275", "Delivery, freight & express"),
    "freight": ("9275", "Delivery, freight & express"),
    "shipping": ("9275", "Delivery, freight & express"),
    "vehicle": ("9281", "Motor vehicle expenses"),
    "automobile": ("9281", "Motor vehicle expenses"),
    "auto": ("9281", "Motor vehicle expenses"),
    "mileage": ("9281", "Motor vehicle expenses"),
    "motor": ("9281", "Motor vehicle expenses"),
    "software": ("9270", "Other expenses"),
    "subscription": ("9270", "Other expenses"),
    "hosting": ("9270", "Other expenses"),
    "education": ("9270", "Other expenses"),
    "training": ("9270", "Other expenses"),
}

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
        source="Tax Foundation, State Individual Income Tax Rates and Brackets, 2025",
        source_url="https://taxfoundation.org/data/all/state/state-income-tax-rates/",
        verified="2026-07-12", review="annual-january", sanity={"min": 0.0, "max": 1.0}),
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
        description="IRS standard business mileage rate (cents/mile)",
        source="IRS Notice 2026-10 (2026: 72.5c); Notice 2025-5 (2025: 70c)",
        source_url="https://www.irs.gov/pub/irs-drop/n-26-10.pdf",
        verified="2026-07-12", review="annual-december",
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
    "T2125_LINE_MAP": dict(values=_T2125_LINE_MAP, year_keyed=False,
        jurisdiction="CA-federal", kind="stable_statute",
        description="QB account keyword -> T2125 Part 4 line mapping",
        source="CRA Form T2125 (Statement of Business or Professional Activities)",
        source_url="https://www.canada.ca/en/revenue-agency/services/forms-publications/forms/t2125.html",
        verified="2026-07-12", review="annual-january", sanity={}),
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
    """One-line provenance footer for tax tool outputs."""
    vintage = f"{vintage_year} tables" if vintage_year else "current tables"
    return ("\n\n---\n"
            f"*Rates: {vintage} · verified {TAX_DATA_VERIFIED} · "
            f"TAX_DATA v{TAX_DATA_VERSION} · details: qb_tax_data_info*")


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
