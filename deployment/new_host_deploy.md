# 新主机部署流程

本目录用于集中放置“数据库迁移 + 新主机部署”相关文件。

## 1. 先安装数据库软件

建议在新主机安装：

- MySQL Server 8.x
- MySQL Shell 或 MySQL Command Line Client
- MySQL Workbench（可选）

安装完成后确认：

- MySQL 服务已启动
- 3306 端口已放通
- 可以使用 `root` 或管理账户登录

## 2. 执行总建表脚本

首次初始化空库时执行：

```powershell
mysql -u root -p < deployment\schema_all.sql
```

该脚本会：

- 创建数据库 `shiyou_files`
- 创建当前项目实际使用的全部表
- 初始化 `file_types` 字典数据

## 3. 从旧远端数据库导出

这里采用逻辑迁移：

- 导出 SQL dump
- 导入到新主机

不需要迁移 MySQL 的物理数据文件目录。

在可访问旧数据库的机器上执行：

```powershell
mysqldump -h 183.168.97.2 -P 3306 -u shiyou_app -p --single-transaction --routines --triggers --default-character-set=utf8mb4 shiyou_files > D:\backup\shiyou_files.sql
```

## 4. 导入到新主机

```powershell
mysql -u root -p shiyou_files < D:\backup\shiyou_files.sql
```

如果目标库是全新空库，通常直接导入 dump 即可。

如果你想先建空库、再补齐表结构、最后再导入，也可以按以下顺序：

1. 执行 `deployment\schema_all.sql`
2. 导入 `shiyou_files.sql`

## 5. 迁移文件存储目录

数据库只存元数据，真实文件不在 MySQL 里。必须同时迁移以下目录：

- `Y:\shiyou_file_storage`
- `Y:\special_strategy_inputs`
- `Y:\special_strategy_runtime`

建议新主机尽量保持相同盘符和目录结构，避免历史记录中的绝对路径失效。

## 6. 部署代码到新主机

示例目录：

```text
D:\pyproject\shiyou
```

建议命令：

```powershell
cd D:\pyproject\shiyou
python -m venv .venv
.venv\Scripts\activate
python -m pip install -U pip
pip install -r requirements.txt
```

## 7. 配置 db_config.json

复制模板：

```powershell
copy shiyou_db\db_config.example.json shiyou_db\db_config.json
```

然后按新主机实际情况修改：

- `database.host`
- `database.port`
- `database.user`
- `database.password`
- `database.database`
- `storage_root`

如果代码部署在数据库主机本机，`host` 建议优先写：

- `127.0.0.1`

如果代码部署在其他机器，`host` 写新数据库服务器 IP。

## 8. 验证

### 8.1 验证数据库可连

```powershell
@'
from services.file_db_adapter import list_files
rows = list_files(module_code="model_files")
print("ok", len(rows))
'@ | python -
```

### 8.2 验证主程序能启动

```powershell
python main.py
```

### 8.3 验证特检 Word 自动更新

当前代码会调用：

- `pythoncom`
- `win32com.client`

因此新主机必须安装：

- Microsoft Word 桌面版

否则特检报告的目录静默更新链路无法工作。

## 9. 建议的迁移顺序

推荐按这个顺序做，不要乱：

1. 安装 MySQL 8.x
2. 创建数据库管理账号
3. 执行 `deployment\schema_all.sql`
4. 从旧库导出 dump
5. 导入到新主机
6. 拷贝 `shiyou_file_storage` 和两个特检共享目录
7. 部署代码
8. 安装 Python 依赖
9. 配置 `db_config.json`
10. 启动并验证

## 10. 注意事项

- 代码不会硬编码数据库地址，仍然通过 `db_config.json` 连接数据库。
- 数据库迁移采用逻辑导出/导入，不迁移 MySQL 物理文件。
- 如果只迁数据库、不迁文件目录，页面会出现“记录在库里但文件打不开”。
- 如果改了 `storage_root` 路径，旧记录里只依赖 `storage_path` 的文件可能失效。
- `requirements.txt` 已补入 `PyMySQL` 和 `pywin32`，新主机直接用它安装即可。
