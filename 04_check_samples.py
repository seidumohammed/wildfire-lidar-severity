"""Basic checks on the extracted sample table, written to a text file for the record.

Run with the project environment:
    C:/data/wildfire-lidar/venv/Scripts/python.exe 04_check_samples.py

Reads C:/data/wildfire-lidar/k61884_samples.csv and writes sample_check.txt next to this script.
"""
from pathlib import Path

import pandas as pd

SRC = Path("C:/data/wildfire-lidar/k61884_samples.csv")
OUT = Path(__file__).with_name("sample_check.txt")

df = pd.read_csv(SRC)
lines = []
add = lines.append

add(f"rows: {len(df)}")
add(f"columns: {', '.join(df.columns)}")
add("")
add("missing values per column:")
add(df.isna().sum().to_string())
add("")
add("summary statistics:")
add(df.describe().round(3).T.to_string())
add("")

# dNBR classes (USGS / Key and Benson style thresholds, used only to describe the spread).
bins = [-10, -0.1, 0.1, 0.27, 0.44, 0.66, 10]
labels = ["enhanced regrowth", "unburned", "low severity", "moderate-low", "moderate-high", "high"]
cls = pd.cut(df["dnbr"], bins=bins, labels=labels)
add("share of samples by dNBR class:")
add((cls.value_counts(normalize=True).sort_index() * 100).round(1).to_string())
add("")

num = df.select_dtypes("number").drop(columns=["lon", "lat"], errors="ignore")
add("Spearman correlation with dNBR:")
add(num.corr(method="spearman")["dnbr"].drop("dnbr").round(3).sort_values().to_string())
add("")

dup = df.duplicated(subset=["lon", "lat"]).sum()
add(f"duplicate coordinates: {dup}")

OUT.write_text("\n".join(lines), encoding="utf-8")
print("\n".join(lines))
