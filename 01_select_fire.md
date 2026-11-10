# Fire selection

Source: BC Wildfire Service historical fire perimeters, queried through the BC Data Catalogue web feature service for fires from 2020 onward larger than 30,000 ha, then filtered by latitude.

Rule: GEDI covers only up to about 51.6 degrees north, so a fire must lie south of that. Fires in northern BC are excluded.

## Candidates south of 51.6 N

| Fire number | Year | Area (ha) | Latitude range | Note |
|---|---|---|---|---|
| K71086 | 2021 | 83,671 | 50.15 to 50.43 | Large, within GEDI range |
| K61884 | 2021 | 83,047 | 50.15 to 50.57 | Large, within GEDI range |
| K21001 | 2021 | 89,627 | 50.81 to 51.21 | Largest in range; closest to the 51.6 limit |
| K21849 | 2021 | 62,524 | 50.47 to 50.77 | Medium |
| K52125 | 2023 | 46,504 | 48.95 to 49.25 | Southern; more years of GEDI before the fire |
| K21633 | 2023 | 45,745 | 50.83 to 51.13 | More years of GEDI before the fire |
| K71030 | 2021 | 44,964 | 50.80 to 51.10 | Smaller |

Excluded: C41602 (2021) reaches 51.67 N; G41307, G51279 and R91162 lie far north of the GEDI limit.

## Things still to check before choosing

- Number of good-quality GEDI footprints that fall inside the fire polygon and were collected before the fire started. This decides whether the sample is large enough.
- Cloud-free Landsat or Sentinel-2 images before and after the fire in the same season.
- Fire start date and the date the fire was declared out, taken from the BC Wildfire Service record.
- GEDI data availability end date in the live Earth Engine catalogue (sources disagree on the exact date).

## Choice

Not made yet. The footprint count per fire is the deciding test.

## GEDI counts (run on 2026-11-10 with 02_count_gedi.py)

Good-quality GEDI L2A shots (quality_flag = 1, degrade_flag = 0) inside each fire polygon, from 18 April 2019 to the fire date. Counts are approximate (pixel sums at 25 m, polygon simplified to about 100 m). They include all land cover, not only forest, so the usable forest sample will be smaller.

| Fire | Year | Area (ha) | Approx. good pre-fire shots |
|---|---|---|---|
| K21001 | 2021 | 89,627 | 234,600 |
| K61884 | 2021 | 83,046 | 224,900 |
| K71086 | 2021 | 83,671 | 193,200 |
| K21849 | 2021 | 62,524 | 189,900 |
| K52125 | 2023 | 46,504 | 211,800 |
| K21633 | 2023 | 45,745 | 190,800 |
| K71030 | 2021 | 44,964 | 111,800 |
| C41602 | 2021 | 73,862 | 380,200 (fire reaches 51.67 N, edge of GEDI coverage) |
| G41307, G51279, R91162 | 2023 | | no data (north of GEDI coverage) |
