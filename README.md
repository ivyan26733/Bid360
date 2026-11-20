# Bid Intelligence – Case Study

A data and AI case study for a power plant **Bid Management** organisation.

- **Task 1:** what is wrong with today's data landscape, and which *data product* fixes it?
- **Task 2:** clean and analyse the data from three tools, model it, and predict whether a bid will be won.

📄 Reports: [Task 1 – Concept](reports/Task1_Concept.md) · [Task 2 – Analysis](reports/Task2_Analysis.md)

---

## 1. The story in one minute

**The business:** the company prepares bids (price offers) for big power plants. A bid passes through several tools:

```
Customer documents → CRA (requirements) → PPD (plant design) → EXCEL (manual!) → CT (cost) → Offer
Salesforce (sales) → MG (project management) ↔ Snowflake (data warehouse, only part of MG)
```

**The problem:** data is copied by hand through Excel, each tool names the project ID differently, and nothing is checked. Users complain that they **can't find data**, **numbers differ**, **Salesforce data is wrong**, and **they type the same thing twice**.

**What I did:**
1. **Proved the problems with data.** I found 7 data quality issues in the three exports and fixed each one with a tested rule.
2. **Joined the three tools** into one table per project, called **"Bid 360"**.
3. **Designed a data model** showing which tool owns which data.
4. **Built a model** that predicts the chance of winning a bid and explains why.
5. **Proposed the "Bid 360" data product** in Snowflake to fix the root causes (Task 1).

**One sentence:** *the complaints in Task 1 are visible in the data of Task 2, so the fix is one governed data product, and the ML model shows the value it unlocks.*

---

## 2. Key results

| What | Result |
|---|---|
| Data quality issues found and fixed | 7 (duplicates, unit mix-up, placeholders, missing IDs, date formats, ...) |
| Records unique and linkable after cleaning | 100 % in all three tools |
| Lost project IDs recovered | 91 of 94 (method tested: 100 % correct) |
| Projects in all three tools | 1,699 of 2,000 (85 %) |
| Best model | Logistic Regression, ROC-AUC **0.72** (cross-validation) / **0.79** (test) |
| What drives a win | Plant efficiency, customer, country/region, plant size, price |

---

## 3. How to run it

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

python run_pipeline.py                     # runs everything (~30 s), writes results to data/processed/
python -m pytest -q                        # runs the 8 unit tests
python reports/diagrams/draw_diagrams.py   # redraws the diagrams
jupyter notebook notebooks/                # opens the notebooks with charts and explanations
```

---

## 4. Folder map: what is where

```
bid-intelligence/
├── run_pipeline.py        ← ONE command that runs everything, in order
├── data/
│   ├── raw/               ← the 3 original CSVs (never changed)
│   └── processed/         ← everything the code produces (clean data, Bid 360, quality log, model results)
├── src/                   ← the actual logic, one file per step
├── notebooks/             ← the "story" with charts (uses src/, no duplicate logic)
├── tests/                 ← small tests that prove the cleaning rules work
└── reports/               ← the two reports, charts (figures/) and diagrams
```

### What each file in `src/` does

The files run in this order: **load → clean → quality → integrate → features → train**.

| File | What it does | Why |
|---|---|---|
| `config.py` | All settings and rules: file paths, placeholder list, valid ranges, country→region map | Change a rule in one place, not in ten |
| `load.py` | Reads the CSVs **as text** and renames the 3 different ID columns to `project_id` | Reading as text stops pandas from guessing types; one ID name makes joining possible |
| `clean.py` | One small function per data problem. Each one logs how many rows it changed | Easy to test, easy to explain; the log is the evidence for the reports |
| `quality.py` | Measures quality before and after cleaning (completeness, uniqueness, linkability) | Shows the improvement; the same idea becomes monitoring in Task 1 |
| `integrate.py` | Checks which project is in which tool, checks whether shared fields agree, builds **Bid 360** | This is a small version of the data product from Task 1 |
| `features.py` | Prepares data for ML: new useful columns and preprocessing | The model needs numbers, and only data known *at bid time* |
| `train.py` | Trains 4 models, compares them fairly, tests the best, explains it, saves charts | Gives a fair and honest result |

---

## 5. How I cleaned the data, and why

**Rules I followed:**
- Never change the raw files.
- Fix what is certain; flag what is uncertain.
- **Never invent data.**

| # | Problem found | Example | What I did | Why |
|---|---|---|---|---|
| 1 | **Placeholder text** instead of empty cells | `XX`, `N.A.`, `-`, `none` | Turned them into real "missing" values | Otherwise "XX" looks like real data and numbers become text |
| 2 | **Duplicate rows** | CT: 86, MG: 56, all exact copies | Removed the copies | Same project counted twice, which looks like a double upload |
| 3 | **Wrong unit** | Pressure `1013` (mbar) next to `1.01` (bar) | Divided values > 10 by 1000 | Same thing in two units means a manual entry error |
| 4 | **Missing project ID** | 94 design rows with no ID | Recovered 91 by matching size + plant type + region with the cost tool; only accepted **unique** matches | A row without an ID is invisible to every other system |
| 5 | **Two date formats** | `21.11.2022` and `2022-11-21` | Read both formats explicitly | If you let the computer guess, 03.04 can become March 4th instead of April 3rd |
| 6 | **Empty cost that is not missing** | Steam plant (ST) with no gas turbine cost | Set to **0**, because the plant has no gas turbine | Filling with an average would invent a turbine that doesn't exist |
| 7 | **Field nobody fills** | Fuel type never filled for ST plants | Labelled `Unknown` and reported it | Needs an owner and a clear definition (Task 1 governance) |

**How do I know the ID recovery is right?** I took 470 rows whose ID I *knew*, deleted their IDs, and ran the recovery. It gave back 445 IDs, and **all 445 were correct**. The 25 unclear rows were skipped, not guessed.

**Interesting finding:** once IDs are linked correctly, the same fields in different tools (customer, price, size, region) agree **100 %**. So "data differs" isn't caused by the tools disagreeing. It's caused by the **manual copying process**: duplicates, missing IDs, units and formats.

---

## 6. How the model works, in simple words

**Question:** given what we know when we submit a bid, how likely are we to win?

**Steps:**
1. **Use only bid-time information.** Nothing that is known only after the customer decides (that would be cheating, called "data leakage").
2. **Add useful columns**, e.g. *price per MW* and *bid ÷ cost* (the margin).
3. **Fill gaps safely.** Missing numbers get the middle value (median) plus a "was missing" marker. Missing categories get `Unknown`. This is learned only from the training data.
4. **Split the data.** 80 % for learning, 20 % kept hidden for the final test.
5. **Compare 4 models**, from simple to complex, with 5-fold cross-validation (train and test 5 times on different slices, then average):

| Model | Simple explanation | ROC-AUC |
|---|---|---|
| Dummy | Always says "win" (the baseline to beat) | 0.50 |
| **Logistic Regression** ✅ | Gives each factor a weight (+ or −) and adds them up | **0.72** |
| Random Forest | Many decision trees vote | 0.71 |
| Gradient Boosting | Trees learn one after another, fixing earlier mistakes | 0.71 |

**Why Logistic Regression won:** it scored best, it is the most stable, and every factor can be explained to a business person. The complex models didn't help, which means the patterns in this data are fairly simple.

**What is ROC-AUC?** If you pick one won bid and one lost bid at random, it's the chance the model gives the won bid the higher score. 0.5 = coin flip, 1.0 = perfect. **0.72 means clearly useful, but not magic.**

**Why not just accuracy?** 60 % of bids are wins, so a model that always says "win" already gets 60 % accuracy while being useless.

**What the model learned:**
- ➕ Higher plant efficiency, larger plants, EU/US markets, some customers
- ➖ **Higher price for the same plant size** (customers are price-sensitive), hot sites, some markets (e.g. Mexico)

**Limits:** only ~1,900 bids, and no competitor or pricing-strategy data. Use it to **prioritise and review bids**, not to decide automatically.

---

## 7. The Task 1 proposal in short: "Bid 360"

One **governed data product** in the **existing Snowflake**:
- Every tool sends its data **automatically**.
- Data passes three layers: **Bronze** (raw) → **Silver** (cleaned with the same rules as in this repo) → **Gold** (one trusted row per bid).
- **One project ID** for all tools, **one owner per field**, a **data contract** with Salesforce, and **automatic quality checks**.
- Used by dashboards, the win model, an **AI Bid Assistant (RAG/MCP)**, and an **API to the Costing Tool** that replaces Excel.

---

## 8. Note on tools

This project was built with AI-assisted development (Claude Code) to speed up implementation. Problem framing, cleaning decisions, validation and model choices were reviewed by me, and every rule is covered by tests or documented checks.
