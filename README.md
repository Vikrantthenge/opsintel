# OpsIntel — Operations Intelligence Workbench

An operations analytics portfolio project built with **Python, Streamlit, Pandas, Plotly, and SQLite**, combining executive dashboards, data-quality checks, reporting-period comparisons and PDF reporting.

**Version 2.6 · Created by Vikrant Thenge**

## Explore the Project

- **[View Source Repository](https://github.com/Vikrantthenge/Apps)**
- **[Read the User Guide](USER_GUIDE.md)**
- **[Explore Period Comparison Methodology](PERIOD_COMPARISON.md)**

## Project Overview

OpsIntel is an interactive workbench designed to help operations teams review performance, compare locations and services, investigate exceptions and prepare executive reports.

The application connects the analytical workflow—from CSV preparation and validation to KPI monitoring, period comparisons and analyst-approved findings—within one interface. It extends an existing Streamlit MVP while retaining its original workflows.

Potential applications include service delivery reviews, fulfilment monitoring, branch performance comparisons and periodic client reporting.

## Key Performance Indicators

The Command Centre calculates the following indicators from the active dataset and selected filters:

- **Records analysed:** Number of records in the selected view.
- **Total volume:** Sum of the operational volume field.
- **Average cycle time:** Mean cycle time, expressed in minutes.
- **SLA breach rate:** Percentage of row-level numeric 0/1 flags indicating a breach.

Prior-period changes use the preceding window of equal length with the same location and service selections. Results depend on the uploaded data and its coverage; no fixed performance figures are claimed.

## What the Workbench Demonstrates

- Monitoring operational KPIs through an executive command centre
- Filtering performance by reporting period, location and service
- Comparing baseline and current periods with coverage warnings and optional per-day normalization
- Connecting custom CSV headers through validated column mapping
- Checking missing values, duplicates, invalid fields and operational inconsistencies
- Previewing cleanup before applying changes, with restoration of the pre-cleanup dataset
- Evaluating configurable KPI targets with warning, critical and unavailable states
- Recording evidence, alternative explanations and proposed validation steps
- Generating executive PDFs with charts, quality context and analyst-approved findings
- Retaining project datasets, configurations and saved records in SQLite

## Application Workspaces

| Workspace | Purpose |
| --- | --- |
| **Command Centre** | Executive KPIs, interactive filters, trends and segment comparisons |
| **Period Comparison** | Reporting-window comparisons, aligned trends and PDF/CSV exports |
| **Data Workspace** | CSV upload/paste, profiling, column mapping and guided cleanup |
| **KPI Explorer** | Custom numeric metric exploration and grouped calculations |
| **Targets & Alerts** | Configurable thresholds and on-demand exception evaluation |
| **Investigation** | Evidence capture, alternative explanations and finding approval |
| **Client Report** | Executive narrative, charts, target results and reviewed findings |
| **Audit Trail** | Recorded project actions and JSON export |

## Suggested Demo Walkthrough

1. Start with the fictional sample data and explore **Command Centre** filters.
2. Run a weekly or monthly **Period Comparison** and inspect coverage before interpreting changes.
3. Create a cycle-time or SLA target in **Targets & Alerts**.
4. Review data-quality issues and preview optional cleanup in **Data Workspace**.
5. Save and approve a finding in **Investigation**, then export a PDF from **Client Report**.

## Skills Demonstrated

Business analysis · KPI design · Data validation · Descriptive analytics · Interactive visualization · Modular Python development · SQLite persistence · Executive reporting · Automated calculation and workflow checks

## Technology Stack

Python · Streamlit · Pandas · NumPy · Plotly · SQLite · Matplotlib · ReportLab · unittest · Streamlit AppTest

## Run Locally

From the application folder:

```bash
python -m pip install -r requirements.txt
python -m streamlit run app.py
```

**`app.py` is the entry point.** Keep the supporting modules and `.streamlit` folder together. New projects start with fictional sample data; another CSV can be loaded through Data Workspace.

Run the included period-comparison calculation tests with:

```bash
python -m unittest discover -s tests -v
```

## Data and Interpretation Disclaimer

The built-in sample data is fictional and provided for portfolio demonstration. It does not represent verified organizational performance, operational improvements or cost savings.

Comparisons are descriptive and do not establish causation. SLA breach rate is calculated from row-level 0/1 flags and is not volume-weighted. Missing fields and incomplete date coverage affect interpretation. Mapping does not convert units: cycle time must already be in minutes and cost in INR.

Command Centre filters apply to that workspace. Client Reports use the full active project dataset, while Period Comparison uses its own saved selections. Findings require human review; only analyst-approved findings appear in reports.

## Current Scope and Demo Use

Version 2.6 has **no login or visitor-level data isolation**. Projects use a shared SQLite database on the application host, so public-demo visitors may access the same saved projects. Use fictional or de-identified data only.

This release is designed as a single-user workbench. Concurrent edits can overwrite changes, and hosting with temporary storage can lose saved projects across restarts or redeployments. Alerts run on demand inside the app; background monitoring and email notifications are not included. The audit trail is an application history, not a tamper-proof compliance log.

Detailed setup, backup, calculation and operating instructions are available in the [User Guide](USER_GUIDE.md) and [Period Comparison Guide](PERIOD_COMPARISON.md).

## Author

**Vikrant Thenge**

[LinkedIn](https://www.linkedin.com/in/vthenge) · [GitHub](https://github.com/Vikrantthenge/Apps) · [Email](mailto:vikrantthenge@outlook.com)

© 2026 Vikrant Thenge
