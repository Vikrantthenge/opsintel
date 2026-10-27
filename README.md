# OpsIntel Version 2.5 — Login & Project Access

Built on the supplied Streamlit MVP, preserving all six original workspaces and retaining Targets & Alerts, saved projects and applied column mapping. This release adds local user accounts, administrator/analyst/viewer roles, per-project permissions and protection against conflicting saves. Guided cleanup and chart-rich reports remain available.

## Install and start

Extract this package into a new folder. Stop the old app, open a terminal in the new `opsintel-v2` folder, then run:

    python -m pip install -r requirements.txt
    python -m streamlit run app.py

Windows users can also double-click `Start-OpsIntel.bat` after installing the requirements. Keep all Python files and `.streamlit` together. `app.py` is the entry point; supporting modules do not display standalone apps.

## First administrator and account setup

On first startup, open `data/setup-key.txt` locally and enter its contents on Set up OpsIntel. Choose your administrator credentials, then sign in. There is no default password. Existing accounts are retained if upgrading from a version that already has account tables.

Read [ACCESS_SETUP.md](ACCESS_SETUP.md) for the full setup, role matrix, project assignment, password recovery and deployment scope. The first administrator can access existing projects; non-administrator users require explicit access grants to existing projects. The default server address is local-only (`127.0.0.1`).

## Saved projects

The sidebar now provides Saved projects, Open selected project, editable project/client names, Save project now and Create a project.

- Datasets, source names, saved findings/approval status, audit history, client/project names and report summary/limitations/chart choice, applied column mappings, target definitions, diagnostic settings and the pre-cleanup original copy are saved automatically after interactions.
- Each account's last-opened accessible project reopens after sign-in; otherwise the most recently saved accessible project is used. Select a different project and press Open selected project to switch. Permitted pending edits are saved before switching. Read-only users do not write project data.
- New projects start with the fictional sample dataset. Upload or paste your own data in Data Workspace.
- Dashboard filters and unsaved investigation form text are temporary. Press Save finding to retain a finding. Mapping drafts are temporary; press Apply mapping to save them.
- Data lives in `data/opsintel.sqlite3` beside `app.py`. The folder/database are created automatically. Storage failures show an error; keep the session open and fix folder permissions or disk space before retrying.

### Upgrade from Version 2.1, 2.2, 2.3 or 2.4 (saved projects)

1. Stop the running app.
2. Back up its entire `data` folder.
3. Extract this release into a new folder, then copy your existing `data` folder beside the new `app.py`.
4. Run `python -m pip install -r requirements.txt` to install the updated dependencies, including Matplotlib.
5. Start `app.py` from that folder, complete the one-time administrator setup using `data/setup-key.txt`, and sign in. Your existing project payloads, mappings, findings, targets and cleanup originals are retained. Account tables are added automatically.

The package includes no database and will not replace your saved projects. If you replace files in the existing app folder instead, retain its `data` folder and copy every new/updated application file, including `security.py`, `auth_ui.py` and `manage_users.py` as well as the existing supporting modules.

### Upgrade from Version 2 (memory-only)

Before stopping the old app, export its CSV, findings JSON and audit JSON. Upload the CSV into the new app. Findings and audit JSON imports are not included; keep those exports as reference or recreate findings in Investigation.

## Data quality and guided cleanup

Open Data Workspace. Its Active source data table shows the current working dataset. Export original CSV uses the saved pre-cleanup original if one exists, otherwise the current source. The original is the parsed uploaded dataset, not a byte-for-byte copy of the original CSV file; CSV formatting and inferred column types can differ.

Under Data quality & guided cleanup:

1. Choose source columns for date checks, numeric checks, breach flags and completed-versus-volume comparison. Existing mappings and standard field names supply defaults; custom headers can be selected directly even if invalid values prevent applying a mapping.
2. Choose the date format. Use Check data & preview cleanup to save these diagnostic settings and inspect the issue log. Leave every cleanup checkbox off for diagnostics only.
3. If desired, select cleanup steps and preview them. The Before/After tables, row counts, replaced-invalid-cell count and remaining issue count describe the proposed result. Previewing does not change the dataset.
4. Press Apply previewed cleanup only after reviewing the preview. Changed settings or changed source data require a new preview.
5. Use Restore data before cleanup to restore the original parsed source. The backup survives app restarts and is stored with the project.

Checks include missing/blank cells, exact duplicate rows, completely empty rows, invalid selected dates, invalid/non-finite selected numbers, breach values outside 0/1, negative selected numbers and completed work greater than volume. Negative values are review items because some signed measures are legitimate. Issue entries can overlap: one cell or row may have several issues. The screen shows up to 1,000 entries; the issue CSV contains all entries. Value examples are limited to 200 characters; source data retains full values. Empty datasets show no-records guidance rather than a passing result.

Cleanup runs in this order: trim text, normalize blank text to missing, convert selected dates/numbers, remove empty rows, remove duplicates. Every step is optional. Conversion replaces invalid selected dates/numbers and invalid breach flags with missing values, converts valid values to date/numeric types, and normalizes timezone-aware dates to UTC. Plain numbers are required; currency symbols and thousands separators count as invalid. Duplicates are compared after the selected transformations, keeping the first matching row. Completely empty rows are assessed after those transformations. Therefore, conversion may make a row empty or make previously different rows equal.

Cleanup never fills missing values, guesses units, resolves negative values, adjusts completed work or infers a correction. Conversion may increase missing-value issues while reducing invalid-value issues; fewer issue entries alone is not proof of better data. Review remaining issues and use the original export when needed.

The first applied cleanup preserves the dataset before cleanup. Further cleanups retain that same original, not a version history. Restoring clears the active backup; applying cleanup again creates a new one. Importing a replacement dataset or restoring the fictional sample starts a new source history and clears the previous backup, diagnostic settings and mapping. Existing findings and targets remain historical/project records and must be reviewed after data changes.

## Enhanced PDF reports

Open Client Report, enter the executive summary and limitations, choose a numeric chart metric and download the PDF. PDF generation is cached for unchanged report inputs. The PDF includes:

- Project/client/source information, generation time, valid date coverage and full-dataset scope.
- Executive record, volume, cycle-time and SLA KPIs.
- Embedded performance trend, location and service charts when the required fields exist.
- Saved target results including warning/critical/unavailable states and sample/missing counts.
- A data-confidence snapshot, issue counts by type and cleanup/original-row context.
- Analyst-approved findings, limitations and the applied column mapping.

PDFs use the full active mapped/cleaned project dataset. Command Centre filters are not applied, matching the existing report CSV scope. Only approved findings are included. Missing chart fields or non-numeric data produce an explanation instead of a chart. A saved mapping that cannot be applied blocks PDF generation until it is fixed or removed; original CSV and findings exports remain available. Non-finite measures or invalid breach flags are not silently treated as passing. Charts show daily/segment totals for volume, completed and cost; other metrics use row averages. Segment charts show the top 12 by value when there are more than 12 segments, and state that limit. Long labels may be shortened in charts; exports retain full values.

The report uses a print-friendly navy/white design, embedded fonts, sharp chart images, repeated table headers and page numbers. Charts are generated locally with Matplotlib; no external chart rendering service or browser download is required. The app still provides CSV and findings JSON exports. The previously supplied sample report uses fictional data; reports generated by this release carry the current version footer.

## KPI targets and alerts

1. Open Targets & Alerts and select Create a new target.
2. Name the target, choose its numeric metric and calculation, and select At most or At least.
3. Choose Overall, By location or By service. Grouped rules evaluate each visible segment separately.
4. Set the target and critical thresholds and press Save target.
5. Return to Command Centre. Its Performance alerts table updates with your date, location and service selections. The Targets & Alerts page always evaluates the full dataset.

Examples (set thresholds appropriate to your operations):

| Target | Metric | Calculation | Direction | Target | Critical |
| --- | --- | --- | --- | --- | --- |
| Cycle time guardrail | cycle_time_min | mean | At most | 40 minutes | 60 minutes |
| SLA breach limit | sla_breach | mean | At most | 5% | 10% |
| Minimum throughput | volume | sum | At least | 1,000 | 800 |

For At most, equality with the target is On target; values above the target are Warning; values at or above the critical threshold are Critical. Critical must exceed the target. For At least, equality with the target is On target; values below the target are Warning; values at or below the critical threshold are Critical. Critical must be below the target. Thresholds are absolute numbers in the calculated metric's units, not relative percentage changes.

SLA breach targets require mean over numeric 0/1 flags and percentage thresholds from 0 to 100. Other metrics support mean, sum, median and count. Count counts non-missing numeric values, not volume. Missing metric values are excluded and their count is shown. Empty views, missing/non-numeric metrics, non-finite values, absent scope columns, invalid breach flags and no usable values show Unavailable. Unavailable results never produce an all-on-track message.

Target totals use the current reporting window; thresholds are not prorated by date range or number of locations. A project-level threshold applies equally to every segment when grouped. A missing location or service value is shown as a missing segment on the full-dataset page; Command Centre segment filters may exclude it.

Choose a saved target to edit it. To remove it, select the target, confirm removal and press Remove selected target. Export alert results CSV downloads current evaluated results; Export target definitions JSON downloads the saved rules. JSON import is not included. Definitions, edits and removals are saved with the project and recorded in its audit trail. Alert evaluations are computed on demand and are not appended to the audit trail.

These are in-app alerts. There is no background monitoring, email or external notification. Rules are retained when replacing a dataset or changing its mapping; review their metrics and units after any data change. Missing fields show Unavailable until the rule or mapping is updated. Target configuration drafts are saved only by pressing Save target. The existing KPI Explorer optional target remains an audit-only KPI definition field; configure live thresholds here.

## Connect your CSV columns

1. Open Data Workspace and upload or paste your data.
2. Under Connect your columns, select the source header for each available field, for example `Branch` → Location and `Cases` → Volume. Fields are optional; standard OpsIntel headers are preselected when present.
3. Select the source date format: ISO (`2026-08-01`), day/month/year (`01/08/2026`) or month/day/year (`08/01/2026`).
4. Press Preview mapping and inspect the resulting field names, values and dates.
5. Press Apply mapping. All analysis pages and analysis CSV exports use the mapped view. The mapping is saved per project and restored after restarting.

Source data and extra columns remain available. Data Workspace profiles the original source and offers Export original CSV; Client Report CSV and Command Centre filtered CSV use the analysis view. Export mapping JSON downloads the applied configuration, not a draft. Mapping JSON import is not included.

Mapped numeric fields accept plain numbers (no currency symbols or thousands separators). Cycle time must already be in minutes and cost in INR. Breach flags must be 0/1; text labels and percentage rates require source preparation. Invalid non-empty values, duplicate source assignments and destination column collisions block the whole mapping. No partial mapping is committed. Empty mapped dates/numbers stay missing, and rows are retained. Dates carrying timezone offsets are converted to UTC. Mapping does not convert units, fill gaps or remove duplicates.

A source column can supply one field only. If the destination name already exists, use that existing column or map it to another available field to avoid duplicate analysis columns. Unmapped columns remain under their original names, so existing standard headers continue to work even if left unassigned.

Remove applied mapping returns analysis to original source fields. Loading a replacement dataset or restoring the sample clears the previous mapping to prevent stale assignments. Findings already saved remain historical records; review them after changing the dataset or mapping. Mapping changes are recorded in the project audit trail.

### Backup and move computers

Stop the app, then copy the entire `data` folder to a safe location. To restore or move projects, stop the destination app and copy that folder beside its `app.py`. Keep the database when replacing application files in future. The ZIP contains no user data. Data is stored on the machine running Streamlit, which may differ from the browser machine.

Local accounts and project permissions now control workbench access. The database is not encrypted. Conflicting saves are rejected rather than silently overwriting newer work; export any unsaved draft and explicitly reload the saved project. Backups contain accounts and permissions as well as project data. See ACCESS_SETUP.md for password handling, offline recovery and the limitations of Streamlit-native download links. Hosted services with temporary disks need persistent storage to retain this database across redeployments.

## Existing capabilities

Dark interface using the requested navy palette, Inter with Arial fallback, date/location/service filters, four executive KPIs with prior-period deltas, selectable performance trends, location/service comparisons and filtered CSV export. CSV upload/paste, profiling, KPI exploration, investigation, approved-finding PDF reports and CSV/JSON exports remain available.

Run from this folder to load `.streamlit/config.toml` for native table and widget colors. Inter loads from Google Fonts when available.

## Data and calculation notes

Recognized dashboard columns are `date`, `location`, `service`, `volume`, `completed`, `cycle_time_min`, `sla_breach` and `cost_inr`. Other numeric fields remain available for exploration. Missing columns disable corresponding controls or show N/A. Applied column mapping supplies these fields from your source headers in the analysis view; original stored data remains unchanged.

Volume, completed work and cost charts use sums; other metrics use row averages. SLA assumes a numeric 0/1 breach flag per row and is displayed as a percentage, not a volume-weighted rate. Date filters exclude invalid dates and show their count. Missing segment values are excluded by active segment filters. Empty selections show no records. Prior-period deltas use an equal-length preceding period and the same segment selections; incomplete source coverage can affect comparisons.

Command Centre filters apply only to that page. Other workspaces and report data exports use the full active dataset. Comparisons are descriptive, and findings require human review. PDFs contain embedded charts, target/quality summaries and approved findings. Use fictional or de-identified data.

## Verification

Streamlit AppTest passed mapping preview/application, mapped KPIs/charts/filters, rejection of invalid drafts, original-data preservation, fresh-session mapping restoration, project isolation, mapping removal, replacement-data resets, older project compatibility and all six original pages. Saved-project regression checks cover project creation, switching, autosave, findings, report drafts and audit restoration. Storage round trips preserve tested datetime, string identifiers and missing numeric values. Targets & Alerts checks also passed upper/lower threshold boundaries, warning/critical levels, grouped and filter-sensitive results, SLA percentage calculations, all four aggregations, unavailable/empty states, target creation/edit/removal, invalid edit preservation, restart persistence, project isolation, older payload compatibility and all seven pages. Data quality and report checks passed non-mutating previews, preview-before-apply enforcement, stale-plan rejection, explicit cleanup steps, original-copy persistence/restore, replacement-data resets, diagnostic issue types, approved-only findings, chart embedding, escaped metadata and no-numeric fallback. Storage checks retain numeric infinities so diagnostic evidence survives restart. Long text, long category labels and multi-page target tables were exercised. The sample PDF was rendered and visually inspected. Authentication checks cover one-time setup keys, salted password hashes, temporary-password changes, sign-in throttling, idle/absolute expiry, session revocation, last-administrator protection, role boundaries, direct data-layer authorization, project assignment/revocation, read-only exports and stale-write rejection. AppTest exercised account administration and all existing workspaces after sign-in. Migration checks preserve existing project payloads and cleanup originals, and expired sessions clear private project state. Existing project, mapping, cleanup, alert and report suites are run using real signed-in test accounts. Python compilation passed. New account controls were tested with AppTest; their browser appearance has not been manually verified.
