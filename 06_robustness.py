"""Robustness checks for the main result (2 km blocks, XGBoost, 10-fold GroupKFold).

Run with the project environment:
    C:/data/wildfire-lidar/venv/Scripts/python.exe 06_robustness.py

Reads  C:/data/wildfire-lidar/k61884_samples.csv
Writes robustness.json next to this script.

Checks
1. Uncertainty of the gain from adding LiDAR structure: block bootstrap (resample 2 km blocks with
   replacement, 2,000 times) of out-of-fold R2 for the covariate-only and the full model.
2. Per-fold gain: the difference in R2 on each held-out fold (how many of 10 folds improve).
3. Sensitivity to the rh98 cleaning range.
"""
import json
from pathlib import Path

import numpy as np
import pandas as pd
from pyproj import Transformer
from sklearn.metrics import r2_score
from sklearn.model_selection import GroupKFold
from xgboost import XGBRegressor

HERE = Path(__file__).parent
SRC = Path("C:/data/wildfire-lidar/k61884_samples.csv")
SEED = 7
COV = ["ndvi_pre", "elevation", "slope"]
STR = ["rh98", "rh75", "rh50", "rh25", "cover", "pai"]
to_utm = Transformer.from_crs("EPSG:4326", "EPSG:32611", always_xy=True)


def model():
    return XGBRegressor(n_estimators=400, learning_rate=0.05, max_depth=4, subsample=0.8,
                        colsample_bytree=0.8, random_state=SEED, n_jobs=4)


def prepare(lo, hi):
    raw = pd.read_csv(SRC)
    df = raw[(raw["rh98"] >= lo) & (raw["rh98"] <= hi)].copy()
    df["x"], df["y"] = to_utm.transform(df["lon"].values, df["lat"].values)
    df["block"] = (np.floor(df["x"] / 2000).astype(int).astype(str) + "_" + np.floor(df["y"] / 2000).astype(int).astype(str))
    return df.reset_index(drop=True)


def oof(df, feats):
    X, y, g = df[feats].values, df["dnbr"].values, df["block"].values
    pred = np.zeros(len(df))
    fold = np.zeros(len(df), dtype=int)
    for k, (tr, te) in enumerate(GroupKFold(n_splits=10).split(X, y, g)):
        pred[te] = model().fit(X[tr], y[tr]).predict(X[te])
        fold[te] = k
    return pred, fold


out = {}

# ---- 1 and 2: main cleaning range ----------------------------------------------------
df = prepare(2, 60)
y = df["dnbr"].values
p_cov, fold = oof(df, COV)
p_all, _ = oof(df, COV + STR)
out["main"] = {
    "n": int(len(df)),
    "r2_covariates": float(r2_score(y, p_cov)),
    "r2_all": float(r2_score(y, p_all)),
    "gain": float(r2_score(y, p_all) - r2_score(y, p_cov)),
}
per_fold = []
for k in range(10):
    m = fold == k
    per_fold.append(float(r2_score(y[m], p_all[m]) - r2_score(y[m], p_cov[m])))
out["per_fold_gain"] = {
    "values": [round(v, 3) for v in per_fold],
    "folds_improved": int(sum(v > 0 for v in per_fold)),
    "mean": float(np.mean(per_fold)),
}

rng = np.random.default_rng(SEED)
blocks = df["block"].values
uniq = np.unique(blocks)
idx_by_block = {b: np.where(blocks == b)[0] for b in uniq}
gains, r2c, r2a = [], [], []
for _ in range(2000):
    pick = rng.choice(uniq, size=len(uniq), replace=True)
    idx = np.concatenate([idx_by_block[b] for b in pick])
    a, c = r2_score(y[idx], p_all[idx]), r2_score(y[idx], p_cov[idx])
    gains.append(a - c); r2a.append(a); r2c.append(c)
q = lambda v: [float(np.percentile(v, 2.5)), float(np.percentile(v, 97.5))]
out["bootstrap_95ci"] = {"gain": q(gains), "r2_all": q(r2a), "r2_covariates": q(r2c),
                         "share_of_resamples_with_positive_gain": float(np.mean(np.array(gains) > 0))}

# ---- 3: cleaning range sensitivity ---------------------------------------------------
sens = {}
for lo, hi in [(0, 1000), (2, 60), (5, 50), (2, 40)]:
    d = prepare(lo, hi)
    yy = d["dnbr"].values
    pc, _ = oof(d, COV)
    pa, _ = oof(d, COV + STR)
    sens[f"rh98_{lo}_to_{hi}"] = {"n": int(len(d)), "r2_covariates": float(r2_score(yy, pc)),
                                  "r2_all": float(r2_score(yy, pa)),
                                  "gain": float(r2_score(yy, pa) - r2_score(yy, pc))}
out["cleaning_sensitivity"] = sens

(HERE / "robustness.json").write_text(json.dumps(out, indent=2), encoding="utf-8")
print(json.dumps(out, indent=2))
