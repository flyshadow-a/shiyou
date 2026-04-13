# shiyou

海洋平台文件管理与特检策略桌面程序。

项目目前包含两部分：
- 主程序：PyQt5 桌面界面、文件管理、历史检测、特检策略
- 数据库模块：`shiyou_db/`，负责 MySQL 元数据存储和文件落盘管理

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

2. 复制数据库配置模板：

```powershell
copy shiyou_db\db_config.example.json shiyou_db\db_config.json
```

3. 修改 `shiyou_db\db_config.json` 中的连接信息和存储目录。

4. 初始化表结构：

```powershell
python shiyou_db\init_db.py
```

## 启动程序

```powershell
python main.py
```

## 特检策略配置

仓库中提供两类运行配置：

- 本地开发配置  
  `pages/output_special_strategy/wc19_1d_run_config.json`  
  `pages/output_special_strategy/wc9_7_run_config.json`

- 示例配置  
  `pages/output_special_strategy/wc19_1d_run_config.example.json`  
  `pages/output_special_strategy/wc9_7_run_config.example.json`

新环境建议先复制示例配置，再改成自己的实际路径。

## 目录说明

- `main.py`：程序入口
- `pages/`：各业务页面
- `pages/output_special_strategy/`：特检策略算法、配置、报告生成
- `shiyou_db/`：数据库模型、服务、初始化脚本
- `pict/`：界面资源

## 不提交的本地内容

默认忽略以下内容：

- `shiyou_db/db_config.json`
- `shiyou_db/shiyou_file_storage/`
- `upload/`
- `uploads/`
- `special_strategy_runtime/`
- 本地生成的 `docx/xlsx` 结果文件

这样可以避免把本地密码、数据库文件和运行产物一起提交。
