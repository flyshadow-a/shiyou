# shiyou

海上平台结构载荷管理系统桌面程序，技术栈为 `Python + PyQt5`。

## 环境要求

- Windows
- Python 3.10+
- MySQL 8.x

## 安装依赖

```powershell
pip install -r requirements.txt
```

## 数据库初始化

1. 创建数据库：

```sql
CREATE DATABASE shiyou_files CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
```

2. 复制配置模板：

```powershell
copy shiyou_db\db_config.example.json shiyou_db\db_config.json
```

3. 修改 `shiyou_db\db_config.json` 中的数据库连接和存储路径。

4. 初始化表结构：

```powershell
python shiyou_db\init_db.py
```

## 启动

```powershell
python main.py
```

## 目录说明

- `main.py`：程序入口。
- `core/`：页面基类、公共路径、通用下拉控件等基础模块。
- `pages/`：各业务页面及导航配置。
- `services/`：文件管理、特检策略等业务服务与适配层。
- `shiyou_db/`：数据库模型、服务、初始化脚本。
- `scripts/`：运维或修复脚本。
- `docs/`：方案与说明文档。
- `data/`：示例与联调用数据。
- `upload/`：统一上传目录；原 `uploads/` 已合并废弃。
- `pict/`：界面资源。
- `pages/output_special_strategy/`：特检策略算法配置与输出目录。

## 本地运行说明

- 文件上传只保留 `upload/` 一套目录。
- `special_strategy_runtime/`、测试缓存和各类临时渲染目录均属于可再生运行产物。
- 本地敏感配置和运行数据默认不提交。

## 默认忽略的本地内容

- `shiyou_db/db_config.json`
- `shiyou_db/shiyou_file_storage/`
- `upload/`
- `special_strategy_runtime/`
- 本地生成的 `docx/xlsx` 结果文件
