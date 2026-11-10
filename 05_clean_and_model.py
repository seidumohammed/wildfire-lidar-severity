"""Clean the sample table, validate on spatial blocks, fit models, and attribute with SHAP.

Run with the project environment:
    C:/data/wildfire-lidar/venv/Scripts/python.exe 05_clean_and_model.py

Reads  C:/data/wildfire-lidar/k61884_samples.csv
Writes results.json, figures/*.png and cleaned_samples.csv next to this script.

Question: do pre-fire forest structure measures from GEDI explain burn severity (dNBR) beyond
terrain and pre-fire greenness?

Feature sets
    covariates : pre-fire NDVI, elevation, slope
    structure  : rh98, rh75, rh50, rh25, canopy cover, plant area index
    all        : covariates + structure

Validation: GroupKFold on whole spatial blocks (block size set in BLOCK_KM). Block sizes of 1, 2
and 5 km are all run, because nearby shots are alike and a small block can still leak.
"""
import json
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import shap
from pyproj import Transformer
from sklearn.ensemble import RandomForestRegressor
from sklearn.metrics import mean_squared_error, r2_score
from sklearn.model_selection import GroupKFold
from xgboost import XGBRegressor

HERE = Path(__file__).parent
SRC = Path("C:/data/wildfire-lidar/k61884_samples.csv")
FIG = HERE / "figures"
FIG.mkdir(exist_ok=True)
SEED = 7
N_FOLDS = 10
BLOCK_KM = [1, 2, 5]
MAIN_BLOCK_KM = 2

COVARIATES = ["ndvi_pre", "elevation", "slope"]
STRUCTURE = ["rh98", "rh75", "rh50", "rh25", "cover", "pai"]
SETS = {"covariates": COVARIATES, "structure": STRUCTURE, "all": COVARIATES + STRUCTURE}

# ---- cleaning ----------------------------------------------------------------------
raw = pd.read_csv(SRC)
df = raw[(raw["rh98"] >= 2) & (raw["rh98"] <= 60)].copy()
clean_log = {
    "rows_raw": int(len(raw)),
    "rows_after_rh98_2_to_60": int(len(df)),
    "rows_dropped": int(len(raw) - len(df)),
}
# Project to UTM zone 11N (EPSG:32611) so blocks are in metres.
to_utm = Transformer.from_crs("EPSG:4326", "EPSG:32611", always_xy=True)
df["x"], df["y"] = to_utm.transform(df["lon"].values, df["lat"].values)
df.to_csv(HERE / "cleaned_samples.csv", index=False)


def blocks(km):
    size = km * 1000
    return (np.floor(df["x"] / size).astype(int).astype(str) + "_" + np.floor(df["y"] / size).astype(int).astype(str)).values


def make_models():
    return {
        "random_forest": RandomForestRegressor(
            n_estimators=300, min_samples_leaf=5, n_jobs=-1, random_state=SEED
        ),
        "xgboost": XGBRegressor(
            n_estimators=400, learning_rate=0.05, max_depth=4, subsample=0.8,
            colsample_bytree=0.8, random_state=SEED, n_jobs=4,
        ),
    }


def cv_scores(features, groups):
    """Out-of-fold predictions for each model and a mean baseline."""
    X, y = df[features].values, df["dnbr"].values
    out = {m: np.zeros(len(df)) for m in ["baseline", "random_forest", "xgboost"]}
    for tr, te in GroupKFold(n_splits=N_FOLDS).split(X, y, groups):
        out["baseline"][te] = y[tr].mean()
        for name, model in make_models().items():
            model.fit(X[tr], y[tr])
            out[name][te] = model.predict(X[te])
    y_all = df["dnbr"].values
    return {
        m: {
            "r2": float(r2_score(y_all, p)),
            "rmse": float(np.sqrt(mean_squared_error(y_all, p))),
        }
        for m, p in out.items()
    }


results = {"cleaning": clean_log, "n_blocks": {}, "scores": {}}
for km in BLOCK_KM:
    g = blocks(km)
    results["n_blocks"][f"{km}km"] = int(len(set(g)))
    results["scores"][f"{km}km"] = {name: cv_scores(f, g) for name, f in SETS.items()}
    print(km, "km done", flush=True)

# Random (non-spatial) K-fold for contrast: shows how much random splits overstate accuracy.
rng = np.random.default_rng(SEED)
random_groups = rng.integers(0, 10**9, len(df)).astype(str)
results["scores"]["random_split"] = {name: cv_scores(f, random_groups) for name, f in SETS.items()}

# ---- SHAP on held-out folds (all features, XGBoost, main block size) --------------------
g_main = blocks(MAIN_BLOCK_KM)
X_all, y_all = df[SETS["all"]].values, df["dnbr"].values
shap_vals = np.zeros_like(X_all, dtype=float)
for tr, te in GroupKFold(n_splits=N_FOLDS).split(X_all, y_all, g_main):
    m = make_models()["xgboost"].fit(X_all[tr], y_all[tr])
    shap_vals[te] = shap.TreeExplainer(m).shap_values(X_all[te])

imp = pd.Series(np.abs(shap_vals).mean(axis=0), index=SETS["all"]).sort_values(ascending=False)
results["shap_mean_abs"] = {k: float(v) for k, v in imp.items()}

# Permutation-free check of the structure-only contribution: drop in R2 from adding structure.
sc = results["scores"][f"{MAIN_BLOCK_KM}km"]
results["structure_gain_r2_xgboost"] = float(sc["all"]["xgboost"]["r2"] - sc["covariates"]["xgboost"]["r2"])

# Correlation among structure predictors, for the log.
results["structure_spearman"] = df[STRUCTURE].corr(method="spearman").round(3).to_dict()

(HERE / "results.json").write_text(json.dumps(results, indent=2), encoding="utf-8")

# ---- figures ---------------------------------------------------------------------------
fig, ax = plt.subplots(figsize=(6, 4))
imp.sort_values().plot.barh(ax=ax, color="#2a6f97")
ax.set_xlabel("Mean |SHAP| (change in predicted dNBR), out-of-fold")
ax.set_title("Which factors the model relies on")
fig.tight_layout()
fig.savefig(FIG / "shap_importance.png", dpi=200)
plt.close(fig)

fig, ax = plt.subplots(figsize=(6, 4))
labels, vals = [], []
for km in BLOCK_KM:
    for name in SETS:
        labels.append(f"{km} km\n{name}")
        vals.append(results["scores"][f"{km}km"][name]["xgboost"]["r2"])
labels += [f"random\n{n}" for n in SETS]
vals += [results["scores"]["random_split"][n]["xgboost"]["r2"] for n in SETS]
ax.bar(range(len(vals)), vals, color="#2a6f97")
ax.set_xticks(range(len(vals)))
ax.set_xticklabels(labels, fontsize=6)
ax.axhline(0, color="k", lw=0.5)
ax.set_ylabel("Out-of-fold R2 (XGBoost)")
ax.set_title("Validation by split type and feature set")
fig.tight_layout()
fig.savefig(FIG / "validation_r2.png", dpi=200)
plt.close(fig)

fig, ax = plt.subplots(figsize=(6, 6))
sc_ = ax.scatter(df["lon"], df["lat"], c=df["dnbr"], s=4, cmap="inferno", vmin=0, vmax=1)
fig.colorbar(sc_, ax=ax, label="dNBR")
ax.set_xlabel("Longitude")
ax.set_ylabel("Latitude")
ax.set_title("Sampled GEDI shots by burn severity")
fig.tight_layout()
fig.savefig(FIG / "sample_map.png", dpi=200)
plt.close(fig)

print(json.dumps({k: results[k] for k in ["cleaning", "n_blocks", "shap_mean_abs", "structure_gain_r2_xgboost"]}, indent=2))
for k, v in results["scores"].items():
    print(k, {n: {m: round(x["r2"], 3) for m, x in d.items()} for n, d in v.items()})
