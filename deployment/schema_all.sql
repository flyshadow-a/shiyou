SET NAMES utf8mb4;
SET FOREIGN_KEY_CHECKS = 0;

CREATE DATABASE IF NOT EXISTS `shiyou_files`
    CHARACTER SET utf8mb4
    COLLATE utf8mb4_unicode_ci;

USE `shiyou_files`;

-- =========================================================
-- 核心文件库与业务表
-- =========================================================

CREATE TABLE IF NOT EXISTS `file_types` (
    `id` INT AUTO_INCREMENT PRIMARY KEY,
    `code` VARCHAR(50) NOT NULL UNIQUE,
    `name` VARCHAR(100) NOT NULL,
    `description` TEXT NULL,
    `sort_order` INT NOT NULL DEFAULT 0,
    `is_active` TINYINT(1) NOT NULL DEFAULT 1,
    `created_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    `updated_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS `file_records` (
    `id` BIGINT AUTO_INCREMENT PRIMARY KEY,
    `original_name` VARCHAR(255) NOT NULL,
    `stored_name` VARCHAR(255) NOT NULL,
    `file_ext` VARCHAR(20) NULL,
    `file_type_id` INT NOT NULL,
    `module_code` VARCHAR(100) NOT NULL DEFAULT 'general',
    `logical_path` VARCHAR(255) NULL,
    `facility_code` VARCHAR(100) NULL,
    `storage_path` VARCHAR(500) NOT NULL,
    `storage_rel_path` VARCHAR(500) NULL,
    `file_size` BIGINT NULL,
    `file_hash` VARCHAR(64) NULL,
    `source_modified_at` DATETIME NULL,
    `uploaded_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    `updated_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    `category_name` VARCHAR(255) NULL,
    `work_condition` VARCHAR(255) NULL,
    `remark` TEXT NULL,
    `is_deleted` TINYINT(1) NOT NULL DEFAULT 0,
    KEY `ix_file_records_type_module_path` (`file_type_id`, `module_code`, `logical_path`),
    KEY `ix_file_records_facility` (`facility_code`),
    KEY `ix_file_records_hash` (`file_hash`),
    CONSTRAINT `fk_file_records_type`
        FOREIGN KEY (`file_type_id`) REFERENCES `file_types` (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS `facility_profiles` (
    `id` INT AUTO_INCREMENT PRIMARY KEY,
    `facility_code` VARCHAR(100) NOT NULL UNIQUE,
    `facility_name` VARCHAR(255) NULL,
    `branch` VARCHAR(255) NULL,
    `op_company` VARCHAR(255) NULL,
    `oilfield` VARCHAR(255) NULL,
    `facility_type` VARCHAR(100) NULL,
    `category` VARCHAR(100) NULL,
    `start_time` VARCHAR(100) NULL,
    `design_life` VARCHAR(100) NULL,
    `description_text` TEXT NULL,
    `updated_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    KEY `ix_facility_profiles_code` (`facility_code`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS `inspection_projects` (
    `id` BIGINT AUTO_INCREMENT PRIMARY KEY,
    `facility_code` VARCHAR(100) NOT NULL,
    `project_type` VARCHAR(50) NOT NULL,
    `project_name` VARCHAR(255) NOT NULL,
    `project_year` VARCHAR(50) NULL,
    `event_date` VARCHAR(50) NULL,
    `summary_text` TEXT NULL,
    `sort_order` INT NOT NULL DEFAULT 0,
    `created_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    `updated_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    `is_deleted` TINYINT(1) NOT NULL DEFAULT 0,
    KEY `ix_inspection_projects_facility_type` (`facility_code`, `project_type`),
    KEY `ix_inspection_projects_sort` (`facility_code`, `project_type`, `sort_order`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS `inspection_findings` (
    `id` BIGINT AUTO_INCREMENT PRIMARY KEY,
    `project_id` BIGINT NOT NULL,
    `item_code` VARCHAR(255) NULL,
    `item_type` VARCHAR(50) NULL,
    `risk_level` VARCHAR(50) NULL,
    `conclusion` TEXT NULL,
    `sort_order` INT NOT NULL DEFAULT 0,
    `created_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    `updated_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    `is_deleted` TINYINT(1) NOT NULL DEFAULT 0,
    KEY `ix_inspection_findings_project_sort` (`project_id`, `sort_order`),
    CONSTRAINT `fk_inspection_findings_project`
        FOREIGN KEY (`project_id`) REFERENCES `inspection_projects` (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS `platform_load_information_items` (
    `id` BIGINT AUTO_INCREMENT PRIMARY KEY,
    `facility_code` VARCHAR(100) NOT NULL,
    `seq_no` INT NOT NULL DEFAULT 0,
    `project_name` VARCHAR(255) NULL,
    `rebuild_time` VARCHAR(100) NULL,
    `rebuild_content` TEXT NULL,
    `total_weight_mt` VARCHAR(100) NULL,
    `weight_limit_mt` VARCHAR(100) NULL,
    `weight_delta_mt` VARCHAR(100) NULL,
    `center_xyz` VARCHAR(255) NULL,
    `center_radius_m` VARCHAR(100) NULL,
    `fx_kn` VARCHAR(100) NULL,
    `fy_kn` VARCHAR(100) NULL,
    `fz_kn` VARCHAR(100) NULL,
    `mx_kn_m` VARCHAR(100) NULL,
    `my_kn_m` VARCHAR(100) NULL,
    `mz_kn_m` VARCHAR(100) NULL,
    `safety_op` VARCHAR(100) NULL,
    `safety_extreme` VARCHAR(100) NULL,
    `overall_assessment` VARCHAR(100) NULL,
    `assessment_org` VARCHAR(255) NULL,
    `sort_order` INT NOT NULL DEFAULT 0,
    `created_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    `updated_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    KEY `ix_platform_load_information_facility_sort` (`facility_code`, `sort_order`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- =========================================================
-- 特检策略状态表
-- =========================================================

CREATE TABLE IF NOT EXISTS `special_strategy_runs` (
    `id` BIGINT AUTO_INCREMENT PRIMARY KEY,
    `facility_code` VARCHAR(100) NOT NULL,
    `params_json` LONGTEXT NULL,
    `metadata_json` LONGTEXT NULL,
    `inputs_json` LONGTEXT NULL,
    `intermediate_workbook` VARCHAR(500) NOT NULL,
    `output_report` VARCHAR(500) NULL,
    `config_path` VARCHAR(500) NULL,
    `status` VARCHAR(50) NOT NULL DEFAULT 'completed',
    `created_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    `updated_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    `report_generated_at` DATETIME NULL,
    KEY `ix_special_strategy_runs_facility` (`facility_code`),
    KEY `ix_special_strategy_runs_facility_updated` (`facility_code`, `updated_at`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS `special_strategy_result_snapshots` (
    `id` BIGINT AUTO_INCREMENT PRIMARY KEY,
    `run_id` BIGINT NULL,
    `facility_code` VARCHAR(100) NOT NULL,
    `result_json` LONGTEXT NOT NULL,
    `created_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    `updated_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    KEY `ix_special_strategy_result_facility` (`facility_code`),
    KEY `ix_special_strategy_result_facility_updated` (`facility_code`, `updated_at`),
    KEY `ix_special_strategy_result_run_id` (`run_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS `special_strategy_risk_images` (
    `id` BIGINT AUTO_INCREMENT PRIMARY KEY,
    `run_id` BIGINT NULL,
    `facility_code` VARCHAR(100) NOT NULL,
    `page_code` VARCHAR(100) NOT NULL,
    `image_type` VARCHAR(80) NOT NULL,
    `year_label` VARCHAR(50) NULL,
    `row_name` VARCHAR(100) NOT NULL,
    `image_path` VARCHAR(1000) NOT NULL,
    `image_name` VARCHAR(255) NOT NULL,
    `remark` VARCHAR(255) NULL,
    `created_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    `updated_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    KEY `ix_ss_risk_images_facility` (`facility_code`),
    KEY `ix_ss_risk_images_run` (`run_id`),
    KEY `ix_ss_risk_images_page` (`page_code`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- =========================================================
-- 结构导入 / 快速评估 / 上部组块辅助表
-- 这些表由页面与服务层运行时使用，但同样属于当前项目实际建表范围。
-- =========================================================

CREATE TABLE IF NOT EXISTS `joints` (
    `id` BIGINT AUTO_INCREMENT PRIMARY KEY,
    `job_name` VARCHAR(100) NOT NULL,
    `joint_id` VARCHAR(20) NOT NULL,
    `x` DOUBLE NULL,
    `y` DOUBLE NULL,
    `z` DOUBLE NULL,
    `mark` VARCHAR(50) NULL,
    KEY `idx_joints_job_joint` (`job_name`, `joint_id`),
    KEY `idx_joints_job_z` (`job_name`, `z`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS `members` (
    `id` BIGINT AUTO_INCREMENT PRIMARY KEY,
    `job_name` VARCHAR(100) NOT NULL,
    `joint_a` VARCHAR(20) NOT NULL,
    `joint_b` VARCHAR(20) NOT NULL,
    `group_id` VARCHAR(20) NULL,
    `mark` VARCHAR(50) NULL,
    KEY `idx_members_job_a` (`job_name`, `joint_a`),
    KEY `idx_members_job_b` (`job_name`, `joint_b`),
    KEY `idx_members_job_group` (`job_name`, `group_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS `sacs_groups` (
    `id` BIGINT AUTO_INCREMENT PRIMARY KEY,
    `job_name` VARCHAR(100) NOT NULL,
    `group_id` VARCHAR(20) NOT NULL,
    `od` DOUBLE NULL,
    `mark` VARCHAR(50) NULL,
    KEY `idx_groups_job_group` (`job_name`, `group_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS `load_cases` (
    `id` BIGINT AUTO_INCREMENT PRIMARY KEY,
    `job_name` VARCHAR(100) NOT NULL,
    `load_case` VARCHAR(20) NOT NULL,
    `load_type` VARCHAR(20) NULL,
    `mark` VARCHAR(50) NULL,
    KEY `idx_loadcases_job_case` (`job_name`, `load_case`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS `wizard_model_info` (
    `id` BIGINT AUTO_INCREMENT PRIMARY KEY,
    `job_name` VARCHAR(100) NOT NULL,
    `model_file` TEXT NULL,
    `sea_file` TEXT NULL,
    `new_model_file` TEXT NULL,
    `new_sea_file` TEXT NULL,
    `mudline` DOUBLE NULL,
    `workpoint` DOUBLE NULL,
    `autorun_file` TEXT NULL,
    KEY `idx_model_info_job` (`job_name`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS `wizard_levels` (
    `id` BIGINT AUTO_INCREMENT PRIMARY KEY,
    `job_name` VARCHAR(100) NOT NULL,
    `level_no` INT NOT NULL,
    `z` DOUBLE NULL,
    `occurrence` INT NULL,
    `selected` TINYINT(1) NULL,
    KEY `idx_levels_job_z` (`job_name`, `z`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS `wizard_legs` (
    `id` BIGINT AUTO_INCREMENT PRIMARY KEY,
    `job_name` VARCHAR(100) NOT NULL,
    `leg_no` INT NOT NULL,
    `joint_id` VARCHAR(20) NOT NULL,
    `x` DOUBLE NULL,
    `y` DOUBLE NULL,
    `z` DOUBLE NULL,
    KEY `idx_legs_job_joint` (`job_name`, `joint_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS `leg_candidates` (
    `id` BIGINT AUTO_INCREMENT PRIMARY KEY,
    `job_name` VARCHAR(100) NOT NULL,
    `candidate_no` INT NOT NULL,
    `joint_id` VARCHAR(20) NOT NULL,
    `x` DOUBLE NULL,
    `y` DOUBLE NULL,
    `z` DOUBLE NULL,
    `max_od` DOUBLE NULL,
    KEY `idx_leg_candidates_job_joint` (`job_name`, `joint_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS `forbidden_target_joints` (
    `id` BIGINT AUTO_INCREMENT PRIMARY KEY,
    `job_name` VARCHAR(100) NOT NULL,
    `dummy_name` VARCHAR(100) NULL,
    `joint_id` VARCHAR(20) NOT NULL,
    `source_line` TEXT NULL,
    `reason` VARCHAR(200) NULL,
    KEY `idx_ftj_job_joint` (`job_name`, `joint_id`),
    KEY `idx_ftj_job_dummy` (`job_name`, `dummy_name`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS `well_slots` (
    `id` BIGINT AUTO_INCREMENT PRIMARY KEY,
    `job_name` VARCHAR(100) NOT NULL,
    `slot_no` INT NOT NULL,
    `x` DOUBLE NULL,
    `y` DOUBLE NULL,
    `conductor_od` DOUBLE NULL,
    `conductor_wt` DOUBLE NULL,
    `support_od` DOUBLE NULL,
    `support_wt` DOUBLE NULL,
    `top_load_fz` DOUBLE NULL,
    KEY `idx_ws_job_slot` (`job_name`, `slot_no`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS `well_slot_connections` (
    `id` BIGINT AUTO_INCREMENT PRIMARY KEY,
    `job_name` VARCHAR(100) NOT NULL,
    `slot_no` INT NOT NULL,
    `level_z` DOUBLE NULL,
    `connection_type` VARCHAR(50) NULL,
    KEY `idx_wsc_job_slot` (`job_name`, `slot_no`),
    KEY `idx_wsc_job_level` (`job_name`, `level_z`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS `risers` (
    `id` BIGINT AUTO_INCREMENT PRIMARY KEY,
    `job_name` VARCHAR(100) NOT NULL,
    `riser_no` INT NOT NULL,
    `x` DOUBLE NULL,
    `y` DOUBLE NULL,
    `riser_od` DOUBLE NULL,
    `riser_wt` DOUBLE NULL,
    `support_od` DOUBLE NULL,
    `support_wt` DOUBLE NULL,
    `batter_x` DOUBLE NULL,
    `batter_y` DOUBLE NULL,
    KEY `idx_risers_job_riser` (`job_name`, `riser_no`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS `riser_connections` (
    `id` BIGINT AUTO_INCREMENT PRIMARY KEY,
    `job_name` VARCHAR(100) NOT NULL,
    `riser_no` INT NOT NULL,
    `level_z` DOUBLE NULL,
    `connection_type` VARCHAR(50) NULL,
    KEY `idx_rc_job_riser` (`job_name`, `riser_no`),
    KEY `idx_rc_job_level` (`job_name`, `level_z`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS `topside_weights` (
    `id` BIGINT AUTO_INCREMENT PRIMARY KEY,
    `job_name` VARCHAR(100) NOT NULL,
    `weight_no` INT NOT NULL,
    `x` DOUBLE NULL,
    `y` DOUBLE NULL,
    `z` DOUBLE NULL,
    `weight_t` DOUBLE NULL,
    KEY `idx_tw_job_weight` (`job_name`, `weight_no`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS `new_groups` (
    `id` BIGINT AUTO_INCREMENT PRIMARY KEY,
    `job_name` VARCHAR(100) NOT NULL,
    `group_id` VARCHAR(20) NOT NULL,
    `group_type` VARCHAR(30) NOT NULL,
    `od_mm` DOUBLE NULL,
    `wt_mm` DOUBLE NULL,
    `od_cm` DOUBLE NULL,
    `wt_cm` DOUBLE NULL,
    `slot_no` INT NOT NULL,
    `sequence_no` INT NOT NULL,
    `mark` VARCHAR(50) NULL,
    KEY `idx_ng_job_group` (`job_name`, `group_id`),
    KEY `idx_ng_job_slot` (`job_name`, `slot_no`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS `new_joints` (
    `id` BIGINT AUTO_INCREMENT PRIMARY KEY,
    `job_name` VARCHAR(100) NOT NULL,
    `joint_id` VARCHAR(20) NOT NULL,
    `x` DOUBLE NULL,
    `y` DOUBLE NULL,
    `z` DOUBLE NULL,
    `fixity` VARCHAR(20) NULL,
    `joint_kind` VARCHAR(30) NOT NULL,
    `slot_no` INT NOT NULL,
    `sequence_no` INT NOT NULL,
    `mark` VARCHAR(50) NULL,
    KEY `idx_nj_job_joint` (`job_name`, `joint_id`),
    KEY `idx_nj_job_slot` (`job_name`, `slot_no`),
    KEY `idx_nj_job_z` (`job_name`, `z`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS `new_members` (
    `id` BIGINT AUTO_INCREMENT PRIMARY KEY,
    `job_name` VARCHAR(100) NOT NULL,
    `joint_a` VARCHAR(20) NOT NULL,
    `joint_b` VARCHAR(20) NOT NULL,
    `group_id` VARCHAR(20) NOT NULL,
    `offset_ax_mm` DOUBLE NULL,
    `offset_ay_mm` DOUBLE NULL,
    `offset_az_mm` DOUBLE NULL,
    `offset_bx_mm` DOUBLE NULL,
    `offset_by_mm` DOUBLE NULL,
    `offset_bz_mm` DOUBLE NULL,
    `member_kind` VARCHAR(30) NOT NULL,
    `connection_type` VARCHAR(50) NULL,
    `slot_no` INT NOT NULL,
    `sequence_no` INT NOT NULL,
    `mark` VARCHAR(50) NULL,
    KEY `idx_nm_job_slot` (`job_name`, `slot_no`),
    KEY `idx_nm_job_group` (`job_name`, `group_id`),
    KEY `idx_nm_job_a` (`job_name`, `joint_a`),
    KEY `idx_nm_job_b` (`job_name`, `joint_b`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS `new_riser_groups` (
    `id` BIGINT AUTO_INCREMENT PRIMARY KEY,
    `job_name` VARCHAR(100) NOT NULL,
    `group_id` VARCHAR(20) NOT NULL,
    `group_type` VARCHAR(30) NOT NULL,
    `od_mm` DOUBLE NULL,
    `wt_mm` DOUBLE NULL,
    `od_cm` DOUBLE NULL,
    `wt_cm` DOUBLE NULL,
    `riser_no` INT NOT NULL,
    `sequence_no` INT NOT NULL,
    `mark` VARCHAR(50) NULL,
    KEY `idx_nrg_job_group` (`job_name`, `group_id`),
    KEY `idx_nrg_job_riser` (`job_name`, `riser_no`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS `new_riser_joints` (
    `id` BIGINT AUTO_INCREMENT PRIMARY KEY,
    `job_name` VARCHAR(100) NOT NULL,
    `joint_id` VARCHAR(20) NOT NULL,
    `x` DOUBLE NULL,
    `y` DOUBLE NULL,
    `z` DOUBLE NULL,
    `fixity` VARCHAR(20) NULL,
    `joint_kind` VARCHAR(30) NOT NULL,
    `riser_no` INT NOT NULL,
    `sequence_no` INT NOT NULL,
    `mark` VARCHAR(50) NULL,
    KEY `idx_nrj_job_joint` (`job_name`, `joint_id`),
    KEY `idx_nrj_job_riser` (`job_name`, `riser_no`),
    KEY `idx_nrj_job_z` (`job_name`, `z`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS `new_riser_members` (
    `id` BIGINT AUTO_INCREMENT PRIMARY KEY,
    `job_name` VARCHAR(100) NOT NULL,
    `joint_a` VARCHAR(20) NOT NULL,
    `joint_b` VARCHAR(20) NOT NULL,
    `group_id` VARCHAR(20) NOT NULL,
    `offset_ax_mm` DOUBLE NULL,
    `offset_ay_mm` DOUBLE NULL,
    `offset_az_mm` DOUBLE NULL,
    `offset_bx_mm` DOUBLE NULL,
    `offset_by_mm` DOUBLE NULL,
    `offset_bz_mm` DOUBLE NULL,
    `member_kind` VARCHAR(30) NOT NULL,
    `connection_type` VARCHAR(50) NULL,
    `riser_no` INT NOT NULL,
    `sequence_no` INT NOT NULL,
    `mark` VARCHAR(50) NULL,
    KEY `idx_nrm_job_riser` (`job_name`, `riser_no`),
    KEY `idx_nrm_job_group` (`job_name`, `group_id`),
    KEY `idx_nrm_job_a` (`job_name`, `joint_a`),
    KEY `idx_nrm_job_b` (`job_name`, `joint_b`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS `topside_weight_leg_loads` (
    `id` BIGINT AUTO_INCREMENT PRIMARY KEY,
    `job_name` VARCHAR(100) NOT NULL,
    `weight_no` INT NOT NULL,
    `leg_no` INT NOT NULL,
    `source_x` DOUBLE NULL,
    `source_y` DOUBLE NULL,
    `source_z` DOUBLE NULL,
    `source_weight_t` DOUBLE NULL,
    `used_level_z` DOUBLE NULL,
    `joint_id` VARCHAR(20) NOT NULL,
    `joint_x` DOUBLE NULL,
    `joint_y` DOUBLE NULL,
    `joint_z` DOUBLE NULL,
    `f_uniform` DOUBLE NULL,
    `f_moment_y` DOUBLE NULL,
    `f_moment_x` DOUBLE NULL,
    `leg_load` DOUBLE NULL,
    KEY `idx_twll_job_weight` (`job_name`, `weight_no`),
    KEY `idx_twll_job_joint` (`job_name`, `joint_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- =========================================================
-- 历史改扩建 / 海域环境参数业务表
-- =========================================================

CREATE TABLE IF NOT EXISTS `history_rebuild_projects` (
    `id` BIGINT NOT NULL AUTO_INCREMENT PRIMARY KEY,
    `facility_code` VARCHAR(64) NOT NULL,
    `facility_name` VARCHAR(255) NOT NULL DEFAULT '',
    `folder_name` VARCHAR(128) NOT NULL,
    `project_order` INT NOT NULL DEFAULT 0,
    `project_name` VARCHAR(255) NOT NULL,
    `project_year` VARCHAR(32) NOT NULL DEFAULT '',
    `conclusion_text` TEXT NOT NULL,
    `created_at` TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    `updated_at` TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    UNIQUE KEY `uq_history_project` (`facility_code`, `folder_name`, `project_name`, `project_year`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS `history_rebuild_project_files` (
    `id` BIGINT NOT NULL AUTO_INCREMENT PRIMARY KEY,
    `project_id` BIGINT NOT NULL,
    `file_order` INT NOT NULL DEFAULT 0,
    `file_name` VARCHAR(255) NOT NULL,
    `file_type` VARCHAR(64) NOT NULL DEFAULT '',
    `updated_text` VARCHAR(64) NOT NULL DEFAULT '',
    `note_text` VARCHAR(255) NOT NULL DEFAULT '',
    `created_at` TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    `updated_at` TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    UNIQUE KEY `uq_project_file` (`project_id`, `file_name`),
    CONSTRAINT `fk_history_project_files_project`
        FOREIGN KEY (`project_id`) REFERENCES `history_rebuild_projects` (`id`)
        ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS `oilfield_env_profile` (
    `id` BIGINT PRIMARY KEY AUTO_INCREMENT,
    `branch` VARCHAR(100) NOT NULL,
    `op_company` VARCHAR(100) NOT NULL,
    `oilfield` VARCHAR(100) NOT NULL,
    `version_no` INT NOT NULL DEFAULT 1,
    `remark` VARCHAR(255) DEFAULT NULL,
    `created_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    `updated_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    UNIQUE KEY `uk_oilfield_env_profile` (`branch`, `op_company`, `oilfield`, `version_no`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS `oilfield_water_level_item` (
    `id` BIGINT PRIMARY KEY AUTO_INCREMENT,
    `profile_id` BIGINT NOT NULL,
    `group_name` VARCHAR(50) DEFAULT NULL,
    `item_name` VARCHAR(100) NOT NULL,
    `value` DECIMAL(10, 3) NOT NULL,
    `unit` VARCHAR(20) NOT NULL DEFAULT 'm',
    `sort_order` INT NOT NULL DEFAULT 0,
    `created_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    `updated_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    KEY `idx_water_level_profile` (`profile_id`),
    KEY `idx_water_level_sort` (`profile_id`, `sort_order`),
    KEY `idx_water_level_group` (`profile_id`, `group_name`),
    CONSTRAINT `fk_water_level_profile`
        FOREIGN KEY (`profile_id`) REFERENCES `oilfield_env_profile` (`id`)
        ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS `oilfield_wind_param_item` (
    `id` BIGINT PRIMARY KEY AUTO_INCREMENT,
    `profile_id` BIGINT NOT NULL,
    `group_name` VARCHAR(100) NOT NULL,
    `item_name` VARCHAR(50) NOT NULL,
    `return_period` INT NOT NULL,
    `value` DECIMAL(10, 3) NOT NULL,
    `unit` VARCHAR(20) NOT NULL DEFAULT 'm/s',
    `sort_order` INT NOT NULL DEFAULT 0,
    `created_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    `updated_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    KEY `idx_wind_profile` (`profile_id`),
    KEY `idx_wind_sort` (`profile_id`, `sort_order`),
    KEY `idx_wind_group` (`profile_id`, `group_name`),
    KEY `idx_wind_period` (`profile_id`, `return_period`),
    CONSTRAINT `fk_wind_param_profile`
        FOREIGN KEY (`profile_id`) REFERENCES `oilfield_env_profile` (`id`)
        ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS `oilfield_wave_param_item` (
    `id` BIGINT PRIMARY KEY AUTO_INCREMENT,
    `profile_id` BIGINT NOT NULL,
    `group_name` VARCHAR(100) NOT NULL,
    `item_name` VARCHAR(100) NOT NULL,
    `return_period` INT NOT NULL,
    `value` DECIMAL(10, 3) NOT NULL,
    `unit` VARCHAR(20) NOT NULL,
    `sort_order` INT NOT NULL DEFAULT 0,
    `created_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    `updated_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    KEY `idx_wave_profile` (`profile_id`),
    KEY `idx_wave_sort` (`profile_id`, `sort_order`),
    KEY `idx_wave_group` (`profile_id`, `group_name`),
    KEY `idx_wave_period` (`profile_id`, `return_period`),
    CONSTRAINT `fk_wave_param_profile`
        FOREIGN KEY (`profile_id`) REFERENCES `oilfield_env_profile` (`id`)
        ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS `oilfield_current_param_item` (
    `id` BIGINT PRIMARY KEY AUTO_INCREMENT,
    `profile_id` BIGINT NOT NULL,
    `group_name` VARCHAR(100) NOT NULL,
    `item_name` VARCHAR(100) NOT NULL,
    `return_period` INT NOT NULL,
    `value` DECIMAL(10, 3) NOT NULL,
    `unit` VARCHAR(20) NOT NULL DEFAULT 'm/s',
    `sort_order` INT NOT NULL DEFAULT 0,
    `created_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    `updated_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    KEY `idx_current_profile` (`profile_id`),
    KEY `idx_current_sort` (`profile_id`, `sort_order`),
    KEY `idx_current_group` (`profile_id`, `group_name`),
    KEY `idx_current_period` (`profile_id`, `return_period`),
    CONSTRAINT `fk_current_param_profile`
        FOREIGN KEY (`profile_id`) REFERENCES `oilfield_env_profile` (`id`)
        ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- =========================================================
-- 初始化文件类型字典
-- =========================================================

INSERT INTO `file_types` (`code`, `name`, `description`, `sort_order`, `is_active`)
VALUES
    ('model', '结构模型', '结构模型与分析输入', 1, 1),
    ('seismic', '地震', '地震分析相关文件', 2, 1),
    ('fatigue', '疲劳', '疲劳分析相关文件', 3, 1),
    ('collapse', '倒塌', '倒塌分析相关文件', 4, 1),
    ('drawing', '图纸', '图纸与示意图', 5, 1),
    ('inspection_doc', '检测文档', '检测报告与文档', 6, 1),
    ('history', '历史资料', '历史检查与重建资料', 7, 1),
    ('summary', '汇总资料', '汇总与统计资料', 8, 1),
    ('other', '其他', '其他文件', 9, 1)
ON DUPLICATE KEY UPDATE
    `name` = VALUES(`name`),
    `description` = VALUES(`description`),
    `sort_order` = VALUES(`sort_order`),
    `is_active` = VALUES(`is_active`),
    `updated_at` = CURRENT_TIMESTAMP;

SET FOREIGN_KEY_CHECKS = 1;
