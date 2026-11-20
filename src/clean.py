"""
Cleaning rules - one small function per data quality issue.

Every function:
  * returns a NEW DataFrame (the input is never modified),
  * writes an entry to the QualityLog saying how many rows it touched.

The log is the evidence base for the reports: each finding has a number,
an action and the user complaint it relates to.
"""
from dataclasses import dataclass, field

import numpy as np
import pandas as pd

from src import config

C = config.COMPLAINTS  # short alias for the complaint labels (C1-C4)


# --------------------------------------------------------------------------- #
# Quality log
# --------------------------------------------------------------------------- #
@dataclass
class QualityLog:
    entries: list = field(default_factory=list)  # one dict per cleaning action

    def add(self, system, column, issue, rows_affected, action, complaint=""):
        # Record what was found, how many rows, what we did, and which complaint it relates to
        self.entries.append({
            "system": system,
            "column": column,
            "issue": issue,
            "rows_affected": int(rows_affected),
            "action": action,
            "related_complaint": complaint,
        })

    def to_frame(self) -> pd.DataFrame:
        return pd.DataFrame(self.entries)  # turn the log into a table for reports


# --------------------------------------------------------------------------- #
# Generic rules (all systems)
# --------------------------------------------------------------------------- #
def replace_null_tokens(df, system, log):
    """'XX', 'N.A.', '-', 'none', 'nan' and empty strings -> real missing value."""
    df = df.copy()  # never change the input
    for col in df.columns:
        is_token = df[col].isin(config.NULL_TOKENS) & (df[col] != "")  # placeholder text (not plain blanks)
        if is_token.any():
            log.add(system, col, "Placeholder text used instead of empty value",
                    is_token.sum(), "Converted to missing (NaN)", C["manual"])
    return df.replace(config.NULL_TOKENS, np.nan)  # every placeholder and blank becomes NaN


def to_numeric(df, system, log):
    """Convert numeric columns from text to numbers. Anything unparseable becomes NaN."""
    df = df.copy()
    for col in config.NUMERIC_COLUMNS[system]:
        before = df[col].notna().sum()                      # values present before converting
        df[col] = pd.to_numeric(df[col], errors="coerce")   # text -> number; garbage -> NaN
        lost = before - df[col].notna().sum()               # how many values were not numbers
        if lost:
            log.add(system, col, "Non-numeric value in numeric column", lost, "Converted to missing (NaN)")
    return df


def drop_missing_keys(df, system, log):
    """Rows without a project_id cannot be linked to any other system."""
    missing = df[config.KEY].isna()  # rows with no project ID
    if missing.any():
        log.add(system, config.KEY, "Missing project ID (row cannot be linked)",
                missing.sum(), "Removed after recovery attempt", C["find"])
    return df[~missing].copy()  # keep only rows that have an ID


def drop_exact_duplicates(df, system, log):
    """Remove rows that are 100 % identical copies of another row."""
    dup = df.duplicated()  # True for every repeat of an earlier identical row
    if dup.any():
        log.add(system, "(all)", "Exact duplicate rows", dup.sum(),
                "Removed duplicates, kept one copy", C["differs"])
    return df[~dup].copy()  # keep the first copy only


def resolve_conflicting_duplicates(df, system, log):
    """Same project_id but different values: keep the most complete row and log it."""
    dup_ids = df[config.KEY][df[config.KEY].duplicated()].unique()  # IDs that still appear twice
    if len(dup_ids) == 0:
        return df  # nothing to resolve (the case in this data)
    log.add(system, config.KEY, "Same ID with conflicting values", len(dup_ids),
            "Kept most complete row per ID", C["differs"])
    df = df.assign(_filled=df.notna().sum(axis=1))  # count filled fields per row
    df = df.sort_values("_filled", ascending=False).drop_duplicates(config.KEY)  # keep the fullest row per ID
    return df.drop(columns="_filled")


def fill_unknown_categories(df, system, log):
    """Missing categorical values -> explicit 'Unknown' category (no guessing)."""
    df = df.copy()
    for col in config.CATEGORICAL_COLUMNS[system]:
        n = df[col].isna().sum()  # how many text fields are empty
        if n:
            log.add(system, col, "Missing categorical value", n, "Set to 'Unknown'")
            df[col] = df[col].fillna("Unknown")  # honest label instead of a guess
    return df


def invalidate_out_of_range(df, system, log, ranges):
    """Physically implausible measurements -> missing (they are wrong, not extreme)."""
    df = df.copy()
    for col, (lo, hi) in ranges.items():
        if col not in df:
            continue  # rule does not apply to this system
        bad = df[col].notna() & ~df[col].between(lo, hi)  # values outside the plausible range
        if bad.any():
            log.add(system, col, f"Value outside plausible range [{lo}, {hi}]", bad.sum(),
                    "Set to missing", C["manual"])
            df.loc[bad, col] = np.nan  # an impossible value is treated as unknown
    return df


# --------------------------------------------------------------------------- #
# PPD - Power Plant Design
# --------------------------------------------------------------------------- #
def fix_pressure_units(df, log):
    """Ambient pressure is in bar (~1.0); values ~1000 were entered in mbar."""
    df = df.copy()
    mbar = df["ambient_press"] > config.PRESSURE_MBAR_THRESHOLD  # values > 10 must be mbar
    log.add("PPD", "ambient_press", "Mixed units: mbar instead of bar", mbar.sum(),
            "Divided by 1000 (mbar -> bar)", C["manual"])
    df.loc[mbar, "ambient_press"] = df.loc[mbar, "ambient_press"] / 1000  # convert mbar -> bar
    return df


def check_efficiency_by_plant_type(df, log):
    """Efficiency must fit the plant technology (a CCGT at 25 % is not plausible)."""
    df = df.copy()
    lo = df["plant_type"].map(lambda t: config.EFFICIENCY_RANGES.get(t, (0, 100))[0])  # lower limit per row
    hi = df["plant_type"].map(lambda t: config.EFFICIENCY_RANGES.get(t, (0, 100))[1])  # upper limit per row
    bad = df["efficiency"].notna() & ~df["efficiency"].between(lo, hi)  # outside its plant type's range
    log.add("PPD", "efficiency", "Efficiency implausible for plant type", bad.sum(),
            "Set to missing" if bad.any() else "Check passed - no action")
    df.loc[bad, "efficiency"] = np.nan
    return df


def log_fuel_type_pattern(df, log):
    """Fuel type is never filled for ST plants -> field not maintained for that type."""
    st_missing = (df["plant_type"].eq("ST") & df["fuel_type"].isna()).sum()  # ST plants without fuel
    st_total = df["plant_type"].eq("ST").sum()                               # all ST plants
    log.add("PPD", "fuel_type", f"Never recorded for ST plants ({st_missing}/{st_total})",
            st_missing, "Set to 'Unknown'; field needs an owner/definition", C["find"])
    return df  # finding only - data unchanged here


def recover_missing_ids(ppd, ct, log):
    """
    Try to give orphan PPD rows (no project_id) their ID back.

    PPD and CT describe the same plant: net output (MW), plant type and region
    always match for linked projects. An orphan gets an ID only if exactly ONE
    unused CT project matches, and that CT project matches only ONE orphan.
    """
    ppd = ppd.copy()
    orphans = ppd[ppd[config.KEY].isna()]  # design rows that lost their ID
    if orphans.empty:
        return ppd

    used = set(ppd[config.KEY].dropna())  # IDs already present in PPD cannot be reused
    candidates = (ct[~ct[config.KEY].isin(used)]  # CT projects with no design row yet
                  .drop_duplicates(config.KEY)[[config.KEY, "capacity_mw", "plant_type", "region"]])

    o = orphans.reset_index()[["index", "net_output_mw", "plant_type", "region"]]  # keep row position as "index"
    o["mw"] = o["net_output_mw"].round(1)                                         # MW rounded for safe matching
    candidates = candidates.assign(mw=candidates["capacity_mw"].round(1))
    matches = o.merge(candidates, on=["mw", "plant_type", "region"])              # same MW + type + region

    one_per_orphan = matches.groupby("index")[config.KEY].transform("nunique") == 1  # orphan has 1 candidate
    one_per_id = matches.groupby(config.KEY)["index"].transform("nunique") == 1      # candidate fits 1 orphan
    accepted = matches[one_per_orphan & one_per_id]                                  # only unique matches

    ppd[config.KEY] = ppd[config.KEY].astype(object)                       # allow writing text IDs
    ppd.loc[accepted["index"], config.KEY] = accepted[config.KEY].values   # write recovered IDs back
    log.add("PPD", config.KEY, f"Missing project ID - recovered by unique match on "
            f"MW + plant type + region ({len(accepted)}/{len(orphans)})",
            len(accepted), "ID restored", C["find"])
    return ppd


def clean_ppd(df, log, ct=None):
    # Run all PPD rules in order
    df = replace_null_tokens(df, "PPD", log)                   # placeholders -> missing
    df = to_numeric(df, "PPD", log)                            # text -> numbers
    if ct is not None:
        df = recover_missing_ids(df, ct, log)                  # give orphan rows their ID back
    df = drop_missing_keys(df, "PPD", log)                     # drop rows still without ID
    df = drop_exact_duplicates(df, "PPD", log)                 # remove copies
    df = resolve_conflicting_duplicates(df, "PPD", log)        # one row per ID
    df = fix_pressure_units(df, log)                           # mbar -> bar
    df = invalidate_out_of_range(df, "PPD", log, config.VALID_RANGES)  # impossible values -> missing
    df = check_efficiency_by_plant_type(df, log)               # efficiency must fit plant type
    df = log_fuel_type_pattern(df, log)                        # record the fuel-type finding
    df = fill_unknown_categories(df, "PPD", log)               # empty text -> "Unknown"
    return df.reset_index(drop=True)


# --------------------------------------------------------------------------- #
# CT - Costing Tool
# --------------------------------------------------------------------------- #
def fill_structural_zero_costs(df, log):
    """
    An ST plant has no gas turbine and an SCGT plant has no steam turbine, so
    those costs are 0, not 'missing'. Only costs that SHOULD exist stay missing.
    """
    df = df.copy()
    for plant_type, cols in config.STRUCTURAL_ZERO_COSTS.items():
        for col in cols:
            mask = df["plant_type"].eq(plant_type) & df[col].isna()  # empty cost for a turbine that doesn't exist
            log.add("CT", col, f"Empty cost for component that a {plant_type} plant does not have",
                    mask.sum(), "Set to 0 (structural zero, not missing)")
            df.loc[mask, col] = 0.0  # no turbine -> cost is zero
    for col in config.COST_COLUMNS:
        n = df[col].isna().sum()  # costs still empty = genuinely missing
        if n:
            log.add("CT", col, "Cost genuinely missing (component exists)", n,
                    "Kept missing, flagged; imputed only inside ML pipeline", C["manual"])
            df[f"{col}_missing"] = df[col].isna().astype(int)  # 1 = this cost was missing
    return df


def flag_bid_to_cost(df, log):
    """Bid should exceed estimated cost; extreme ratios point to entry errors."""
    df = df.copy()
    cost_total = df[config.COST_COLUMNS].sum(axis=1, min_count=1)  # sum of the 4 cost components
    ratio = df["bid_value_meur"] / cost_total                       # bid / cost = implied margin
    complete = df[config.COST_COLUMNS].notna().all(axis=1)          # only judge rows with all costs
    lo, hi = config.BID_TO_COST_RANGE
    bad = complete & ~ratio.between(lo, hi)                         # below cost or absurd margin
    df["flag_bid_to_cost"] = bad.astype(int)                        # flag only, values kept
    log.add("CT", "bid_value_meur", f"Bid / cost ratio outside [{lo}, {hi}]", bad.sum(),
            "Flagged for review (kept)", C["differs"])
    return df


def log_capped_values(df, log):
    """Many values sit exactly on a round maximum -> likely capped/defaulted entries."""
    for col in config.COST_COLUMNS + ["bid_value_meur"]:
        mx = df[col].max()          # highest value in the column
        n = (df[col] == mx).sum()   # how many rows sit exactly on it
        if n >= 5:                  # 5+ identical maximums looks like a cap/default
            log.add("CT", col, f"{n} rows exactly at maximum value {mx:g} (possible cap/default)",
                    n, "Kept; flagged as finding for source owner")
    return df  # finding only - data unchanged


def clean_ct(df, log):
    # Run all CT rules in order
    df = replace_null_tokens(df, "CT", log)              # placeholders -> missing
    df = to_numeric(df, "CT", log)                       # text -> numbers
    df = drop_missing_keys(df, "CT", log)                # rows without ID
    df = drop_exact_duplicates(df, "CT", log)            # remove copies
    df = resolve_conflicting_duplicates(df, "CT", log)   # one row per ID
    df = fill_structural_zero_costs(df, log)             # no turbine -> cost 0
    df = log_capped_values(df, log)                      # record capped values
    df = flag_bid_to_cost(df, log)                       # flag odd margins
    df = fill_unknown_categories(df, "CT", log)          # empty text -> "Unknown"
    return df.reset_index(drop=True)


# --------------------------------------------------------------------------- #
# MG - Management Tool
# --------------------------------------------------------------------------- #
def parse_mixed_dates(series: pd.Series) -> pd.Series:
    """Parse every accepted format explicitly; never let pandas guess day vs month."""
    result = pd.Series(pd.NaT, index=series.index)  # start with all dates empty
    for fmt in config.DATE_FORMATS:
        parsed = pd.to_datetime(series, format=fmt, errors="coerce")  # try one exact format
        result = result.fillna(parsed)                                 # fill dates this format understood
    return result


def clean_handover_date(df, log):
    df = df.copy()
    raw = df["handover_date"]
    for fmt, label in zip(config.DATE_FORMATS, ["dd.mm.yyyy", "yyyy-mm-dd"]):
        n = pd.to_datetime(raw, format=fmt, errors="coerce").notna().sum()  # count dates in each format
        log.add("MG", "handover_date", f"Date format {label}", n, "Parsed to one date type", C["manual"])
    df["handover_date"] = parse_mixed_dates(raw)                     # one proper date type
    unparsed = raw.notna() & df["handover_date"].isna()              # text that matched no format
    if unparsed.any():
        log.add("MG", "handover_date", "Unparseable date", unparsed.sum(), "Set to missing")
    log.add("MG", "handover_date", "Handover date not filled", df["handover_date"].isna().sum(),
            "Kept missing + flag column")
    return df


def add_region_from_country(df, log):
    df = df.copy()
    df["region"] = df["country"].map(config.COUNTRY_TO_REGION)  # e.g. Germany -> EU
    unmapped = df["region"].isna() & df["country"].notna()       # countries missing from the map
    if unmapped.any():
        log.add("MG", "country", "Country without region mapping", unmapped.sum(), "Region left missing")
    return df


def clean_mg(df, log):
    # Run all MG rules in order
    df = replace_null_tokens(df, "MG", log)              # placeholders -> missing
    df = to_numeric(df, "MG", log)                       # text -> numbers
    df = drop_missing_keys(df, "MG", log)                # rows without ID
    df = drop_exact_duplicates(df, "MG", log)            # remove copies
    df = resolve_conflicting_duplicates(df, "MG", log)   # one row per ID
    df = clean_handover_date(df, log)                    # two date formats -> one
    df = add_region_from_country(df, log)                # add region for comparison with PPD/CT
    df = fill_unknown_categories(df, "MG", log)          # empty text -> "Unknown"
    df["win_loss"] = df["win_loss"].astype("Int64")      # target as whole number (0/1)
    return df.reset_index(drop=True)


# --------------------------------------------------------------------------- #
def clean_all(raw: dict[str, pd.DataFrame]) -> tuple[dict[str, pd.DataFrame], QualityLog]:
    """Clean all three systems. CT is cleaned first because PPD ID recovery uses it."""
    log = QualityLog()                            # one shared log for all findings
    ct = clean_ct(raw["CT"], log)
    ppd = clean_ppd(raw["PPD"], log, ct=ct)       # needs clean CT for ID recovery
    mg = clean_mg(raw["MG"], log)
    return {"PPD": ppd, "CT": ct, "MG": mg}, log
