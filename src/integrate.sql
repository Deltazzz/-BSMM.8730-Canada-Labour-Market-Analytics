INSERT INTO Occupation(noc_code,occupation_title)
SELECT p.noc,MAX(p.occupation) FROM postings p LEFT JOIN Occupation o ON o.noc_code=p.noc
WHERE p.noc IS NOT NULL AND o.occupation_id IS NULL GROUP BY p.noc;
INSERT INTO Location(natural_key,province,city,economic_region)
SELECT DISTINCT UNHEX(SHA2(JSON_ARRAY(p.province,p.city,p.economic_region),256)),p.province,p.city,p.economic_region
FROM postings p LEFT JOIN Location l ON l.natural_key=UNHEX(SHA2(JSON_ARRAY(p.province,p.city,p.economic_region),256))
WHERE l.location_id IS NULL;
INSERT INTO TimePeriod(period_id,period_date,calendar_year,calendar_month)
SELECT DISTINCT p.posting_month,CONCAT(p.posting_month,'-01'),YEAR(p.first_posting_date),MONTH(p.first_posting_date)
FROM postings p LEFT JOIN TimePeriod t ON t.period_id=p.posting_month WHERE t.period_id IS NULL;
INSERT INTO Qualification(qualification_type,qualification_name)
SELECT DISTINCT 'Education',p.education FROM postings p LEFT JOIN Qualification q
ON q.qualification_type='Education' AND q.qualification_name=p.education WHERE p.education IS NOT NULL AND q.qualification_id IS NULL
UNION ALL
SELECT DISTINCT 'Experience',p.experience FROM postings p LEFT JOIN Qualification q
ON q.qualification_type='Experience' AND q.qualification_name=p.experience WHERE p.experience IS NOT NULL AND q.qualification_id IS NULL;
DELETE FROM JobPosting;
INSERT INTO JobPosting(posting_id,occupation_id,location_id,period_id,salary_min,salary_max,salary_per,vacancies,weekly_hours_min,weekly_hours_max,employment_type)
SELECT p.snapshot_id,o.occupation_id,l.location_id,t.period_id,p.salary_minimum,p.salary_maximum,p.salary_per,p.vacancy_count,
CASE WHEN p.hours_per='Week' AND p.hours_minimum>0 AND p.hours_maximum>=p.hours_minimum THEN p.hours_minimum END,
CASE WHEN p.hours_per='Week' AND p.hours_minimum>0 AND p.hours_maximum>=p.hours_minimum THEN p.hours_maximum END,p.employment_type
FROM postings p LEFT JOIN Occupation o ON o.noc_code=p.noc
JOIN Location l ON l.natural_key=UNHEX(SHA2(JSON_ARRAY(p.province,p.city,p.economic_region),256))
JOIN TimePeriod t ON t.period_id=p.posting_month;
INSERT INTO PostingQualification(posting_id,qualification_id)
SELECT p.snapshot_id,q.qualification_id FROM postings p JOIN Qualification q ON q.qualification_type='Education' AND p.education=q.qualification_name
UNION ALL SELECT p.snapshot_id,q.qualification_id FROM postings p JOIN Qualification q ON q.qualification_type='Experience' AND p.experience=q.qualification_name;
