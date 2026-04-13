# 文件管理数据库规划

## 目标

- 所有文件页统一走 `MySQL 元数据 + 磁盘文件`。
- 前端页面样式和交互不变。
- 空文件夹不再预铺样例行。
- 一行对应一个文件，同一类别允许多行。
- 平台数据按 `facility_code` 隔离。

## 已有表

### `file_types`

- `id`
- `code`
- `name`
- `description`
- `sort_order`
- `is_active`
- `created_at`
- `updated_at`

### `file_records`

- `id`
- `original_name`
- `stored_name`
- `file_ext`
- `file_type_id`
- `module_code`
- `logical_path`
- `facility_code`
- `storage_path`
- `file_size`
- `file_hash`
- `source_modified_at`
- `uploaded_at`
- `updated_at`
- `remark`
- `is_deleted`

## 建议新增业务表

### `facility_profiles`

存平台描述和基础信息。

- `id`
- `facility_code`
- `facility_name`
- `branch`
- `op_company`
- `oilfield`
- `facility_type`
- `category`
- `start_time`
- `design_life`
- `description_text`
- `updated_at`

### `inspection_projects`

存检测项目主表，覆盖完工检测、第一次检测、第 N 次检测、定期检测、特殊事件检测、延寿检测等。

- `id`
- `facility_code`
- `project_type`
  - `complete`
  - `first`
  - `nth`
  - `periodic`
  - `special_event`
  - `life_extension`
- `project_name`
- `project_year`
- `event_date`
- `summary_text`
- `created_at`
- `updated_at`
- `is_deleted`

### `inspection_findings`

存抽检记录、特殊事件检测记录、延寿检测记录等结构化结果。

- `id`
- `project_id`
- `item_code`
- `item_type`
  - `joint`
  - `member`
  - `area`
  - `other`
- `risk_level`
- `conclusion`
- `sort_order`
- `created_at`
- `updated_at`
- `is_deleted`

## 文件挂载方式

文件本体仍然只存在 `file_records`。

页面侧按下面约定取文件：

- `module_code`
  - `model_files`
  - `doc_man`
  - `special_strategy`
  - 其他模块后续再扩展
- `facility_code`
  - 平台隔离
- `logical_path`
  - 页面路径 + 项目路径 + 行号

示例：

- `详细设计/结构/设计图纸/row_1`
- `历史改造信息/改造项目A/row_3`
- `定期检测/第1次定期检测/row_2`
- `特殊事件检测/台风损伤检测/row_4`

## 页面落地规则

### 文件页

- 使用统一 `DocManWidget`
- `db_list_mode=True`
- `hide_empty_templates=True`
- 点击“新增”时创建空白一行

### 结构化业务页

下列表不要再用 demo 数据作为最终来源：

- 平台描述
- 抽检记录
- 特殊事件检测记录
- 延寿检测记录

这些内容应改为读取：

- `facility_profiles`
- `inspection_projects`
- `inspection_findings`

## 迁移顺序建议

1. 当前模型 / 详细设计 / 历史改造 等纯文件页先统一到 `file_records`
2. 定期检测 / 特殊事件检测 的中间文件区统一到 `DocManWidget`
3. 平台描述迁入 `facility_profiles`
4. 抽检记录 / 特殊事件记录 / 延寿记录迁入 `inspection_projects + inspection_findings`

