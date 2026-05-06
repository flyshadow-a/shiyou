SET NAMES utf8mb4;
USE `shiyou_files`;

-- Minimal required data only.
-- Rule: migrate only data that may directly cause runtime errors when missing.

-- file_types:
-- upload_file() resolves file_type_code against this table.
-- Missing codes may raise:
-- ValueError: Unknown file type code: xxx
-- Some code paths auto-seed this table, but this script makes a fresh database safe
-- even before any Python-side initialization runs.

INSERT INTO `file_types` (
    `id`, `code`, `name`, `description`, `sort_order`, `is_active`, `created_at`, `updated_at`
) VALUES
    (1, 'model', 'model', 'model files', 1, 1, NOW(), NOW()),
    (2, 'seismic', 'seismic', 'seismic files', 2, 1, NOW(), NOW()),
    (3, 'fatigue', 'fatigue', 'fatigue files', 3, 1, NOW(), NOW()),
    (4, 'collapse', 'collapse', 'collapse files', 4, 1, NOW(), NOW()),
    (5, 'drawing', 'drawing', 'drawing files', 5, 1, NOW(), NOW()),
    (6, 'inspection_doc', 'inspection_doc', 'inspection documents', 6, 1, NOW(), NOW()),
    (7, 'history', 'history', 'history files', 7, 1, NOW(), NOW()),
    (8, 'summary', 'summary', 'summary files', 8, 1, NOW(), NOW()),
    (9, 'other', 'other', 'other files', 9, 1, NOW(), NOW())
ON DUPLICATE KEY UPDATE
    `name` = VALUES(`name`),
    `description` = VALUES(`description`),
    `sort_order` = VALUES(`sort_order`),
    `is_active` = VALUES(`is_active`),
    `updated_at` = NOW();

-- Data intentionally not migrated here:
-- file_records
-- facility_profiles
-- inspection_projects
-- inspection_findings
-- platform_load_information_items
-- special_strategy_runs
-- special_strategy_result_snapshots
-- special_strategy_risk_images
-- history_rebuild_projects
-- history_rebuild_project_files
-- oilfield_env_profile
-- oilfield_water_level_item
-- oilfield_wind_param_item
-- oilfield_wave_param_item
-- oilfield_current_param_item
-- platform_strength_splash_zone_item
-- platform_strength_pile_info_item
-- platform_strength_marine_growth_item
-- joints / members / sacs_groups / load_cases / wizard_* / new_* / well_* / risers / topside_*
