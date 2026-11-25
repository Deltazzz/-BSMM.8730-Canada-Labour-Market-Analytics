# Canadian Job Bank postings from August to October 2026

This BSMM.8730 team project uses Python, MySQL and Power BI to examine newly first-posted job-location records, advertised vacancies, qualifications, pay and work arrangements. October contained 59,130 records, up 9.9% from August. External feeds accounted for the net gain. The report shows how repeated listings across locations affect that comparison.

## Open the deliverables

| Deliverable | Contents |
|---|---|
| [Final report](reports/D5%20Final%20report.pdf) | Six pages of evidence, denominators, sensitivity analysis and limitations |
| [Power BI dashboard](powerbi/Job%20Bank.pbix) · [editable project](powerbi/Job%20Bank.pbip) | Six visible pages and an occupation drill-through page. The PBIX opens with the August–October data loaded. Both versions refresh from MySQL. |
| [Dashboard implementation review](reports/Dashboard%20implementation%20review.pdf) · [full-size screenshots](reports/dashboard-screenshots/) | Each approved mockup beside its Power BI Desktop screenshot, with data checks and native visual differences. |
| [Final presentation](reports/D6%20Presentation.pdf) | Eight slides for presenting the findings |
| [Midterm report](reports/D3%20Midterm%20report.pdf) | Retrospective two-release checkpoint |
| [Field dictionary](data/clean/data_dictionary.csv) | All 65 source fields and seven derived fields, with types and definitions |
| [Analytical results](results/) | Monthly, occupation, geography, qualifications, original-unit pay, working conditions and quality tables |
| [Tool evaluation and project board](docs/project-board.md) | Platform selection, milestone dates, dependencies and review evidence |

Python downloads the original releases to `data/raw`, writes the consolidated UTF-8 file to `data/clean/postings.csv` and loads the records into the MySQL database `jobbank`. Power BI imports the reporting view `jobbank.powerbi_postings` on refresh.

## Reproduce the analysis

On Windows, use Python 3.11 or later, the Oracle MySQL 8.4 server ZIP, Power BI Desktop and Oracle MySQL Connector/NET. Extract the server ZIP and supply its extracted directory to the startup script on the first run. The script creates a dedicated local instance on port 3307 and stores its credentials under your Windows account. Run these commands in PowerShell from the repository root. [Microsoft's MySQL connector setup](https://learn.microsoft.com/en-us/power-query/connectors/mysql-database)

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\scripts\start-mysql.ps1 -ServerHome 'C:\path\to\extracted\mysql-8.4.11-winx64'
.\.venv\Scripts\python.exe src/pipeline.py --download
.\scripts\grant-reader.ps1
.\.venv\Scripts\python.exe src/powerbi.py
.\.venv\Scripts\python.exe src/verify.py
```

On subsequent runs, start the existing instance with `.\scripts\start-mysql.ps1`. Once the three raw files are present, the pipeline checks their hashes and rebuilds using those files and the local database. Each URL, byte count and SHA-256 checksum is in [the source manifest](results/sources.csv). To regenerate the written reports, install `reportlab==4.4.9` in the same Python environment and run `src/reports.py`.

For optional Power BI JSON schema verification, install `jsonschema==4.25.1` in the same environment and run `src/verify.py --schemas` with access to developer.microsoft.com. The verifier reads raw records independently, checks exact identifiers in the clean CSV and the MySQL reporting view, and compares monthly counts, openings, occupational and geographic totals, and hourly medians. It also checks the Power BI model's source and visual bindings. [SQL view definitions](src/analysis.sql)

## Explore the report

Open the PBIX in Power BI Desktop to explore the loaded data. To work from the PBIP, keep its sibling report and semantic-model folders in place. To load the latest data in your local MySQL database, start the server and select **Home → Refresh** in either version. If prompted, choose **Database** authentication for server `127.0.0.1:3307` and database `jobbank`. Enter `jobbank_reader`, run `.\scripts\copy-reader-password.ps1` in PowerShell and paste the password into Power BI. The occupation, province, city, time period and education slicers carry across the six pages.

- **Overview** summarizes the selected records. Right-click an occupation in the summary table and choose **Drill through → Occupation detail**.
- **Demand Over Time** compares monthly records and advertised openings and ranks occupations by posting locations. To check a filter, select **2026-10** and **Ontario**. Retail salespersons and visual merchandisers should lead with 1,668 records, followed by Cooks with 556.
- **Geographic Distribution** maps postings by province or territory and ranks cities within the selection.
- **Qualifications** shows reported education and experience. **Compensation** compares hourly pay, including average midpoints for the ten occupations with the most eligible hourly records.
- **Work Conditions** shows employment type, weekly hours, work arrangements and benefits.

## Counting and cleaning rules

1. **Window and unit.** The proposal specifies multiple months and identifies August 2026. The study takes August and the next two consecutive English releases through October, the latest in the saved catalogue. The observed first-posting dates run from August 1 through October 31. Each of the 92 dates occurs. Each record is one WIC job-location snapshot, identified by its source ID. There is no stable underlying requisition or employer identifier. Record counts and sums of advertised openings are separate measures. The study does not count hires or the stock of all active vacancies.
2. **Ingestion and types.** The publisher uses a CSV extension for UTF-16 tab-delimited data. Read logical records with a CSV parser, enforce the 65-field schema, validate record width, normalize headers to snake case and normalize Unicode to NFC. Preserve the publisher's NOC codes as strings, including leading zeros. Dates become ISO calendar dates. Codes from NOC 2016 and NOC 2021 stay separate. Analysis uses NOC 2021.
3. **Traceability and duplicates.** A clean record retains its release month, one-based source record number and snapshot ID. Within-release and cross-release ID checks run before aggregation. A repeated or missing ID, invalid first date, missing calendar day or schema mismatch stops integration for investigation. Unique IDs allow similar title, pay and location combinations to remain. The retail sensitivity table measures one observed pattern without deduplicating it.
4. **Missingness and categories.** Trim whitespace. Blank, NA and *No data (case-insensitive) become SQL NULL and empty CSV cells. Keep explicit No, No experience and No degree as observed values. Report known-response denominators separately. The direct and external channels correspond to External Indicator 0 and 1. Province/territory labels and accented region names are preserved. No education, experience or pay is imputed.
5. **Pay and hours.** Keep positive, ordered bounds tied to a known pay period for comparisons. Each record's midpoint is (minimum + maximum) / 2. Calculate independent medians of minimum, maximum and midpoint by unit. Preserve invalid or incomplete records for counts and audit. The hourly sensitivity table omits lower bounds below $5 or upper bounds above $500. Weekly hours summaries require an explicit weekly unit and positive, ordered hours. Advertised nominal amounts are not adjusted for inflation or converted to an assumed work year.
6. **Interpretation.** Occupation and region tables retain a missing category. Month comparisons use all location records unless labelled as a subset. Reported rates per day use the actual number of calendar dates. No seasonal or population weights were applied. Outcome measures from employer surveys, fulfilment of openings and earnings received lie outside these records.

The results files preserve a one-row-per-group structure. In `qualifications.csv`, `total_records` and `known_records` repeat within a month, occupation and dimension. Use the denominator once per group. In `pay.csv`, the `scope` field identifies national, provincial, occupational or occupation-by-province summaries. Do not combine different scopes or average group medians to produce a pooled median. In `work_conditions.csv`, sum counts within a single measure because a record contributes to each measure.

## Source and licence

Contains information licensed under the Open Government Licence – Canada. Employment and Social Development Canada publishes both direct advertisements and eligible external contributions. The original publisher retains responsibility for the source fields. The interpretations here are the project's own. [Job Bank catalogue](https://open.canada.ca/data/en/dataset/ea639e28-c0fc-48bf-b5dd-b8899bd43072) · [Open Government Licence – Canada](https://open.canada.ca/en/open-government-licence-canada)

The sampling framework and vacancy definition for Statistics Canada's Job Vacancy and Wage Survey are documented separately. [Survey guide](https://www150.statcan.gc.ca/n1/pub/75-514-g/75-514-g2023001-eng.htm)
