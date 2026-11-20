"""
Load the raw CSV exports and give them consistent column names.

Everything is read as text first, so pandas cannot silently guess types or
turn placeholders like "N.A." into something else. Type conversion happens
explicitly in clean.py.
"""
import pandas as pd

from src import config


def load_raw(system: str) -> pd.DataFrame:
    """Read one system's CSV exactly as it is (all values as text)."""
    # dtype=str: read everything as text; keep_default_na=False: don't auto-convert "N.A." etc.
    return pd.read_csv(config.RAW_FILES[system], dtype=str, keep_default_na=False)


def standardise_columns(df: pd.DataFrame, system: str) -> pd.DataFrame:
    """Rename the system-specific ID to `project_id` and use lower_snake_case names."""
    df = df.rename(columns={config.ID_COLUMNS[system]: config.KEY})  # Project_ID / ID / Opportunity_ID -> project_id
    df = df.rename(columns=config.COLUMN_RENAMES[system])            # align other names (e.g. Output -> output_mw)
    df.columns = [c.lower() for c in df.columns]                     # consistent lowercase names
    return df


def load_all() -> dict[str, pd.DataFrame]:
    """Load PPD, CT and MG with standardised column names."""
    return {system: standardise_columns(load_raw(system), system) for system in config.RAW_FILES}
