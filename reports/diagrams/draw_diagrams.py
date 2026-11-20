"""
Draws the report diagrams as PNG ("diagrams as code"):
  * data_model.png         - logical data model (Task 2)
  * architecture_current.png / architecture_future.png  (Task 1)

Run:  python reports/diagrams/draw_diagrams.py
"""
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.patches import FancyBboxPatch  # noqa: E402

OUT = Path(__file__).resolve().parent
SOURCE_COLORS = {"MG": "#4f81bd", "PPD": "#2a7f8e", "CT": "#c0504d", "Salesforce": "#8064a2",
                 "Reference": "#7f7f7f", "Snowflake": "#29b5e8"}
LINE_H = 2.6


# --------------------------------------------------------------------------- #
# Logical data model
# --------------------------------------------------------------------------- #
ENTITIES = {
    # name: (x, y_top, width, source, [attributes])   PK = primary key, FK = foreign key
    "REGION": (2, 66, 17, "Reference", ["PK region_code", "   region_name"]),
    "COUNTRY": (24, 66, 19, "Reference", ["PK country_code", "   country_name", "FK region_code"]),
    "CUSTOMER": (64, 66, 19, "Salesforce", ["PK customer_id", "   customer_name"]),
    "PROJECT / OPPORTUNITY": (36, 46, 25, "MG", ["PK project_id", "FK customer_id", "FK country_code",
                                                  "   handover_date (est.)", "   status"]),
    "BID_OUTCOME": (76, 42, 20, "MG", ["PK,FK project_id", "   win_loss", "   decision_date*"]),
    "SITE_CONDITIONS": (2, 42, 21, "PPD", ["PK,FK project_id", "   ambient_temp (°C)",
                                             "   ambient_press (bar)", "   ambient_humidity (%)"]),
    "PLANT_DESIGN": (24, 18, 24, "PPD", ["PK design_id*", "FK project_id", "FK plant_type", "   net_output_mw",
                                         "   efficiency (%)", "   fuel_type", "   cooling_type",
                                         "   cooling_water_type"]),
    "COST_ESTIMATE": (58, 18, 24, "CT", ["PK estimate_id*", "FK project_id", "FK design_id*", "   cost_gt",
                                         "   cost_st", "   cost_auxiliaries", "   cost_installation",
                                         "   bid_value_meur", "   version*"]),
    "PLANT_TYPE": (2, 16, 17, "Reference", ["PK plant_type", "   description", "   has_gas_turbine",
                                             "   has_steam_turbine"]),
}

# (from, to, label at "from" end, label at "to" end)
RELATIONS = [
    ("REGION", "COUNTRY", "1", "N"),
    ("COUNTRY", "PROJECT / OPPORTUNITY", "1", "N"),
    ("CUSTOMER", "PROJECT / OPPORTUNITY", "1", "N"),
    ("PROJECT / OPPORTUNITY", "BID_OUTCOME", "1", "0..1"),
    ("PROJECT / OPPORTUNITY", "SITE_CONDITIONS", "1", "1"),
    ("PROJECT / OPPORTUNITY", "PLANT_DESIGN", "1", "1..N"),
    ("PROJECT / OPPORTUNITY", "COST_ESTIMATE", "1", "1..N"),
    ("PLANT_DESIGN", "COST_ESTIMATE", "1", "1..N"),
    ("PLANT_TYPE", "PLANT_DESIGN", "1", "N"),
]


def _box(ax, name, x, y_top, w, source, attrs):
    h = LINE_H * (len(attrs) + 1) + 1
    color = SOURCE_COLORS[source]
    ax.add_patch(FancyBboxPatch((x, y_top - h), w, h, boxstyle="round,pad=0.2", fc="white", ec=color, lw=1.8))
    ax.add_patch(FancyBboxPatch((x, y_top - LINE_H - 0.6), w, LINE_H + 0.6, boxstyle="round,pad=0.2",
                                fc=color, ec=color))
    ax.text(x + w / 2, y_top - LINE_H / 2 - 0.3, name, ha="center", va="center", color="white",
            fontsize=9, fontweight="bold")
    for i, a in enumerate(attrs):
        bold = a.startswith("PK")
        ax.text(x + 0.8, y_top - LINE_H * (i + 1.5) - 0.8, a, fontsize=7.6, va="center",
                family="monospace", fontweight="bold" if bold else "normal")
    return (x, y_top - h, w, h)


def _anchor(b, other):
    """Point on the edge of box b facing the other box."""
    x, y, w, h = b
    cx, cy = x + w / 2, y + h / 2
    ox, oy = other[0] + other[2] / 2, other[1] + other[3] / 2
    dx, dy = ox - cx, oy - cy
    if abs(dx) / w > abs(dy) / h:
        return (x + w if dx > 0 else x, cy)
    return (cx, y + h if dy > 0 else y)


def draw_data_model():
    fig, ax = plt.subplots(figsize=(15, 10))
    ax.set_xlim(0, 100); ax.set_ylim(-26, 72); ax.axis("off")
    boxes = {n: _box(ax, n, *spec) for n, spec in ENTITIES.items()}
    for a, b, la, lb in RELATIONS:
        p, q = _anchor(boxes[a], boxes[b]), _anchor(boxes[b], boxes[a])
        ax.annotate("", xy=q, xytext=p, arrowprops=dict(arrowstyle="-", color="#555", lw=1.2))
        for (px, py), (qx, qy), lab in [(p, q, la), (q, p, lb)]:
            tx, ty = px + (qx - px) * 0.12, py + (qy - py) * 0.12
            ax.text(tx, ty, lab, fontsize=8, color="#222", ha="center", va="center",
                    bbox=dict(fc="#fff8dc", ec="none", pad=0.6))
    for i, (src, c) in enumerate([(s, c) for s, c in SOURCE_COLORS.items() if s != "Snowflake"]):
        ax.add_patch(plt.Rectangle((2 + i * 16, -24), 2.5, 2.2, color=c))
        ax.text(5.2 + i * 16, -22.9, f"source: {src}", fontsize=8, va="center")
    ax.text(2, -18.5, "PK = primary key   FK = foreign key   * = not in the extract, recommended for the "
            "target model (versioning of designs/estimates, decision date)", fontsize=8, color="#444")
    ax.set_title("Logical data model - Bid Management (PPD · CT · MG)", fontsize=14, fontweight="bold")
    fig.tight_layout(); fig.savefig(OUT / "data_model.png", dpi=150); plt.close(fig)


# --------------------------------------------------------------------------- #
# Architecture: current vs future
# --------------------------------------------------------------------------- #
def _node(ax, x, y, w, h, text, color, fs=9, fc=None):
    ax.add_patch(FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0.3", fc=fc or "white", ec=color, lw=1.8))
    ax.text(x + w / 2, y + h / 2, text, ha="center", va="center", fontsize=fs,
            color="white" if fc else "#222", fontweight="bold" if fc else "normal")


def _arrow(ax, p, q, color="#555", style="-|>", ls="-", lw=1.4, text=None):
    ax.annotate("", xy=q, xytext=p, arrowprops=dict(arrowstyle=style, color=color, lw=lw, ls=ls))
    if text:
        ax.text((p[0] + q[0]) / 2, (p[1] + q[1]) / 2 + 1.2, text, ha="center", fontsize=7.5, color=color)


def draw_current():
    fig, ax = plt.subplots(figsize=(13, 6))
    ax.set_xlim(0, 100); ax.set_ylim(0, 52); ax.axis("off")
    red = "#c0504d"
    _node(ax, 2, 32, 12, 7, "Customer\nspec docs", "#777")
    _node(ax, 20, 32, 12, 7, "CRA", "#555")
    _node(ax, 38, 32, 12, 7, "PPD\n(design)", "#2a7f8e")
    _node(ax, 56, 32, 11, 7, "EXCEL\n(manual)", red, fc=red)
    _node(ax, 74, 32, 12, 7, "CT\n(cost)", "#c0504d")
    _node(ax, 90, 32, 9, 7, "Proposal", "#777")
    _node(ax, 2, 14, 12, 7, "Salesforce\n(other org)", "#8064a2")
    _node(ax, 38, 14, 12, 7, "MG\n(project mgmt)", "#4f81bd")
    _node(ax, 38, 1, 12, 6, "Snowflake\n(MG subset only)", "#29b5e8")
    for p, q in [((14, 35.5), (20, 35.5)), ((32, 35.5), (38, 35.5)), ((50, 35.5), (56, 35.5)),
                 ((67, 35.5), (74, 35.5)), ((86, 35.5), (90, 35.5)), ((14, 17.5), (38, 17.5))]:
        _arrow(ax, p, q)
    _arrow(ax, (50, 17.5), (61.5, 32), color=red, text="copy/paste")
    _arrow(ax, (44, 14), (44, 7), style="<|-|>")
    pains = [("1", 21, 42, "manual re-entry\nCRA → PPD"), ("2", 57, 42, "export, edit, upload:\nduplicates, units,\nplaceholders"),
             ("3", 2, 25, "outdated/incorrect\ndata, no contract"), ("4", 54, 4, "no design / cost data\n→ no overview"),
             ("5", 74, 22, "no shared key\n(3 different ID names)")]
    for n, x, y, t in pains:
        ax.add_patch(plt.Circle((x, y + 2), 1.5, color=red))
        ax.text(x, y + 2, n, color="white", ha="center", va="center", fontsize=8, fontweight="bold")
        ax.text(x + 2.2, y + 2, t, fontsize=7.8, va="center", color=red)
    ax.set_title("Current state - point-to-point, manual integration", fontsize=13, fontweight="bold")
    fig.tight_layout(); fig.savefig(OUT / "architecture_current.png", dpi=150); plt.close(fig)


def draw_future():
    fig, ax = plt.subplots(figsize=(14, 7.5))
    ax.set_xlim(0, 100); ax.set_ylim(0, 62); ax.axis("off")
    green, sf = "#2e7d32", "#29b5e8"
    sources = [("Salesforce", "#8064a2"), ("CRA", "#555"), ("PPD", "#2a7f8e"), ("MG", "#4f81bd"), ("CT", "#c0504d")]
    ax.text(8, 58, "Source systems\n(domain owners)", ha="center", fontsize=9, fontweight="bold")
    for i, (s, c) in enumerate(sources):
        y = 46 - i * 10
        _node(ax, 2, y, 12, 6, s, c)
        _arrow(ax, (14, y + 3), (24, 30), color="#777")
    _node(ax, 2, 0.5, 12, 3.5, "data contracts", green, fs=7.5)

    ax.add_patch(FancyBboxPatch((24, 6), 44, 48, boxstyle="round,pad=0.5", fc="#eaf7fd", ec=sf, lw=2))
    ax.text(46, 51.5, "Snowflake - Integrated Bid Data Platform", ha="center", fontsize=10.5, fontweight="bold")
    layers = [("BRONZE - raw copies (as delivered)", "#b08d57"),
              ("SILVER - cleaned, validated, one project_id\n(rules from this case: placeholders, units,\ndates, duplicates, ID recovery)", "#9e9e9e"),
              ("GOLD - Data Product 'Bid 360'\none governed row per bid + win model scores", "#d4a017")]
    for i, (t, c) in enumerate(layers):
        y = 39 - i * 13
        _node(ax, 27, y, 38, 9, t, c, fs=8.3, fc=c)
        if i:
            _arrow(ax, (46, y + 13), (46, y + 9.6))
    _node(ax, 27, 7.5, 38, 2.5, "Governance: owners · quality checks · lineage · access roles", green, fs=7.5)

    consumers = [("Bid 360 dashboards\n(bid managers, mgmt)", 44), ("Win-probability model\n(ML)", 34),
                 ("AI Bid Assistant\n(RAG / MCP)", 24), ("CT input API\n(replaces Excel)", 14)]
    ax.text(85, 58, "Consumers", ha="center", fontsize=9, fontweight="bold")
    for t, y in consumers:
        _node(ax, 76, y, 18, 7, t, "#333")
        _arrow(ax, (65.3, 17.5), (76, y + 3.5), color="#777")
    _arrow(ax, (85, 14), (85, 9), color=green)
    ax.text(85, 6.5, "CT receives validated PPD+MG data\nautomatically - no manual Excel", ha="center",
            fontsize=7.5, color=green)
    ax.set_title("Target state - one governed data product for every bid", fontsize=13, fontweight="bold")
    fig.tight_layout(); fig.savefig(OUT / "architecture_future.png", dpi=150); plt.close(fig)


def draw_ai_assistant():
    """How the AI Bid Assistant gets data from Snowflake (MCP tools + RAG) and drafts an answer/proposal."""
    fig, ax = plt.subplots(figsize=(14, 8))
    ax.set_xlim(0, 100); ax.set_ylim(0, 60); ax.axis("off")
    purple, blue, green, sf = "#8064a2", "#4f81bd", "#2e7d32", "#29b5e8"

    # row 1: question -> agent -> draft
    _node(ax, 4, 46, 18, 9, "Bid manager asks:\n'Draft a proposal outline\nfor bid ID2450'", "#333")
    _node(ax, 34, 46, 24, 9, "AI Bid Assistant\n(LLM agent)", purple, fs=10, fc=purple)
    _node(ax, 70, 46, 27, 9, "Draft proposal / answer\nfacts only from tools, with sources\n-> reviewed by the bid manager", green)
    _arrow(ax, (22.6, 50.5), (33.4, 50.5), text="1 question")
    _arrow(ax, (58.6, 50.5), (69.4, 50.5), color=green, text="5 draft")

    # row 2: MCP server
    _node(ax, 24, 33, 44, 6, "MCP server: approved tools, read-only, user's access rights", blue, fs=9, fc=blue)
    _arrow(ax, (46, 45.4), (46, 39.6), style="<|-|>", text="")
    ax.text(47.5, 42, "2 call tools  /  4 results + sources", fontsize=8, color="#555", va="center")

    # row 3: tools
    tools = ["get_bid(id)\nfull 360° record", "find_similar_bids()\ncomparable past bids",
             "get_win_score(id)\nwin probability", "search_documents()\nRAG over text"]
    for i, t in enumerate(tools):
        x = 6 + i * 22
        _node(ax, x, 19, 20, 7, t, blue, fs=8.5)
        _arrow(ax, (46, 32.6), (x + 10, 26.6), color="#777")
        _arrow(ax, (x + 10, 18.4), (x + 10, 11.2), color="#777")
    ax.text(31, 14.6, "3 SQL", fontsize=8, color="#555")
    ax.text(83, 14.6, "3 vector search", fontsize=8, color="#555")

    # row 4: Snowflake
    ax.add_patch(FancyBboxPatch((3, 1), 94, 11, boxstyle="round,pad=0.4", fc="#eaf7fd", ec=sf, lw=2))
    _node(ax, 6, 3, 42, 6.5, "GOLD layer: Bid 360 tables (SQL views)", "#d4a017", fs=8.5)
    _node(ax, 50, 3, 20, 6.5, "Win scores\n(ML output in Gold)", "#d4a017", fs=8.5)
    _node(ax, 72, 3, 20, 6.5, "Document index\n(specs, past proposals)", "#d4a017", fs=8.5)
    ax.text(50, 11.6, "Snowflake", ha="center", fontsize=9, fontweight="bold", color="#1b6f8a")

    ax.set_title("AI Bid Assistant - retrieving governed data with MCP and RAG", fontsize=13, fontweight="bold")
    fig.tight_layout(); fig.savefig(OUT / "ai_assistant.png", dpi=150); plt.close(fig)


if __name__ == "__main__":
    draw_data_model()
    draw_current()
    draw_future()
    draw_ai_assistant()
    print("diagrams written to", OUT)
