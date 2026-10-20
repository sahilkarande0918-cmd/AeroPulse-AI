# Model training

`python manage.py train` (or `python -m ml.train`) reproduces every artifact in ~20 s on a laptop CPU. CUDA is not
used: LightGBM on 13 k rows gains nothing from a GPU.

## Data
* Source: NASA PCoE "Turbofan Engine Degradation Simulation Data Set", official archive
  `https://phm-datasets.s3.amazonaws.com/NASA/6.+Turbofan+Engine+Degradation+Simulation+Data+Set.zip`.
  `ml/data.py` downloads it, **verifies sha256** `c9c5dec12a945a82e8bb4446589d7fb3cc057b5e5d81fa1a12e25ee9912ad3b2`
  and extracts the inner `CMAPSSData.zip` to `ml/data/raw/` (git-ignored).
* Subset FD001: 100 training run-to-failure engines (20,631 rows), 100 truncated test engines (13,096 rows), one
  operating condition, one fault mode (HPC degradation).
* Schema (verified at parse time): unit, cycle, 3 operational settings, 21 sensors (26 whitespace-separated columns,
  contiguous cycles per unit, no missing values). Sensor names/units follow Saxena et al. (2008), Table 2.

## Leakage controls
| Risk | Control |
|---|---|
| Rows of one engine in train and validation | Split by unit id (seeded permutation); GroupKFold for CV; asserted in code and tests |
| Future readings in features | Rolling windows only look backwards; `test_features_are_causal` appends future rows and checks past features do not change |
| Test RUL used as a feature | RUL_FD001 is read only for scoring |
| Preprocessing fitted on evaluation data | Sensor selection and OOD statistics use fit engines only; LightGBM needs no scaling; Ridge's scaler lives inside its pipeline |
| Calibration contaminating evaluation | 15 calibration engines are used only for conformal quantiles; 20 hold-out engines are used for nothing but evaluation and the demo fleet |

## Features (49)
`cycle` plus, for each of 12 informative sensors (s2, s3, s4, s7, s9, s11, s12, s14, s15, s17, s20, s21): raw value,
10-cycle rolling mean, 10-cycle rolling std, 20-cycle least-squares slope. Dropped as constant/low-information:
s1, s5, s6, s8, s10, s13, s16, s18, s19.

## Target
RUL = last cycle − current cycle, capped at 125 cycles (piecewise-linear convention; early-life RUL is not
identifiable from sensor data).

## Candidates and selection (engine-grouped 5-fold CV on 65 engines)
| Model | CV RMSE | CV MAE |
|---|---|---|
| Mean-RUL baseline | 41.69 | 36.99 |
| Ridge (standardised features) | 20.73 | 16.62 |
| **LightGBM A** (600 trees, lr 0.03, 31 leaves) | **14.91** | **10.24** |
| LightGBM B (400 trees, lr 0.05, 15 leaves) | 14.94 | 10.46 |

LightGBM A was selected on CV RMSE and refit on all 65 fit engines (`deterministic=True`, seed 42).

## Uncertainty
Mondrian split-conformal: absolute residuals on the 15 calibration engines, grouped by predicted RUL bin
[0, 50), [50, 100), [100, ∞); the ⌈(n+1)(1−α)⌉-th residual (α = 0.10) is the half-width per bin
(13.0, 33.6 and 19.9 cycles from 681, 745 and 1,770 rows). Rows from one engine are correlated, so exchangeability is
approximate — coverage is therefore *measured* on engines never seen in fitting or calibration (see evaluation.md).

## Explanations
`shap.TreeExplainer` on 2,000 fit rows produces the global importance plot; the runtime uses LightGBM's
`pred_contrib=True`, which computes the same TreeSHAP values (verified max absolute difference 0.0) without shipping
SHAP in the backend image.

## Artifacts (`ml/artifacts/`, committed; < 1 MB)
| File | Content |
|---|---|
| `rul_model.joblib` | model, feature list, sensors, conformal table, feature/sensor training statistics, version, provenance |
| `feature_schema.json` | sensors with symbols/units, feature names, windows, version |
| `evaluation_report.json` | config, splits, CV, test + hold-out metrics, coverage, SHAP, per-engine test predictions |
| `holdout_trajectories.csv.gz` | raw readings of the 20 hold-out engines (feeds the synthetic demo fleet and simulator) |

Plots in `ml/evaluation/`: `test_predictions.png`, `error_distribution.png`, `cv_comparison.png`, `shap_summary.png`.
Model version `fd001-lgbm_a-e2bd89e2` = selected candidate + hash of training config and dataset checksum.
