CREATE OR REPLACE VIEW out_monthly AS
SELECT posting_month, COUNT(*) AS records, SUM(vacancy_count) AS advertised_openings,
       COUNT(DISTINCT first_posting_date) AS days, ROUND(COUNT(*)*1.0/COUNT(DISTINCT first_posting_date),2) AS records_per_day,
       SUM(channel='Direct') AS direct, SUM(channel='External') AS `external`,
       COUNT(noc) AS known_noc, COUNT(economic_region) AS known_region,
       COUNT(education) AS known_education, COUNT(experience) AS known_experience,
       COUNT(telework) AS known_telework, SUM(telework='Yes') AS telework_yes,
       COUNT(employment_type) AS known_type, SUM(employment_type='Full time') AS full_time,
       COUNT(employment_term) AS known_term, SUM(employment_term='Permanent employment') AS permanent,
       SUM(pay_status='Comparable' AND salary_per='Hour') AS hourly_records,
       SUM(COALESCE(hourly_review,0)) AS hourly_flagged
FROM postings GROUP BY posting_month ORDER BY posting_month;

-- Additional within-unit sensitivity and hours summaries used in the written report.
CREATE OR REPLACE VIEW out_annual_sensitivity AS
WITH ranked AS (
 SELECT posting_month,pay_midpoint,COUNT(*) OVER (PARTITION BY posting_month) AS n,
 ROW_NUMBER() OVER (PARTITION BY posting_month ORDER BY pay_midpoint) AS rk
 FROM postings WHERE salary_per='Year' AND pay_status='Comparable'
 AND NOT(COALESCE(noc,'')='64100' AND channel='External' AND salary_minimum=111360 AND salary_maximum=111360)
)
SELECT posting_month,n AS retained_records,AVG(pay_midpoint) AS median_annual_excluding_pattern
FROM ranked WHERE rk BETWEEN ((n+1) DIV 2) AND ((n+2) DIV 2) GROUP BY posting_month,n ORDER BY posting_month;

CREATE OR REPLACE VIEW out_weekly_hours AS
WITH ranked AS (
 SELECT posting_month,hours_minimum,hours_maximum,COUNT(*) OVER (PARTITION BY posting_month) AS n,
 ROW_NUMBER() OVER (PARTITION BY posting_month ORDER BY hours_minimum) AS a,
 ROW_NUMBER() OVER (PARTITION BY posting_month ORDER BY hours_maximum) AS b
 FROM postings WHERE hours_per='Week' AND hours_minimum>0 AND hours_maximum>=hours_minimum
)
SELECT posting_month,n AS weekly_records,
 AVG(CASE WHEN a BETWEEN ((n+1) DIV 2) AND ((n+2) DIV 2) THEN hours_minimum END) AS median_minimum,
 AVG(CASE WHEN b BETWEEN ((n+1) DIV 2) AND ((n+2) DIV 2) THEN hours_maximum END) AS median_maximum
FROM ranked GROUP BY posting_month,n ORDER BY posting_month;

CREATE OR REPLACE VIEW out_occupations AS
SELECT posting_month, noc, occupation, COUNT(*) AS records, SUM(vacancy_count) AS advertised_openings,
       SUM(channel='Direct') AS direct, SUM(channel='External') AS external
FROM postings GROUP BY posting_month,noc,occupation ORDER BY posting_month,records DESC,noc;

CREATE OR REPLACE VIEW out_geography AS
SELECT posting_month,province,economic_region,COUNT(*) AS records,SUM(vacancy_count) AS advertised_openings
FROM postings GROUP BY posting_month,province,economic_region ORDER BY posting_month, province,records DESC,economic_region;

CREATE OR REPLACE VIEW out_provinces AS
SELECT posting_month,province,COUNT(*) AS records,SUM(vacancy_count) AS advertised_openings,
       COUNT(economic_region) AS known_region
FROM postings GROUP BY posting_month,province ORDER BY posting_month, records DESC,province;

CREATE OR REPLACE VIEW out_source_coverage AS
SELECT p.posting_month,r.filename,p.channel,COUNT(*) AS records,COUNT(p.education) AS known_education,
       COUNT(p.experience) AS known_experience, COUNT(p.telework) AS known_telework,
       SUM(CASE WHEN p.telework='Yes' THEN 1 ELSE 0 END) AS telework_yes,COUNT(p.economic_region) AS known_region,
       COUNT(p.employment_term_weekend) AS known_weekend, SUM(p.employment_term_weekend='Yes') AS weekend_yes
FROM postings p JOIN releases r USING(release_month)
GROUP BY p.posting_month,r.filename,p.channel ORDER BY p.posting_month,p.channel;

CREATE OR REPLACE VIEW out_qualifications AS
WITH levels AS (
 SELECT posting_month,noc,occupation,'Education' AS dimension,education AS level FROM postings
 UNION ALL SELECT posting_month,noc,occupation,'Experience',experience FROM postings
), frequency AS (
 SELECT posting_month,noc,occupation,dimension,level,COUNT(*) AS records FROM levels
 GROUP BY posting_month,noc,occupation,dimension,level
)
SELECT *, SUM(records) OVER w AS total_records,
       SUM(CASE WHEN level IS NOT NULL THEN records ELSE 0 END) OVER w AS known_records
FROM frequency WINDOW w AS (PARTITION BY posting_month,noc,occupation,dimension)
ORDER BY posting_month,noc,dimension,records DESC,level;

CREATE OR REPLACE VIEW out_work_conditions AS
WITH terms AS (
 SELECT posting_month,channel,noc,province,'Employment type' AS measure, employment_type AS value FROM postings
 UNION ALL SELECT posting_month,channel,noc,province,'Employment term',employment_term FROM postings
 UNION ALL SELECT posting_month,channel,noc,province,'Telework',telework FROM postings
 UNION ALL SELECT posting_month,channel,noc,province,'Weekend',employment_term_weekend FROM postings
 UNION ALL SELECT posting_month,channel,noc,province,'Evening',employment_term_evening FROM postings
)
SELECT posting_month,channel,noc,province,measure,value,COUNT(*) AS records
FROM terms GROUP BY posting_month,channel,noc,province,measure,value
ORDER BY posting_month,channel,noc,province,measure,value;

CREATE OR REPLACE VIEW out_pay_quality AS
SELECT posting_month,channel,salary_per,pay_status,hourly_review,COUNT(*) AS records
FROM postings GROUP BY posting_month,channel,salary_per,pay_status,hourly_review
ORDER BY posting_month,channel,salary_per,pay_status,hourly_review;

-- Keep periods separate. The central one or two sorted values give each median.
-- Compute per month, nationally, by province, occupation, and occupation within province.
CREATE OR REPLACE VIEW out_pay AS
WITH eligible AS (
 SELECT posting_month, noc, province,salary_per,salary_minimum AS lo,salary_maximum AS hi,pay_midpoint AS mid
 FROM postings WHERE pay_status='Comparable'
), slices AS (
 SELECT posting_month,'Canada' AS scope,'' AS noc,'' AS province,salary_per,lo,hi,mid FROM eligible
 UNION ALL SELECT posting_month,'Province','',province,salary_per,lo,hi,mid FROM eligible
 UNION ALL SELECT posting_month,'Occupation',noc,'',salary_per,lo,hi,mid FROM eligible
 UNION ALL SELECT posting_month,'Occupation and province',noc,province,salary_per,lo,hi,mid FROM eligible
), ranks AS (
 SELECT *,COUNT(*) OVER grp AS n,ROW_NUMBER() OVER (grp ORDER BY lo) AS rlo,
 ROW_NUMBER() OVER (grp ORDER BY hi) AS rhi,ROW_NUMBER() OVER (grp ORDER BY mid) AS rmid
 FROM slices WINDOW grp AS (PARTITION BY posting_month,scope,noc,province,salary_per)
)
SELECT posting_month,scope,noc,province,salary_per,n AS comparable_records,
 AVG(CASE WHEN rlo BETWEEN ((n+1) DIV 2) AND ((n+2) DIV 2) THEN lo END) AS median_lower,
 AVG(CASE WHEN rhi BETWEEN ((n+1) DIV 2) AND ((n+2) DIV 2) THEN hi END) AS median_upper,
 AVG(CASE WHEN rmid BETWEEN ((n+1) DIV 2) AND ((n+2) DIV 2) THEN mid END) AS median_midpoint
FROM ranks GROUP BY posting_month,scope,noc,province,salary_per,n
ORDER BY posting_month,scope,noc,province,salary_per;

CREATE OR REPLACE VIEW out_hourly_sensitivity AS
WITH ranked AS (
 SELECT posting_month,pay_midpoint,COUNT(*) OVER (PARTITION BY posting_month) AS n,
 ROW_NUMBER() OVER (PARTITION BY posting_month ORDER BY pay_midpoint) AS rk FROM postings WHERE hourly_review=0
)
SELECT posting_month,n AS retained_records,AVG(pay_midpoint) AS median_midpoint_screened FROM ranked
WHERE rk BETWEEN ((n+1) DIV 2) AND ((n+2) DIV 2) GROUP BY posting_month,n ORDER BY posting_month;

-- Repeated salary/title pattern discovered when investigating the largest retail movement.
-- Blank sums for months without the pattern become zero through the CASE expression.
CREATE OR REPLACE VIEW out_retail_sensitivity AS
WITH flags AS (
 SELECT *,CASE WHEN noc='64100' AND channel='External' AND salary_per='Year'
   AND salary_minimum=111360 AND salary_maximum=111360 THEN 1 ELSE 0 END AS pattern FROM postings
)
SELECT posting_month,COUNT(*) AS all_records,SUM(noc='64100') AS retail_records,SUM(pattern) AS pattern_records,
       COUNT(DISTINCT CASE WHEN pattern=1 THEN original_job_title END) AS pattern_titles,
       COUNT(DISTINCT CASE WHEN pattern=1 THEN city END) AS pattern_city_labels,
       COUNT(DISTINCT CASE WHEN pattern=1 THEN province END) AS pattern_provinces,
       MIN(CASE WHEN pattern=1 THEN first_posting_date END) AS first_pattern_date,
       MAX(CASE WHEN pattern=1 THEN first_posting_date END) AS last_pattern_date,
       SUM(CASE WHEN pattern=1 AND lower(original_job_title) LIKE '%wfh%' THEN 1 ELSE 0 END) AS pattern_wfh_title,
       COUNT(*)-SUM(pattern) AS records_excluding_pattern
FROM flags GROUP BY posting_month ORDER BY posting_month;

CREATE OR REPLACE VIEW out_consistency AS
SELECT posting_month,COUNT(*) AS records,COUNT(commission_type) AS commission_type_known,
       COUNT(salary_condition_commission) AS commission_flag_known,
       SUM(salary_condition_commission='Yes') AS commission_flag_yes,
       COUNT(salary_condition_dental) AS dental_flag_known,SUM(salary_condition_dental='Yes') AS dental_flag_yes,
       COUNT(hours_minimum) AS hours_minimum_known,SUM(hours_per='Week') AS weekly_unit_count,
       SUM(hours_minimum>hours_maximum) AS reversed_hours,
       SUM(employment_term_start_date>employment_term_end_date) AS reversed_term_dates,
       SUM(employment_term_weekend='Yes') AS weekend_yes,COUNT(employment_term_weekend) AS weekend_known,
       SUM(employment_term_evening='Yes') AS evening_yes,COUNT(employment_term_evening) AS evening_known
FROM postings GROUP BY posting_month ORDER BY posting_month;

CREATE OR REPLACE SQL SECURITY DEFINER VIEW powerbi_postings AS
SELECT j.posting_id AS `Snapshot ID`, DATE_FORMAT(p.first_posting_date,'%Y-%m-%d') AS `First posted`,
 t.period_id AS Month, p.channel AS Source, COALESCE(o.noc_code,'Not recorded') AS NOC,
 COALESCE(o.occupation_title,'Not recorded') AS Occupation, COALESCE(l.province,'Not recorded') AS Province,
 COALESCE(l.economic_region,'Not recorded') AS `Economic region`, COALESCE(p.education,'Not recorded') AS Education,
 COALESCE(p.experience,'Not recorded') AS Experience, COALESCE(j.employment_type,'Not recorded') AS `Employment type`,
 COALESCE(p.employment_term,'Not recorded') AS `Employment term`, COALESCE(p.telework,'Not recorded') AS `Telework flag`,
 COALESCE(p.employment_term_weekend,'Not recorded') AS `Weekend flag`, COALESCE(j.salary_per,'Not recorded') AS `Pay period`,
 p.pay_status AS `Pay status`, j.vacancies AS Vacancies,
 CASE WHEN p.pay_status='Comparable' THEN j.salary_min END AS `Lower amount`,
 CASE WHEN p.pay_status='Comparable' THEN j.salary_max END AS `Upper amount`, p.pay_midpoint AS `Midpoint amount`,
 COALESCE(l.city,'Not recorded') AS City,
 CASE WHEN l.city IS NULL THEN 'Not recorded' ELSE CONCAT(l.city,', ',l.province) END AS `City and province`,
 COALESCE(CONCAT(o.occupation_title,' (',o.noc_code,')'),'Not recorded') AS `Occupation and NOC`,
 CASE WHEN j.weekly_hours_min IS NULL THEN 'Not recorded'
      WHEN (j.weekly_hours_min+j.weekly_hours_max)/2 < 20 THEN 'Under 20'
      WHEN (j.weekly_hours_min+j.weekly_hours_max)/2 < 30 THEN '20 to <30'
      WHEN (j.weekly_hours_min+j.weekly_hours_max)/2 < 40 THEN '30 to <40'
      WHEN (j.weekly_hours_min+j.weekly_hours_max)/2 <= 40 THEN '40'
      ELSE 'Over 40' END AS `Weekly hours band`,
 CASE WHEN j.weekly_hours_min IS NULL THEN 6
      WHEN (j.weekly_hours_min+j.weekly_hours_max)/2 < 20 THEN 1
      WHEN (j.weekly_hours_min+j.weekly_hours_max)/2 < 30 THEN 2
      WHEN (j.weekly_hours_min+j.weekly_hours_max)/2 < 40 THEN 3
      WHEN (j.weekly_hours_min+j.weekly_hours_max)/2 <= 40 THEN 4 ELSE 5 END AS `Hours sort`,
 COALESCE(p.salary_condition_dental,'Not recorded') AS `Dental flag`,
 COALESCE(p.salary_condition_medical,'Not recorded') AS `Medical flag`,
 COALESCE(p.employment_term_evening,'Not recorded') AS `Evening flag`,
 t.period_date AS `Period date`
FROM JobPosting j JOIN postings p ON p.snapshot_id=j.posting_id
LEFT JOIN Occupation o ON o.occupation_id=j.occupation_id
JOIN Location l ON l.location_id=j.location_id JOIN TimePeriod t ON t.period_id=j.period_id;
