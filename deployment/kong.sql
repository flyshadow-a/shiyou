CREATE DATABASE  IF NOT EXISTS `shiyou_files` /*!40100 DEFAULT CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci */ /*!80016 DEFAULT ENCRYPTION='N' */;
USE `shiyou_files`;
-- MySQL dump 10.13  Distrib 8.0.44, for Win64 (x86_64)
--
-- Host: 183.168.97.2    Database: shiyou_files
-- ------------------------------------------------------
-- Server version	8.0.42-0ubuntu0.20.04.1

/*!40101 SET @OLD_CHARACTER_SET_CLIENT=@@CHARACTER_SET_CLIENT */;
/*!40101 SET @OLD_CHARACTER_SET_RESULTS=@@CHARACTER_SET_RESULTS */;
/*!40101 SET @OLD_COLLATION_CONNECTION=@@COLLATION_CONNECTION */;
/*!50503 SET NAMES utf8 */;
/*!40103 SET @OLD_TIME_ZONE=@@TIME_ZONE */;
/*!40103 SET TIME_ZONE='+00:00' */;
/*!40014 SET @OLD_UNIQUE_CHECKS=@@UNIQUE_CHECKS, UNIQUE_CHECKS=0 */;
/*!40014 SET @OLD_FOREIGN_KEY_CHECKS=@@FOREIGN_KEY_CHECKS, FOREIGN_KEY_CHECKS=0 */;
/*!40101 SET @OLD_SQL_MODE=@@SQL_MODE, SQL_MODE='NO_AUTO_VALUE_ON_ZERO' */;
/*!40111 SET @OLD_SQL_NOTES=@@SQL_NOTES, SQL_NOTES=0 */;

--
-- Table structure for table `facility_profiles`
--

DROP TABLE IF EXISTS `facility_profiles`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `facility_profiles` (
  `id` int NOT NULL AUTO_INCREMENT,
  `facility_code` varchar(100) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NOT NULL,
  `facility_name` varchar(255) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `branch` varchar(255) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `op_company` varchar(255) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `oilfield` varchar(255) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `facility_type` varchar(100) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `category` varchar(100) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `start_time` varchar(100) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `design_life` varchar(100) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `description_text` text CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci,
  `updated_at` datetime NOT NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `facility_code` (`facility_code`),
  KEY `ix_facility_profiles_code` (`facility_code`)
) ENGINE=InnoDB AUTO_INCREMENT=3 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `file_records`
--

DROP TABLE IF EXISTS `file_records`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `file_records` (
  `id` bigint NOT NULL AUTO_INCREMENT,
  `original_name` varchar(255) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NOT NULL,
  `stored_name` varchar(255) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NOT NULL,
  `file_ext` varchar(20) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `file_type_id` int NOT NULL,
  `module_code` varchar(100) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NOT NULL,
  `logical_path` varchar(255) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `facility_code` varchar(100) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `storage_path` varchar(500) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NOT NULL,
  `storage_rel_path` varchar(500) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `file_size` bigint DEFAULT NULL,
  `file_hash` varchar(64) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `source_modified_at` datetime DEFAULT NULL,
  `uploaded_at` datetime NOT NULL,
  `updated_at` datetime NOT NULL,
  `category_name` varchar(255) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `work_condition` varchar(255) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `remark` text CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci,
  `is_deleted` tinyint(1) NOT NULL,
  PRIMARY KEY (`id`),
  KEY `ix_file_records_hash` (`file_hash`),
  KEY `ix_file_records_type_module_path` (`file_type_id`,`module_code`,`logical_path`),
  KEY `ix_file_records_facility` (`facility_code`),
  CONSTRAINT `file_records_ibfk_1` FOREIGN KEY (`file_type_id`) REFERENCES `file_types` (`id`)
) ENGINE=InnoDB AUTO_INCREMENT=42 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `file_types`
--

DROP TABLE IF EXISTS `file_types`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `file_types` (
  `id` int NOT NULL AUTO_INCREMENT,
  `code` varchar(50) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NOT NULL,
  `name` varchar(100) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NOT NULL,
  `description` text CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci,
  `sort_order` int NOT NULL,
  `is_active` tinyint(1) NOT NULL,
  `created_at` datetime NOT NULL,
  `updated_at` datetime NOT NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `code` (`code`)
) ENGINE=InnoDB AUTO_INCREMENT=10 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `forbidden_target_joints`
--

DROP TABLE IF EXISTS `forbidden_target_joints`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `forbidden_target_joints` (
  `id` bigint NOT NULL AUTO_INCREMENT,
  `job_name` varchar(100) NOT NULL,
  `dummy_name` varchar(100) DEFAULT NULL,
  `joint_id` varchar(20) NOT NULL,
  `source_line` text,
  `reason` varchar(200) DEFAULT NULL,
  PRIMARY KEY (`id`),
  KEY `idx_ftj_job_joint` (`job_name`,`joint_id`),
  KEY `idx_ftj_job_dummy` (`job_name`,`dummy_name`)
) ENGINE=InnoDB AUTO_INCREMENT=8990 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `inspection_findings`
--

DROP TABLE IF EXISTS `inspection_findings`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `inspection_findings` (
  `id` bigint NOT NULL AUTO_INCREMENT,
  `project_id` bigint NOT NULL,
  `item_code` varchar(255) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `item_type` varchar(50) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `risk_level` varchar(50) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `conclusion` text CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci,
  `sort_order` int NOT NULL,
  `created_at` datetime NOT NULL,
  `updated_at` datetime NOT NULL,
  `is_deleted` tinyint(1) NOT NULL,
  PRIMARY KEY (`id`),
  KEY `ix_inspection_findings_project_sort` (`project_id`,`sort_order`),
  CONSTRAINT `inspection_findings_ibfk_1` FOREIGN KEY (`project_id`) REFERENCES `inspection_projects` (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `inspection_projects`
--

DROP TABLE IF EXISTS `inspection_projects`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `inspection_projects` (
  `id` bigint NOT NULL AUTO_INCREMENT,
  `facility_code` varchar(100) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NOT NULL,
  `project_type` varchar(50) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NOT NULL,
  `project_name` varchar(255) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NOT NULL,
  `project_year` varchar(50) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `event_date` varchar(50) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `summary_text` text CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci,
  `sort_order` int NOT NULL,
  `created_at` datetime NOT NULL,
  `updated_at` datetime NOT NULL,
  `is_deleted` tinyint(1) NOT NULL,
  PRIMARY KEY (`id`),
  KEY `ix_inspection_projects_sort` (`facility_code`,`project_type`,`sort_order`),
  KEY `ix_inspection_projects_facility_type` (`facility_code`,`project_type`)
) ENGINE=InnoDB AUTO_INCREMENT=6 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `joints`
--

DROP TABLE IF EXISTS `joints`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `joints` (
  `id` bigint NOT NULL AUTO_INCREMENT,
  `job_name` varchar(100) NOT NULL,
  `joint_id` varchar(20) NOT NULL,
  `x` double DEFAULT NULL,
  `y` double DEFAULT NULL,
  `z` double DEFAULT NULL,
  `mark` varchar(50) DEFAULT NULL,
  PRIMARY KEY (`id`),
  KEY `idx_joints_job_joint` (`job_name`,`joint_id`),
  KEY `idx_joints_job_z` (`job_name`,`z`)
) ENGINE=InnoDB AUTO_INCREMENT=481266 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `leg_candidates`
--

DROP TABLE IF EXISTS `leg_candidates`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `leg_candidates` (
  `id` bigint NOT NULL AUTO_INCREMENT,
  `job_name` varchar(100) NOT NULL,
  `candidate_no` int NOT NULL,
  `joint_id` varchar(20) NOT NULL,
  `x` double DEFAULT NULL,
  `y` double DEFAULT NULL,
  `z` double DEFAULT NULL,
  `max_od` double DEFAULT NULL,
  PRIMARY KEY (`id`),
  KEY `idx_leg_candidates_job_joint` (`job_name`,`joint_id`)
) ENGINE=InnoDB AUTO_INCREMENT=14040 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `load_cases`
--

DROP TABLE IF EXISTS `load_cases`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `load_cases` (
  `id` bigint NOT NULL AUTO_INCREMENT,
  `job_name` varchar(100) NOT NULL,
  `load_case` varchar(20) NOT NULL,
  `load_type` varchar(20) DEFAULT NULL,
  `mark` varchar(50) DEFAULT NULL,
  PRIMARY KEY (`id`),
  KEY `idx_loadcases_job_case` (`job_name`,`load_case`)
) ENGINE=InnoDB AUTO_INCREMENT=35149 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `members`
--

DROP TABLE IF EXISTS `members`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `members` (
  `id` bigint NOT NULL AUTO_INCREMENT,
  `job_name` varchar(100) NOT NULL,
  `joint_a` varchar(20) NOT NULL,
  `joint_b` varchar(20) NOT NULL,
  `group_id` varchar(20) DEFAULT NULL,
  `mark` varchar(50) DEFAULT NULL,
  PRIMARY KEY (`id`),
  KEY `idx_members_job_a` (`job_name`,`joint_a`),
  KEY `idx_members_job_b` (`job_name`,`joint_b`),
  KEY `idx_members_job_group` (`job_name`,`group_id`)
) ENGINE=InnoDB AUTO_INCREMENT=873247 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `new_groups`
--

DROP TABLE IF EXISTS `new_groups`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `new_groups` (
  `id` bigint NOT NULL AUTO_INCREMENT,
  `job_name` varchar(100) NOT NULL,
  `group_id` varchar(20) NOT NULL,
  `group_type` varchar(30) NOT NULL,
  `od_mm` double DEFAULT NULL,
  `wt_mm` double DEFAULT NULL,
  `od_cm` double DEFAULT NULL,
  `wt_cm` double DEFAULT NULL,
  `slot_no` int NOT NULL,
  `sequence_no` int NOT NULL,
  `mark` varchar(50) DEFAULT NULL,
  PRIMARY KEY (`id`),
  KEY `idx_ng_job_group` (`job_name`,`group_id`),
  KEY `idx_ng_job_slot` (`job_name`,`slot_no`)
) ENGINE=InnoDB AUTO_INCREMENT=145 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `new_joints`
--

DROP TABLE IF EXISTS `new_joints`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `new_joints` (
  `id` bigint NOT NULL AUTO_INCREMENT,
  `job_name` varchar(100) NOT NULL,
  `joint_id` varchar(20) NOT NULL,
  `x` double DEFAULT NULL,
  `y` double DEFAULT NULL,
  `z` double DEFAULT NULL,
  `fixity` varchar(20) DEFAULT NULL,
  `joint_kind` varchar(30) NOT NULL,
  `slot_no` int NOT NULL,
  `sequence_no` int NOT NULL,
  `mark` varchar(50) DEFAULT NULL,
  PRIMARY KEY (`id`),
  KEY `idx_nj_job_joint` (`job_name`,`joint_id`),
  KEY `idx_nj_job_slot` (`job_name`,`slot_no`),
  KEY `idx_nj_job_z` (`job_name`,`z`)
) ENGINE=InnoDB AUTO_INCREMENT=769 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `new_members`
--

DROP TABLE IF EXISTS `new_members`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `new_members` (
  `id` bigint NOT NULL AUTO_INCREMENT,
  `job_name` varchar(100) NOT NULL,
  `joint_a` varchar(20) NOT NULL,
  `joint_b` varchar(20) NOT NULL,
  `group_id` varchar(20) NOT NULL,
  `offset_ax_mm` double DEFAULT NULL,
  `offset_ay_mm` double DEFAULT NULL,
  `offset_az_mm` double DEFAULT NULL,
  `offset_bx_mm` double DEFAULT NULL,
  `offset_by_mm` double DEFAULT NULL,
  `offset_bz_mm` double DEFAULT NULL,
  `member_kind` varchar(30) NOT NULL,
  `connection_type` varchar(50) DEFAULT NULL,
  `slot_no` int NOT NULL,
  `sequence_no` int NOT NULL,
  `mark` varchar(50) DEFAULT NULL,
  PRIMARY KEY (`id`),
  KEY `idx_nm_job_slot` (`job_name`,`slot_no`),
  KEY `idx_nm_job_group` (`job_name`,`group_id`),
  KEY `idx_nm_job_a` (`job_name`,`joint_a`),
  KEY `idx_nm_job_b` (`job_name`,`joint_b`)
) ENGINE=InnoDB AUTO_INCREMENT=1097 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `new_riser_groups`
--

DROP TABLE IF EXISTS `new_riser_groups`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `new_riser_groups` (
  `id` bigint NOT NULL AUTO_INCREMENT,
  `job_name` varchar(100) NOT NULL,
  `group_id` varchar(20) NOT NULL,
  `group_type` varchar(30) NOT NULL,
  `od_mm` double DEFAULT NULL,
  `wt_mm` double DEFAULT NULL,
  `od_cm` double DEFAULT NULL,
  `wt_cm` double DEFAULT NULL,
  `riser_no` int NOT NULL,
  `sequence_no` int NOT NULL,
  `mark` varchar(50) DEFAULT NULL,
  PRIMARY KEY (`id`),
  KEY `idx_nrg_job_group` (`job_name`,`group_id`),
  KEY `idx_nrg_job_riser` (`job_name`,`riser_no`)
) ENGINE=InnoDB AUTO_INCREMENT=97 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `new_riser_joints`
--

DROP TABLE IF EXISTS `new_riser_joints`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `new_riser_joints` (
  `id` bigint NOT NULL AUTO_INCREMENT,
  `job_name` varchar(100) NOT NULL,
  `joint_id` varchar(20) NOT NULL,
  `x` double DEFAULT NULL,
  `y` double DEFAULT NULL,
  `z` double DEFAULT NULL,
  `fixity` varchar(20) DEFAULT NULL,
  `joint_kind` varchar(30) NOT NULL,
  `riser_no` int NOT NULL,
  `sequence_no` int NOT NULL,
  `mark` varchar(50) DEFAULT NULL,
  PRIMARY KEY (`id`),
  KEY `idx_nrj_job_joint` (`job_name`,`joint_id`),
  KEY `idx_nrj_job_riser` (`job_name`,`riser_no`),
  KEY `idx_nrj_job_z` (`job_name`,`z`)
) ENGINE=InnoDB AUTO_INCREMENT=481 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `new_riser_members`
--

DROP TABLE IF EXISTS `new_riser_members`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `new_riser_members` (
  `id` bigint NOT NULL AUTO_INCREMENT,
  `job_name` varchar(100) NOT NULL,
  `joint_a` varchar(20) NOT NULL,
  `joint_b` varchar(20) NOT NULL,
  `group_id` varchar(20) NOT NULL,
  `offset_ax_mm` double DEFAULT NULL,
  `offset_ay_mm` double DEFAULT NULL,
  `offset_az_mm` double DEFAULT NULL,
  `offset_bx_mm` double DEFAULT NULL,
  `offset_by_mm` double DEFAULT NULL,
  `offset_bz_mm` double DEFAULT NULL,
  `member_kind` varchar(30) NOT NULL,
  `connection_type` varchar(50) DEFAULT NULL,
  `riser_no` int NOT NULL,
  `sequence_no` int NOT NULL,
  `mark` varchar(50) DEFAULT NULL,
  PRIMARY KEY (`id`),
  KEY `idx_nrm_job_riser` (`job_name`,`riser_no`),
  KEY `idx_nrm_job_group` (`job_name`,`group_id`),
  KEY `idx_nrm_job_a` (`job_name`,`joint_a`),
  KEY `idx_nrm_job_b` (`job_name`,`joint_b`)
) ENGINE=InnoDB AUTO_INCREMENT=641 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `oilfield_env_profile`
--

DROP TABLE IF EXISTS `oilfield_env_profile`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `oilfield_env_profile` (
  `id` bigint NOT NULL AUTO_INCREMENT,
  `branch` varchar(100) NOT NULL,
  `op_company` varchar(100) NOT NULL,
  `oilfield` varchar(100) NOT NULL,
  `version_no` int NOT NULL DEFAULT '1',
  `remark` varchar(255) DEFAULT NULL,
  `created_at` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP,
  `updated_at` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  UNIQUE KEY `uk_oilfield_env_profile` (`branch`,`op_company`,`oilfield`,`version_no`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `oilfield_water_level_item`
--

DROP TABLE IF EXISTS `oilfield_water_level_item`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `oilfield_water_level_item` (
  `id` bigint NOT NULL AUTO_INCREMENT,
  `profile_id` bigint NOT NULL,
  `group_name` varchar(50) DEFAULT NULL,
  `item_name` varchar(100) NOT NULL,
  `value` decimal(10,3) NOT NULL,
  `unit` varchar(20) NOT NULL DEFAULT 'm',
  `sort_order` int NOT NULL DEFAULT '0',
  `created_at` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP,
  `updated_at` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  KEY `idx_water_level_profile` (`profile_id`),
  KEY `idx_water_level_sort` (`profile_id`,`sort_order`),
  KEY `idx_water_level_group` (`profile_id`,`group_name`),
  CONSTRAINT `fk_water_level_profile` FOREIGN KEY (`profile_id`) REFERENCES `oilfield_env_profile` (`id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `oilfield_wind_param_item`
--

DROP TABLE IF EXISTS `oilfield_wind_param_item`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `oilfield_wind_param_item` (
  `id` bigint NOT NULL AUTO_INCREMENT,
  `profile_id` bigint NOT NULL,
  `group_name` varchar(100) NOT NULL,
  `item_name` varchar(50) NOT NULL,
  `return_period` int NOT NULL,
  `value` decimal(10,3) NOT NULL,
  `unit` varchar(20) NOT NULL DEFAULT 'm/s',
  `sort_order` int NOT NULL DEFAULT '0',
  `created_at` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP,
  `updated_at` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  KEY `idx_wind_profile` (`profile_id`),
  KEY `idx_wind_sort` (`profile_id`,`sort_order`),
  KEY `idx_wind_group` (`profile_id`,`group_name`),
  KEY `idx_wind_period` (`profile_id`,`return_period`),
  CONSTRAINT `fk_wind_param_profile` FOREIGN KEY (`profile_id`) REFERENCES `oilfield_env_profile` (`id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `oilfield_wave_param_item`
--

DROP TABLE IF EXISTS `oilfield_wave_param_item`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `oilfield_wave_param_item` (
  `id` bigint NOT NULL AUTO_INCREMENT,
  `profile_id` bigint NOT NULL,
  `group_name` varchar(100) NOT NULL,
  `item_name` varchar(100) NOT NULL,
  `return_period` int NOT NULL,
  `value` decimal(10,3) NOT NULL,
  `unit` varchar(20) NOT NULL,
  `sort_order` int NOT NULL DEFAULT '0',
  `created_at` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP,
  `updated_at` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  KEY `idx_wave_profile` (`profile_id`),
  KEY `idx_wave_sort` (`profile_id`,`sort_order`),
  KEY `idx_wave_group` (`profile_id`,`group_name`),
  KEY `idx_wave_period` (`profile_id`,`return_period`),
  CONSTRAINT `fk_wave_param_profile` FOREIGN KEY (`profile_id`) REFERENCES `oilfield_env_profile` (`id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `oilfield_current_param_item`
--

DROP TABLE IF EXISTS `oilfield_current_param_item`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `oilfield_current_param_item` (
  `id` bigint NOT NULL AUTO_INCREMENT,
  `profile_id` bigint NOT NULL,
  `group_name` varchar(100) NOT NULL,
  `item_name` varchar(100) NOT NULL,
  `return_period` int NOT NULL,
  `value` decimal(10,3) NOT NULL,
  `unit` varchar(20) NOT NULL DEFAULT 'm/s',
  `sort_order` int NOT NULL DEFAULT '0',
  `created_at` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP,
  `updated_at` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  KEY `idx_current_profile` (`profile_id`),
  KEY `idx_current_sort` (`profile_id`,`sort_order`),
  KEY `idx_current_group` (`profile_id`,`group_name`),
  KEY `idx_current_period` (`profile_id`,`return_period`),
  CONSTRAINT `fk_current_param_profile` FOREIGN KEY (`profile_id`) REFERENCES `oilfield_env_profile` (`id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `platform_load_information_items`
--

DROP TABLE IF EXISTS `platform_load_information_items`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `platform_load_information_items` (
  `id` bigint NOT NULL AUTO_INCREMENT,
  `facility_code` varchar(100) COLLATE utf8mb4_unicode_ci NOT NULL,
  `seq_no` int NOT NULL,
  `project_name` varchar(255) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `rebuild_time` varchar(100) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `rebuild_content` text COLLATE utf8mb4_unicode_ci,
  `total_weight_mt` varchar(100) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `weight_limit_mt` varchar(100) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `weight_delta_mt` varchar(100) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `center_xyz` varchar(255) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `center_radius_m` varchar(100) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `fx_kn` varchar(100) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `fy_kn` varchar(100) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `fz_kn` varchar(100) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `mx_kn_m` varchar(100) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `my_kn_m` varchar(100) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `mz_kn_m` varchar(100) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `safety_op` varchar(100) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `safety_extreme` varchar(100) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `overall_assessment` varchar(100) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `assessment_org` varchar(255) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `sort_order` int NOT NULL,
  `created_at` datetime NOT NULL,
  `updated_at` datetime NOT NULL,
  PRIMARY KEY (`id`),
  KEY `ix_platform_load_information_facility_sort` (`facility_code`,`sort_order`)
) ENGINE=InnoDB AUTO_INCREMENT=3 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `platform_strength_marine_growth_item`
--

DROP TABLE IF EXISTS `platform_strength_marine_growth_item`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `platform_strength_marine_growth_item` (
  `id` bigint NOT NULL AUTO_INCREMENT,
  `profile_id` bigint NOT NULL,
  `facility_code` varchar(100) COLLATE utf8mb4_unicode_ci NOT NULL,
  `layer_no` int NOT NULL,
  `upper_limit_m` decimal(10,3) DEFAULT NULL,
  `lower_limit_m` decimal(10,3) DEFAULT NULL,
  `thickness_mm` decimal(10,3) DEFAULT NULL,
  `density_t_per_m3` decimal(10,3) DEFAULT NULL,
  `sort_order` int NOT NULL DEFAULT '0',
  `created_at` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP,
  `updated_at` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  KEY `fk_strength_marine_profile` (`profile_id`),
  CONSTRAINT `fk_strength_marine_profile` FOREIGN KEY (`profile_id`) REFERENCES `oilfield_env_profile` (`id`) ON DELETE CASCADE
) ENGINE=InnoDB AUTO_INCREMENT=784 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `platform_strength_pile_info_item`
--

DROP TABLE IF EXISTS `platform_strength_pile_info_item`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `platform_strength_pile_info_item` (
  `id` bigint NOT NULL AUTO_INCREMENT,
  `profile_id` bigint NOT NULL,
  `facility_code` varchar(100) COLLATE utf8mb4_unicode_ci NOT NULL,
  `pile_head_id` varchar(50) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `scour_depth_m` decimal(10,3) DEFAULT NULL,
  `compressive_capacity_t` decimal(12,3) DEFAULT NULL,
  `uplift_capacity_t` decimal(12,3) DEFAULT NULL,
  `submerged_weight_t` decimal(12,3) DEFAULT NULL,
  `is_display_row` tinyint(1) NOT NULL DEFAULT '0',
  `sort_order` int NOT NULL DEFAULT '0',
  `created_at` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP,
  `updated_at` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  KEY `fk_strength_pile_profile` (`profile_id`),
  KEY `idx_ps_pile_head` (`profile_id`,`facility_code`,`pile_head_id`),
  CONSTRAINT `fk_strength_pile_profile` FOREIGN KEY (`profile_id`) REFERENCES `oilfield_env_profile` (`id`) ON DELETE CASCADE
) ENGINE=InnoDB AUTO_INCREMENT=88 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `platform_strength_splash_zone_item`
--

DROP TABLE IF EXISTS `platform_strength_splash_zone_item`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `platform_strength_splash_zone_item` (
  `id` bigint NOT NULL AUTO_INCREMENT,
  `profile_id` bigint NOT NULL,
  `facility_code` varchar(100) COLLATE utf8mb4_unicode_ci NOT NULL,
  `upper_limit_m` decimal(10,3) DEFAULT NULL,
  `lower_limit_m` decimal(10,3) DEFAULT NULL,
  `corrosion_allowance_mm_per_y` decimal(10,3) DEFAULT NULL,
  `sort_order` int NOT NULL DEFAULT '0',
  `created_at` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP,
  `updated_at` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  KEY `fk_strength_splash_profile` (`profile_id`),
  CONSTRAINT `fk_strength_splash_profile` FOREIGN KEY (`profile_id`) REFERENCES `oilfield_env_profile` (`id`) ON DELETE CASCADE
) ENGINE=InnoDB AUTO_INCREMENT=88 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `riser_connections`
--

DROP TABLE IF EXISTS `riser_connections`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `riser_connections` (
  `id` bigint NOT NULL AUTO_INCREMENT,
  `job_name` varchar(100) NOT NULL,
  `riser_no` int NOT NULL,
  `level_z` double DEFAULT NULL,
  `connection_type` varchar(50) DEFAULT NULL,
  PRIMARY KEY (`id`),
  KEY `idx_rc_job_riser` (`job_name`,`riser_no`),
  KEY `idx_rc_job_level` (`job_name`,`level_z`)
) ENGINE=InnoDB AUTO_INCREMENT=465 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `risers`
--

DROP TABLE IF EXISTS `risers`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `risers` (
  `id` bigint NOT NULL AUTO_INCREMENT,
  `job_name` varchar(100) NOT NULL,
  `riser_no` int NOT NULL,
  `x` double DEFAULT NULL,
  `y` double DEFAULT NULL,
  `riser_od` double DEFAULT NULL,
  `riser_wt` double DEFAULT NULL,
  `support_od` double DEFAULT NULL,
  `support_wt` double DEFAULT NULL,
  `batter_x` double DEFAULT NULL,
  `batter_y` double DEFAULT NULL,
  PRIMARY KEY (`id`),
  KEY `idx_risers_job_riser` (`job_name`,`riser_no`)
) ENGINE=InnoDB AUTO_INCREMENT=57 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `sacs_groups`
--

DROP TABLE IF EXISTS `sacs_groups`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `sacs_groups` (
  `id` bigint NOT NULL AUTO_INCREMENT,
  `job_name` varchar(100) NOT NULL,
  `group_id` varchar(20) NOT NULL,
  `od` double DEFAULT NULL,
  `mark` varchar(50) DEFAULT NULL,
  PRIMARY KEY (`id`),
  KEY `idx_groups_job_group` (`job_name`,`group_id`)
) ENGINE=InnoDB AUTO_INCREMENT=121807 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `special_strategy_result_snapshots`
--

DROP TABLE IF EXISTS `special_strategy_result_snapshots`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `special_strategy_result_snapshots` (
  `id` bigint NOT NULL AUTO_INCREMENT,
  `run_id` bigint DEFAULT NULL,
  `facility_code` varchar(100) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NOT NULL,
  `result_json` longtext CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NOT NULL,
  `created_at` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP,
  `updated_at` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`)
) ENGINE=InnoDB AUTO_INCREMENT=21 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `special_strategy_risk_images`
--

DROP TABLE IF EXISTS `special_strategy_risk_images`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `special_strategy_risk_images` (
  `id` bigint NOT NULL AUTO_INCREMENT,
  `run_id` bigint DEFAULT NULL,
  `facility_code` varchar(100) COLLATE utf8mb4_unicode_ci NOT NULL,
  `page_code` varchar(100) COLLATE utf8mb4_unicode_ci NOT NULL,
  `image_type` varchar(80) COLLATE utf8mb4_unicode_ci NOT NULL,
  `year_label` varchar(50) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `row_name` varchar(100) COLLATE utf8mb4_unicode_ci NOT NULL,
  `image_path` varchar(1000) COLLATE utf8mb4_unicode_ci NOT NULL,
  `image_name` varchar(255) COLLATE utf8mb4_unicode_ci NOT NULL,
  `remark` varchar(255) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `created_at` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP,
  `updated_at` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`)
) ENGINE=InnoDB AUTO_INCREMENT=454 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `special_strategy_runs`
--

DROP TABLE IF EXISTS `special_strategy_runs`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `special_strategy_runs` (
  `id` bigint NOT NULL AUTO_INCREMENT,
  `facility_code` varchar(100) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NOT NULL,
  `params_json` longtext CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci,
  `metadata_json` longtext CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci,
  `inputs_json` longtext CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci,
  `intermediate_workbook` varchar(500) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NOT NULL,
  `output_report` varchar(500) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `config_path` varchar(500) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `status` varchar(50) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NOT NULL DEFAULT 'completed',
  `created_at` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP,
  `updated_at` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  `report_generated_at` datetime DEFAULT NULL,
  PRIMARY KEY (`id`)
) ENGINE=InnoDB AUTO_INCREMENT=20 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `topside_weight_leg_loads`
--

DROP TABLE IF EXISTS `topside_weight_leg_loads`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `topside_weight_leg_loads` (
  `id` bigint NOT NULL AUTO_INCREMENT,
  `job_name` varchar(100) NOT NULL,
  `weight_no` int NOT NULL,
  `leg_no` int NOT NULL,
  `source_x` double DEFAULT NULL,
  `source_y` double DEFAULT NULL,
  `source_z` double DEFAULT NULL,
  `source_weight_t` double DEFAULT NULL,
  `used_level_z` double DEFAULT NULL,
  `joint_id` varchar(20) NOT NULL,
  `joint_x` double DEFAULT NULL,
  `joint_y` double DEFAULT NULL,
  `joint_z` double DEFAULT NULL,
  `f_uniform` double DEFAULT NULL,
  `f_moment_y` double DEFAULT NULL,
  `f_moment_x` double DEFAULT NULL,
  `leg_load` double DEFAULT NULL,
  PRIMARY KEY (`id`),
  KEY `idx_twll_job_weight` (`job_name`,`weight_no`),
  KEY `idx_twll_job_joint` (`job_name`,`joint_id`)
) ENGINE=InnoDB AUTO_INCREMENT=97 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `topside_weights`
--

DROP TABLE IF EXISTS `topside_weights`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `topside_weights` (
  `id` bigint NOT NULL AUTO_INCREMENT,
  `job_name` varchar(100) NOT NULL,
  `weight_no` int NOT NULL,
  `x` double DEFAULT NULL,
  `y` double DEFAULT NULL,
  `z` double DEFAULT NULL,
  `weight_t` double DEFAULT NULL,
  PRIMARY KEY (`id`),
  KEY `idx_tw_job_weight` (`job_name`,`weight_no`)
) ENGINE=InnoDB AUTO_INCREMENT=22 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `well_slot_connections`
--

DROP TABLE IF EXISTS `well_slot_connections`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `well_slot_connections` (
  `id` bigint NOT NULL AUTO_INCREMENT,
  `job_name` varchar(100) NOT NULL,
  `slot_no` int NOT NULL,
  `level_z` double DEFAULT NULL,
  `connection_type` varchar(50) DEFAULT NULL,
  PRIMARY KEY (`id`),
  KEY `idx_wsc_job_slot` (`job_name`,`slot_no`),
  KEY `idx_wsc_job_level` (`job_name`,`level_z`)
) ENGINE=InnoDB AUTO_INCREMENT=841 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `well_slots`
--

DROP TABLE IF EXISTS `well_slots`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `well_slots` (
  `id` bigint NOT NULL AUTO_INCREMENT,
  `job_name` varchar(100) NOT NULL,
  `slot_no` int NOT NULL,
  `x` double DEFAULT NULL,
  `y` double DEFAULT NULL,
  `conductor_od` double DEFAULT NULL,
  `conductor_wt` double DEFAULT NULL,
  `support_od` double DEFAULT NULL,
  `support_wt` double DEFAULT NULL,
  `top_load_fz` double DEFAULT NULL,
  PRIMARY KEY (`id`),
  KEY `idx_ws_job_slot` (`job_name`,`slot_no`)
) ENGINE=InnoDB AUTO_INCREMENT=85 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `wizard_legs`
--

DROP TABLE IF EXISTS `wizard_legs`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `wizard_legs` (
  `id` bigint NOT NULL AUTO_INCREMENT,
  `job_name` varchar(100) NOT NULL,
  `leg_no` int NOT NULL,
  `joint_id` varchar(20) NOT NULL,
  `x` double DEFAULT NULL,
  `y` double DEFAULT NULL,
  `z` double DEFAULT NULL,
  PRIMARY KEY (`id`),
  KEY `idx_legs_job_joint` (`job_name`,`joint_id`)
) ENGINE=InnoDB AUTO_INCREMENT=809 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `wizard_levels`
--

DROP TABLE IF EXISTS `wizard_levels`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `wizard_levels` (
  `id` bigint NOT NULL AUTO_INCREMENT,
  `job_name` varchar(100) NOT NULL,
  `level_no` int NOT NULL,
  `z` double DEFAULT NULL,
  `occurrence` int DEFAULT NULL,
  `selected` tinyint(1) DEFAULT NULL,
  PRIMARY KEY (`id`),
  KEY `idx_levels_job_z` (`job_name`,`z`)
) ENGINE=InnoDB AUTO_INCREMENT=1011 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `wizard_model_info`
--

DROP TABLE IF EXISTS `wizard_model_info`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `wizard_model_info` (
  `id` bigint NOT NULL AUTO_INCREMENT,
  `job_name` varchar(100) NOT NULL,
  `model_file` text,
  `sea_file` text,
  `new_model_file` text,
  `new_sea_file` text,
  `mudline` double DEFAULT NULL,
  `workpoint` double DEFAULT NULL,
  `autorun_file` text,
  PRIMARY KEY (`id`),
  KEY `idx_model_info_job` (`job_name`)
) ENGINE=InnoDB AUTO_INCREMENT=102 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;
/*!40103 SET TIME_ZONE=@OLD_TIME_ZONE */;

/*!40101 SET SQL_MODE=@OLD_SQL_MODE */;
/*!40014 SET FOREIGN_KEY_CHECKS=@OLD_FOREIGN_KEY_CHECKS */;
/*!40014 SET UNIQUE_CHECKS=@OLD_UNIQUE_CHECKS */;
/*!40101 SET CHARACTER_SET_CLIENT=@OLD_CHARACTER_SET_CLIENT */;
/*!40101 SET CHARACTER_SET_RESULTS=@OLD_CHARACTER_SET_RESULTS */;
/*!40101 SET COLLATION_CONNECTION=@OLD_COLLATION_CONNECTION */;
/*!40111 SET SQL_NOTES=@OLD_SQL_NOTES */;

-- Dump completed on 2026-05-06 16:38:10
