# NeuroPower_Hackathon2026
Stuff+, Pitching+ and Location+ models via XGBoost for LMB 2023-2025 seasons
# Altitude and Pitching Quality in the Mexican Baseball League (LMB)

**An applied baseball analytics project exploring how altitude relates to pitch movement, pitching quality, and expected run value.**

This project was developed for the **ISAC 2026 Sports Analytics Hackathon** using three seasons of TrackMan pitch-level data from the Diablos Rojos del México. It investigates differences in pitch characteristics across stadiums at different elevations and develops machine learning models to evaluate pitching performance.

The project combines pitch-level modeling, contextual analysis, out-of-sample validation, and an interactive dashboard to explore how physical pitch characteristics and game context contribute to pitching outcomes.

## Project Overview

Altitude can influence the physical behavior of a baseball, including its movement and trajectory. However, evaluating pitching performance requires separating measurable pitch characteristics from the influence of game context and the variability of individual pitch outcomes.

This project addresses that problem through several complementary analytical components:

- **Stuff+:** evaluates pitch characteristics using physical and movement-related information.
- **Location+:** incorporates pitch location into the evaluation framework.
- **Pitching+:** combines pitch characteristics with additional information, including pitch count, arsenal, pitcher handedness, altitude, and game state.
- **Expected run value (xRunValue):** provides a common target for evaluating how well the models predict the run value associated with an individual pitch.
- **Altitude analysis:** examines how pitch movement and model-based pitching evaluations vary across elevation environments.

The goal is not simply to identify the best-performing model, but to understand what each metric measures, how well it generalizes, and where its limitations lie.

## Data

The analysis uses three seasons of TrackMan pitch-level data from the Diablos Rojos del México, including observations from different stadium environments.

The data support analyses of pitch characteristics, location, arsenal, game context, and expected run value. These variables are used to train and evaluate the pitching models and to investigate potential altitude-related differences.

**Data availability:** Please refer to the repository's data files and any accompanying documentation for details about included datasets, their scope, and applicable access or redistribution restrictions.

## Methodology

### 1. Pitch-level modeling

Python-based machine learning models are used to estimate expected run value and construct complementary pitching-quality metrics. XGBoost is used in the modeling workflow.

The models are evaluated at multiple levels of complexity, including physical pitch characteristics, pitch location, arsenal information, and contextual variables.

### 2. Validation strategy

Because pitches thrown by the same pitcher share characteristics, a random pitch-level split can produce overly optimistic estimates of generalization. The primary validation strategy therefore emphasizes groups that were not seen during training.

The evaluation includes:

- **Pitcher holdout:** five-fold GroupKFold validation grouped by pitcher.
- **Season holdout:** training on earlier seasons and testing on the 2026 season.
- **Altitude holdout:** withholding an entire altitude category for testing.
- **Random split:** reported only as a secondary reference.

Pitcher-level summaries are calculated using out-of-sample predictions so that each pitcher's evaluation is based on a model that did not train on that pitcher.

### 3. Model evaluation

The models are compared using the coefficient of determination (\(R^2\)) for xRunValue, alongside calibration, discrimination for auxiliary classification tasks, and stability across seasons.

This distinction matters: predicting the value of a single pitch is inherently noisy, while year-to-year stability helps assess whether a metric captures a persistent pitcher characteristic.

## Selected Results

The following results summarize the current analysis.

| Model | Unseen pitchers | 2026 season holdout | Extreme-altitude holdout |
|---|---:|---:|---:|
| Stuff | 0.004 | 0.004 | 0.004 |
| Stuff + location | 0.011 | 0.011 | 0.012 |
| Stuff + location + arsenal | 0.011 | 0.011 | 0.012 |
| Pitching+ (full model) | 0.040 | 0.042 | 0.035 |

*Values are \(R^2\) for xRunValue. They should be interpreted in the context of pitch-level outcome variability, rather than as direct measures of overall pitching skill.*

Several findings stand out:

- Adding location and count information improves xRunValue prediction relative to the Stuff-only model.
- Adding arsenal information does not produce a measurable improvement in the reported holdouts.
- The full Pitching+ model achieves higher \(R^2\), partly because it includes game-state variables. It should therefore not be interpreted as a pure measure of a pitcher's underlying ability.
- The full model retains predictive performance on the withheld extreme-altitude category, although this result does not establish universal generalization to every stadium or league.

### Year-to-year stability

In the current analysis, Stuff+ shows substantially greater year-to-year stability than Pitching+:

- **Stuff+:** \(R^2\) of approximately 0.51–0.52 between seasons.
- **Pitching+:** \(R^2\) of approximately 0.12–0.14 between seasons.

These results suggest that Stuff+ behaves more like a persistent pitcher characteristic, whereas Pitching+ is more sensitive to context that can change between seasons. Rankings and individual-player conclusions should be interpreted with these differences in mind.

## Interactive Dashboard

The repository includes an interactive HTML dashboard for exploring model outputs and pitch-level analyses.

**Current dashboard:** `diablos_dashboard_v5.html`

The prediction grid remains `prediction_grid_v4.json`. The dashboard supports the presentation and exploration of model-based results, including pitching-quality metrics and related pitch evaluations.

The dashboard does not run ONNX models in the browser.

## Repository Contents

The repository includes the following project artifacts:

| File | Purpose |
|---|---|
| `diablos_dashboard_v5.html` | Interactive results dashboard |
| `prediction_grid_v4.json` | Prediction grid used by the dashboard |
| `scores_por_pitcheo.csv.gz` | Pitch-level model scores |
| `scores_por_arsenal_lanzador_tipo.csv` | Scores summarized by pitcher arsenal and pitch type |
| `movement_sample.csv` | Sample of pitch-movement data |
| `top3_bottom3_*.csv` | Tables containing selected top-three and bottom-three comparisons |
| Analysis notebook | Data processing, modeling, and evaluation workflow; confirm the current filename in the repository |

File descriptions are based on their intended role in the project. Consult the files themselves and the accompanying notebook for exact column definitions, filters, and processing details.

## Tools and Technologies

- **Python** for data processing and modeling
- **Pandas** and **NumPy** for data manipulation
- **XGBoost** for machine learning
- **Scikit-learn** for model evaluation and validation
- **HTML and JavaScript** for the interactive dashboard

*Confirm the notebook's imports and environment before adding installation commands or a pinned dependency list.*

## Limitations

This project has several important limitations:

- A single pitch's run value is noisy and depends on more than pitch quality, including contact outcomes, defense, and game context.
- A model that includes outs, count, and other game-state variables evaluates a broader context than the pitch's physical characteristics alone.
- Performance on a held-out altitude category is evidence of generalization within this evaluation, not proof that the model will transfer unchanged to every environment.
- Year-to-year stability, predictive accuracy, and usefulness for player evaluation are related but distinct properties.
- Exploratory altitude rankings should be treated cautiously when their stability across samples is limited.

These limitations motivate the use of multiple validation strategies and the separate interpretation of physical pitch quality and context-dependent pitching evaluation.

## Reproducibility

The analysis artifacts and dashboard are included to make the workflow easier to inspect.

For reproducibility, users should verify the notebook's current filename, required package versions, dataset availability, and any data-access restrictions before rerunning the pipeline. The dashboard may rely on accompanying JSON or CSV artifacts, so keep the expected files in their documented relative paths.

## Acknowledgments

Developed for the **ISAC 2026 Sports Analytics Hackathon**, focused on analyzing TrackMan data from the Diablos Rojos del México.

---

**Author:** J. Redondo-Matus  
**Co-author:** D. Cuevas-Carreón
