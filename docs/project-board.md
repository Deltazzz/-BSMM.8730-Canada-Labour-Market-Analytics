# Project board and platform selection

## Milestone board

The proposal's dates are course targets. This board records the available artifacts and their dependencies. The project lead owns the end-to-end work. Review uses the files and reconciliations below. The board makes no claim that weekly meetings took place or that course submissions occurred.

| Course target | Work item | Depends on | Review evidence | Status |
|---|---|---|---|---|
| Sept 27 · D1 | Define questions, scope and milestones | Proposal | Supplied Word proposal, research questions in the final report | Supplied |
| Sept 28–Oct 25 | Locate English releases, retain originals and licence, verify dates and units | Scope | Raw release bytes, source manifest and coverage table | Complete |
| Sept 28–Oct 25 | Profile fields, handle missingness and duplicates, standardize and consolidate | Acquisition | Field coverage, 72-field dictionary, consolidated CSV and MySQL tables | Complete |
| Nov 8 · D3 | Review preparation and preliminary comparisons | Two verified releases | Retrospective midterm PDF covering August and September | Complete |
| Nov 9–22 | Analyse demand, geography, education, experience, wages, employment and work arrangements | Clean data | SQL views, exported results and sensitivity tables | Complete |
| Nov 9–22 | Evaluate dashboard platforms and build a filterable report with drill-through | Research questions and data model | Populated PBIX snapshot and editable four-page PBIP with a native MySQL source | Snapshot verified in Desktop; MySQL view reconciled independently |
| Nov 29 · D4 | Package the final solution, verify code and document acquisition and cleaning | Integrated solution | README, reproducible scripts, QA verifier and output tables | Complete locally |
| Dec 1 · D5 | Interpret results for students and career planners | Analysis and validation | Six-page final report | Complete |
| Dec 7/9 · D6 | Present results, supporting evidence and limits | Final interpretation | Eight-slide presentation with speaker notes in the editable version and a portable PDF | Complete |
| Shared repository | Publish code, documentation and project artifacts under the owner's account | Repository destination and authenticated owner | [Project repository and commit history](https://github.com/Deltazzz/-BSMM.8730-Canada-Labour-Market-Analytics/commits/main/) | See main branch |

## Platform assessment

The comparison uses the proposal's five selection criteria. Suitability for the course schedule and for career planners is a project judgment. The assessment is documentation-based. Power BI is the implemented tool.

| Platform | Structured inputs | Preparation and model | Interactivity | Audience and timetable |
|---|---|---|---|---|
| Power BI | CSV and tabular import | Power Query and reusable DAX measures for counts and hourly medians | Slicers, cross-filtering and occupation drill-through | The reader can choose a month and occupation on a local multi-page report. A source-controlled project packages the model and visuals together. |
| Tableau | Text files and relational connections | Relationships, calculated fields and data-source preparation | Dashboard filter actions can connect a location chart to an occupation view | Suitable for a visual explorer. Moving the final project to Tableau would require another workbook and its own sharing setup. |
| Apache Superset | Connects to a SQL database | SQL Lab and defined datasets can reuse prepared SQL aggregates | Dashboard filters and charts over the database | Suitable for browser access. Hosting the service and its database adds administration to this course project. |
| KNIME | File readers and database nodes | Visual workflows handle ingestion, joins and transformations | Components and Data Apps expose guided interactive views | Useful for demonstrating preparation. A separate workflow and deployment route would be needed to distribute a multi-page app. |

Power BI was selected because the proposal requires it and its local report supports a student moving from national counts to a single occupation and province. Python and SQL handle cleaning and metrics that require repeatable validation. This also allows the same underlying numbers to be checked outside the dashboard.

Sources: [Microsoft Power BI project overview](https://learn.microsoft.com/en-us/power-bi/developer/projects/projects-overview), [Tableau dashboard actions](https://help.tableau.com/current/pro/desktop/en-us/actions_dashboards.htm), [Apache Superset dashboard documentation](https://superset.apache.org/docs/using-superset/creating-your-first-dashboard/), [KNIME Data Apps guide](https://docs.knime.com/latest/data_apps_beginners_guide/data_apps_beginners_guide.pdf).

## Review checkpoints

- Acquisition review reconciles pinned bytes, logical record counts, release months, distinct dates and snapshot IDs. See `results/sources.csv` and `results/coverage.csv`.
- Preparation review compares known and missing values before interpreting conditions or qualifications. `results/field_coverage.csv` covers every source field and `results/source_coverage.csv` exposes the external-feed gaps.
- Analytical review reconciles counts by occupation, province and region, rechecks raw hourly midpoints and tests the repeated October retail-pay pattern. Definitions are in `src/analysis.sql`.
- Delivery review compares the MySQL reporting view to the raw records and checks the editable Power BI project's field bindings. The reports and presentation were reviewed page by page.
- In the packaged snapshot, Power BI Desktop 2.159.1231.0 loaded 165,297 records and rendered all four pages. Drilling from Cooks opened its detail page with 7,261 records. The October slicer returned 2,269 records, 3,446 advertised openings, 2,237 eligible hourly records and a $20.00 hourly midpoint median. For the subsequent MySQL migration, the read-only account and .NET provider retrieved all 165,297 records. A completed Desktop refresh of the migrated PBIP is pending verification.
