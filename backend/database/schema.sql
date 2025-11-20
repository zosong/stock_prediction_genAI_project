CREATE TABLE Company(
    company_id INT PRIMARY KEY,
    company_name VARCHAR(255) NOT NULL,
    stock_ticker VARCHAR(10) NOT NULL UNIQUE,
    sector VARCHAR(100),
    industry VARCHAR(100)
);

CREATE TABLE Article(
    article_id INT PRIMARY KEY,
    title VARCHAR(500) NOT NULL,
    summary TEXT NOT NULL,
    publication_date TIMESTAMP NOT NULL,
    url VARCHAR(1000) NOT NULL,
    source_location VARCHAR(2000)
);

CREATE TABLE ArticleCompanyLink(
    link_id INT PRIMARY KEY,
    article_id INT NOT NULL,
    company_id INT NOT NULL,
    FOREIGN KEY (article_id) REFERENCES Article(article_id) ON DELETE CASCADE,
    FOREIGN KEY (company_id) REFERENCES Company(company_id) ON DELETE CASCADE,
    UNIQUE (article_id, company_id)
);

CREATE TABLE OfficialReport(
    report_id INT PRIMARY KEY,
    company_id INT NOT NULL,
    title VARCHAR(500) NOT NULL,
    report_type VARCHAR(100) NOT NULL,
    period_start DATE NOT NULL,
    period_end DATE NOT NULL,
    publication_date TIMESTAMP NOT NULL,
    summary TEXT,
    url VARCHAR(1000) NOT NULL,
    source_location VARCHAR(2000),
    FOREIGN KEY (company_id) REFERENCES Company(company_id) ON DELETE CASCADE
);

CREATE TABLE SocialMedia(
    post_id INT PRIMARY KEY,
    platform VARCHAR(20) NOT NULL,
    user_id VARCHAR(100) NOT NULL,
    author_handle VARCHAR(100) NOT NULL,
    content TEXT NOT NULL,
    post_time TIMESTAMP NOT NULL,
    url VARCHAR(1000) NOT NULL,
    like_count INT DEFAULT 0,
    repost_count INT DEFAULT 0
);

CREATE TABLE SocialPostCompanyLink(
    link_id INT PRIMARY KEY,
    post_id INT NOT NULL,
    company_id INT NOT NULL,
    FOREIGN KEY (post_id) REFERENCES SocialMedia(post_id) ON DELETE CASCADE,
    FOREIGN KEY (company_id) REFERENCES Company(company_id) ON DELETE CASCADE,
    UNIQUE (post_id, company_id)
);

CREATE TABLE PredictionSummary(
    prediction_id INT PRIMARY KEY,
    trend VARCHAR(10),
    confidence DECIMAL(5, 2) NOT NULL,
    reason TEXT,
    prediction_time TIMESTAMP NOT NULL,
    company_id INT NOT NULL,
    model_version VARCHAR(50),
    FOREIGN KEY (company_id) REFERENCES Company(company_id) ON DELETE CASCADE,
    CHECK (trend IN ('UP','DOWN','STABLE')),
    CHECK (confidence >= 0 AND confidence <= 100)
);