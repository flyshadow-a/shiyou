# 文件管理数据库设计规划

## 1. 设计结论

当前 `file_records + logical_path` 的方案可以继续兼容已有数据，但不再适合作为长期主设计。

原因是当前文件管理已经从“按字符串路径归档文件”升级为以下需求：

- 所有文件路径都需要带平台上下文：公司、油田、平台。
- 历次改造文件新增改造项目后，模型文件需要自动出现对应二级目录。
- 检测记录文件需要项目描述、抽检记录、项目编辑/删除与文件目录联动。
- 模型文件、检测记录文件、历次改造文件都需要按业务项目动态生成目录。
- 改造项目改名或年份变更时，显示目录名应变化，但文件不应丢失。

因此目标设计应改为：

- 用目录实体表表达树形目录。
- 用文件记录表保存文件元数据。
- 用业务表保存改造项目、检测项目、抽检记录等结构化数据。
- 文件记录通过 `directory_id` 和可选业务外键绑定目录/项目，而不是只依赖 `logical_path` 字符串。

`logical_path` 暂时保留，用于兼容旧数据、导入导出、调试展示，不再作为长期主关联键。

## 2. 外部设计依据

本方案参考常见关系型数据库层级建模方式：

- 邻接表：目录表通过 `parent_id` 指向自身，适合大多数层级存储，结构简单、并发友好。
- 递归查询：支持用递归 CTE 查询目录子树。
- 物化路径：可作为冗余字段提高前缀查询和展示效率。

对本项目而言，目录层级较浅，主要操作是新增、改名、软删除和读取子目录，因此采用“邻接表 + 冗余路径字段”的混合方案最稳妥。

## 3. 当前表保留与职责调整

### 3.1 `file_records`

继续作为文件元数据主表。

当前已有字段继续保留：

- `id`
- `original_name`
- `stored_name`
- `file_ext`
- `file_type_id`
- `module_code`
- `logical_path`
- `facility_code`
- `storage_path`
- `storage_rel_path`
- `file_size`
- `file_hash`
- `source_modified_at`
- `uploaded_at`
- `updated_at`
- `category_name`
- `work_condition`
- `remark`
- `document_code`
- `document_title`
- `design_stage_code`
- `design_stage_name`
- `discipline_code`
- `discipline_name`
- `file_class_code`
- `file_class_name`
- `asset_unit_code`
- `asset_unit_name`
- `module_unit_code`
- `module_unit_name`
- `drawing_no`
- `sub_sequence`
- `recognition_status`
- `recognition_message`
- `is_deleted`

建议新增字段：

- `directory_id`
  - 外键指向 `document_directories.id`
  - 文件真正所属目录
- `related_entity_type`
  - 可选，例如 `rebuild_directory`、`inspection_project`、`model_root`
- `related_entity_id`
  - 可选，存对应业务实体 id
- `display_order`
  - 同目录下文件排序

职责调整：

- `directory_id` 是主归属。
- `logical_path` 只作为旧数据兼容和调试展示。
- `category_name` 仍可用于文件类别显示，但不再承担目录关系。

### 3.2 `document_rebuild_directories`

继续作为“历次改造文件”的业务项目表。

职责：

- 记录某个平台下的改造项目。
- 提供模型文件动态目录的来源。

现有字段合理：

- `facility_code`
- `project_type`
- `seq_no`
- `directory_name`
- `project_name`
- `project_year`
- `summary_text`
- `sort_order`
- `is_deleted`

建议补充：

- `model_directory_id`
  - 可选，关联模型文件中自动生成的“xxx（yyyy）模型”目录。
  - 如果不想强绑定，也可由服务层按 `related_entity_type/id` 动态查找。

### 3.3 `inspection_projects`

继续作为检测项目表。

职责：

- 记录定期检测、特殊事件检测等检测项目。
- 驱动检测记录文件目录。
- 提供检测描述。

现有字段基本合理：

- `facility_code`
- `project_type`
- `project_name`
- `project_year`
- `event_date`
- `summary_text`
- `sort_order`
- `is_deleted`

建议补充：

- `directory_id`
  - 对应检测记录文件中的项目目录。

### 3.4 `inspection_findings`

继续作为抽检记录表。

职责：

- 存检测项目下的结构化抽检记录。
- 与文件记录分离。

现有字段合理：

- `project_id`
- `item_code`
- `item_type`
- `risk_level`
- `conclusion`
- `sort_order`
- `is_deleted`

## 4. 建议新增核心目录表

### `document_directories`

用于统一表达所有文件管理页面的目录树。

字段建议：

- `id`
  - 主键
- `facility_code`
  - 平台隔离字段
- `module_code`
  - 页面/模块，例如：
    - `design_docs`
    - `history_rebuild`
    - `inspection_records`
    - `model_files`
- `parent_id`
  - 自引用外键，根目录为 `NULL`
- `name`
  - 当前显示名称
- `stable_key`
  - 稳定键，不随显示名变化
  - 示例：`current_model`、`detail_design_model`、`rebuild_directory_12`
- `directory_type`
  - 目录类型，例如：
    - `root`
    - `fixed`
    - `business_project`
    - `model_category`
    - `file_category`
- `related_entity_type`
  - 可选，例如：
    - `rebuild_directory`
    - `inspection_project`
- `related_entity_id`
  - 可选，关联业务表主键
- `path_cache`
  - 冗余展示路径，例如 `模型文件/某改造（2026）模型/静力`
  - 可重算，不作为唯一业务依据
- `depth`
  - 层级深度
- `sort_order`
  - 同级排序
- `is_system`
  - 系统固定目录不可手动删除
- `is_deleted`
  - 软删除
- `created_at`
- `updated_at`

建议索引：

- `(facility_code, module_code, parent_id, sort_order)`
- `(facility_code, module_code, stable_key)`
- `(related_entity_type, related_entity_id)`
- `(facility_code, module_code, path_cache)`

唯一性建议：

- 同一平台、同一模块、同一父目录下，`stable_key` 唯一。
- 显示名 `name` 不强制全局唯一。

## 5. 模型文件目录生成规则

模型文件根目录来自 `document_directories`，不是页面硬编码。

固定二级目录：

- `当前模型`
- `详细设计模型`

动态二级目录：

- 来源：`document_rebuild_directories`
- 条件：
  - `facility_code = 当前平台`
  - `project_type = history_rebuild` 或历史兼容空值
  - `is_deleted = false`
- 显示名：
  - `directory_name（project_year）模型`
  - 若无年份，则 `directory_name模型`
- 稳定键：
  - `rebuild_directory_{id}_model`

每个二级目录下固定生成五个三级目录：

- `静力`
- `地震`
- `疲劳`
- `倒塌`
- `其他模型`

三级目录建议 stable_key：

- `static`
- `seismic`
- `fatigue`
- `collapse`
- `other_model`

重要规则：

- 改造项目改名或年份变更时，只更新目录 `name` 和 `path_cache`。
- 不修改文件记录的真实归属，因为文件通过 `directory_id` 关联。
- 删除改造项目时，关联模型目录软删除，目录下文件按业务要求软删除或保留隐藏。

## 6. 检测记录文件目录生成规则

检测记录文件目录应由 `inspection_projects` 驱动。

一级/二级结构建议：

- `检测记录文件`
  - `定期检测`
    - `{project_name}`
  - `特殊事件检测`
    - `{project_name}`

检测项目目录字段：

- `related_entity_type = inspection_project`
- `related_entity_id = inspection_projects.id`
- `stable_key = inspection_project_{id}`

检测描述来自：

- `inspection_projects.summary_text`

抽检记录来自：

- `inspection_findings`

文件来自：

- `file_records.directory_id`

## 7. 历次改造文件目录生成规则

历次改造文件目录由 `document_rebuild_directories` 驱动。

建议结构：

- `历次改造文件`
  - `{directory_name}`
    - `结构(ST)`
      - `规格书`
      - `报告`
      - `图纸`
      - `料单`
      - `设计基础`
    - `总体(GE)`
      - `图纸`
      - `规格书`
      - `报告`
    - `其他`

改造项目目录字段：

- `related_entity_type = rebuild_directory`
- `related_entity_id = document_rebuild_directories.id`
- `stable_key = rebuild_directory_{id}`

## 8. 文件上传规则

新上传文件流程：

1. 页面确定当前目录 `directory_id`。
2. 用户选择文件类别或系统自动识别类别。
3. 写入 `file_records`：
   - `facility_code`
   - `module_code`
   - `directory_id`
   - `related_entity_type`
   - `related_entity_id`
   - `category_name`
   - `work_condition`
   - `remark`
   - 文件识别字段
4. 同步写入 `logical_path` 作为兼容展示值。

修改/替换文件：

- 对于“同类别只允许一个文件”的目录，可软删除旧记录或标记旧版本。
- 对于允许多个文件的类别，新增文件记录。

建议后续新增版本字段：

- `version_no`
- `replaced_by_id`
- `is_current`

## 9. 迁移策略

### 第一步：加表加字段

新增：

- `document_directories`

修改：

- `file_records.directory_id`
- `file_records.related_entity_type`
- `file_records.related_entity_id`
- `file_records.display_order`

不删除：

- `logical_path`

### 第二步：初始化系统固定目录

为每个平台生成：

- 设计文件根目录
- 历次改造文件根目录
- 检测记录文件根目录
- 模型文件根目录
- 模型文件下的 `当前模型`、`详细设计模型`

### 第三步：从业务表生成动态目录

从 `document_rebuild_directories` 生成：

- 历次改造项目目录
- 模型文件对应改造模型目录

从 `inspection_projects` 生成：

- 检测项目目录

### 第四步：回填历史文件

按旧 `file_records.logical_path` 解析并匹配目录：

- 能匹配业务实体的，写入 `directory_id` 和 `related_entity_*`。
- 不能匹配的，挂到对应模块的“未分类/其他”目录。

### 第五步：服务层切换读取逻辑

优先按 `directory_id` 查询。

旧数据兼容：

- 如果 `directory_id` 为空，继续按 `logical_path` 查询。
- 上传新文件必须写 `directory_id`。

### 第六步：页面逐步移除硬编码树

页面只负责：

- 请求某模块目录树。
- 根据目录类型渲染操作按钮。
- 上传文件时传 `directory_id`。

目录生成、命名、同步由服务层完成。

## 10. 推荐服务接口

新增服务接口：

- `ensure_system_directories(facility_code)`
- `sync_rebuild_model_directories(facility_code)`
- `sync_inspection_project_directories(facility_code)`
- `list_document_tree(facility_code, module_code)`
- `get_directory(directory_id)`
- `create_directory(...)`
- `rename_directory(directory_id, name)`
- `soft_delete_directory(directory_id)`
- `list_files_by_directory(directory_id)`
- `upload_file_to_directory(directory_id, local_path, metadata)`

兼容接口保留：

- `list_files_by_prefix(...)`
- `load_docman_records(...)`
- `replace_docman_file(...)`

但新页面逻辑应逐步切到 directory API。

## 11. 适合当前项目的最终判断

短期：

- 当前数据库可以继续运行。
- 不建议马上删除 `logical_path`。
- 当前功能可以通过服务层补丁继续迭代。

中期：

- 必须引入 `document_directories`。
- 模型文件与历次改造文件的联动应通过 `related_entity_type/id` 实现。
- 检测记录文件应通过 `inspection_project_id` 或目录 `related_entity_id` 关联。

长期：

- 页面不再拼路径。
- 业务实体负责生成目录。
- 文件表只记录“这个文件属于哪个目录/哪个业务对象”。
- 显示路径可以随业务名称变化重新计算，文件归属不受影响。
