CREATE TABLE IF NOT EXISTS Occupation (
    occupation_id INT AUTO_INCREMENT PRIMARY KEY, noc_code CHAR(5) NOT NULL UNIQUE,
    occupation_title VARCHAR(255), classification VARCHAR(16) NOT NULL DEFAULT 'NOC 2021'
) ENGINE=InnoDB;
CREATE TABLE IF NOT EXISTS Location (
    location_id INT AUTO_INCREMENT PRIMARY KEY, natural_key BINARY(32) NOT NULL UNIQUE,
    province VARCHAR(80), city VARCHAR(255), economic_region VARCHAR(255)
) ENGINE=InnoDB;
CREATE TABLE IF NOT EXISTS TimePeriod (
    period_id CHAR(7) PRIMARY KEY, period_date DATE NOT NULL UNIQUE,
    calendar_year SMALLINT NOT NULL, calendar_month TINYINT NOT NULL
) ENGINE=InnoDB;
CREATE TABLE IF NOT EXISTS Qualification (
    qualification_id INT AUTO_INCREMENT PRIMARY KEY, qualification_type VARCHAR(16) NOT NULL,
    qualification_name VARCHAR(255) NOT NULL, UNIQUE(qualification_type,qualification_name)
) ENGINE=InnoDB;
CREATE TABLE IF NOT EXISTS JobPosting (
    posting_id VARCHAR(40) PRIMARY KEY, occupation_id INT, location_id INT NOT NULL, period_id CHAR(7) NOT NULL,
    salary_min DECIMAL(18,6), salary_max DECIMAL(18,6), salary_per VARCHAR(80), vacancies INT UNSIGNED NOT NULL,
    weekly_hours_min DECIMAL(18,6), weekly_hours_max DECIMAL(18,6), employment_type VARCHAR(80),
    FOREIGN KEY (occupation_id) REFERENCES Occupation(occupation_id),
    FOREIGN KEY (location_id) REFERENCES Location(location_id),
    FOREIGN KEY (period_id) REFERENCES TimePeriod(period_id)
) ENGINE=InnoDB;
CREATE TABLE IF NOT EXISTS PostingQualification (
    posting_id VARCHAR(40) NOT NULL, qualification_id INT NOT NULL, PRIMARY KEY(posting_id,qualification_id),
    FOREIGN KEY (posting_id) REFERENCES JobPosting(posting_id) ON DELETE CASCADE,
    FOREIGN KEY (qualification_id) REFERENCES Qualification(qualification_id)
) ENGINE=InnoDB;
CREATE TABLE IF NOT EXISTS ScrapedJobText (
    scraped_text_id BIGINT AUTO_INCREMENT PRIMARY KEY, occupation_id INT NOT NULL,
    page_url VARCHAR(512) NOT NULL, description TEXT, duties TEXT, requirements TEXT, retrieved_at DATETIME NOT NULL,
    UNIQUE(occupation_id,page_url,retrieved_at), FOREIGN KEY (occupation_id) REFERENCES Occupation(occupation_id)
) ENGINE=InnoDB;
CREATE TABLE IF NOT EXISTS StatCanSeries (
    series_id INT PRIMARY KEY, series_title VARCHAR(255) NOT NULL, geography VARCHAR(80) NOT NULL,
    unit VARCHAR(20) NOT NULL, table_code VARCHAR(20) NOT NULL
) ENGINE=InnoDB;
CREATE TABLE IF NOT EXISTS StatCanObservation (
    series_id INT NOT NULL, period_id CHAR(7) NOT NULL, value DECIMAL(9,3) NOT NULL, source_url TEXT NOT NULL,
    PRIMARY KEY(series_id,period_id), FOREIGN KEY(series_id) REFERENCES StatCanSeries(series_id),
    FOREIGN KEY(period_id) REFERENCES TimePeriod(period_id)
) ENGINE=InnoDB;
