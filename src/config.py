"""
Central configuration: file paths and business rules.

No logic lives here - only settings. If a rule changes (e.g. a new placeholder
value appears in the source data), it is changed in exactly one place.
"""
from pathlib import Path

# --- Paths -------------------------------------------------------------------
ROOT = Path(__file__).resolve().parent.parent
RAW_DIR = ROOT / "data" / "raw"
PROCESSED_DIR = ROOT / "data" / "processed"
FIGURES_DIR = ROOT / "reports" / "figures"

RAW_FILES = {
    "PPD": RAW_DIR / "PPD_data.csv",  # Power Plant Design tool
    "CT": RAW_DIR / "CT_data.csv",    # Costing Tool
    "MG": RAW_DIR / "MG_data.csv",    # Management Tool
}

# --- Identifiers -------------------------------------------------------------
# The same project key has a different name in every system.
ID_COLUMNS = {"PPD": "Project_ID", "CT": "ID", "MG": "Opportunity_ID"}
KEY = "project_id"

# --- Missing values ----------------------------------------------------------
# Placeholders typed by users instead of leaving a field empty.
NULL_TOKENS = ["XX", "N.A.", "-", "none", "nan", ""]

# --- Column types ------------------------------------------------------------
NUMERIC_COLUMNS = {
    "PPD": ["net_output_mw", "efficiency", "ambient_temp", "ambient_press", "ambient_humidity"],
    "CT": ["capacity_mw", "cost_gt", "cost_st", "cost_auxiliaries", "cost_installation", "bid_value_meur"],
    "MG": ["output_mw", "bid_value_meur", "win_loss"],
}
CATEGORICAL_COLUMNS = {
    "PPD": ["plant_type", "region", "fuel_type", "cooling_type", "cooling_water_type"],
    "CT": ["customer", "region", "plant_type"],
    "MG": ["customer", "country"],
}

# Consistent column names across systems (raw name -> standard name).
COLUMN_RENAMES = {
    "PPD": {"Region_of_Installation": "region"},
    "CT": {},
    "MG": {"Output": "output_mw"},
}

# --- Domain rules ------------------------------------------------------------
COST_COLUMNS = ["cost_gt", "cost_st", "cost_auxiliaries", "cost_installation"]

# A plant type that physically has no gas / steam turbine has a cost of 0,
# not a "missing" cost.
STRUCTURAL_ZERO_COSTS = {
    "ST": ["cost_gt"],     # steam plant: no gas turbine
    "SCGT": ["cost_st"],   # single-cycle gas plant: no steam turbine
}

# Ambient pressure must be in bar. Values above this are assumed to be mbar.
PRESSURE_MBAR_THRESHOLD = 10

# Plausible ranges (min, max). Values outside are flagged, not deleted.
VALID_RANGES = {
    "ambient_temp": (-50, 60),
    "ambient_press": (0.8, 1.2),       # bar
    "ambient_humidity": (0.1, 100),    # exactly 0 % relative humidity is physically implausible
    "net_output_mw": (1, 2000),
}
EFFICIENCY_RANGES = {  # typical net efficiency (%) by plant type
    "CCGT": (45, 65),
    "SCGT": (20, 45),
    "ST": (20, 45),
}

# Business rule: bids are expected to be above cost but not absurdly so.
BID_TO_COST_RANGE = (1.0, 4.0)

# MG stores country, PPD/CT store region.
COUNTRY_TO_REGION = {
    "Germany": "EU", "Spain": "EU", "France": "EU", "Italy": "EU", "Netherlands": "EU",
    "United States": "AM", "Canada": "AM", "Mexico": "AM", "Brazil": "AM", "Chile": "AM",
    "India": "APAC", "Indonesia": "APAC", "Japan": "APAC", "Australia": "APAC", "Thailand": "APAC",
}

# Accepted date formats in MG.Handover_date (parsed explicitly, never guessed).
DATE_FORMATS = ["%d.%m.%Y", "%Y-%m-%d"]

# Which user complaint (Task 1) each kind of issue relates to.
COMPLAINTS = {
    "find": "C1: Cannot find data / no overview",
    "differs": "C2: Data differs across systems",
    "salesforce": "C3: Salesforce data outdated/incorrect",
    "manual": "C4: Manual entry into multiple applications",
}

RANDOM_STATE = 42
