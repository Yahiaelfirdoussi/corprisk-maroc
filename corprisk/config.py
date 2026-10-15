"""Central configuration: paths, thresholds and risk tables.

All thresholds mirror the MOCK policies in /policies. When you adapt this to your
bank, change the numbers here AND in the policy documents so they stay consistent.
"""
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "data"
POLICY_DIR = ROOT / "policies"
REPORT_DIR = ROOT / "reports"

# --- Transaction monitoring (POL-AML-02) -----------------------------------
CASH_THRESHOLD_MAD = 100_000
STRUCTURING_LOWER_MAD = 90_000
STRUCTURING_MIN_COUNT = 3          # deposits within the window
STRUCTURING_WINDOW_DAYS = 30
CASH_INTENSITY_MAX = 0.30          # cash deposits / declared revenue
TURNOVER_MAX_RATIO = 1.50          # total credits / declared revenue
PASS_THROUGH_DAYS = 3
PASS_THROUGH_MIN_SHARE = 0.90
ROUND_AMOUNT_UNIT = 50_000
ROUND_AMOUNT_MAX_SHARE = 0.40

# Countries subject to a FATF call for action (update from the latest FATF publication)
FATF_CALL_FOR_ACTION = {"KP": "North Korea", "IR": "Iran", "MM": "Myanmar"}
# Bank's internal list of high-secrecy jurisdictions (illustrative)
HIGH_SECRECY = {"VG": "British Virgin Islands", "PA": "Panama", "SC": "Seychelles", "KY": "Cayman Islands"}

# --- KYC (POL-KYC-01) --------------------------------------------------------
UBO_THRESHOLD_PCT = 25
NEW_COMPANY_MONTHS = 24
LARGE_REQUEST_MAD = 5_000_000
SECTOR_RISK = {  # inherent sector risk -> points
    "real_estate": ("High", 10),
    "general_trading": ("High", 10),
    "money_exchange": ("High", 10),
    "logistics": ("Medium", 5),
    "construction": ("Medium", 5),
    "agriculture_export": ("Low", 0),
    "manufacturing": ("Low", 0),
}

# --- Credit (POL-CRD-04) -----------------------------------------------------
MAX_DEBT_TO_EQUITY = 3.0
MIN_CURRENT_RATIO = 1.0
MIN_DSCR = 1.5
UNUSUAL_GROWTH = 1.0               # +100% revenue in one year
MAX_EXPOSURE_TO_REVENUE = 0.50

# --- Screening (POL-SAN-03) --------------------------------------------------
PROBABLE_MATCH = 0.90
POTENTIAL_MATCH = 0.80
PEP_LOOKBACK_YEARS = 5

# --- Scoring -----------------------------------------------------------------
SEVERITY_POINTS = {"info": 0, "low": 3, "medium": 8, "high": 15, "critical": 40}
CATEGORY_CAPS = {"screening": 40, "kyc": 25, "transactions": 30, "financial": 20, "inherent": 15}
RISK_LEVELS = [(60, "High"), (35, "Medium"), (0, "Low")]

AS_OF_DATE = "2026-10-14"  # analysis date (fixed so the demo is reproducible)
