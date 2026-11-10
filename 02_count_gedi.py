"""Count good-quality GEDI L2A shots (monthly raster, one pixel per shot) inside each candidate fire, collected before the fire date.

Run with the project environment:
    C:/data/wildfire-lidar/venv/Scripts/python.exe 02_count_gedi.py

Inputs: C:/data/wildfire-lidar/south.json (fire polygons from the BC Data Catalogue)
Output: gedi_counts.csv next to this script
"""
import csv
import os
import sys
from pathlib import Path

import ee
import geopandas as gpd

PROJECT = os.environ.get("EE_PROJECT", "your-earth-engine-project-id")
FIRES_FILE = Path("C:/data/wildfire-lidar/south.json")
OUT = Path(__file__).with_name("gedi_counts.csv")
GEDI_START = "2019-04-18"
SIMPLIFY_DEG = 0.001  # about 100 m, keeps the Earth Engine request small

ee.Initialize(project=PROJECT)

fires = gpd.read_file(FIRES_FILE)
fires = fires[fires["FIRE_SIZE_HECTARES"] > 1000].copy()
fires["geometry"] = fires.geometry.simplify(SIMPLIFY_DEG)

# Monthly 25 m rasters of GEDI L2A shots (one pixel per shot), with quality bands.
gedi = ee.ImageCollection("LARSE/GEDI/GEDI02_A_002_MONTHLY")


def good_shots(img):
    ok = img.select("quality_flag").eq(1).And(img.select("degrade_flag").eq(0))
    return img.select("rh98").updateMask(ok)


rows = []
for _, fire in fires.iterrows():
    fire_date = str(fire["FIRE_DATE"])[:10]
    geom = ee.Geometry(fire.geometry.__geo_interface__)
    shots = gedi.filterBounds(geom).filterDate(GEDI_START, fire_date).map(good_shots)
    try:
        # Sum, over months, of the number of valid shot pixels inside the fire.
        n = (
            shots.map(lambda im: im.mask().rename("n").toInt())
            .sum()
            .reduceRegion(ee.Reducer.sum(), geom, scale=25, maxPixels=int(1e10), tileScale=8)
            .get("n")
            .getInfo()
        )
    except Exception as exc:  # report and carry on with the other fires
        n = f"error: {str(exc)[:80]}"
    row = {
        "fire": fire["FIRE_NUMBER"],
        "year": int(fire["FIRE_YEAR"]),
        "fire_date": fire_date,
        "area_ha": round(float(fire["FIRE_SIZE_HECTARES"])),
        "good_pre_fire_shots": n,
    }
    rows.append(row)
    print(row, flush=True)

with OUT.open("w", newline="") as fh:
    writer = csv.DictWriter(fh, fieldnames=list(rows[0]))
    writer.writeheader()
    writer.writerows(rows)
print("wrote", OUT, file=sys.stderr)
