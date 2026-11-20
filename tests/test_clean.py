"""
Unit tests for the cleaning rules, using tiny hand-made examples.
Run:  python -m pytest -q
"""
import numpy as np
import pandas as pd

from src import clean
from src.clean import QualityLog


def test_placeholders_become_missing():
    df = pd.DataFrame({"project_id": ["ID1"] * 6, "x": ["XX", "N.A.", "-", "none", "nan", "5"]})
    out = clean.replace_null_tokens(df, "T", QualityLog())
    assert out["x"].isna().sum() == 5
    assert out["x"].iloc[5] == "5"


def test_pressure_mbar_converted_to_bar():
    df = pd.DataFrame({"ambient_press": [1013.0, 1.01, np.nan]})
    out = clean.fix_pressure_units(df, QualityLog())
    assert out["ambient_press"].iloc[0] == 1.013
    assert out["ambient_press"].iloc[1] == 1.01      # already in bar -> unchanged
    assert np.isnan(out["ambient_press"].iloc[2])


def test_both_date_formats_parse_to_same_date():
    s = pd.Series(["21.11.2022", "2022-11-21", None])
    out = clean.parse_mixed_dates(s)
    assert out.iloc[0] == out.iloc[1] == pd.Timestamp("2022-11-21")
    assert pd.isna(out.iloc[2])


def test_day_and_month_are_not_swapped():
    out = clean.parse_mixed_dates(pd.Series(["03.04.2024"]))
    assert out.iloc[0] == pd.Timestamp("2024-04-03")   # 3 April, not 4 March


def test_structural_zero_costs():
    df = pd.DataFrame({
        "plant_type": ["ST", "SCGT", "CCGT"],
        "cost_gt": [np.nan, 150.0, np.nan],
        "cost_st": [80.0, np.nan, np.nan],
        "cost_auxiliaries": [10.0, 10.0, 10.0],
        "cost_installation": [10.0, 10.0, 10.0],
    })
    out = clean.fill_structural_zero_costs(df, QualityLog())
    assert out.loc[0, "cost_gt"] == 0      # steam plant has no gas turbine
    assert out.loc[1, "cost_st"] == 0      # single-cycle has no steam turbine
    assert np.isnan(out.loc[2, "cost_gt"])  # combined-cycle SHOULD have both -> stays missing
    assert np.isnan(out.loc[2, "cost_st"])


def test_exact_duplicates_removed():
    df = pd.DataFrame({"project_id": ["A", "A", "B"], "v": [1, 1, 2]})
    out = clean.drop_exact_duplicates(df, "T", QualityLog())
    assert len(out) == 2


def test_conflicting_duplicates_keep_most_complete_row():
    df = pd.DataFrame({"project_id": ["A", "A"], "v": [np.nan, 5.0], "w": [1.0, 1.0]})
    log = QualityLog()
    out = clean.resolve_conflicting_duplicates(df, "T", log)
    assert len(out) == 1 and out["v"].iloc[0] == 5.0
    assert log.entries[0]["rows_affected"] == 1


def test_id_recovery_only_accepts_unique_match():
    ppd = pd.DataFrame({
        "project_id": [np.nan, np.nan, np.nan],
        "net_output_mw": [100.0, 200.0, 200.0],
        "plant_type": ["CCGT", "ST", "ST"],
        "region": ["EU", "AM", "AM"],
    })
    ct = pd.DataFrame({
        "project_id": ["ID1", "ID2"],
        "capacity_mw": [100.0, 200.0],
        "plant_type": ["CCGT", "ST"],
        "region": ["EU", "AM"],
    })
    out = clean.recover_missing_ids(ppd, ct, QualityLog())
    assert out.loc[0, "project_id"] == "ID1"     # unique match -> recovered
    assert out.loc[1:, "project_id"].isna().all()  # two orphans claim ID2 -> ambiguous, not guessed
