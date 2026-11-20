"""
Train and evaluate models that predict bid success (win_loss).

Approach (simple -> stronger):
  1. Dummy baseline      - always predicts the most common outcome ("win").
  2. Logistic Regression - simple, interpretable linear model.
  3. Random Forest       - many decision trees voting; handles non-linear effects.
  4. Gradient Boosting   - trees built one after another, each fixing earlier errors.

Evaluation: 80/20 stratified split. Models are compared with 5-fold
cross-validation on the 80 %, and the winner is tested once on the untouched 20 %.
"""
import json

import joblib
import matplotlib
import pandas as pd
from sklearn.dummy import DummyClassifier
from sklearn.ensemble import HistGradientBoostingClassifier, RandomForestClassifier
from sklearn.inspection import permutation_importance
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (ConfusionMatrixDisplay, accuracy_score, f1_score,
                             precision_score, recall_score, roc_auc_score)
from sklearn.model_selection import StratifiedKFold, cross_validate, train_test_split
from sklearn.pipeline import Pipeline

from src import config
from src.features import build_preprocessor

matplotlib.use("Agg")  # draw charts to files, no window needed
import matplotlib.pyplot as plt  # noqa: E402

SCORING = ["roc_auc", "accuracy", "precision", "recall", "f1"]  # metrics measured in cross-validation


def get_models() -> dict:
    rs = config.RANDOM_STATE  # fixed seed -> same result every run
    return {
        "Dummy baseline": DummyClassifier(strategy="most_frequent"),                 # always says "win"
        "Logistic Regression": LogisticRegression(max_iter=2000, C=1.0),             # weighted sum -> probability
        "Random Forest": RandomForestClassifier(n_estimators=400, min_samples_leaf=5,  # 400 voting trees
                                                random_state=rs, n_jobs=-1),
        "Gradient Boosting": HistGradientBoostingClassifier(learning_rate=0.05, max_iter=300,  # trees fixing errors
                                                            max_leaf_nodes=15, l2_regularization=1.0,
                                                            random_state=rs),
    }


def make_pipeline(model) -> Pipeline:
    return Pipeline([("prep", build_preprocessor()), ("model", model)])  # preprocessing + model always together


def split_data(X, y):
    # 80 % train / 20 % locked test set, same win/loss mix in both
    return train_test_split(X, y, test_size=0.2, stratify=y, random_state=config.RANDOM_STATE)


def cross_validate_models(X_train, y_train) -> pd.DataFrame:
    cv = StratifiedKFold(n_splits=5, shuffle=True, random_state=config.RANDOM_STATE)  # 5 fair practice rounds
    rows = []
    for name, model in get_models().items():
        res = cross_validate(make_pipeline(model), X_train, y_train, cv=cv, scoring=SCORING)  # train + score 5x
        row = {"model": name}
        for m in SCORING:
            row[m] = round(res[f"test_{m}"].mean(), 3)          # average over the 5 rounds
            row[f"{m}_std"] = round(res[f"test_{m}"].std(), 3)  # how stable across rounds
        rows.append(row)
    return pd.DataFrame(rows).sort_values("roc_auc", ascending=False).reset_index(drop=True)  # best first


def evaluate_on_test(pipe, X_test, y_test) -> dict:
    proba = pipe.predict_proba(X_test)[:, 1]  # win probability for each test bid
    pred = (proba >= 0.5).astype(int)         # >= 50 % counts as "win"
    return {
        "roc_auc": round(roc_auc_score(y_test, proba), 3),       # ranking quality
        "accuracy": round(accuracy_score(y_test, pred), 3),      # share correct
        "precision": round(precision_score(y_test, pred), 3),    # when it says win, how often right
        "recall": round(recall_score(y_test, pred), 3),          # of real wins, how many found
        "f1": round(f1_score(y_test, pred), 3),                  # balance of precision and recall
        "test_rows": int(len(y_test)),
        "test_win_rate": round(float(y_test.mean()), 3),
    }


def explain_model(pipe, X_test, y_test) -> pd.DataFrame:
    """
    Permutation importance: shuffle one input column and measure how much
    ROC-AUC drops. Big drop = the model relies on that column.
    Works on the original business columns, so it is easy to explain.
    """
    r = permutation_importance(pipe, X_test, y_test, scoring="roc_auc", n_repeats=20,  # shuffle each column 20x
                               random_state=config.RANDOM_STATE, n_jobs=-1)
    return (pd.DataFrame({"feature": X_test.columns, "importance": r.importances_mean,
                          "std": r.importances_std})
            .sort_values("importance", ascending=False).reset_index(drop=True))  # most important first


def save_figures(pipes: dict, best_name, X_test, y_test, importance):
    out = config.FIGURES_DIR
    out.mkdir(parents=True, exist_ok=True)

    # Confusion matrix of the chosen model
    fig, ax = plt.subplots(figsize=(4.5, 4))
    ConfusionMatrixDisplay.from_estimator(pipes[best_name], X_test, y_test, ax=ax,
                                          display_labels=["Lost", "Won"], cmap="Blues", colorbar=False)
    ax.set_title(f"Confusion matrix - {best_name}")
    fig.tight_layout(); fig.savefig(out / "ml_confusion_matrix.png", dpi=150); plt.close(fig)

    # Top 12 drivers
    top = importance.head(12).iloc[::-1]
    fig, ax = plt.subplots(figsize=(6.5, 5))
    ax.barh(top["feature"], top["importance"], xerr=top["std"], color="#2a7f8e")
    ax.set_xlabel("Drop in ROC-AUC when feature is shuffled")
    ax.set_title(f"What drives a win? - {best_name}")
    fig.tight_layout(); fig.savefig(out / "ml_feature_importance.png", dpi=150); plt.close(fig)


def run(X, y) -> dict:
    X_train, X_test, y_train, y_test = split_data(X, y)  # lock away the test set first

    cv_table = cross_validate_models(X_train, y_train)                                  # compare 4 models
    best_name = cv_table.loc[cv_table["model"] != "Dummy baseline", "model"].iloc[0]   # best real model

    # train the 3 real models on all training data, then test once
    pipes = {name: make_pipeline(m).fit(X_train, y_train) for name, m in get_models().items()
             if name != "Dummy baseline"}
    test_results = {name: evaluate_on_test(p, X_test, y_test) for name, p in pipes.items()}
    importance = explain_model(pipes[best_name], X_test, y_test)  # what drives the chosen model
    save_figures(pipes, best_name, X_test, y_test, importance)

    # save results and the chosen model
    config.PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
    joblib.dump(pipes[best_name], config.PROCESSED_DIR / "win_model.joblib")
    cv_table.to_csv(config.PROCESSED_DIR / "ml_cv_results.csv", index=False)
    importance.to_csv(config.PROCESSED_DIR / "ml_feature_importance.csv", index=False)
    summary = {"best_model": best_name, "train_rows": len(X_train), "test": test_results}
    (config.PROCESSED_DIR / "ml_test_results.json").write_text(json.dumps(summary, indent=2))

    return {"cv": cv_table, "best": best_name, "test": test_results, "importance": importance}
