# Reporting-period comparisons

OpsIntel 2.6 is built on the no-login Version 2.4. The new Period Comparison workspace adds a comparison workflow; existing Command Centre filters and full-project Client Report exports keep their original scope.

## Run a comparison

1. Load or open a saved project. Apply column mapping in Data Workspace if your source headers differ from the standard OpsIntel fields.
2. Open Period Comparison.
3. Choose a starting preset, or select Custom ranges. Presets use the latest valid date in the full active dataset, rather than the computer's current date:
   - Latest 7 days versus the previous 7 days.
   - Latest 30 days versus the previous 30 days.
   - Latest calendar week (Monday-Sunday) versus the previous calendar week.
   - Latest calendar month versus the previous calendar month.
4. Set Baseline period and Comparison period. Start/end dates are inclusive. Each period can contain up to 3,660 calendar days. Calendar presets include the full week/month, which may extend beyond available data.
5. Choose locations and services. The same selections apply to both periods. All available values are selected by default, including an explicit Missing value option if relevant. An empty selection means no rows, not all rows. When a dimension is absent, its filter and segment comparison are omitted.
6. Select a numeric chart metric and calculation. Default uses sums for volume, completed and cost, and means for other numeric fields. SLA breach rate requires Default or Mean over numeric 0/1 flags.
7. Optionally enable per-calendar-day normalization or add report commentary.
8. Press Run comparison. This saves the configuration to the project, records the run settings in its audit trail and updates the results.

Changing the form without running it does not replace the displayed comparison. The results caption names the exact dates of the last run. Switching to another preset provides new starting dates, while the displayed results remain based on the last valid run until Run comparison is pressed.

## Read the results

Coverage shows each requested range, its calendar-day count, distinct days with records, days without records and row count. Rows outside both periods are not included. Missing/invalid dates are excluded and counted after applying the location/service filters. Non-ISO date strings require an applied Date mapping; the comparison does not guess whether 01/02/2026 means January 2 or February 1. Timezone-aware dates are grouped by UTC date, matching applied mapping conversion.

KPI changes include Records, Total volume, Completed, Average cycle time, SLA breach rate and Total cost. Missing fields display N/A. If the chosen chart metric/calculation differs from these definitions, it adds its own summary row. The four cards show comparison-period values and changes versus baseline for records, volume, cycle time and SLA.

- Change = comparison value minus baseline value.
- Relative change = change / absolute baseline value x 100.
- Relative change is N/A for a zero or unavailable baseline. Two reported zero values have zero absolute change but undefined relative change.
- SLA values are percentages; their absolute changes are percentage points. For example, moving from 5% to 8% is +3 percentage points and +60% relative change.
- Missing metric values are excluded from their calculation. All-missing/no-row measures, non-numeric fields, non-finite values and invalid breach flags are unavailable. Metric sample sizes and exceptions can be inspected separately.
- Increase/Decrease describes numeric movement, not success or failure. Cost can rise because volume rises; a location's apparent performance can change with service mix. No causal interpretation is generated.

Per-day normalization divides additive period totals (volume, completed, cost and selected custom Sum measures) by all requested calendar days. It does not divide rates or averages again. Records remain raw row counts. Missing days are unverified: a total divided by the requested duration is not proof of a complete operational daily average. Check coverage before treating unequal-length periods as comparable.

Location and service tables use the union of both periods. A segment absent from one period is marked Only in baseline or Only in comparison, with unavailable numerical change. Absence is not treated as zero, and does not prove that a location opened or closed. Reported zero activity and missing activity are different cases.

## Charts

The daily chart aligns Day 1 of the baseline with Day 1 of the comparison, and provides actual dates and row counts on hover. It does not align by calendar date. Each day's value uses the selected Sum/Mean/Median calculation; missing/unusable values create gaps. Per-day period normalization is not applied a second time to daily values.

Segment charts use the chosen calculation and, for sums when selected, period-level normalization. Charts show up to 12 segments ranked by the larger absolute value in either period. Full tables and exports retain all segments. In the PDF, very long category labels may be shortened for readability; tables and CSVs retain the full values.

## Exports

- KPI comparison CSV: all summary rows, values, changes, units, sample sizes and calculation notes.
- Daily comparison CSV: period, actual date, aligned day, value, source row count and availability notes.
- Location/service comparison CSVs: all segments, values, changes, availability and row counts.
- Baseline/comparison records CSVs: rows in the mapped analysis view matching the saved dates and filters; internal helper columns are omitted.
- Comparison settings JSON: the last run dates, filters, metric, calculation, normalization and commentary. JSON import is not included.
- Comparison PDF: the same saved comparison scope, coverage, KPI changes, commentary, charts, segment tables, availability exceptions and sample sizes. Main Client Report continues to produce the separate full-project report with approved findings and existing target/quality summaries.

Numbers are rounded for display in tables/PDFs; CSVs retain calculation precision. Exports are generated from the latest active dataset with the last saved comparison configuration. They are not an immutable historical snapshot. Retain exported files with your source-data backup if you need to reproduce a past review.

## Saved settings and data changes

Comparison configuration is saved per project and reopens after restarting. Different projects have separate configurations. A fresh or older project has no comparison results until its first run. Importing a replacement dataset or restoring the fictional sample clears the previous comparison configuration. Cleanup keeps the configuration and recomputes results from the current working data. Changing a mapping can invalidate saved metrics or filters; review the form and run it again rather than silently broadening the filter.

Coverage gaps, unequal lengths, overlapping periods and unavailable measures are explicitly reported. Overlapping periods may contain the same source rows in both groups. Equal date ranges are permitted and naturally produce the same measurements when filters are unchanged.

This remains a local workbench without sign-in or user permissions. The download binds to 127.0.0.1 by default. Existing database payloads are preserved; any account tables from a 2.5 database are ignored and do not protect access in this no-login build.
