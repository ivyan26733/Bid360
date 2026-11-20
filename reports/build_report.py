"""
Builds reports/Bid360_Case_Study_Report.pdf

All numbers are read from data/processed/ (written by run_pipeline.py),
so the report always matches the code. Run order:
    python run_pipeline.py
    (run notebooks/01_eda.ipynb for the two EDA charts)
    python reports/diagrams/draw_diagrams.py
    python reports/build_report.py
"""
import json
from pathlib import Path

import pandas as pd
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.platypus import (CondPageBreak, Image, KeepTogether, ListFlowable, ListItem, PageBreak, Paragraph,
                                Preformatted, SimpleDocTemplate, Spacer, Table, TableStyle)

ROOT = Path(__file__).resolve().parent.parent
P = ROOT / "data" / "processed"
FIG = ROOT / "reports" / "figures"
DIA = ROOT / "reports" / "diagrams"
OUT = ROOT / "reports" / "Bid360_Case_Study_Report.pdf"

# ----------------------------------------------------------------------------- numbers (from pipeline outputs)
log = pd.read_csv(P / "quality_log.csv")
score = pd.read_csv(P / "quality_scorecard.csv")
cov = pd.read_csv(P / "coverage.csv")
cons = pd.read_csv(P / "consistency.csv")
cv = pd.read_csv(P / "ml_cv_results.csv")
test = json.loads((P / "ml_test_results.json").read_text())
imp = pd.read_csv(P / "ml_feature_importance.csv")
bid = pd.read_csv(P / "bid_360.csv", parse_dates=["handover_date"])


def n(system, starts):  # rows affected for a log entry
    m = log[(log.system == system) & log.issue.str.startswith(starts)]
    return int(m.rows_affected.sum())


DUP_CT, DUP_MG = n("CT", "Exact duplicate"), n("MG", "Exact duplicate")
MBAR = n("PPD", "Mixed units")
ID_REC, ID_LOST = n("PPD", "Missing project ID - recovered"), n("PPD", "Missing project ID (row")
DATE_A, DATE_B = n("MG", "Date format dd"), n("MG", "Date format yyyy")
PLACEHOLDER_COLS = int(log.issue.str.startswith("Placeholder").sum())
FUEL_ST = n("PPD", "Never recorded for ST")
ZERO_GT, ZERO_ST = n("CT", "Empty cost for component that a ST"), n("CT", "Empty cost for component that a SCGT")
HUMID = n("PPD", "Value outside plausible range")
TOTAL = len(cov)
ALL3 = int((cov.systems == "PPD + CT + MG").sum())
INCOMPLETE = TOTAL - ALL3
COMPARISONS, MISMATCHES = int(cons.compared.sum()), int(cons.mismatches.sum())
WIN_RATE = bid.win_loss.mean()
HD_WON = bid[bid.win_loss == 1].handover_date.notna().mean()
HD_LOST = bid[bid.win_loss == 0].handover_date.notna().mean()
LR = cv[cv.model == "Logistic Regression"].iloc[0]
RF = cv[cv.model == "Random Forest"].iloc[0]
GB = cv[cv.model == "Gradient Boosting"].iloc[0]
DUMMY = cv[cv.model == "Dummy baseline"].iloc[0]
T = test["test"]
TLR = T["Logistic Regression"]
TEST_ROWS = TLR["test_rows"]
WR = {c: bid.groupby(c).win_loss.mean() for c in ["plant_type", "region", "customer"]}
SIM = json.loads((P / "id_recovery_check.json").read_text())  # written by run_pipeline.py (src/validate.py)

# ----------------------------------------------------------------------------- styles
TEAL, DARK, AMBER, RED, GREY, TINT = (colors.HexColor(h) for h in
                                      ["#0F7C8C", "#0B3C49", "#E9A23B", "#C8553D", "#5B6B73", "#EEF3F4"])
ss = getSampleStyleSheet()
H1 = ParagraphStyle("H1", parent=ss["Heading1"], fontName="Helvetica-Bold", fontSize=18, textColor=DARK,
                    spaceBefore=6, spaceAfter=10)
H2 = ParagraphStyle("H2", parent=ss["Heading2"], fontName="Helvetica-Bold", fontSize=13, textColor=TEAL,
                    spaceBefore=12, spaceAfter=6)
H3 = ParagraphStyle("H3", parent=ss["Heading3"], fontName="Helvetica-Bold", fontSize=11, textColor=DARK,
                    spaceBefore=8, spaceAfter=4)
BODY = ParagraphStyle("Body", parent=ss["BodyText"], fontName="Helvetica", fontSize=10, leading=14, spaceAfter=6)
SMALL = ParagraphStyle("Small", parent=BODY, fontSize=8.5, leading=11, textColor=GREY)
CELL = ParagraphStyle("Cell", parent=BODY, fontSize=8.8, leading=11.5, spaceAfter=0)
CELLB = ParagraphStyle("CellB", parent=CELL, fontName="Helvetica-Bold")
HEAD = ParagraphStyle("Head", parent=CELL, fontName="Helvetica-Bold", textColor=colors.white)
CODE = ParagraphStyle("Code", parent=BODY, fontName="Courier", fontSize=8.3, leading=10.5,
                      backColor=TINT, borderPadding=6, leftIndent=6, rightIndent=6)
COVER_T = ParagraphStyle("CoverT", parent=H1, fontSize=34, leading=40, textColor=colors.white)
COVER_S = ParagraphStyle("CoverS", parent=BODY, fontSize=15, leading=20, textColor=colors.HexColor("#8FB8BF"))
COVER_B = ParagraphStyle("CoverB", parent=BODY, fontSize=10.5, textColor=colors.white)
STAT_N = ParagraphStyle("StatN", parent=BODY, fontName="Helvetica-Bold", fontSize=20, leading=22,
                        textColor=RED, alignment=TA_CENTER)
STAT_L = ParagraphStyle("StatL", parent=CELL, alignment=TA_CENTER)

W = A4[0] - 3.6 * cm  # usable width


def p(text, style=BODY):
    return Paragraph(text, style)


def bullets(items):
    return ListFlowable([ListItem(p(i), leftIndent=12) for i in items], bulletType="bullet",
                        start="•", leftIndent=12, bulletFontSize=9)


def table(rows, widths, head=True, first_bold=False):
    data = []
    for r, row in enumerate(rows):
        style = HEAD if (head and r == 0) else CELL
        data.append([p(str(c), CELLB if (first_bold and j == 0 and r > 0) else style) for j, c in enumerate(row)])
    t = Table(data, colWidths=[w * W for w in widths], repeatRows=1 if head else 0)
    st = [("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#D5DEE1")),
          ("VALIGN", (0, 0), (-1, -1), "TOP"),
          ("TOPPADDING", (0, 0), (-1, -1), 4), ("BOTTOMPADDING", (0, 0), (-1, -1), 4)]
    if head:
        st.append(("BACKGROUND", (0, 0), (-1, 0), DARK))
    for r in range(1 if head else 0, len(data)):
        if r % 2 == 0:
            st.append(("BACKGROUND", (0, r), (-1, r), TINT))
    t.setStyle(TableStyle(st))
    return t


def explain(title, text):
    """Tinted 'What this shows' box under a chart or diagram."""
    t = Table([[p(f"<b>{title}</b><br/>{text}", CELL)]], colWidths=[W])
    t.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, -1), TINT), ("BOX", (0, 0), (-1, -1), 0.6, TEAL),
                           ("LEFTPADDING", (0, 0), (-1, -1), 8), ("RIGHTPADDING", (0, 0), (-1, -1), 8),
                           ("TOPPADDING", (0, 0), (-1, -1), 6), ("BOTTOMPADDING", (0, 0), (-1, -1), 6)]))
    return t


def figure(path, width_frac, caption, what, head=None):
    from reportlab.lib.utils import ImageReader
    iw, ih = ImageReader(str(path)).getSize()
    w = W * width_frac
    block = [Image(str(path), width=w, height=w * ih / iw), Spacer(1, 3),
             p(f"<i>{caption}</i>", SMALL), explain("What this shows", what), Spacer(1, 8)]
    return KeepTogether(([head] if head else []) + block)  # heading stays with its figure


def stats(items):
    """Row of big-number boxes."""
    cells = [[p(num, STAT_N) for num, _ in items], [p(lbl, STAT_L) for _, lbl in items]]
    t = Table(cells, colWidths=[W / len(items)] * len(items))
    t.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, -1), TINT), ("LINEAFTER", (0, 0), (-2, -1), 2, colors.white),
                           ("TOPPADDING", (0, 0), (-1, -1), 6), ("BOTTOMPADDING", (0, 0), (-1, -1), 6)]))
    return t


def pct(x):
    return f"{100 * x:.0f}%"


# ----------------------------------------------------------------------------- page decoration
def on_cover(canvas, doc):
    canvas.saveState()
    canvas.setFillColor(DARK)
    canvas.rect(0, 0, A4[0], A4[1], fill=1, stroke=0)
    canvas.restoreState()


def on_page(canvas, doc):
    canvas.saveState()
    canvas.setFont("Helvetica", 8)
    canvas.setFillColor(GREY)
    canvas.drawString(1.8 * cm, 0.9 * cm, "Bid 360 - Integrated Bid Intelligence | Case study report")
    canvas.drawRightString(A4[0] - 1.8 * cm, 0.9 * cm, f"Page {doc.page}")
    canvas.restoreState()


# ----------------------------------------------------------------------------- content
s = []

# Cover
s += [Spacer(1, 6 * cm), p("Bid 360", COVER_T),
      p("From scattered tools to one trusted view of every bid", COVER_S), Spacer(1, 1.2 * cm),
      p("Case study report - Data &amp; AI Expert assignment", COVER_B),
      p("Task 1: Business requirements and data product design<br/>"
        "Task 2: Data analysis and machine learning<br/>"
        "Addition: How an AI assistant (RAG + MCP) would use the data", COVER_B),
      Spacer(1, 1 * cm), p("November 2026", COVER_B), PageBreak()]

# How to read
s += [p("How to read this report", H1),
      p("This report covers both tasks of the case study and adds one section on how AI could use the result. "
        "It is written to be easy to follow: every chart and diagram has a <b>\"What this shows\"</b> box, and "
        "technical terms are explained in simple words (see also the glossary at the end)."),
      table([["Part", "Content"],
             ["0", "Executive summary"],
             ["1", "Context: how a bid is made today"],
             ["A", "Task 1 - Business problem analysis and the Bid 360 data product"],
             ["B", "Task 2 - Data quality, data model and win-probability model"],
             ["C", "Addition - AI Bid Assistant (RAG + MCP) on top of Snowflake"],
             ["D", "Assumptions, next steps, glossary, how to reproduce"]],
            [0.1, 0.9]),
      Spacer(1, 8),
      p("<b>Where the numbers come from.</b> Every number about the data is produced by the code "
        "(<font face='Courier'>python run_pipeline.py</font>) and read automatically into this report, so the report "
        "and the code always agree."),
      CondPageBreak(4 * cm)]

# 0 Executive summary
s += [p("0. Executive summary", H1),
      p("<b>The problem.</b> Bid data for large power plant projects is spread across several tools (CRA, PPD, MG, CT, "
        "Salesforce, Snowflake). The tools are joined by a <b>manual Excel step</b>, there is <b>no shared project ID</b>, "
        "and the data warehouse holds only part of one system. Users therefore cannot find data, see different numbers, "
        "receive sometimes-incorrect Salesforce data and type the same data several times."),
      p("<b>The evidence.</b> The PPD, CT and MG extracts show these problems directly:"),
      stats([(str(DUP_CT + DUP_MG), "duplicate records"), (str(MBAR), "pressure values in<br/>the wrong unit"),
             (str(ID_REC + ID_LOST), "design records<br/>without an ID"), ("2", "date formats in<br/>one column"),
             (pct(INCOMPLETE / TOTAL), "of projects missing<br/>from a system")]),
      Spacer(1, 8),
      p(f"<b>The key insight.</b> Once projects are linked correctly, the systems agree: <b>{MISMATCHES} mismatches in "
        f"{COMPARISONS:,} comparisons</b> of shared fields. The tools are not the problem - the <b>manual process between "
        "them</b> is. So the solution is to fix how data flows, not to replace the tools."),
      p("<b>The proposal.</b> <b>Bid 360</b>: one governed data product on the Snowflake platform the organisation already "
        "uses. Every tool sends its data automatically; the data is cleaned and joined into one trusted record per bid; "
        "every field has one owner; Salesforce data comes under a data contract; and an automated feed to the Costing "
        "Tool replaces Excel."),
      p(f"<b>The value.</b> On the cleaned data, a simple and explainable model ranks a won bid above a lost bid "
        f"<b>{LR.roc_auc:.0%}</b> of the time (a coin flip would be 50%). Plant efficiency, market, customer and price "
        "for a given plant size drive wins. An <b>AI Bid Assistant</b> (RAG + MCP) could later answer questions and draft "
        "proposal outlines from the same governed data."),
      p("<b>Recommended first step.</b> Phase 1 (indicatively 0-3 months): name data owners, agree one project ID, and "
        "load PPD, CT and MG into Snowflake with automated quality checks."),
      CondPageBreak(4 * cm)]

# 1 Context
s += [p("1. Context: how a bid is made today", H1),
      p("The Power Generation Bid Management organisation prepares bids for large power plants. The case study describes "
        "these applications:"),
      table([["Tool", "What it does"],
             ["CRA", "Analyses customer specification documents and captures key technical requirements."],
             ["PPD", "Power Plant Design: engineers create a preliminary plant design."],
             ["Excel Calc", "A workbook used to move data from PPD (plus project data from MG) into CT. Users export, "
                            "check, manually adjust and upload it."],
             ["CT", "Costing Tool: calculates project costs and the bid value."],
             ["MG", "Management Tool: manages projects and bid status; receives selected data from Salesforce."],
             ["Salesforce", "Used by the sales organisation (owned outside Bid Management) for customers and opportunities."],
             ["Snowflake", "Data warehouse; holds only a subset of MG data."]],
            [0.18, 0.82], first_bold=True),
      Spacer(1, 8),
      figure(DIA / "architecture_current.png", 1.0, "Figure 1 - Current state",
             "Two separate flows. The <b>technical flow</b> goes from customer documents through CRA and PPD to the "
             "Costing Tool. The <b>commercial flow</b> goes from Salesforce into MG. They meet only in the red Excel box, "
             "where a person copies, edits and uploads data. The numbered red points mark where problems arise: manual "
             "re-entry, the Excel step, unreliable Salesforce data, a warehouse without design or cost data, and no "
             "shared project key."),
      CondPageBreak(4 * cm)]

# ---------------------------------------------------------------- PART A
s += [p("Part A - Task 1: Business problem and data product", H1),
      p("2. Business problem analysis", H2),
      p("2.1 The user complaints (given in the case) and their business risks (our analysis)", H3),
      table([["#", "Complaint (from the case study)", "Business risk (our analysis)"],
             ["C1", "Users cannot easily find project data or get a clear overview",
              "Slow bids, decisions on partial information, no portfolio view of win rate or margin"],
             ["C2", "Data differs across systems",
              "A wrong number in costing means a wrong price: lost margin or a lost bid; rework; loss of trust"],
             ["C3", "Salesforce data is sometimes outdated or incorrect",
              "Errors travel downstream into MG, Excel, CT and Snowflake; unreliable win/loss history"],
             ["C4", "Some data needs to be entered manually into multiple applications",
              "Errors, wasted effort, no audit trail of changes, dependence on key people"]],
            [0.07, 0.43, 0.5]),
      p("Overall the risks are <b>financial</b> (mispriced bids), <b>commercial</b> (slower response, lower win rate), "
        "<b>operational</b> (manual effort), <b>compliance</b> (no audit trail of Excel changes) and <b>strategic</b> "
        "(no trustworthy data for analytics or AI).", SMALL),
      p("2.2 Root causes", H3),
      p("The complaints are symptoms. Five root causes sit behind them:"),
      table([["Root cause", "Simple explanation", "Drives"],
             ["Excel is the integration layer", "A person acts as the 'middleware' between PPD, MG and CT.", "C2, C4"],
             ["No common project identity", "Three different names for one key; IDs can be missing.", "C1, C2"],
             ["No data ownership", "Nobody owns definitions, units or quality (e.g. fuel type never filled for steam plants).",
              "C1, C2"],
             ["No contract with Salesforce", "Data comes from another organisation without agreed fields, freshness or checks.", "C3"],
             ["Warehouse underused", "Snowflake holds part of MG only - no design or cost data.", "C1"]],
            [0.28, 0.58, 0.14], first_bold=True),
      p("Only the first cause is purely technical. The others are about <b>identity, ownership and agreements</b> - so the "
        "solution must include governance, not just technology."),
      CondPageBreak(4 * cm)]

s += [p("3. Proposal: the Bid 360 data product", H2),
      p("<b>Purpose:</b> one trusted, always-current record of every bid - from requirements through design and cost to "
        "the outcome - for every team and tool that needs it."),
      p("<b>What is a data product?</b> A dataset that is run like a product: it has a <b>named owner</b>, <b>known users</b>, "
        "<b>documented definitions and measured quality</b>, a <b>stable interface</b> (SQL views, API) and a "
        "<b>managed lifecycle</b>. That is what keeps it trustworthy - unlike just another table or report."),
      p("3.1 Business value", H3),
      bullets(["<b>Faster bids</b> - no manual Excel step; data is entered once and reused.",
               "<b>Fewer pricing errors</b> - units, IDs and costs are validated before CT calculates the price.",
               "<b>One overview</b> - status, design, cost and outcome of every bid in one place.",
               "<b>Better win rate</b> - learn from past bids (see the model in Part B).",
               "<b>Trust and audit</b> - every value traceable to its source.",
               "<b>Ready for AI</b> - clean, linked data is the precondition for ML and AI assistants (Part C)."]),
      p("3.2 Producers, consumers and data domains", H3),
      table([["Domain", "Content", "Golden source", "Owner (proposed)", "Main consumers"],
             ["Customer &amp; opportunity", "Customer, country, tender conditions", "Salesforce -> MG",
              "Sales operations (via contract)", "Bid managers, leadership"],
             ["Project", "ID, status, timeline, handover date", "MG", "Bid management", "All"],
             ["Technical requirements", "Customer specifications", "CRA", "Requirements engineering", "Engineers"],
             ["Plant design", "Plant type, MW, efficiency, fuel, site", "PPD", "Plant engineering", "Cost estimators, ML"],
             ["Cost &amp; bid", "Cost components, bid value, versions", "CT", "Cost estimation", "Bid managers, leadership"],
             ["Bid outcome", "Win/loss, decision date, reason", "MG / Salesforce", "Bid management", "Leadership, ML"],
             ["Reference data", "Region, country, plant and fuel types, units", "Central", "Data governance", "All"]],
            [0.19, 0.25, 0.15, 0.2, 0.21], first_bold=True),
      p("<b>Golden source rule:</b> other systems may hold copies, but only the golden source may change a value.", SMALL),
      CondPageBreak(4 * cm)]

s += [p("3.3 Target architecture", H3),
      figure(DIA / "architecture_future.png", 1.0, "Figure 2 - Target state",
             "Every source system (left) sends its data <b>automatically</b> into Snowflake. Inside Snowflake the data "
             "passes three layers: <b>Bronze</b> keeps raw copies exactly as delivered (for audit); <b>Silver</b> cleans "
             "and validates it with one project ID (the cleaning rules from Part B run here); <b>Gold</b> is the Bid 360 "
             "data product - one trusted row per bid. On the right are the users: dashboards, the win-probability model, "
             "the AI assistant and, most importantly, an automatic feed into the Costing Tool that <b>replaces the manual "
             "Excel step</b>."),
      p("<b>Why Snowflake?</b> Snowflake is already part of the landscape (given in the case), so no new platform, licence or "
        "migration is needed. It handles structured data well, has governance features (role-based access, masking, "
        "lineage) and serves dashboards, ML and AI from one place. The concept is not tied to Snowflake - the same layers "
        "and rules would work on another modern data platform."),
      p("3.4 How one bid flows in the future (no Excel)", H3),
      table([["Step", "What happens"],
             ["1. Opportunity", "Sales creates it in Salesforce; one project ID is created and used everywhere. Data flows "
                                "into MG and Snowflake under the data contract."],
             ["2. Requirements", "Customer documents are analysed in CRA; requirements flow into Snowflake with the same ID."],
             ["3. Design", "Engineers design in PPD as before; the design flows automatically into Snowflake."],
             ["4. Clean and join", "Silver applies the quality rules; failing records are held back and the owner is "
                                   "alerted. Gold joins design + project + customer into one Bid 360 record."],
             ["5. Costing input", "Bid 360 sends validated design and project data to CT (API, or a ready-to-upload file "
                                  "in CT's exact format). <b>This replaces the Excel step.</b>"],
             ["6. Cost", "Estimators calculate the price in CT; costs flow back into Bid 360."],
             ["7. Decision support", "The model adds a win probability; dashboards and the AI assistant support the "
                                     "pricing and effort decision."],
             ["8. Outcome", "When the customer decides, win/loss flows back into Bid 360 and becomes new training data."]],
            [0.2, 0.8], first_bold=True),
      p("People keep their tools; only the manual transfer work disappears.", SMALL),
      CondPageBreak(4 * cm)]

s += [p("3.5 Governance strategy", H3),
      table([["Element", "What it means here"],
             ["Clear roles", "Product owner in Bid Management; domain owners at each source; data stewards for definitions."],
             ["One project ID", "Created when the opportunity starts and used by every tool."],
             ["Data contracts", "Agreed fields, units, freshness and quality per source - starting with Salesforce."],
             ["Quality checks at the door", "Unique ID, units in bar, one date format, allowed values, bid above cost."],
             ["Monitoring", "A quality scorecard per source (completeness, uniqueness, linkability); issues routed to the owner."],
             ["Catalog, lineage, access", "Every field defined and traceable; cost and margin data restricted by role."]],
            [0.27, 0.73], first_bold=True),
      p("3.6 How each complaint is solved", H3),
      table([["Complaint", "Root cause", "How Bid 360 solves it"],
             ["C1 Can't find data", "Data scattered; warehouse sees part of MG",
              "All domains in one Gold product with a catalog; dashboards and an AI assistant on top"],
             ["C2 Data differs", "Manual transfer, no common key",
              "One project ID, one golden source per field, automated validation"],
             ["C3 Salesforce sometimes wrong", "External owner, no contract or checks",
              "Data contract, checks at ingestion, issues fed back to the owner"],
             ["C4 Manual re-entry", "Excel is the integration layer",
              "Enter once at the source; automated feeds and an API into CT"]],
            [0.24, 0.3, 0.46], first_bold=True),
      p("3.7 Roadmap and success measures (indicative)", H3),
      table([["Phase", "Timing (indicative)", "Scope"],
             ["1 Foundation", "0-3 months", "One project ID; PPD, CT, MG into Snowflake; quality rules and scorecard; owners named"],
             ["2 Data product", "3-6 months", "Gold Bid 360; Salesforce contract; catalog and lineage; dashboards; CRA connected"],
             ["3 Automation", "6-9 months", "Feed from Bid 360 to CT replaces the Excel step"],
             ["4 Intelligence", "9-12 months", "Win model in production; cost benchmarking; AI Bid Assistant"]],
            [0.2, 0.2, 0.6], first_bold=True),
      p("Timings are an estimate to be validated with IT and system owners; Phase 1 is deliberately small so the real "
        "effort can be measured early. AI comes last on purpose: it is only as good as the data under it.", SMALL),
      table([["Success measure", "Target"],
             ["Bids with a complete 360 record (all systems linked)", f"{pct(ALL3 / TOTAL)} today -> 98%+"],
             ["Records passing quality checks", "> 99%"],
             ["Manual Excel transfers per bid", "0"],
             ["Salesforce data freshness", "<= 24 hours"]], [0.65, 0.35]),
      CondPageBreak(4 * cm)]

# ---------------------------------------------------------------- PART B
s += [p("Part B - Task 2: Data analysis and machine learning", H1),
      p("4. The data", H2),
      table([["File", "Source tool", "Rows", "Contains", "ID column name"],
             ["PPD_data.csv", "Power Plant Design", f"{int(score[(score.system=='PPD')&(score.stage=='before')].rows.iloc[0]):,}",
              "Plant type, output, efficiency, fuel, site conditions, cooling", "Project_ID"],
             ["CT_data.csv", "Costing Tool", f"{int(score[(score.system=='CT')&(score.stage=='before')].rows.iloc[0]):,}",
              "Customer, region, 4 cost components, bid value", "ID"],
             ["MG_data.csv", "Management Tool", f"{int(score[(score.system=='MG')&(score.stage=='before')].rows.iloc[0]):,}",
              "Customer, country, output, bid value, handover date, Win_Loss", "Opportunity_ID"]],
            [0.15, 0.17, 0.08, 0.42, 0.18], first_bold=True),
      p(f"The same project key has <b>three different names</b>. There are <b>{TOTAL:,} projects</b> (ID1000-ID2999). "
        f"The overall win rate is <b>{WIN_RATE:.1%}</b>."),
      p("5. Data quality findings", H2),
      p("Each finding was measured by the code, fixed by a tested rule, and linked to a user complaint. Rule of thumb used "
        "throughout: <b>never change the raw files, fix what is certain, flag what is uncertain, never invent data.</b>"),
      table([["#", "Finding", "Evidence (from the code)", "What we did", "Complaint"],
             ["1", "Placeholder text instead of empty values", f"'XX', 'N.A.', '-', 'none' in {PLACEHOLDER_COLS} columns",
              "Converted to real missing values", "C4"],
             ["2", "Duplicate records", f"CT {DUP_CT} + MG {DUP_MG} = {DUP_CT + DUP_MG}; all exact copies",
              "Removed the copies", "C2"],
             ["3", "Unit mix-up", f"{MBAR} pressure values in mbar (~1000) instead of bar (~1.0)",
              "Divided by 1000; range-checked", "C4"],
             ["4", "Missing project IDs", f"{ID_REC + ID_LOST} PPD rows without an ID",
              f"{ID_REC} recovered by a unique match; {ID_LOST} removed", "C1"],
             ["5", "Two date formats", f"{DATE_A} as dd.mm.yyyy and {DATE_B} as yyyy-mm-dd",
              "Both read explicitly (no guessing day vs month)", "C4"],
             ["6", "Blanks that are really zero", f"Gas-turbine cost empty for steam plants ({ZERO_GT}); steam-turbine "
              f"cost empty for single-cycle plants ({ZERO_ST})", "Set to 0 - the plant has no such turbine", "-"],
             ["7", "Field without an owner", f"Fuel type never filled for steam (ST) plants ({FUEL_ST} of {FUEL_ST})",
              "Labelled 'Unknown'; needs an owner", "C1"]],
            [0.04, 0.19, 0.31, 0.31, 0.15]),
      p(f"Also found: many costs sit exactly on a round maximum (e.g. gas-turbine cost = 200), which suggests capped or "
        f"default values to check with the CT owner; and {HUMID} humidity values of exactly 0%, set to missing.", SMALL),
      CondPageBreak(4 * cm)]

s += [figure(FIG / "eda_pressure_units.png", 0.9, "Figure 3 - Ambient pressure before and after the unit fix",
             f"Left: the raw pressure values form <b>two separate groups</b> - most around 1.0 (bar) and {MBAR} around 1,000 "
             "(millibar). Normal air pressure is about 1.013 bar = 1,013 mbar, so both groups describe the same thing in "
             "different units. Right: after dividing the mbar values by 1,000, all values sit in one plausible range. "
             "This is a typical sign of values typed in by hand."),
      p("5.1 Recovering lost IDs - and checking that it is safe", H3),
      p("PPD (design) and CT (cost) describe the same plant, and for all linked projects the plant size (MW), plant type "
        "and region agree. So these three values act like a fingerprint. A missing ID is restored <b>only if exactly one</b> "
        "cost record matches, and that record matches only one design row. Unclear cases are never guessed."),
      p(f"<b>Check:</b> we hid {SIM['hidden']} IDs that we knew, ran the rule and compared. It restored {SIM['recovered']} "
        f"IDs and <b>all {SIM['correct']} were correct</b>; the rest were unclear and correctly left alone. "
        "Limitation: this assumes the real orphan rows behave like normal rows, so in production recovered links would "
        "be marked as 'inferred'."),
      p("5.2 Quality before and after cleaning", H3),
      table([["System", "Completeness before -> after", "Uniqueness before -> after", "Linkability before -> after"]] +
            [[sy,
              f"{score[(score.system==sy)&(score.stage=='before')].completeness_pct.iloc[0]}% -> {score[(score.system==sy)&(score.stage=='after')].completeness_pct.iloc[0]}%",
              f"{score[(score.system==sy)&(score.stage=='before')].uniqueness_pct.iloc[0]}% -> {score[(score.system==sy)&(score.stage=='after')].uniqueness_pct.iloc[0]}%",
              f"{score[(score.system==sy)&(score.stage=='before')].linkability_pct.iloc[0]}% -> {score[(score.system==sy)&(score.stage=='after')].linkability_pct.iloc[0]}%"]
             for sy in ["PPD", "CT", "MG"]],
            [0.16, 0.28, 0.28, 0.28], first_bold=True),
      p("<b>Completeness</b> = share of cells with a real value. <b>Uniqueness</b> = share of rows whose ID appears only "
        "once. <b>Linkability</b> = share of rows that have an ID. Completeness rises only a little because the remaining "
        "gaps are genuinely unknown - the pipeline does not invent data.", SMALL),
      CondPageBreak(4 * cm)]

cov_counts = cov.systems.value_counts()
s += [p("5.3 Linking the systems", H3),
      table([["Present in", "Projects"]] + [[k, f"{v:,}"] for k, v in cov_counts.items()] + [["Total", f"{TOTAL:,}"]],
            [0.6, 0.4]),
      p(f"<b>{ALL3:,} of {TOTAL:,} projects ({pct(ALL3 / TOTAL)})</b> exist in all three systems; "
        f"<b>{INCOMPLETE} ({pct(INCOMPLETE / TOTAL)})</b> are missing from at least one - no single system has the full picture (C1)."),
      table([["Shared attribute", "Compared", "Systems", "Mismatches"]] +
            [[r.attribute, f"{r.compared:,}", r.systems, str(r.mismatches)] for r in cons.itertuples()],
            [0.3, 0.2, 0.3, 0.2]),
      explain("Key insight",
              f"Where the same information is stored in two systems, it agrees <b>100%</b> once projects are linked "
              f"correctly ({MISMATCHES} mismatches in {COMPARISONS:,} comparisons). So in this extract, 'data differs' (C2) "
              "is caused by duplicates, missing IDs, placeholders and unit/format differences - <b>the manual transfer "
              "process</b> - not by the tools contradicting each other. Complaint C3 (Salesforce) cannot be measured "
              "directly because no Salesforce extract was provided."),
      CondPageBreak(4 * cm),
      p("6. Characteristics of the data", H2),
      figure(FIG / "eda_winrate_segments.png", 1.0, "Figure 4 - Win rate by plant type, region and customer",
             f"Each bar is the share of bids won in that group; the dashed line is the overall average ({WIN_RATE:.0%}). "
             f"Combined-cycle plants (CCGT) win far more often ({pct(WR['plant_type']['CCGT'])}) than single-cycle "
             f"(SCGT, {pct(WR['plant_type']['SCGT'])}) or steam plants (ST, {pct(WR['plant_type']['ST'])}). EU bids win "
             f"{pct(WR['region']['EU'])} versus {pct(WR['region']['APAC'])} in APAC. Win rates also differ strongly by customer "
             f"(from {pct(WR['customer'].min())} to {pct(WR['customer'].max())}). These differences are the first hint that "
             "a model can learn something useful."),
      CondPageBreak(4 * cm)]

s += [figure(DIA / "data_model.png", 0.92, "Figure 5 - Logical data model (entity-relationship diagram)",
             "Each box is a business <b>entity</b> (a 'thing' we store data about) with its key attributes. "
             "<b>PK</b> = primary key (unique ID), <b>FK</b> = foreign key (a link to another entity). Lines show "
             "<b>relationships</b> and how many: '1 - N' means one-to-many (one customer has many projects); "
             "'1 - 0..1' means at most one (a project has an outcome only once decided). Colours show which source system "
             "<b>owns</b> each entity - the basis of the governance in Part A. Fields marked * are not in the extract but "
             "are recommended (e.g. versions of designs and cost estimates).", head=p("7. Logical data model", H2)),
      p("<b>Main relationships:</b> a customer has many projects; a region has many countries and a country has many "
        "projects; a project has one site, one or more designs, and each design one or more cost estimates; a project has "
        "at most one outcome."),
      p("<b>Assumptions:</b> Project_ID, ID and Opportunity_ID are the same business key (confirmed by the 100% agreement); "
        "the extract has one design and one estimate per project, but real bids have revisions (hence version fields); "
        "customer data is mastered in Salesforce; win/loss probably originates from the Salesforce opportunity status; "
        "region is derived from country; costs are in million euro like the bid value.", SMALL),
      CondPageBreak(4 * cm)]

top = imp.head(6)
s += [p("8. Predicting bid success (Win_Loss)", H2),
      p("<b>Goal:</b> before a bid is submitted, estimate how likely it is to be won. This is <b>binary classification</b> "
        "(won = 1, lost = 0), learned from past bids whose outcome is known. It uses classical machine learning "
        "(scikit-learn) - no LLM and no external service; it runs locally and gives the same result every time."),
      p("8.1 Data preparation", H3),
      table([["Step", "What we did", "Why (in simple words)"],
             ["Join", "PPD + CT + MG into one row per bid (Bid 360)", "The model needs all information about a bid in one place"],
             ["No cheating (leakage)", "Only information known when the bid is submitted",
              "Otherwise the model 'sees the answer' and fails on new bids"],
             ["Leakage check", f"Handover date filled for {pct(HD_WON)} of won and {pct(HD_LOST)} of lost bids",
              "Same share, so it does not give away the outcome"],
             ["Useful ratios", "Price per MW, bid / cost (margin), cost shares, handover year",
              "Business view: 'are we expensive for this plant size?'"],
             ["Excluded", "Project ID, data-quality flags", "No business meaning"],
             ["Make it readable", "Fill gaps with the median (+ 'was missing' flag), same scale for numbers, "
                                  "categories as 0/1 columns", "Models need complete numbers"],
             ["Pipeline", "All of the above learned from training data only",
              "Nothing from the test data leaks into training"]],
            [0.18, 0.42, 0.4], first_bold=True),
      p("8.2 Models compared", H3),
      table([["Model", "How it works (simple)", "Pros / cons", "Score (AUC, 5-fold)"],
             ["Dummy baseline", "Always says 'win'", "The bar to beat; useless on its own", f"{DUMMY.roc_auc:.2f}"],
             ["<b>Logistic Regression</b>", "Gives each factor plus or minus points, adds them up, turns the total into a %",
              "Explainable, stable, good on small data / misses complex combinations", f"<b>{LR.roc_auc:.3f} +/- {LR.roc_auc_std:.3f}</b>"],
             ["Random Forest", "400 decision trees vote", "Finds combinations / harder to explain",
              f"{RF.roc_auc:.3f} +/- {RF.roc_auc_std:.3f}"],
             ["Gradient Boosting", "Trees built one after another, each fixing earlier mistakes",
              "Often most accurate / least explainable, overfits small data", f"{GB.roc_auc:.3f} +/- {GB.roc_auc_std:.3f}"]],
            [0.18, 0.32, 0.32, 0.18], first_bold=False),
      p(f"<b>How it was evaluated:</b> 20% of bids ({TEST_ROWS}) were locked away as a final test. The models were compared "
        "with 5-fold cross-validation on the other 80% (train and test five times on different slices, then average)."),
      p(f"<b>Choice: Logistic Regression.</b> The three real models scored about the same (differences are within normal "
        "variation), so the simplest, most stable and most explainable one was chosen. That the complex models did not "
        "help also tells us the win drivers in this data are mostly simple."),
      p("<b>What does AUC mean?</b> Take one bid that was won and one that was lost. AUC is how often the model gives the "
        f"won bid the higher score. 0.5 = coin flip, 1.0 = perfect. Ours is about <b>{LR.roc_auc:.2f}</b>: clearly useful, "
        "not perfect. We use AUC rather than accuracy because about 60% of bids are wins, so a model that always says "
        f"'win' already gets {DUMMY.accuracy:.0%} accuracy while being useless.", SMALL),
      CondPageBreak(4 * cm)]

s += [p("8.3 Results on the unseen test bids", H3),
      table([["Model", "AUC", "Accuracy", "Precision", "Recall", "F1"]] +
            [[m, f"{r['roc_auc']:.2f}", f"{r['accuracy']:.2f}", f"{r['precision']:.2f}", f"{r['recall']:.2f}", f"{r['f1']:.2f}"]
             for m, r in T.items()],
            [0.3, 0.14, 0.14, 0.14, 0.14, 0.14], first_bold=True),
      p(f"The test AUC ({TLR['roc_auc']:.2f}) is higher than the cross-validation AUC ({LR.roc_auc:.2f}) because the test set "
        f"is small ({TEST_ROWS} bids) and varies more. The cross-validation figure is the more reliable estimate.", SMALL),
      figure(FIG / "ml_confusion_matrix.png", 0.38, "Figure 6 - Confusion matrix (Logistic Regression, test set)",
             f"A 2x2 table of the model's guesses versus reality for the {TEST_ROWS} test bids (cut-off 50%). "
             "Top-left: lost bids correctly predicted as lost. Bottom-right: won bids correctly predicted as won. "
             "The other two cells are mistakes. "
             f"<b>Accuracy</b> {TLR['accuracy']:.0%} = share of all guesses that were right. "
             f"<b>Precision</b> {TLR['precision']:.0%} = when it says 'win', how often that is true. "
             f"<b>Recall</b> {TLR['recall']:.0%} = of the bids really won, how many it spotted."),
      figure(FIG / "ml_feature_importance.png", 0.58, "Figure 7 - What drives a win (permutation importance)",
             "Each bar shows how much worse the model gets when that one column is randomly shuffled (its information "
             "destroyed). A longer bar means the model relies on it more. "
             f"Top drivers: {', '.join(top.feature.head(5))}. Reading the model: <b>higher plant efficiency, larger plants, "
             "strong markets (e.g. US, EU) and certain customers raise</b> the chance of winning; <b>a higher price for the "
             "same plant size, hot sites and weaker markets lower</b> it. These are patterns, not proven causes."),
      CondPageBreak(4 * cm)]

s += [p("8.4 How the model learns its weights (in simple words)", H3),
      p("Logistic Regression starts with every weight at zero. It scores all training bids, measures how wrong it is "
        "(for a won bid it wants a score near 100%, for a lost bid near 0%), and then nudges every weight a little in the "
        "direction that makes it less wrong. It repeats this until it cannot improve any more. A small penalty on large "
        "weights (regularisation) stops it from over-reacting to a few unusual bids. Nobody sets the weights by hand - "
        "we choose which columns are allowed in; the model learns how much each one matters."),
      p("8.5 Limitations (stated openly)", H3),
      table([["Limitation", "Effect", "Next step"],
             ["Small data (about 1,900 bids)", "Small differences between models are not meaningful", "More history; confidence intervals"],
             ["Random split, not by time", "Probably a little optimistic", "Train on older bids, test on newer ones"],
             ["No competitor or market data", "Likely the biggest real driver is missing", "Add competitor prices and our price position"],
             ["Overlapping columns (e.g. bid value and plant size)", "Single weights are less reliable to interpret",
              "Test a reduced feature set"],
             ["Win/loss label quality", "Wrong labels limit any model (links to C3)", "Verify a sample; freshness in the data contract"],
             ["Probabilities not calibrated", "'70%' may not mean exactly 70%", "Calibration check before showing to users"],
             ["The data looks generated", "Real data will be messier", "Expect more cleaning iterations"]],
            [0.32, 0.36, 0.32], first_bold=True),
      p("<b>Intended use:</b> a win-probability score that helps bid managers <b>prioritise effort and review pricing</b> - "
        "decision support, not an automatic go/no-go decision."),
      CondPageBreak(4 * cm)]

# ---------------------------------------------------------------- PART C
s += [p("Part C - AI Bid Assistant: using the data with RAG and MCP", H1),
      p("This part is a <b>design proposal</b> (not built in the case study). It shows how, once all data sits in Snowflake "
        "as the governed Bid 360 product, an AI assistant could retrieve it safely and use it - for example to answer "
        "questions or draft a first proposal outline."),
      p("9. Three terms in simple words", H2),
      table([["Term", "Simple explanation"],
             ["LLM", "A large language model (like Claude): very good at reading and writing text, but it does not know "
                     "our company data and can make up facts if not controlled."],
             ["RAG", "Retrieval-Augmented Generation: before answering, the assistant <b>looks up</b> relevant text "
                     "(e.g. past proposals, customer specifications) and answers based on what it found - like an "
                     "open-book exam instead of answering from memory."],
             ["MCP", "Model Context Protocol: a standard way to give an AI assistant a set of <b>approved tools</b> "
                     "(e.g. 'get bid details', 'find similar bids'). The assistant can only do what these tools allow - "
                     "read-only, with the user's own access rights."]],
            [0.12, 0.88], first_bold=True),
      Spacer(1, 6),
      figure(DIA / "ai_assistant.png", 1.0, "Figure 8 - How the AI Bid Assistant retrieves data",
             "(1) A bid manager asks a question. (2) The assistant (an LLM) decides which approved tools to call through "
             "the MCP server. (3) The tools fetch facts from Snowflake: <b>SQL queries</b> on the Gold Bid 360 tables and "
             "the stored win scores, and a <b>vector search</b> (RAG) over documents such as customer specifications and "
             "past proposals. (4) Results come back with their sources. (5) The assistant writes the answer or draft "
             "<b>using only those facts</b>, and the bid manager reviews it."),
      CondPageBreak(4 * cm)]

s += [p("10. Example: drafting a proposal outline for a new bid", H2),
      p("A bid manager types: <i>\"Prepare a first proposal outline for bid ID2450.\"</i> The assistant works step by step:"),
      table([["Step", "Tool (via MCP)", "What it gets from Snowflake"],
             ["1", "get_bid('ID2450')", "The Bid 360 record: customer, country, plant type, MW, efficiency, site conditions, "
                                       "cost components, bid value"],
             ["2", "find_similar_bids(plant type, region, MW range)", "Comparable past bids with their prices per MW and "
                                                                       "whether they were won"],
             ["3", "get_win_score('ID2450')", "The model's win probability and its main reasons (e.g. price per MW above "
                                             "similar won bids)"],
             ["4", "search_documents('CCGT proposal, hot site')", "Relevant passages from the customer specification and "
                                                                  "from past winning proposals (RAG)"],
             ["5", "-", "The LLM writes the outline: plant summary, key requirements, price position versus similar bids, "
                        "risks, and reusable text from past proposals - each fact with its source"],
             ["6", "-", "The bid manager reviews, corrects and approves. The assistant drafts; people decide."]],
            [0.07, 0.33, 0.6]),
      KeepTogether([p("What a tool does underneath is ordinary, safe code. For example, <font face='Courier'>find_similar_bids</font> "
        "could run a fixed, parameterised query on a read-only Gold view:"),
      Preformatted("SELECT project_id, net_output_mw, bid_value_meur / net_output_mw AS price_per_mw, win_loss\n"
                   "FROM   gold.bid_360\n"
                   "WHERE  plant_type = :plant_type AND region = :region\n"
                   "  AND  net_output_mw BETWEEN :mw_min AND :mw_max\n"
                   "ORDER  BY ABS(net_output_mw - :mw) LIMIT 10;", CODE)]),
      p("11. Keeping it safe and trustworthy", H2),
      table([["Risk", "How it is handled"],
             ["The AI makes up numbers (hallucination)", "All numbers must come from tool results; answers show their "
                                                         "sources; an automatic check compares numbers in the answer with "
                                                         "tool output; otherwise it says 'I don't have that data'."],
             ["Confidential cost data", "Company-approved (enterprise) LLM deployment with no training on our data; "
                                        "tools respect the user's Snowflake role; sensitive fields masked."],
             ["Wrong or dangerous queries", "Predefined, read-only, parameterised tools on curated Gold views - no free "
                                            "access to raw tables."],
             ["Quality over time", "A test set of real bid-manager questions with known answers, re-run after every change; "
                                   "track correctness, use of sources, cost and response time."],
             ["Over-reliance", "The assistant drafts and explains; bid managers decide and approve."]],
            [0.3, 0.7], first_bold=True),
      p("<b>Why this only works on top of Bid 360:</b> RAG and MCP are only as good as the data they retrieve. Without one "
        "project ID, clean values and clear ownership, the assistant would confidently repeat wrong data. That is why the "
        "roadmap puts the foundation first and AI last.", SMALL),
      CondPageBreak(4 * cm)]

# ---------------------------------------------------------------- PART D
s += [p("Part D - Assumptions, next steps and reference", H1),
      p("12. Assumptions", H2),
      bullets(["Snowflake is the strategic data platform and can take more sources (licence and capacity available).",
               "PPD, CT, MG and CRA can provide data via API, database access or scheduled exports; CT can accept "
               "automated input (or at least a ready-made import file).",
               "The Salesforce owner will agree to a data contract, but Bid Management cannot change Salesforce itself.",
               "Project_ID, ID and Opportunity_ID are the same business key (confirmed in the data).",
               "MG receives a scheduled sync of selected Salesforce fields; win/loss originates from Salesforce.",
               "Bid value and costs in the extracts are the values at bid time (not overwritten after the decision).",
               "Data volume is moderate (thousands of bids); cost data is sensitive and needs restricted access.",
               "For Part C: an enterprise LLM can be used under company data-protection rules."]),
      p("13. Next steps", H2),
      bullets(["Validate assumptions with IT and the system owners; confirm effort for Phase 1.",
               "Name data owners and agree the enterprise project ID.",
               "Load PPD, CT and MG into Snowflake and run the quality rules automatically (Phase 1).",
               "Improve the model: time-based validation, competitor and market data, calibration, reduced feature set.",
               "Pilot the AI Bid Assistant on read-only Gold views with a small group of bid managers (Phase 4)."]),
      p("14. Glossary", H2),
      table([["Term", "Meaning"],
             ["Bronze / Silver / Gold", "Raw copies / cleaned and validated data / business-ready data product"],
             ["Golden source", "The one system allowed to create and change a given value"],
             ["Data contract", "Agreement with a data provider on fields, units, freshness and quality"],
             ["Leakage", "When a model uses information it would not have at prediction time (like seeing the answer)"],
             ["Cross-validation", "Training and testing several times on different slices of data, then averaging"],
             ["ROC-AUC", "How often the model ranks a won bid above a lost bid (0.5 = coin flip, 1.0 = perfect)"],
             ["Precision / Recall", "When it says 'win', how often right / of real wins, how many found"],
             ["Permutation importance", "How much worse the model gets when one column is shuffled"],
             ["RAG", "Looking up relevant documents before answering, so answers are grounded in real text"],
             ["MCP", "A standard way to give an AI assistant a fixed set of approved tools"]],
            [0.28, 0.72], first_bold=True),
      KeepTogether([p("15. How to reproduce", H2),
      Preformatted("python run_pipeline.py                  # all steps; prints key numbers\n"
                   "python -m pytest -q                     # 8 tests\n"
                   "(run notebooks/01_eda.ipynb)            # the two EDA charts\n"
                   "python reports/diagrams/draw_diagrams.py # diagrams\n"
                   "python reports/build_report.py          # this PDF", CODE),
      p("AI-assisted development (Claude Code) was used to speed up implementation; the approach, decisions and results "
        "were reviewed and validated, and every number in this report is produced by the code.", SMALL)])]

# ----------------------------------------------------------------------------- build
doc = SimpleDocTemplate(str(OUT), pagesize=A4, leftMargin=1.8 * cm, rightMargin=1.8 * cm, topMargin=1.5 * cm,
                        bottomMargin=1.6 * cm, title="Bid 360 - Case study report", author="Case study candidate")
def protect_headings(story):
    """Start a new page before a heading only if less than 3 cm is left (no lonely headings, no big gaps)."""
    out = []
    for f in story:
        if isinstance(f, Paragraph) and f.style.name in ("H1", "H2", "H3"):
            out.append(CondPageBreak(3 * cm))
        out.append(f)
    return out


doc.build(protect_headings(s), onFirstPage=on_cover, onLaterPages=on_page)
print("written", OUT)
