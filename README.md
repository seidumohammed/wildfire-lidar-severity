# Pre-fire forest structure and burn severity in British Columbia

Status: preliminary results for fire K61884 (2021). With 2 km spatial block validation, adding GEDI forest structure to terrain and pre-fire NDVI raised out-of-fold R2 for dNBR from 0.15 to 0.22 (XGBoost, 5,848 samples). Most variation is unexplained and nothing is validated in the field. See `WORKLOG.md` for every step, setting and caveat.

## Question

Which pre-fire forest structure measures (canopy height, canopy cover, vertical structure) explain how severely different parts of a British Columbia wildfire burned?

## Method (planned)

1. Select one fire. Fire polygons come from the BC Wildfire Service historical perimeters (BC Data Catalogue, layer PROT_HISTORICAL_FIRE_POLYS_SP).
2. Burn severity: pre-fire and post-fire NBR from Landsat or Sentinel-2 in Google Earth Engine, differenced to dNBR.
3. Forest structure: GEDI footprints collected before the fire (L2A relative height metrics, L2B canopy cover), filtered by quality flags.
4. Join GEDI footprints to dNBR. Add terrain and pre-fire NDVI as covariates.
5. Models: random forest and XGBoost, validated on whole spatial blocks. SHAP for attribution.
6. Report limits: sparse GEDI sampling, footprint geolocation error, dNBR not validated against field severity.

## Constraint that decides the study area

GEDI only observes up to about 51.6 degrees north. The fire must lie south of that line, so northern BC fires are excluded.

## Layout

- Code and notes: this folder (on OneDrive, small files only).
- Data and Python environment: `C:\data\wildfire-lidar` (outside OneDrive).
  - `venv\` Python 3.12 environment
  - `south.json`, `cand.json` fire candidate queries

## Setup

```
C:\data\wildfire-lidar\venv\Scripts\activate
earthengine authenticate
```

`earthengine authenticate` is run once by the account owner.

## Files

- `WORKLOG.md` dated record of steps, settings, problems, fixes and limits
- `01_select_fire.md` candidate fires, GEDI counts and the choice
- `02_count_gedi.py` counts GEDI shots per fire
- `03_extract_samples.py` builds the GEDI plus dNBR sample table
- `04_check_samples.py` checks the table (output in `sample_check.txt`)
- `05_clean_and_model.py` cleaning, spatial block validation, models and SHAP (`results.json`, `figures/`)
- `requirements.txt` package versions

## Reproducing

1. Create the Python environment and install `requirements.txt`.
2. Run `earthengine authenticate` once, then set your own Earth Engine project: `EE_PROJECT=your-project-id`.
3. Fire polygons come from the BC Data Catalogue web feature service. Save the result for fire K61884 to `south.json` in the data folder named in the scripts (the folder path is set at the top of each script).
4. Run the scripts in order, 02 to 05.

Data sources: GEDI L2A and L2B monthly rasters, Sentinel-2 L2A (harmonized), NASADEM, ESA WorldCover 2020 (all through Google Earth Engine), and BC Wildfire Service historical fire perimeters. Check each source's licence and attribution requirements before reuse.

Results are preliminary and not validated against field severity.
