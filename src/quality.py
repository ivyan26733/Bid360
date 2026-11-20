"""
Measure data quality - per column and as a simple before/after scorecard.

Three dimensions (the classic data quality dimensions used in governance):
  * Completeness: share of cells that hold a real value
  * Uniqueness:   share of rows whose project_id appears only once
  * Linkability:  share of rows that have a project_id at all
"""
import numpy as np
import pandas as pd

from src import config


def profile(df: pd.DataFrame, system: str) -> pd.DataFrame:
    """One row per column: missing %, distinct values, example placeholder values."""
    rows = []
    for col in df.columns:
        s = df[col]
        # placeholder values found in this column (text columns only)
        tokens = s[s.isin(config.NULL_TOKENS) & (s != "")] if s.dtype == object else pd.Series(dtype=object)
        # truly empty cells
        empty = s.isna() | (s == "") if s.dtype == object else s.isna()
        rows.append({
            "system": system,
            "column": col,
            "missing_pct": round(100 * (empty.sum() + len(tokens)) / len(s), 1),  # empty + placeholder share
            "placeholders": ", ".join(sorted(tokens.unique())),                  # which placeholders appear
            "distinct": s.nunique(),                                             # number of different values
        })
    return pd.DataFrame(rows)


def _as_missing(df: pd.DataFrame) -> pd.DataFrame:
    """Treat placeholders and the 'Unknown' category as missing for scoring."""
    return df.replace(config.NULL_TOKENS + ["Unknown"], np.nan)


def scorecard(df: pd.DataFrame, system: str, stage: str) -> dict:
    # ignore helper columns we added ourselves (flags), then treat placeholders as missing
    data = _as_missing(df.drop(columns=[c for c in df.columns if c.endswith("_missing") or c.startswith("flag_")]))
    ids = data[config.KEY]
    return {
        "system": system,
        "stage": stage,                                                          # "before" or "after" cleaning
        "rows": len(data),
        "completeness_pct": round(100 * data.notna().mean().mean(), 1),          # share of filled cells
        "uniqueness_pct": round(100 * (~ids.dropna().duplicated(keep=False)).mean(), 1),  # IDs appearing once
        "linkability_pct": round(100 * ids.notna().mean(), 1),                   # rows that have an ID
    }


def build_scorecard(raw: dict, clean: dict) -> pd.DataFrame:
    rows = []
    for system in raw:
        rows.append(scorecard(raw[system], system, "before"))   # quality of the raw export
        rows.append(scorecard(clean[system], system, "after"))  # quality after cleaning
    return pd.DataFrame(rows)


def profile_all(raw: dict) -> pd.DataFrame:
    return pd.concat([profile(df, s) for s, df in raw.items()], ignore_index=True)  # profile all 3 systems
