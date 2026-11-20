"""
Turn the Bid 360 table into model-ready features.

Rule: only use information that is known AT BID TIME. Anything that is only
known after the customer decides would be "data leakage" (the model would be
cheating and fail on real future bids).
"""
import numpy as np
import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.impute import SimpleImputer
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler

from src import config

TARGET = "win_loss"  # what we predict: 1 = won, 0 = lost

NUMERIC_FEATURES = [
    # technical design (PPD)
    "net_output_mw", "efficiency", "ambient_temp", "ambient_press", "ambient_humidity",
    # cost estimate (CT)
    "cost_gt", "cost_st", "cost_auxiliaries", "cost_installation", "bid_value_meur",
    # engineered
    "cost_total", "bid_to_cost_ratio", "bid_per_mw",
    "share_gt", "share_st", "share_auxiliaries", "share_installation",
    "handover_year", "has_handover_date",
]
CATEGORICAL_FEATURES = [
    "plant_type", "region", "country", "customer", "fuel_type", "cooling_type", "cooling_water_type",
]

# Columns deliberately NOT used, and why (documented for the report).
EXCLUDED = {
    "project_id": "Identifier - carries no business meaning",
    "handover_date": "Replaced by handover_year + has_handover_date",
    "in_ppd / in_ct": "Describe system coverage, not the bid itself",
    "*_missing / flag_*": "Data quality flags - imputer adds its own missing indicators",
}


def engineer_features(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    costs = df[config.COST_COLUMNS]
    df["cost_total"] = costs.sum(axis=1, min_count=len(config.COST_COLUMNS))  # total cost (only if all 4 known)
    df["bid_to_cost_ratio"] = df["bid_value_meur"] / df["cost_total"]      # implied margin
    df["bid_per_mw"] = df["bid_value_meur"] / df["net_output_mw"]          # price competitiveness
    for col in config.COST_COLUMNS:
        df[col.replace("cost_", "share_")] = df[col] / df["cost_total"]    # cost structure
    df["handover_year"] = df["handover_date"].dt.year                      # date -> number the model can use
    df["has_handover_date"] = df["handover_date"].notna().astype(int)      # 1 = date was planned
    return df.replace([np.inf, -np.inf], np.nan)                           # division by 0 -> missing


def get_xy(bid_360: pd.DataFrame) -> tuple[pd.DataFrame, pd.Series]:
    df = engineer_features(bid_360)
    df = df[df[TARGET].notna()]                       # only bids with a known outcome
    X = df[NUMERIC_FEATURES + CATEGORICAL_FEATURES]   # inputs
    y = df[TARGET].astype(int)                        # answer to learn
    return X, y


def build_preprocessor() -> ColumnTransformer:
    """
    Numbers:     fill gaps with the median (+ a 'was missing' indicator), then scale.
    Categories:  fill gaps with 'Unknown', then one-hot encode.
    Fitted on training data only (inside the model pipeline) -> no leakage.
    """
    numeric = Pipeline([
        ("impute", SimpleImputer(strategy="median", add_indicator=True)),  # gap -> median, add "was missing" column
        ("scale", StandardScaler()),                                        # same scale for all numbers
    ])
    categorical = Pipeline([
        ("impute", SimpleImputer(strategy="constant", fill_value="Unknown")),  # gap -> "Unknown"
        ("onehot", OneHotEncoder(handle_unknown="ignore")),                     # category -> 0/1 columns; new values ignored
    ])
    return ColumnTransformer([
        ("num", numeric, NUMERIC_FEATURES),          # apply numeric steps to number columns
        ("cat", categorical, CATEGORICAL_FEATURES),  # apply category steps to text columns
    ])
