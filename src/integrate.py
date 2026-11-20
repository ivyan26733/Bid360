"""
Bring the three systems together into one view per project: "Bid 360".

This is a small, local version of the data product proposed in Task 1.
Where the same attribute exists in several systems, ONE system is the
"golden source" for it (see GOLDEN_SOURCE) - that is the governance rule.
"""
import pandas as pd

from src import config

# Which system owns which attribute.
GOLDEN_SOURCE = {
    "customer": "MG",         # commercial master data (originates in Salesforce)
    "country": "MG",
    "region": "PPD",          # site of installation
    "plant_type": "PPD",      # technical design
    "net_output_mw": "PPD",
    "bid_value_meur": "CT",   # calculated by the costing tool
    "win_loss": "MG",
}

# Attributes that are stored in more than one system: (system A col, system B col).
SHARED_ATTRIBUTES = [
    ("customer", ("CT", "customer"), ("MG", "customer")),
    ("bid_value_meur", ("CT", "bid_value_meur"), ("MG", "bid_value_meur")),
    ("plant_type", ("PPD", "plant_type"), ("CT", "plant_type")),
    ("region", ("PPD", "region"), ("CT", "region")),
    ("region", ("CT", "region"), ("MG", "region")),
    ("net_output_mw", ("PPD", "net_output_mw"), ("CT", "capacity_mw")),
    ("net_output_mw", ("CT", "capacity_mw"), ("MG", "output_mw")),
]


def coverage_report(data: dict) -> pd.DataFrame:
    """In which combination of systems does each project exist?"""
    ids = {s: set(df[config.KEY]) for s, df in data.items()}  # project IDs per system
    all_ids = set().union(*ids.values())                       # every project seen anywhere
    rows = [{config.KEY: i, **{f"in_{s.lower()}": i in ids[s] for s in ids}} for i in all_ids]  # True/False per system
    cov = pd.DataFrame(rows)
    cov["systems"] = cov[[f"in_{s.lower()}" for s in ids]].apply(               # e.g. "PPD + CT + MG"
        lambda r: " + ".join(s for s, flag in zip(ids, r) if flag), axis=1)
    return cov


def check_consistency(data: dict) -> pd.DataFrame:
    """Compare every attribute that is stored twice. Mismatch = 'data differs'."""
    rows = []
    for attr, (sa, ca), (sb, cb) in SHARED_ATTRIBUTES:
        a = data[sa][[config.KEY, ca]].rename(columns={ca: "a"})   # value in system A
        b = data[sb][[config.KEY, cb]].rename(columns={cb: "b"})   # value in system B
        m = a.merge(b, on=config.KEY).dropna()                      # projects present in both
        m = m[(m["a"] != "Unknown") & (m["b"] != "Unknown")]        # skip unknown labels
        if pd.api.types.is_numeric_dtype(m["a"]):
            diff = (m["a"] - m["b"]).abs() > 0.05                   # numbers: allow tiny rounding
        else:
            diff = m["a"] != m["b"]                                 # text: must be identical
        rows.append({"attribute": attr, "systems": f"{sa} vs {sb}",
                     "compared": len(m), "mismatches": int(diff.sum()),
                     "match_pct": round(100 * (1 - diff.mean()), 1) if len(m) else None})
    return pd.DataFrame(rows)


def build_bid_360(data: dict) -> pd.DataFrame:
    """
    One row per project. MG is the spine because it holds the outcome (win_loss).
    PPD and CT are left-joined; flags show which systems had the project.
    """
    # rename overlapping columns so the joins don't clash
    mg = data["MG"].rename(columns={"region": "region_mg", "bid_value_meur": "bid_value_mg"})
    ppd = data["PPD"].assign(in_ppd=1)
    ct = (data["CT"].drop(columns=["customer"])  # customer comes from MG (golden source)
          .rename(columns={"region": "region_ct", "plant_type": "plant_type_ct"})
          .assign(in_ct=1))

    df = mg.merge(ppd, on=config.KEY, how="left").merge(ct, on=config.KEY, how="left")  # MG + design + cost
    df[["in_ppd", "in_ct"]] = df[["in_ppd", "in_ct"]].fillna(0).astype(int)           # 1 = found in that system

    # Golden-source fields, falling back to the other system when the owner has no record.
    df["plant_type"] = df["plant_type"].fillna(df["plant_type_ct"])
    df["region"] = df["region"].fillna(df["region_ct"]).fillna(df["region_mg"])
    df["net_output_mw"] = df["net_output_mw"].fillna(df["capacity_mw"]).fillna(df["output_mw"])
    df["bid_value_meur"] = df["bid_value_meur"].fillna(df["bid_value_mg"])

    # drop the now-redundant duplicate columns
    df = df.drop(columns=["plant_type_ct", "region_ct", "region_mg", "capacity_mw",
                          "output_mw", "bid_value_mg"])
    return df.sort_values(config.KEY).reset_index(drop=True)
