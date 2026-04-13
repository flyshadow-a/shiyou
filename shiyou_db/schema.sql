CREATE TABLE IF NOT EXISTS file_types (
    id INT AUTO_INCREMENT PRIMARY KEY,
    code VARCHAR(50) NOT NULL UNIQUE,
    name VARCHAR(100) NOT NULL,
    description TEXT NULL,
    sort_order INT NOT NULL DEFAULT 0,
    is_active TINYINT(1) NOT NULL DEFAULT 1,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS file_records (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    original_name VARCHAR(255) NOT NULL,
    stored_name VARCHAR(255) NOT NULL,
    file_ext VARCHAR(20) NULL,
    file_type_id INT NOT NULL,
    module_code VARCHAR(100) NOT NULL DEFAULT 'general',
    logical_path VARCHAR(255) NULL,
    facility_code VARCHAR(100) NULL,
    storage_path VARCHAR(500) NOT NULL,
    file_size BIGINT NULL,
    file_hash VARCHAR(64) NULL,
    source_modified_at DATETIME NULL,
    uploaded_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    remark TEXT NULL,
    is_deleted TINYINT(1) NOT NULL DEFAULT 0,
    CONSTRAINT fk_file_records_type FOREIGN KEY (file_type_id) REFERENCES file_types(id)
);

CREATE INDEX ix_file_records_type_module_path ON file_records(file_type_id, module_code, logical_path);
CREATE INDEX ix_file_records_facility ON file_records(facility_code);
CREATE INDEX ix_file_records_hash ON file_records(file_hash);

CREATE TABLE IF NOT EXISTS facility_profiles (
    id INT AUTO_INCREMENT PRIMARY KEY,
    facility_code VARCHAR(100) NOT NULL UNIQUE,
    facility_name VARCHAR(255) NULL,
    branch VARCHAR(255) NULL,
    op_company VARCHAR(255) NULL,
    oilfield VARCHAR(255) NULL,
    facility_type VARCHAR(100) NULL,
    category VARCHAR(100) NULL,
    start_time VARCHAR(100) NULL,
    design_life VARCHAR(100) NULL,
    description_text TEXT NULL,
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS inspection_projects (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    facility_code VARCHAR(100) NOT NULL,
    project_type VARCHAR(50) NOT NULL,
    project_name VARCHAR(255) NOT NULL,
    project_year VARCHAR(50) NULL,
    event_date VARCHAR(50) NULL,
    summary_text TEXT NULL,
    sort_order INT NOT NULL DEFAULT 0,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    is_deleted TINYINT(1) NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS inspection_findings (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    project_id BIGINT NOT NULL,
    item_code VARCHAR(255) NULL,
    item_type VARCHAR(50) NULL,
    risk_level VARCHAR(50) NULL,
    conclusion TEXT NULL,
    sort_order INT NOT NULL DEFAULT 0,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    is_deleted TINYINT(1) NOT NULL DEFAULT 0,
    CONSTRAINT fk_inspection_findings_project FOREIGN KEY (project_id) REFERENCES inspection_projects(id)
);

CREATE INDEX ix_facility_profiles_code ON facility_profiles(facility_code);
CREATE INDEX ix_inspection_projects_facility_type ON inspection_projects(facility_code, project_type);
CREATE INDEX ix_inspection_projects_sort ON inspection_projects(facility_code, project_type, sort_order);
CREATE INDEX ix_inspection_findings_project_sort ON inspection_findings(project_id, sort_order);
