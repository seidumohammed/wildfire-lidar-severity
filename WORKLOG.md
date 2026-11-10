# Work log

Project: pre-fire forest structure and burn severity, fire K61884 (British Columbia, 2021).
This file records what was done, why, with which settings, what went wrong, and what is still uncertain. New entries go at the bottom. Dates are the dates the work was done.

## Environment

- Python 3.12.10 in a virtual environment at `C:\data\wildfire-lidar\venv` (outside OneDrive, about 2 GB).
- Package versions are in `requirements.txt` (earthengine-api 1.7.52, geopandas 1.2.0, rasterio 1.5.2, scikit-learn 1.9.1, XGBoost 3.4.1, SHAP 0.54.1, pandas 3.1.1, numpy 2.5.4).
- Google Earth Engine project: set with the `EE_PROJECT` environment variable. Authentication was done once by the account owner with `earthengine authenticate`. No credentials are stored in this folder.
- Data folder: `C:\data\wildfire-lidar` (fire query results and the sample table). Large files stay out of OneDrive.
- Free disk space on C: was 13.7 GB at the start. The Earth Engine route downloads only small tables.

## Entry 1: 2026-11-10 | Choosing the study fire

**Aim:** pick one large British Columbia wildfire with enough pre-fire GEDI LiDAR shots.

**Steps**
1. Queried the BC Data Catalogue web feature service (layer `WHSE_LAND_AND_NATURAL_RESOURCE.PROT_HISTORICAL_FIRE_POLYS_SP`) for fires from 2020 onward larger than 30,000 ha. The first requests returned empty or error responses. The cause was the server, which reported a temporary database connection timeout. Repeating the request later worked.
2. Found that GEDI observes only up to about 51.6 degrees north. This rules out northern fires, so candidates were filtered by their latitude range. Fires G41307, G51279 and R91162 lie far north and were excluded. C41602 reaches 51.67 N and was set aside as being at the edge of coverage.
3. Wrote `02_count_gedi.py` to count good-quality GEDI shots inside each remaining fire before the fire date.

**Problems and fixes**
- The first version of the counting script treated `LARSE/GEDI/GEDI02_A_002` as a table. Earth Engine reported that the asset is not a table collection. The script now uses the monthly raster `LARSE/GEDI/GEDI02_A_002_MONTHLY`, where each pixel is one 25 m shot.
- Two northern fires returned no data, which is expected.

**Settings:** GEDI from 2019-04-18 to the fire date; keep shots with `quality_flag` = 1 and `degrade_flag` = 0; polygons simplified to about 100 m (0.001 degrees); sums at 25 m.

**Result:** about 190,000 to 235,000 good shots for the main 2021 candidates (full table in `01_select_fire.md`, raw output in `gedi_counts.csv`). Counts include all land cover and are approximate because pixel sums at polygon edges are fractional.

**Decision:** K61884 (2021, 83,046 ha, latitude 50.15 to 50.57 N, fire date 2021-07-12). Reasons: large, large GEDI sample (about 225,000 shots), well inside the GEDI latitude range. K21001 had slightly more shots but sits closer to the edge. K52125 (2023) is the backup if more years of pre-fire GEDI data are wanted.

## Entry 2: 2026-11-10 | Joining GEDI structure to burn severity

**Aim:** build a table with one row per sampled GEDI pixel, with forest structure measures and burn severity.

**Script:** `03_extract_samples.py`. Output: `C:\data\wildfire-lidar\k61884_samples.csv`.

**Burn severity**
- dNBR = NBR(pre-fire) minus NBR(post-fire), with NBR = (B8 - B12) / (B8 + B12), from Sentinel-2 L2A (`COPERNICUS/S2_SR_HARMONIZED`).
- Pre-fire composite: 1 July to 16 September 2020 (median). Post-fire composite: 1 July to 16 September 2022 (median), the growing season after the fire (extended assessment).
- Cloud masking with the scene classification layer (removed classes 3, 8, 9, 10, 11) and a scene cloud limit of 40 percent.

**GEDI structure**
- L2A: `rh98`, `rh75`, `rh50`, `rh25` (relative height metrics, metres). Kept where `quality_flag` = 1 and `degrade_flag` = 0.
- L2B: `cover` (canopy cover) and `pai` (plant area index). Kept where `l2b_quality_flag` = 1 and `degrade_flag` = 0.
- Period: 2019-04-18 to the fire date. Where several months cover the same pixel, the per-pixel median is used.

**Covariates and filters**
- Pre-fire NDVI (Sentinel-2, same pre-fire composite).
- Elevation and slope from NASADEM (`NASA/NASADEM_HGT/001`).
- Forest filter: ESA WorldCover 2020 class 10 (tree cover). Only pixels with a valid GEDI value and a valid dNBR are kept.

**Sampling:** 25 m scale, random seed 7, up to about 64,000 requested, returned in 8 chunks to stay within the Earth Engine 5,000-row limit per request. The request returned **5,858 rows** (the stack was masked heavily by the quality filters and forest mask).

## Entry 3: 2026-11-10 | Checking the sample table

**Script:** `04_check_samples.py`. Full output saved in `sample_check.txt`.

**Findings**
- 5,858 rows, no missing values, no duplicate coordinates.
- Latitude 50.15 to 50.57 N and longitude -120.09 to -119.34 W, as expected for the fire.
- dNBR ranges from -0.34 to 1.19 with mean 0.38. Share of samples by class: unburned 17.4 percent, low 22.4, moderate-low 20.0, moderate-high 22.5, high 17.3, enhanced regrowth 0.5. All severity classes are present, which suits the question.
- Spearman correlation with dNBR: rh98 0.26, rh75 0.25, rh50 0.23, canopy cover 0.20, PAI 0.20, rh25 0.20, elevation 0.17, slope 0.11, pre-fire NDVI 0.08. These are only first-look associations. They are not tested for spatial dependence and are not results.

**Data problems found (to fix before modelling)**
- `rh98` has a maximum of 93.2 m. This is not a realistic tree height in this region and is probably noise or a bad waveform.
- Several relative height values are negative (for example `rh25` as low as -4.9 m). GEDI relative heights can fall slightly below zero from ground detection error, but extreme values should be handled by a stated rule.
- Rule to apply next: drop shots with `rh98` above 60 m or below 2 m, and check the effect of this choice in a sensitivity run. The thresholds are provisional and will be reported.

## Entry 4: 2026-11-10 | Cleaning, spatial validation, models and SHAP

**Script:** `05_clean_and_model.py`. Outputs: `results.json`, `cleaned_samples.csv`, `figures/shap_importance.png`, `figures/validation_r2.png`, `figures/sample_map.png`.

**Cleaning rule (stated before modelling):** keep shots with rh98 from 2 m to 60 m. This dropped 10 of 5,858 rows (5,848 kept). The thresholds are provisional. A sensitivity run with other thresholds is still to do.

**Validation design**
- Coordinates projected to UTM zone 11N (EPSG:32611). Whole spatial blocks go to training or test with 10-fold GroupKFold.
- Block sizes 1, 2 and 5 km (911, 269 and 57 blocks). The 2 km result is the main one. A random (non-spatial) split is run for contrast.
- Feature sets: covariates (pre-fire NDVI, elevation, slope), structure (rh98, rh75, rh50, rh25, canopy cover, plant area index), and all.
- Models: random forest (300 trees, min leaf 5) and XGBoost (400 trees, depth 4, learning rate 0.05, subsample 0.8), plus a mean-only baseline. Random seed 7. Hyperparameters were fixed in advance and not tuned on the test blocks.
- SHAP (TreeSHAP) computed on held-out folds only (XGBoost, all features, 2 km blocks).

**Results (out-of-fold R2, XGBoost; random forest is within about 0.01 to 0.02)**

| Split | Covariates only | Structure only | All features |
|---|---|---|---|
| 1 km blocks | 0.160 | 0.049 | 0.234 |
| 2 km blocks (main) | 0.150 | 0.054 | 0.219 |
| 5 km blocks | 0.130 | 0.024 | 0.196 |
| Random split | 0.189 | 0.066 | 0.255 |

- The mean baseline scored R2 near 0 (-0.02 to 0.00), as it should.
- Adding LiDAR structure to terrain and pre-fire greenness raised R2 by 0.069 (2 km blocks): 0.150 to 0.219.
- Random splits scored higher than spatial blocks (for example 0.255 against 0.219 for all features), which is the inflation that spatial validation avoids. Scores fall as blocks get larger.
- SHAP mean absolute contribution to predicted dNBR: elevation 0.062, pre-fire NDVI 0.050, rh98 0.039, rh50 0.025, slope 0.023, rh75 0.015, rh25 0.014, canopy cover 0.009, plant area index 0.008.

**What this does and does not show**
- Forest structure carries some information about burn severity, with canopy height (rh98) the strongest structure measure, but the model explains only about a fifth of the variation. Most of the variation is unexplained. The model has no fire weather, fuel moisture, fire progression or suppression data, all of which strongly affect severity.
- SHAP rankings describe the fitted model and not causes. The predictors are correlated (the height metrics move together), so credit is shared between them.
- Results are for one fire and one sample of GEDI shots. They are preliminary and unvalidated against field severity.

**Next steps:** sensitivity to the cleaning thresholds and to the post-fire window; add fire-progression or weather covariates if available; repeat on a second fire (for example K21001 or K52125) to see whether the ranking holds; publish the code and log to GitHub.

## Known limits (carry into the write-up)

- GEDI samples sparsely along tracks. This is a sampled analysis, not a wall-to-wall LiDAR map.
- Footprint geolocation error and the 25 m raster product add noise to the match with dNBR.
- A median over months blends shots from different dates at the same pixel. L2A and L2B medians are taken separately, so a pixel's height and cover may come from different shots.
- dNBR from Sentinel-2 is not validated against field severity, and one post-fire year may include early regrowth.
- Spatial dependence between nearby GEDI shots is strong, so models must be validated on spatial blocks and not on random splits.
- WorldCover 2020 is a land cover map. Some pixels labelled as trees may be sparse or partly burned already by earlier disturbance.

## Next steps

1. Sensitivity runs: cleaning thresholds and post-fire window.
2. Add fire weather or progression covariates if they can be sourced.
3. Repeat on a second fire.
4. Publish code and log to GitHub, then write up methods, results and limits.

## Files

| File | Purpose |
|---|---|
| `README.md` | Project question, method, layout |
| `01_select_fire.md` | Candidate fires, GEDI counts, the choice |
| `02_count_gedi.py` | Counts GEDI shots per fire (`gedi_counts.csv`) |
| `03_extract_samples.py` | Builds the GEDI and dNBR sample table |
| `04_check_samples.py` | Checks the table (`sample_check.txt`) |
| `requirements.txt` | Package versions |
| `05_clean_and_model.py` | Cleaning, spatial block validation, models, SHAP (`results.json`, `figures/`) |
| `WORKLOG.md` | This log |
