# 新主机部署流程

本目录现在只认两份数据库脚本：

- `kong.sql`：当前数据库导出的空表结构
- `qianyi_data_min.sql`：最小必需数据

`schema_all.sql` 已废弃，不再作为部署入口。

## 1. 安装 MySQL

建议安装：

- MySQL Server 8.x
- MySQL Command Line Client
- MySQL Workbench（可选）

安装后确认：

- MySQL 服务已启动
- 3306 端口可用
- 可以用 `root` 登录

## 2. 建库

登录 MySQL：

```powershell
mysql -u root -p
```

执行：

```sql
CREATE DATABASE IF NOT EXISTS shiyou_files
  CHARACTER SET utf8mb4
  COLLATE utf8mb4_unicode_ci;
```

如果这台机器要作为数据库服务器给其他机器访问，再额外创建业务账号，例如：

```sql
CREATE USER IF NOT EXISTS 'shiyou_app'@'%' IDENTIFIED BY 'StrongPass_2026!';
GRANT ALL PRIVILEGES ON shiyou_files.* TO 'shiyou_app'@'%';
FLUSH PRIVILEGES;
```

## 3. 导入空表结构

在项目根目录执行：

```powershell
cmd /c "mysql -u root -p < deployment\kong.sql"
```

这一步只建表，不导业务数据。

## 4. 导入最小必需数据

继续执行：

```powershell
cmd /c "mysql -u root -p < deployment\qianyi_data_min.sql"
```

这一步目前只补：

- `file_types`

目的是保证上传、文件分类等代码路径不会因为字典缺失直接报错。

## 5. 准备文件目录

数据库只存元数据，真实文件仍然在磁盘目录里。

至少准备这 3 个同级目录：

- `shiyou_file_storage`
- `special_strategy_inputs`
- `special_strategy_runtime`

例如：

```text
D:\shiyou_data\shiyou_file_storage
D:\shiyou_data\special_strategy_inputs
D:\shiyou_data\special_strategy_runtime
```

注意：

- `special_strategy_inputs`
- `special_strategy_runtime`

必须和 `storage_root` 在同一级目录。

## 6. 复制特检公共模板

把以下文件复制到 `special_strategy_inputs`：

- `pages/output_special_strategy/manual_fill.xlsx`
- `pages/output_special_strategy/report_metadata.template.json`
- `pages/output_special_strategy/special_strategy_params.json`
- `pages/output_special_strategy/special_strategy_report_template.docx`
- `pages/output_special_strategy/special_strategy_template.xlsm`

## 7. 部署代码并安装依赖

```powershell
cd D:\pyproject\shiyou
python -m venv .venv
.venv\Scripts\activate
python -m pip install -U pip
pip install -r requirements.txt
```

当前 `requirements.txt` 已补齐：

- `PyMySQL`
- `pywin32`

## 8. 配置 db_config.json

复制模板：

```powershell
copy shiyou_db\db_config.example.json shiyou_db\db_config.json
```

按新主机实际情况修改：

- `database.host`
- `database.port`
- `database.user`
- `database.password`
- `database.database`
- `storage_root`

如果这台机器也是数据库服务器，建议 `host` 直接写这台机器的固定 IP，不要只写 `127.0.0.1`。

## 9. 验证数据库连通

```powershell
@'
from services.file_db_adapter import list_files
rows = list_files(module_code="model_files")
print("ok", len(rows))
'@ | python -
```

## 10. 启动程序

```powershell
python main.py
```

## 11. 当前部署口径

当前这套部署是：

- 空表结构：`kong.sql`
- 最小数据：`qianyi_data_min.sql`
- 不导历史业务数据
- 不迁 MySQL 物理数据文件

如果后续需要迁历史业务数据，应另外单独生成数据脚本，不要再混进空表结构脚本里。
