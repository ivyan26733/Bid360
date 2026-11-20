"""
Run the whole pipeline end to end:

    load -> clean -> quality report -> integrate (Bid 360) -> features -> train

Usage:  python run_pipeline.py
"""
import pandas as pd

from src import config, integrate, quality, train
from src.clean import clean_all
from src.features import get_xy
from src.load import load_all
from src.validate import simulate_id_recovery


def print_key_numbers(log, coverage, consistency, bid_360, sim):
    """Print every number used in the presentation and reports, with where it comes from."""
    def rows(system, issue_starts):  # rows_affected for one log entry
        m = log[(log.system == system) & log.issue.str.startswith(issue_starts)]
        return int(m.rows_affected.sum())

    all_three = int((coverage.systems == "PPD + CT + MG").sum())
    print("\n=== KEY NUMBERS (used in slides and reports) ===")
    print(f"  Duplicate records     : {rows('CT', 'Exact duplicate') + rows('MG', 'Exact duplicate')}"
          f"  (CT {rows('CT', 'Exact duplicate')} + MG {rows('MG', 'Exact duplicate')})")
    print(f"  Unit errors (mbar)    : {rows('PPD', 'Mixed units')}")
    print(f"  PPD rows without ID   : {rows('PPD', 'Missing project ID - recovered') + rows('PPD', 'Missing project ID (row')}"
          f"  (recovered {rows('PPD', 'Missing project ID - recovered')}, removed {rows('PPD', 'Missing project ID (row')})")
    print(f"  ID recovery test      : {sim['hidden']} IDs hidden, {sim['recovered']} recovered, {sim['correct']} correct")
    print(f"  Date formats          : dd.mm.yyyy {rows('MG', 'Date format dd')}, yyyy-mm-dd {rows('MG', 'Date format yyyy')}")
    print(f"  Columns with placeholders: {int(log.issue.str.startswith('Placeholder').sum())}")
    print(f"  Fuel type missing for ST : {rows('PPD', 'Never recorded for ST')}")
    print(f"  Projects total        : {len(coverage)}")
    print(f"  In all three systems  : {all_three} ({all_three / len(coverage):.0%})")
    print(f"  Missing from >=1 system: {len(coverage) - all_three} ({(len(coverage) - all_three) / len(coverage):.0%})")
    print(f"  Shared fields agree   : {consistency.mismatches.sum()} mismatches in {consistency.compared.sum()} comparisons")
    print(f"  Overall win rate      : {bid_360.win_loss.mean():.1%}")
    won = bid_360[bid_360.win_loss == 1].handover_date.notna().mean()
    lost = bid_360[bid_360.win_loss == 0].handover_date.notna().mean()
    print(f"  Leakage check         : handover date filled for {won:.0%} of won and {lost:.0%} of lost bids")


def main():
    out = config.PROCESSED_DIR
    out.mkdir(parents=True, exist_ok=True)  # make sure the output folder exists

    print("1/5 Loading raw data ...")
    raw = load_all()  # read the 3 CSVs as text, one project_id name

    print("2/5 Cleaning ...")
    clean, log = clean_all(raw)  # apply all cleaning rules, collect the log
    for system, df in clean.items():
        df.to_csv(out / f"{system.lower()}_clean.csv", index=False)  # save cleaned data per system

    print("3/5 Measuring data quality ...")
    log.to_frame().to_csv(out / "quality_log.csv", index=False)                    # every rule + rows affected
    quality.profile_all(raw).to_csv(out / "quality_profile_raw.csv", index=False)  # raw column profile
    scorecard = quality.build_scorecard(raw, clean)                                # before vs after
    scorecard.to_csv(out / "quality_scorecard.csv", index=False)

    print("4/5 Integrating systems into Bid 360 ...")
    coverage = integrate.coverage_report(clean)        # which project is in which system
    coverage.to_csv(out / "coverage.csv", index=False)
    consistency = integrate.check_consistency(clean)   # do shared fields agree?
    consistency.to_csv(out / "consistency.csv", index=False)
    bid_360 = integrate.build_bid_360(clean)           # one row per project
    bid_360.to_csv(out / "bid_360.csv", index=False)

    print("5/5 Training win/loss models ...")
    X, y = get_xy(bid_360)   # features + target
    result = train.run(X, y)  # compare models, test, explain, save

    sim = simulate_id_recovery(raw["PPD"], clean["CT"])  # is the ID recovery rule reliable?
    pd.Series(sim).to_json(out / "id_recovery_check.json")  # saved so the report can read it
    print_key_numbers(log.to_frame(), coverage, consistency, bid_360, sim)  # numbers used in the slides

    # print a short summary to the screen
    pd.set_option("display.width", 200)
    print("\n=== Data quality scorecard ===\n", scorecard.to_string(index=False))
    print("\n=== Coverage ===\n", coverage["systems"].value_counts().to_string())
    print("\n=== Cross-validation (train set) ===\n",
          result["cv"][["model", "roc_auc", "roc_auc_std", "accuracy", "f1"]].to_string(index=False))
    print(f"\n=== Test set ({result['best']} selected) ===")
    for name, res in result["test"].items():
        print(f"  {name:20s} {res}")
    print("\n=== Top drivers ===\n", result["importance"].head(10).to_string(index=False))
    print(f"\nOutputs written to {out}")


if __name__ == "__main__":
    main()
