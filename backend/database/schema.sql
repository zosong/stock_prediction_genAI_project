CREATE TABLE Company(
    company_id PRIMARY KEY,
    company_name VARCHAR(255) NOT NULL,
    stock_ticker VARCHAR(10) NOT NULL UNIQUE,
    sector VARCHAR(100),
    industry VARCHAR(100)
)

CREATE TABLE Article(
    article_id PRIMARY KEY,
    title VARCHAR(500) NOT NULL,
    summary TEXT NOT NULL,
    publication_date TIMESTAMP NOT NULL,
    url VARCHAR(1000) NOT NULL,
    source_location VARCHAR(2000)
)

CREATE TABLE ArticleCompanyLink(
    link_id PRIMARY KEY,
    article_id INT NOT NULL,
    company_id INT NOT NULL,
    FOREIGN KEY (article_id) REFERENCES Article(article_id),
    FOREIGN KEY (company_id) REFERENCES Company(company_id)
)

CREATE TABLE OfficialReport(
    report_id PRIMARY KEY,
    company_id INT NOT NULL,
    title VARCHAR(500) NOT NULL,
    report_type VARCHAR(100) NOT NULL,
    period_start DATE NOT NULL,
    period_end DATE NOT NULL,
    publication_date TIMESTAMP NOT NULL,
    summary TEXT,
    url VARCHAR(1000) NOT NULL,
    source_location VARCHAR(2000),
    FOREIGN KEY (company_id) REFERENCES Company(company_id)
)