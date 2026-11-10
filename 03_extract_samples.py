"""Join pre-fire GEDI forest structure to burn severity (dNBR) for fire K61884 (2021).

Run with the project environment:
    C:/data/wildfire-lidar/venv/Scripts/python.exe 03_extract_samples.py

Output: C:/data/wildfire-lidar/k61884_samples.csv (one row per sampled GEDI pixel)

Design notes
- Burn severity: dNBR = NBR(pre) - NBR(post) from Sentinel-2 L2A, cloud-masked with the scene
  classification layer. Pre = July to September 2020. Post = July to September 2022, the
  following growing season (extended assessment).
- GEDI: L2A relative height (rh98, rh75, rh50, rh25) and L2B canopy cover and plant area
  index, taken from the monthly 25 m rasters between 18 April 2019 and the fire date. Shots are
  kept only where the quality flag is 1 and the degrade flag is 0. Where several months cover
  the same pixel, the per-pixel median is used.
- Forest filter: ESA WorldCover 2020 class 10 (tree cover).
- Covariates: pre-fire NDVI, elevation and slope (NASADEM).
"""
import csv
import os
import sys
from pathlib import Path

import ee
import geopandas as gpd

PROJECT = os.environ.get("EE_PROJECT", "your-earth-engine-project-id")
FIRE = "K61884"
FIRES_FILE = Path("C:/data/wildfire-lidar/south.json")
OUT = Path("C:/data/wildfire-lidar/k61884_samples.csv")
GEDI_START = "2019-04-18"
CHUNKS = 8
PER_CHUNK_TARGET = 4000  # stays under the 5000-row limit of getInfo

ee.Initialize(project=PROJECT)

fire = gpd.read_file(FIRES_FILE)
fire = fire[(fire["FIRE_NUMBER"] == FIRE) & (fire["FIRE_YEAR"] == 2021)].iloc[[0]].copy()
fire_date = str(fire["FIRE_DATE"].iloc[0])[:10]
fire["geometry"] = fire.geometry.simplify(0.001)
geom = ee.Geometry(fire.geometry.iloc[0].__geo_interface__)
print("fire", FIRE, "date", fire_date, file=sys.stderr)


# ---- Sentinel-2 burn severity -------------------------------------------------
def s2_composite(start, end):
    def mask(img):
        scl = img.select("SCL")
        clear = scl.neq(3).And(scl.neq(8)).And(scl.neq(9)).And(scl.neq(10)).And(scl.neq(11))
        return img.updateMask(clear)

    return (
        ee.ImageCollection("COPERNICUS/S2_SR_HARMONIZED")
        .filterBounds(geom)
        .filterDate(start, end)
        .filter(ee.Filter.lt("CLOUDY_PIXEL_PERCENTAGE", 40))
        .map(mask)
        .median()
    )


def nbr(img):
    return img.normalizedDifference(["B8", "B12"]).rename("nbr")


pre = s2_composite("2020-07-01", "2020-09-16")
post = s2_composite("2022-07-01", "2022-09-16")
dnbr = nbr(pre).subtract(nbr(post)).rename("dnbr")
ndvi_pre = pre.normalizedDifference(["B8", "B4"]).rename("ndvi_pre")

# ---- GEDI structure -----------------------------------------------------------
def a_good(img):
    ok = img.select("quality_flag").eq(1).And(img.select("degrade_flag").eq(0))
    return img.select(["rh98", "rh75", "rh50", "rh25"]).updateMask(ok)


def b_good(img):
    ok = img.select("l2b_quality_flag").eq(1).And(img.select("degrade_flag").eq(0))
    return img.select(["cover", "pai"]).updateMask(ok)


gedi_a = (
    ee.ImageCollection("LARSE/GEDI/GEDI02_A_002_MONTHLY")
    .filterBounds(geom).filterDate(GEDI_START, fire_date).map(a_good).median()
)
gedi_b = (
    ee.ImageCollection("LARSE/GEDI/GEDI02_B_002_MONTHLY")
    .filterBounds(geom).filterDate(GEDI_START, fire_date).map(b_good).median()
)

# ---- Covariates and forest mask --------------------------------------------------
dem = ee.Image("NASA/NASADEM_HGT/001").select("elevation")
slope = ee.Terrain.slope(dem).rename("slope")
forest = ee.Image("ESA/WorldCover/v100/2020").select("Map").eq(10)

stack = (
    gedi_a.addBands(gedi_b).addBands(dnbr).addBands(ndvi_pre)
    .addBands(dem.rename("elevation")).addBands(slope)
    .updateMask(forest)
)
# Keep only pixels that have a GEDI shot and a valid dNBR.
stack = stack.updateMask(stack.select(["rh98", "cover", "dnbr"]).mask().reduce(ee.Reducer.min()))

samples = stack.sample(
    region=geom, scale=25, numPixels=CHUNKS * PER_CHUNK_TARGET * 2, seed=7,
    geometries=True, tileScale=8,
).randomColumn("rnd", 7)

rows = []
for i in range(CHUNKS):
    lo, hi = i / CHUNKS, (i + 1) / CHUNKS
    part = samples.filter(ee.Filter.And(ee.Filter.gte("rnd", lo), ee.Filter.lt("rnd", hi)))
    feats = part.getInfo()["features"]
    for f in feats:
        p = dict(f["properties"])
        lon, lat = f["geometry"]["coordinates"]
        p.pop("rnd", None)
        p["lon"], p["lat"] = lon, lat
        rows.append(p)
    print("chunk", i, "rows so far", len(rows), file=sys.stderr, flush=True)

if not rows:
    sys.exit("no samples returned")
fields = sorted({k for r in rows for k in r})
with OUT.open("w", newline="") as fh:
    w = csv.DictWriter(fh, fieldnames=fields)
    w.writeheader()
    w.writerows(rows)
print("wrote", len(rows), "rows to", OUT, file=sys.stderr)
