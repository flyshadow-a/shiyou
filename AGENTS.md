# AGENTS 工作指南（shiyou_v2）
本文件面向在本仓库执行任务的 Agent（含 AI 编码助手）。
目标：快速上手、少踩坑、与现有代码风格保持一致。

## 1. 项目概览
- 技术栈：Python + PyQt5（桌面 GUI），辅以 pandas/openpyxl/matplotlib。
- 应用入口：`main.py`。
- 页面基类：`base_page.py` 中的 `BasePage`。
- 导航配置：`nav_config.py`（树节点键为 `text/page/children`）。
- 业务页面集中在 `pages/`。
- 样例数据集中在 `data/`（含 `.xls/.xlsx/.csv/.inp`）。
- 运行期上传目录有两套：`upload/` 与 `uploads/`（历史并存，勿随意迁移）。

## 2. 环境与依赖
- Python 建议 `3.10+`（仓库使用 `X | None`、`dict[str, T]` 等语法）。
- 建议使用虚拟环境。
```bash
python -m venv .venv
.venv\Scripts\activate
python -m pip install -U pip
```
- 最小运行依赖：
```bash
python -m pip install PyQt5 pandas openpyxl matplotlib xlrd==2.0.1
```
- 说明：`xlrd==2.0.1` 用于读取仓库中的 `.xls` 文件。

## 3. 构建 / 运行 / 测试 / Lint
仓库当前无统一 CI、Makefile、`pytest.ini`，以下命令为推荐实践。

### 3.1 运行
```bash
python main.py
```

### 3.2 语法级“构建”检查
```bash
python -m compileall .
```
- 当前项目无打包脚本；此命令可做最小 smoke check。
- GUI 行为仍需手工打开页面验证。

### 3.3 测试（推荐 pytest）
- 先安装测试依赖：
```bash
python -m pip install pytest pytest-qt
```
- 运行全部测试：
```bash
python -m pytest -q
```
- 运行单个测试文件（重点）：
```bash
python -m pytest tests/test_read_table_xls.py -q
```
- 运行单个测试函数（重点）：
```bash
python -m pytest tests/test_read_table_xls.py::test_options_for -q
```
- 运行单个类中的单测（重点）：
```bash
python -m pytest tests/test_dropdown_bar.py::TestDropdownBar::test_get_all_values -q
```
- 按关键字筛选：
```bash
python -m pytest -k "read_table_xls" -q
```
- 当前仓库暂无 `tests/`，新增测试请放 `tests/` 且命名 `test_*.py`。
- Qt 交互测试优先使用 `pytest-qt` 的 `qtbot`。

### 3.4 Lint 与格式化（当前未强制）
```bash
python -m pip install ruff black
python -m ruff check .
python -m black .
```
- 遵循“改到哪、整理到哪”，避免一次性全仓库格式化。

## 4. Cursor / Copilot 规则同步
已检查：
- `.cursorrules`
- `.cursor/rules/`
- `.github/copilot-instructions.md`
当前状态：仓库中未发现上述规则文件。
若后续新增这些文件：
- 将关键约束同步到本 `AGENTS.md`。
- 规则冲突时，优先更具体、离代码更近的规则。

## 5. 代码风格与工程约定

### 5.1 通用原则
- 先遵循现有结构，再做局部改进，不做无关重构。
- UI 文案、注释、业务术语以中文为主，保持语义连续。
- 每次改动尽量小而完整，便于验证和回溯。

### 5.2 Imports
- 顺序：标准库 -> 第三方 -> 本地模块。
- 同组内顺序保持稳定（字母序或语义分组均可）。
- `PyQt5` 导入较多时用括号换行。
- 避免同一模块重复导入（同文件内收敛到一处）。

### 5.3 格式化
- 4 空格缩进，禁止 Tab。
- 建议行宽 <= 100（历史代码可适度放宽）。
- 多行列表/字典/参数保留尾随逗号，降低 diff 噪音。
- QSS 多行字符串可用三引号，保持缩进整齐。
- 保持 UTF-8 编码，涉及中文文案时避免乱码。

### 5.4 类型标注
- 新增或修改函数尽量补全参数与返回类型。
- Qt 槽函数建议显式 `-> None`。
- 容器类型尽量具体（如 `List[Dict[str, str]]`）。
- 与现有风格一致时可使用 `X | None`。

### 5.5 命名
- 文件名：`snake_case.py`。
- 页面类：`PascalCase` 且建议以 `Page` 结尾。
- 方法/函数：`snake_case`。
- 常量：`UPPER_SNAKE_CASE`（如 `MAX_EXPAND_ROWS`）。
- 信号槽处理函数建议 `_on_xxx`。

### 5.6 页面、导航与 UI 结构
- 业务页面优先继承 `BasePage`。
- 页面主体控件统一挂载到 `self.main_layout`。
- 新页面接入导航时，在 `nav_config.py` 使用 `page` 键，不用 `page_cls`。
- 叶子节点：`{"text": "...", "page": SomePage}`。
- 分组节点：`{"text": "...", "children": [...]}`。

### 5.7 路径与数据文件
- 延续现有 `os.path` 风格（除非当前文件已大量使用 `pathlib`）。
- 基于项目根目录拼接路径，避免硬编码绝对路径。
- 文件读写前先检查存在性；需要时使用 `os.makedirs(..., exist_ok=True)`。
- 涉及上传逻辑时谨慎区分 `upload/` 与 `uploads/`。

### 5.8 错误处理
- 文件 I/O、外部命令、解析逻辑必须做异常保护。
- 捕获异常后给出可操作反馈（`QMessageBox.warning/critical/information`）。
- 错误信息应包含关键路径、文件名或异常文本。
- 避免静默吞异常（如裸 `except` 后 `pass`）。

### 5.9 调试输出
- 临时调试可短期 `print`，交付前应清理。
- 需要长期日志时优先 `logging`。

## 6. 提交前自检（Agent Checklist）
- 代码可启动：`python main.py`（至少不因语法/导入立即崩溃）。
- 受影响页面可达、关键按钮可点击、异常路径有提示框。
- 新页面已在 `nav_config.py` 注册并能从导航打开。
- 文件读写路径正确，不写出仓库外。
- 若新增测试，至少验证单测命令可精确跑到目标用例。
- 未引入与任务无关的大规模格式化/重命名噪音。

## 7. 非目标与注意事项
- 本仓库以业务页面联动为主，不要求一次性工程化重构。
- 未被需求明确要求时，不要改动历史数据样本与上传目录内容。
- 不要擅自替换现有 UI 视觉体系（蓝色系、导航树、表格交互）。

## 8. 本地更新记录（不进 Git）
- 用途：记录你每次对仓库规范、命令、流程的补充说明。
- 使用方式：每次修改后按日期追加一条，写清“改了什么、为什么改”。
- 建议格式：`YYYY-MM-DD：变更内容（可附影响范围）`。
- 示例：
  - 2026-03-18：初始化 AGENTS 文档；补充单测命令与页面接入规范。
  - 2026-03-18：同步当前工作区改动范围：更新主窗口与导航配置，调整载荷信息/结构强度/可行性评估/特检策略等页面逻辑与界面；新增模型文件与特检策略运行产物（`upload/model_files`）及导出样例（`data/platform_load_information_export.csv`），用于联调与回溯。
  - 2026-03-18：已完成与远端 `origin/main` 的合并冲突处理并推送；冲突涉及 `pages/platform_load_information_page.py`、`pages/platform_strength_page.py`、`pages/platform_summary_page.py`，并保留提交 `upload/model_files` 下运行产物及相关页面更新，确保与协作提交一致。
  - 2026-03-18：根据当前改动，已将 `pages/platform_strength_page.py` 中“工作平面高程Workpoint”后的值单元格改为 `QLineEdit`（`self.edt_workpoint`），与上两行输入控件设计保持一致，统一可编辑交互。
  - 2026-03-18：按当前 Git 变更补充页面视觉联调明细（2 文件，`41` 行新增 / `10` 行删除）：`pages/feasibility_assessment_page.py:263` 将表格标题样式由 `font-weight: bold;` 调整为 `font-size: 18px; font-weight: bold; color: #1d2b3a;`；`pages/platform_strength_page.py` 关键参数调整为 `:841` `left_layout.setContentsMargins(8, 6, 8, 8)`、`:1089/:1091` 标题字体 `17px` 且 `margin-top: 10px`、`:1095/:1097/:1098` 标题位置与样式 `subcontrol-position: top left`/`padding: 0 4px`/`background-color: #ffffff`、`:1102` `box_layout.setContentsMargins(10, 6, 10, 10)`、`:1109` 小标题字体 `15px` 粗体、`:1153` 结构模型分组高度余量 `+14 -> +18`、`:1232` 桩基可编辑行高 `30 -> 34`、`:1244` 桩基分组高度余量 `+8 -> +14`、`:1253` 海生物分组内边距 `(8, 8, 8, 10)`、`:1296` 海生物行高 `28 -> 30`、`:1299` 海生物表格高度修正 `+4 -> +8`、`:1307` 海生物分组高度余量 `+6 -> +10`，用于减少留白并避免标题遮挡/行高压缩。
  - 2026-03-18：按当前 Git 变更补充头部与页面联调明细（3 文件，`44` 行新增 / `13` 行删除）：`main.py:314` 左上角图标缩放由 `scaled(28, 28, ...)` 调整为 `scaled(42, 42, ...)`，`main.py:316` 图标容器由 `setFixedSize(30, 30)` 调整为 `setFixedSize(44, 44)`，`main.py:319` 系统标题样式由 `font-size:18px; font-weight:bold;` 调整为 `font-size: 26px; font-weight: 800;`；`pages/feasibility_assessment_page.py:263` 表格标题样式由 `font-weight: bold;` 调整为 `font-size: 18px; font-weight: bold; color: #1d2b3a;`；`pages/platform_strength_page.py` 关键参数保持本次联调结果：`:841` `left_layout.setContentsMargins(8, 6, 8, 8)`、`:1089/:1091` 标题字体 `17px` 且 `margin-top: 10px`、`:1095/:1097/:1098` 标题定位与样式 `subcontrol-position: top left`/`padding: 0 4px`/`background-color: #ffffff`、`:1102` `box_layout.setContentsMargins(10, 6, 10, 10)`、`:1109` 小标题字体 `15px` 粗体、`:1153` 结构模型分组高度余量 `+14 -> +18`、`:1232` 桩基可编辑行高 `30 -> 34`、`:1244` 桩基分组高度余量 `+8 -> +14`、`:1253` 海生物分组内边距 `(8, 8, 8, 10)`、`:1296` 海生物行高 `28 -> 30`、`:1299` 海生物表格高度修正 `+4 -> +8`、`:1307` 海生物分组高度余量 `+6 -> +10`。
  - 2026-03-18：按当前 Git 变更补充导航与油气田页面联调明细（3 文件，`124` 行新增 / `37` 行删除）：`dropdown_bar.py` 新增 Win10/Win11 中文字体回退（`_pick_windows_compatible_zh_font`）与按字体动态高度（`_calc_control_min_height`），支持 `expand/compactMode` 及 `stretch` 解析（`_parse_stretch`），并将 `set_options` 默认参数规范为 `default=""`；`main.py` 新增同源字体回退函数并将左侧菜单树与标签页统一为四号 `14pt`（宋体优先），同时树节点字体改为继承 `self.nav_tree.font()`；`pages/oilfield_water_level_page.py` 新增 `SONGTI_FONT_FALLBACK`，修复选项卡按钮 QSS 花括号转义导致的页面打开异常，顶部下拉条与“保存”按钮调整为左上紧凑对齐、右侧弹性留白，减少违和空隙。
  - 2026-03-19：按当前 Git 变更补充可行性评估结果页标签明细（1 文件，`6` 行新增 / `5` 行删除）：`pages/feasibility_assessment_results_page.py:200` 将“桩承载力操作抗压”文案统一为“操作工况桩基承载力”并新增“极端工况桩基承载力”头部映射；`pages/feasibility_assessment_results_page.py:466` 下部 tab 扩展为 5 项；`pages/feasibility_assessment_results_page.py:566` 使“操作工况桩基承载力/极端工况桩基承载力”共用同一桩基承载力静态表格构建逻辑；`pages/feasibility_assessment_results_page.py:673` 同步更新静态页行数控制注释，确保交互语义一致。
  - 2026-03-19：按当前 Git 变更补充顶部下拉与油气田页面字体联调明细（3 文件，`25` 行新增 / `15` 行删除）：`dropdown_bar.py:56/:58` 将顶部下拉表头与下拉框字体由四号 `14pt` 统一为小四 `12pt`（下拉弹层选项沿用同源字体）；`pages/oilfield_water_level_page.py:43` 新增 `_songti_small_four_font`，并在 `:218/:220/:277/:361/:374/:375` 将“保存”按钮及 tab 驱动的四个表格字体统一为宋体小四，保留表头加粗语义；`pages/feasibility_assessment_results_page.py:200/:466/:566/:673` 保持“操作工况桩基承载力/极端工况桩基承载力”双标签与静态页逻辑映射，确保评估结果页文案与交互一致。
  - 2026-03-19：按当前 Git 变更补充全局小四字体联调明细（4 文件，`30` 行新增 / `20` 行删除）：`main.py:173/:202` 将左侧导航树（QSS 与 QFont）由四号 `14pt` 调整为小四 `12pt`，`main.py:223/:230` 将底部 Tab 导航栏字体由 `14pt` 调整为 `12pt`，`main.py:343` 将系统标题“海上平台结构载荷管理系统”样式由 `26px` 调整为 `12pt`；`dropdown_bar.py:56/:58` 顶部下拉栏表头与下拉框字体统一为小四 `12pt`；`pages/oilfield_water_level_page.py:43/:218/:220/:277/:361/:374/:375` 继续统一“保存”按钮及四个表格为宋体小四并保持表头可加粗；`pages/feasibility_assessment_results_page.py:200/:466/:566/:673` 维持“操作工况桩基承载力/极端工况桩基承载力”双标签与静态表映射一致性，确保评估结果页文案与交互对齐。
  - 2026-03-19：按当前 Git 变更追加字体与评估结果页联调记录（4 文件，`31` 行新增 / `21` 行删除）：`dropdown_bar.py:56/:58` 将顶部下拉栏表头与下拉框字体统一为小四 `12pt`；`main.py:173/:202/:223/:230/:343` 将左侧导航树、底部 Tab 导航栏与系统标题“海上平台结构载荷管理系统”统一为小四；`pages/feasibility_assessment_results_page.py:7/:200/:466/:566/:673` 将“桩承载力操作抗压”语义拆分为“操作工况桩基承载力/极端工况桩基承载力”，并同步 tab 与静态桩基承载力表映射逻辑；`pages/oilfield_water_level_page.py:43/:218/:220/:277/:301/:361/:374/:375` 新增宋体小四字体工厂，统一“保存”按钮、tab 按钮及四个表格字体为 `12pt`，并保持表头可加粗语义。
  - 2026-03-19：按当前 Git 变更追加多页面小四字体与分组样式联调记录（9 文件，`151` 行新增 / `65` 行删除）：`main.py:170/:199/:220/:230/:340` 与 `dropdown_bar.py:53` 将导航树、底部 Tab、系统标题及顶部下拉统一为小四；`pages/platform_load_information_page.py:72/:92/:257/:268/:297/:325/:337/:399/:749/:904` 将平台载荷信息页主表、按钮、序号标签及“重量中心变化曲线”图表（标题/坐标轴/刻度）统一为小四，并缩窄顶部“保存/导出”按钮区域、提高“投产时间”列伸缩比以避免截断；`pages/platform_strength_page.py:691/:700/:1099/:1185/:1227/:1245` 将“结构模型信息/水平层高程/桩基信息/海生物信息”四块表格与 label 统一小四，且通过 `QGroupBox border:none` 与 margin/padding/高度余量调整修复分组标题遮挡并减弱外框线；`pages/summary_information_table_page.py:40/:59/:69/:108/:149/:158/:198` 与 `pages/upper_block_subproject_calculation_table_page.py:59/:122/:130/:171` 同步完成表格页按钮/表格/说明文字小四化（字体用 `pt`，其余尺寸保留 `px`）；`pages/feasibility_assessment_results_page.py` 与 `pages/oilfield_water_level_page.py` 保持双工况标签映射及小四字体一致性；`data/platform_load_information_export.csv` 同步更新导出样例序号与首行演示值，确保与当前页面逻辑一致。
  - 2026-03-19：按当前 Git 变更追加可行性评估页主体字体与列宽联调记录（10 文件，`192` 行新增 / `70` 行删除）：在延续既有 9 文件小四字体联调结果基础上，`pages/feasibility_assessment_page.py:44/:59/:101/:128/:182/:272/:289/:606` 新增宋体小四字体工厂与回退常量，并将页面主体三张表格、表格标题 label、右上角“保存”按钮、底部“创建新模型/计算分析/查看结果”按钮及表内下拉框统一为小四 `12pt`；`pages/feasibility_assessment_page.py:241/:257` 在列宽自适应逻辑中增加“编号”列最小宽度与“新增井槽信息”表“垂向载荷”列最小宽度保护，避免字体统一后表头文本被压缩截断，其余已改文件保持既有联调状态用于联测回归。
  - 2026-03-19：按当前 Git 变更追加工作区联调记录（9 文件，`187` 行新增 / `66` 行删除）：当前未提交改动集中在 `data/platform_load_information_export.csv`、`dropdown_bar.py`、`main.py`、`pages/feasibility_assessment_page.py`、`pages/oilfield_water_level_page.py`、`pages/platform_load_information_page.py`、`pages/platform_strength_page.py`、`pages/summary_information_table_page.py`、`pages/upper_block_subproject_calculation_table_page.py`，整体延续小四字体统一与布局压缩策略；其中 `pages/feasibility_assessment_page.py` 保持主体三表/按钮/标题小四化及“编号列+垂向载荷列”最小宽度保护，`main.py`、`dropdown_bar.py` 与油气田/载荷/强度/汇总/上部组块页面保持导航、Tab、表格与按钮字体一致性，`data/platform_load_information_export.csv` 同步联调样例数据；可行性评估结果页双工况标签与桩基承载力静态表逻辑已独立提交并推送（`da371b1`），不在当前未提交集合内。
  - 2026-03-20：按当前 Git 变更追加“特检策略”页面视觉联调明细（1 文件，涉及 pages/special_inspection_strategy.py）：将顶部右侧操作栏标题及按钮、中间年份 Tab 按钮、上下两张数据表格（含表头、表内容）及其标题的字体统一切换为宋体小四（12pt）；同时统一数据表格底色为白色（#ffffff）、网格线颜色为 #d0d0d0、表头背景色为淡蓝色（#f3f6fb）且字体常规化不加粗，以确保全站视觉及表格交互风格的严格一致。
  - 2026-03-20：按当前 Git 变更追加“新增特检策略”、“更新风险等级结果”两个页面的视觉联调记录（2 文件，涉及 pages/new_special_inspection_page.py, pages/upgrade_special_inspection_result_page.py）：将上述两个页面左侧区域包含表格、表头及相关操作按钮的字体统一更改为宋体小四（12pt）；移除多余的页面标题；针对“新增特检策略”下部的操作按钮采取水平布局避免挤压表格，并将底色统一纯白；针对“更新风险结果”页面优化了自适应列宽计算方式（全列根据内容撑开并补充安全边距以完整呈现标题），并将下部汇总表格的滚动条移除依靠动态计算真实高度完全展开，同时联调其标签在不同 Tab 下动态变更为“构件”或“节点”以优化显示细节。

- 2026-03-23：修复 pages/platform_load_information_page.py 中 PlatformLoadInformationPage 类缺失 _on_save、_on_export 等方法导致的 AttributeError 崩溃问题，恢复了保存、导出、INP结果读取及重心曲线跳转功能。

- 2026-03-23：优化载荷信息页布局（按钮移至底部居中，移除冗余控件）；修复计算表崩溃、空白及缩进问题；增强计算表数据持久化、自动跳转、样式统一及三位小数显示功能。

- 2026-03-23:
    - 修复了 pages/platform_load_information_page.py 中 QCheckBox 未定义的 NameError。
    - 优化了 pages/platform_load_information_page.py 的 _apply_data 方法，确保页面加载数据后立即显示复选框。
    - 解决了 pages/summary_information_table_page.py 中两个横向滚动条嵌套的问题，统一由最外层 QScrollArea 管理滚动。
    - 将 pages/summary_information_table_page.py 的“填表说明”固定在底部，不再随表格滚动而移动。
    - 更新了 pages/summary_information_table_page.py 的按钮样式，应用了与平台载荷信息页一致的橙色主题（TopActionBtn）。

- 2026-03-23:
    - 优化了 pages/platform_strength_page.py 的“快速评估”按钮样式，采用橙色主题。
    - 在 pages/platform_strength_page.py 中实现了从 SACS INP 文件解析 LDOPT 字段以获取泥面高程的逻辑。
    - 调整了结构模型信息表的默认值：节点限制默认为 40，Workpoint 置空。
    - 修复了 pages/platform_strength_page.py 中“水平层高程”标签因 CSS 继承导致的多余框线问题。

- 2026-03-27：按当前 Git 变更追加主程序启动适配记录（1 文件，涉及 `main.py`）：在 `main.py:727` 起恢复 Qt 高 DPI 启动配置，新增 `QApplication.setAttribute(Qt.AA_EnableHighDpiScaling, True)`、`QApplication.setAttribute(Qt.AA_UseHighDpiPixmaps, True)` 以及环境变量 `QT_AUTO_SCREEN_SCALE_FACTOR=1`，用于改善不同缩放比例显示器下的界面与图标显示效果。
- 2026-03-27：按当前 Git 变更追加快速评估页表格交互联调记录（1 文件，涉及 `pages/feasibility_assessment_page.py`）：为“新增井槽信息”“新增立管/电缆信息”“新增组块载荷信息”三张表新增数据行动态增删能力；最后一条数据行悬停时在首列左下侧显示 `+` 用于快速追加新行；序号列右键菜单新增“在上方新增一行 / 在下方新增一行 / 删除当前行”，删除前弹确认框且至少保留 1 条数据行；同时将前两张表“高程及连接形式”列的 `QComboBox` 改为默认仅显示已选文本、鼠标悬停单元格时再显示右侧 `▼` 按钮并弹出下拉，修复删除行后悬停访问已销毁 `QComboBox` 的运行时报错，便于后续 Agent 扫描 `AGENTS.md` 时快速了解本轮交互改造背景。
- 2026-03-27：按当前 Git 变更追加平台载荷信息页表格交互联调记录（1 文件，涉及 `pages/platform_load_information_page.py`）：保留首列“复选框 + 序号”结构，将改扩建项目行操作从底部按钮迁移到首列右键菜单；支持“在上方新增一行 / 在下方新增一行”，删除逻辑统一改为仅对已勾选数据行生效，未勾选时菜单显示灰色提示“请先勾选要删除的行”，勾选后菜单动态显示“删除已勾选行（N）”并在确认后批量删除，同时至少保留 1 条数据行；保留红色结果列原有“读取该行关联的结果文件 (.inp)”右键功能，并移除底部“新增改扩建项目 / 删除改扩建项目”按钮以统一交互入口。
- 2026-03-27：按当前 Git 变更追加结构强度页面左侧表格联调记录（1 文件，涉及 `pages/platform_strength_page.py`）：在“桩基信息”上方新增“飞溅区腐蚀余量”分组表，表头为“飞溅区上限(m) / 飞溅区下限(m) / 腐蚀余量(mm/y)”，整体沿用桩基信息表的单行表格设计与样式；同步将左侧四块区域顺序调整为“结构模型信息 / 飞溅区腐蚀余量 / 桩基信息 / 海生物信息”，并适度压缩分组间距、结构模型信息内边距及桩基/海生物表行高与高度补偿，确保新增一表后四个表均可完整展示且不影响右侧模型预览与其余表格布局。
- 2026-05-11：按当前 Git 变更追加打包策略记录（1 文件，涉及 `main.spec`）：将 `pathex` 显式指向项目根目录，仅保留 `pict/*.png` 作为必需静态资源；明确 `special_strategy_inputs`、`special_strategy_runtime`、`upload`、`data`、`shiyou_db/db_config.json` 以及 `tests/docs/deployment/examples/scripts/__pycache__` 为外置路径，不加入 `datas`；同时在 `excludes` 中排除未使用的 `PyQt6/PySide2/PySide6`，避免误带入其他 Qt 绑定并收紧打包边界。
- 2026-05-11：按当前 Git 变更追加可行性评估报告外置资源打包记录（5 文件，涉及 `main.spec`、`pages/feasibility_assessment_results_page.py`、`pages/output_feasibility_analysis_report/src/resource_paths.py`、`pages/output_feasibility_analysis_report/src/path_config_loader.py`、`pages/output_feasibility_analysis_report/src/config_loader.py`）：为可行性评估报告模块新增“exe 同级目录优先、仓库目录兜底”的资源查找逻辑；将 `pages/output_feasibility_analysis_report` 下两份 `.docx` 模板及 `config/path_config.json`、`config/doc_renderer.xml` 作为外置资源复制到打包输出目录 `output_feasibility_analysis_report/`；同时在 `main.spec` 中补充报告 `src` 子模块隐藏导入收集与额外 `pathex`，并放宽结果页对本地 `src/` 目录存在性的硬依赖，确保打包后仍可生成可行性评估报告且模板配置保持外置可替换。
- 2026-05-11：按当前 Git 变更追加特检策略打包导入修复记录（2 文件，涉及 `services/special_strategy_runtime.py`、`main.spec`）：将特检策略运行时核心导入改为优先使用 `pages.output_special_strategy.inspection_tool` 与 `pages.output_special_strategy.report_jinja2_generator` 的标准包导入，保留原有 `sys.path` 裸导入兜底，避免打包 exe 启动阶段因未命中临时目录导入而出现 `ModuleNotFoundError: inspection_tool`；同时在 `main.spec` 中显式追加上述两个模块的隐藏导入，确保 PyInstaller 在静态分析阶段收录特检策略核心代码。
- 2026-05-11：按当前 Git 变更追加数据库配置外置化打包记录（5 文件，涉及 `shiyou_db/config.py`、`shiyou_db/runtime_db.py`、`services/file_db_adapter.py`、`services/inspection_business_db_adapter.py`、`services/special_strategy_state_db.py`，并同步更新 `main.spec`）：将 `db_config.json` 的默认查找逻辑调整为“环境变量显式路径优先，其次 exe 同级 `shiyou_db/db_config.json`，最后包内兜底”，修复打包后启动阶段误查 `_internal/shiyou_db/db_config.json` 导致的数据库连接失败；同时将 `shiyou_db/db_config.json` 与 `db_config.example.json` 作为外置资源复制到发布目录，保证打包版可直接编辑数据库配置且不需要改动程序内部文件。
- 2026-05-11：按当前 Git 变更追加删除确认与勾选框交互统一记录（7 文件，涉及 `core/message_boxes.py`、`pages/doc_man.py`、`pages/platform_summary_page.py`、`pages/important_history_rebuild_info_page.py`、`pages/history_inspection_summary_page.py`、`pages/platform_load_information_page.py`、`pages/feasibility_assessment_page.py`）：新增中文确认弹窗工具 `ask_yes_no`，将相关删除确认框的按钮文案从默认 `Yes/No` 统一为“是/否”；同时去除 `DocManWidget` 中勾选框选中态的整块蓝色填充，恢复为原生对号勾选效果，用于统一文件管理页勾选交互。
- 2026-05-11：解决合并冲突：`pages/output_feasibility_analysis_report/src/path_config_loader.py` 保留外置模板目录定位（`config_root`）并保留 `appendix_a_reference_path`；同时清理 `pages/platform_summary_page.py` 的 import 冲突，保留 `ask_yes_no` 与 `save_facility_profile` 两侧改动。
- 2026-05-11：收紧打包发布内容：`main.spec` 移除 `shiyou_db/db_config.example.json` 的外置打包项。当前运行时代码只读取 `shiyou_db/db_config.json`，示例文件仅用于开发/初始化说明，不再随正式发布包分发。
- 2026-05-11：修复特检策略打包运行配置路径：`services/special_strategy_runtime.py` 将 `special_strategy_run_config.json` 改为优先从外置 `special_strategy_inputs/` 查找，其次回退到外置 `output_special_strategy/` 与源码目录；`main.spec` 同步将 `pages/output_special_strategy/special_strategy_run_config.json` 复制到发布包的 `special_strategy_inputs/`，修复打包版“更新风险等级结果”阶段误查 `_internal/pages/output_special_strategy/special_strategy_run_config.json` 导致的文件不存在错误。
- 2026-05-11：恢复“生成特检策略报告”等待框交互：`pages/upgrade_special_inspection_result_page.py` 新增 `QProgressDialog`，在“正在导出检验等级图...”与“正在生成报告...”两个阶段弹出模态加载框并随按钮忙碌状态自动关闭，修复此前仅按钮文案变化但无独立加载提示的问题。
- 2026-05-11：修正特检策略报告成功提示：`pages/upgrade_special_inspection_result_page.py` 在“生成特检策略报告”成功后恢复同时提示 Word 与 PDF 输出路径。PDF 仍由 `services/special_strategy_runtime.py` 中的 `refresh_word_document_fields(..., pdf_output_path=...)` 生成，本次仅修正前端成功弹窗文案显示范围。
- 2026-05-11??????????????`pages/new_special_inspection_page.py` ?????????? `pages/upgrade_special_inspection_result_page.py` ?????????????? `QThread + QObject worker + QProgressDialog` ??????????????????????????????????????/?????????????
- 2026-05-12?????????????`main.py` ????????? Windows `AppUserModelID` ?????? `QApplication`???????????????`main.spec` ????????? `logo.ico` ?? `exe` ?????????????????????????? Windows ??????????
- 2026-05-12????????????????????? `logo.ico` ??? PNG ?????????? Windows ???? `exe` ???????????????? `pict/logo.png` ?????? 16/24/32/48/64/128/256 ???????? `logo.ico`????? `main.py`/`main.spec` ??????????????????????
- 2026-05-12???????????????????????`pages/feasibility_assessment_results_page.py` ?????? `services/report_image_batch_export_process.py` ??????????? `python main.py --report-image-export-worker`?????? `main.exe --report-image-export-worker`?????????????`main.py` ???? worker ?????`main.spec` ???? `services.report_image_batch_export_process`??????????????????????????? Word?
- 2026-05-13???????????????????`shiyou_db/service.py` ?????????? `source_modified_at` ??? `uploaded_at` ????? `_record_to_dict` ??????? `uploaded_at/updated_at` ????? `source_modified_at`????? `source_file_modified_at` ?????????????????????????????????????????????
- 2026-05-13??????????????`pages/upgrade_special_inspection_result_page.py` ????????????????? Word ?????????????????????????????`services/special_strategy_services.py` ? `services/special_strategy_runtime.py` ????????? `output_path` ???Word ??? PDF ???????????????????????????
- 2026-05-13：修复文件管理下载时部分无扩展名文件被 Windows 保存框追加 `*`/`.*` 导致复制失败的问题：新增 `core/file_name_utils.py`，在 `pages/doc_man.py` 与 `pages/model_files_page.py` 的单文件和批量下载路径中统一清洗非法文件名字符，并保留 `sacinp`、`psilst`、`lst` 等无扩展名工程文件名。
- 2026-05-13：统一标准文件管理上传行为：`pages/doc_man.py`、`pages/model_files_page.py` 与 `pages/construction_docs_widget.py` 上传成功后均弹出“上传成功”；本地复制上传后立即刷新目标文件 mtime 为当前系统时间；`services/file_db_adapter.py` 与模型文件页数据库回填优先使用 `uploaded_at` 显示“修改时间”，避免继续展示源文件原始修改时间。
- 2026-05-13：继续修复无扩展名文件下载星号问题：`pages/doc_man.py` 与 `pages/model_files_page.py` 的保存式下载保留 Windows 原生保存框，但去掉 `(*.*)` 通配符过滤器并保留返回路径清洗，避免 `sacinp/psilst/lst` 等文件名后出现 `.*`；`shiyou_db/service.py` 的 `download_file` 也增加通配符后缀清洗作为底层兜底。
- 2026-05-13：统一历史检测与历史改造信息页的面包屑圆角样式：`pages/history_inspection_summary_page.py` 与 `pages/important_history_rebuild_info_page.py` 的 `QFrame#PathBar` 补齐 `border-top-left-radius` 和 `border-top-right-radius` 为 `8px`，与 `ConstructionDocsWidget` 标准路径栏一致，修复“首页”所在蓝条边缘显示为直角的问题。
- 2026-05-13：将文件管理路径栏收敛为统一组件：新增 `pages/file_path_bar.py` 的 `PathBreadcrumbBar`，并接入 `ConstructionDocsWidget`、`ModelFilesDocsWidget`、`HistoryInspectionSummaryPage` 和 `ImportantHistoryDetailWidget`；移除上述页面内自写的 `PathBar/Breadcrumb` 标签拼装与重复 QSS，只保留原有页面切换、首页返回、文件夹导航和业务表格逻辑。
- 2026-05-13：修复路径栏统一后的历史改造总页启动崩溃：`pages/history_rebuild_files_page.py` 不再访问已移除的 `ImportantHistoryDetailWidget.lbl_home/lbl_sep`，改为隐藏新统一组件 `path_bar`，保持历史改造总页“直接打开详情页、不显示首页路径入口”的既有特殊行为。
- 2026-05-13：恢复历史改造文件页标题栏：`pages/file_path_bar.py` 的 `PathBreadcrumbBar.set_path` 支持 `show_home=False`，`pages/important_history_rebuild_info_page.py` 增加路径栏首页入口显示开关，`pages/history_rebuild_files_page.py` 保留统一蓝色标题栏但隐藏“首页”入口，兼顾“直接打开详情页”的特殊要求。
- 2026-05-14：记录已提交并推送的 `4ab1a75 完善可行性评估报告 PDF 输出`：将可行性评估报告输出从 Word 文件路径切换为 PDF 文件路径，新增 `pages/output_feasibility_analysis_report/src/pdf_converter.py` 通过 Word COM 将渲染后的 `.docx` 转为 `.pdf`，`report_service.generate_report` 先生成临时/同名 docx 再返回 PDF 输出；同步调整结果页保存路径、成功提示与相关测试，并更新 `data/summary_information_table_export.csv`、新增 `data/platform_load_information_export.csv` 导出样例。提交前尝试运行 `python -m pytest tests/test_feasibility_assessment_results_page.py tests/test_pdf_converter.py tests/test_report_service_pdf_output.py -q`，因当前环境缺少 `pytest` 失败；随后推送 `main -> origin/main` 成功，远端无冲突。
- 2026-05-18：按当前 Git 变更追加“海洋环境”页面布局联调记录（1 文件，涉及 `pages/oilfield_water_level_page.py`）：顶部筛选区由原“下拉条 + 左侧按钮列”调整为横向操作区，`DropdownBar` 左侧垂直居中、右侧弹性留白并将“保存”按钮右对齐；移除 `_fit_table_width_to_columns` 固定宽度方案，新增 `_expand_table_width` 让表格横向扩展；水深水位表列宽从内容自适应加宽改为左两列固定、数值列拉伸，避免右侧空白与宽度失衡；风参数/波浪参数/海流参数页面外层 `QFrame` 使用 `QSizePolicy.Expanding, QSizePolicy.Preferred`，表格添加方式从强制 `AlignTop` 收敛为默认填充，同时保留整体顶对齐；业务保存、加载、四表数据结构与顶部级联逻辑未变。
- 2026-05-19：按当前未提交工作区追加联调记录（12 文件，当前 `git status` 涉及 `AGENTS.md`、`core/dropdown_bar.py`、`pages/feasibility_assessment_results_page.py`、`pages/oilfield_water_level_page.py`、可行性评估报告配置与渲染模块、`pages/platform_load_information_page.py`、`pages/summary_information_table_page.py` 及相关测试）：本轮重点完成载荷信息下“汇总信息”和“平台载荷信息”两张表的视觉统一，复用“文件管理 > 汇总信息”白底浅蓝灰表格风格、表格自身滚动条、浅色网格与选中态；修正汇总信息表稳定列宽、表头单位换行、长表头高度及滚动条继承问题；平台载荷信息表去除外层大框、统一浅色表头和计算列背景、修复首列复选框序号重复显示（`00/11`）、前两行所属信息加粗、取消结果列红色字体，并将重量/载荷等单位统一为去逗号后括号换行格式；本轮已分别对 `pages/summary_information_table_page.py` 与 `pages/platform_load_information_page.py` 执行 `python -m py_compile` 语法检查通过。其余未提交改动保留为既有可行性评估报告与海洋环境页面联调内容，未在本轮回退或覆盖。
- 2026-05-19：已将本轮载荷表格视觉联调、可行性评估报告渲染补充和海洋环境页面布局改动提交并推送到远端 `origin/main`，提交为 `749cba8 更新载荷表格与报告渲染`；推送前执行 `git fetch --prune`，确认 `origin/main` 无新增提交，因此未发生冲突；语法检查命令 `python -m py_compile pages\platform_load_information_page.py pages\summary_information_table_page.py pages\feasibility_assessment_results_page.py pages\oilfield_water_level_page.py pages\output_feasibility_analysis_report\src\chapter_1_3_builder.py pages\output_feasibility_analysis_report\src\path_config_loader.py pages\output_feasibility_analysis_report\src\renderers\doc_renderer.py` 通过；尝试运行 `python -m pytest tests\test_feasibility_assessment_results_page.py tests\test_report_service_pdf_output.py -q` 因当前环境缺少 `pytest` 未执行成功；推送后本地仅剩 `core/dropdown_bar.py` 显示修改但无实际 diff，未纳入提交。
- 2026-06-04：按当前 C/S 分离联调需求追加结构强度与可行性评估运行逻辑修复记录（5 文件，涉及 `pages/platform_strength_page.py`、`server/routers/files.py`、`services/server_file_service.py`、`pages/feasibility_assessment_page.py`、`services/feasibility_runtime.py`）：`pages/platform_strength_page.py` 在顶部平台下拉变化时改为调用 `_autoload_inp_to_view(force_remote=True)`，并将 `force_remote` 贯穿 `_resolve_current_preview_model_file`、`_get_shared_current_model_file` 与 `_download_latest_model_from_server`，确保切换平台后强制重新从 FastAPI 服务端下载当前平台模型，避免复用旧 `.client_cache` 路径导致右侧三维图不刷新；`services/server_file_service.py` 新增 `get_current_sacinp_record` 及当前原模型评分/过滤逻辑，优先选择当前平台“当前模型/结构模型”下的 `sacinp.JKnew`/`sacinp*`，并排除 `sacinp.M1`、`seainp`、历史改造、自动计算结果与结果目录文件；`server/routers/files.py` 将 `/api/files/latest-model` 与 `/api/files/download/latest-model` 切换到 `get_current_sacinp_record`，避免服务端宽泛“最新 sacinp”查询返回错误平台或改造模型；`pages/feasibility_assessment_page.py` 在 `_on_run_analysis` 增加计算前约束：检测到三张新增构件/载荷表有有效数据但未保存时提示先“保存数据”，已保存但未创建新模型时提示先“创建新模型”，三张表为空仍按原逻辑计算原模型，创建新模型后再允许计算改造后模型；`services/feasibility_runtime.py` 新增读取 `feasibility_analysis_state.json` 的辅助逻辑，导出接口在 `analysis_mode=auto` 时使用最后一次成功计算记录中的真实 `analysis_mode` 和 `result_file`，避免页面状态丢失后误把旧 `sacinp.M1/seainp.M1` 与原模型结果一起导出；本轮已执行 `python -m py_compile "pages\platform_strength_page.py" "pages\feasibility_assessment_page.py" "services\server_file_service.py" "server\routers\files.py" "services\feasibility_runtime.py"` 语法检查通过。
- 2026-06-05：按当前对话补充 C/S 分离与报告导出联调记录：确认结构强度/改造可行性评估原模型计算结果应由服务端自动归档到“模型文件 -> 当前模型 -> 静力 -> 结果 -> 自动计算 -> 原模型”，新模型/改造后模型计算结果不自动归档，仅由上一页“导出文件”按钮导出；`pages/feasibility_assessment_results_page.py` 将“生成评估报告”链路改为不再调用 `/api/feasibility/files/export` 下载/解压计算输出包，报告生成只使用服务端已有 `server_result_file` 或由服务端运行目录自行查找 `psilst`，避免与上一页“导出文件”重复；`services/special_strategy_runtime.py` 修复特检策略报告服务端调用不匹配问题，为 `generate_special_strategy_report` 增加 `generate_pdf` 与 `pdf_timeout_seconds` 参数并传入 `refresh_word_document_fields`，解决 `/api/reports/generate` 传参导致的 `unexpected keyword argument 'generate_pdf'`；本轮已执行 `python -m py_compile "services\special_strategy_runtime.py" "pages\new_special_inspection_page.py" "pages\upgrade_special_inspection_result_page.py" "pages\feasibility_assessment_page.py" "pages\feasibility_assessment_results_page.py" "pages\model_files_page.py" "pages\platform_strength_page.py"` 语法检查通过。
- 2026-06-05：按用户要求完成“只拉取合并 GitHub 远端改动、不推送本地代码”的 Git 操作记录：执行 `git fetch --prune origin` 后发现本地 `main` 落后 `origin/main` 5 个提交；先用 `git stash push -m "tracked local changes before merging origin main 2026-06-05"` 保存已跟踪本地改动（未跟踪的 `client_api/`、`server/`、`.client_cache/`、`server_outputs/` 等本地运行/联调文件保留原地），再执行 `git merge --ff-only origin/main` 将远端 `94f3f3f 优化页面异步加载与结果渲染` 等 5 个提交快进合并到本地；随后 `git stash pop` 恢复本地改动，解决 `pages/new_special_inspection_page.py`、`pages/upgrade_special_inspection_result_page.py`、`services/special_strategy_runtime.py` 三个冲突文件，保留远端异步加载/附件插入校验等新逻辑，同时保留本地 C/S 远程模型缓存、服务端 GUI 抑制和特检报告 `generate_pdf/pdf_timeout_seconds` 修复；全程未执行 `git push`，当前 `HEAD` 与 `origin/main` 无 ahead/behind，stash 因冲突恢复被 Git 保留为 `stash@{0}` 本机备份。
- 2026-06-05：按当前未提交工作区追加结构强度与可行性评估结果页性能优化记录（4 文件，涉及 `pages/platform_strength_page.py`、`pages/feasibility_assessment_results_page.py`、`tests/test_platform_strength_page_initial_async.py`、`tests/test_feasibility_assessment_results_page.py`）：结构强度页将右侧模型预览的远程下载、持久缓存命中与模型路径解析整体下沉到 `ModelPreviewLoadWorker`，`_autoload_inp_to_view()` 不再在 UI 线程同步解析/下载最新模型；可行性评估结果页将结果表格解析改为 `AnalysisResultsWorker` 后台执行，并在表格解析完成或失败后再懒加载右侧模型视图，`ModelViewLoadWorker` 复用已解压输出包缓存以减少重复下载/解压；结果表格解析在无桩基承载力输入行影响计算时优先使用 `ApiClient().get_feasibility_result(facility_code)` 的服务端 JSON 快速路径，有桩基输入行时回退本地 `psilst.factor` 解析以保持表格语义一致；本轮新增/更新异步加载、远程 JSON 快速路径、桩基输入回退、模型懒加载与缓存复用相关测试，已执行聚焦 pytest 命令通过（`13 passed in 2.47s`），并对上述页面和测试文件执行 `python -m compileall` 语法检查通过。
- 2026-06-06：记录已提交并推送的 `e61e2e2 优化评估结果异步加载`（4 文件，`568` 行新增 / `48` 行删除）：`pages/platform_strength_page.py` 将结构强度页右侧模型预览的最新模型下载、持久缓存命中、路径解析和视图刷新整理到后台 worker 流程，避免 `_autoload_inp_to_view()` 在 UI 线程同步处理远程模型；`pages/feasibility_assessment_results_page.py` 将可行性评估结果表解析下沉到 `AnalysisResultsWorker`，优先走服务端 JSON 快速路径，存在桩基承载力输入行时回退本地 `psilst.factor` 解析，并在表格解析完成或失败后再懒加载右侧模型视图，`ModelViewLoadWorker` 复用已解压输出包缓存以减少重复下载/解压；`tests/test_platform_strength_page_initial_async.py` 与 `tests/test_feasibility_assessment_results_page.py` 补充结构强度模型异步加载、评估结果远程 JSON 快速路径、桩基输入回退、模型懒加载/缓存复用以及服务端报告生成契约相关测试。推送前按安全流程执行 `git fetch origin`，发现远端新增 `56c9254`、`c8d023d` 后先临时 stash 本地 `AGENTS.md`，再 `git rebase origin/main` 无冲突合并，随后恢复 `AGENTS.md` 且未纳入提交；验证命令 `python -m pytest tests/test_feasibility_assessment_results_page.py tests/test_platform_strength_page_initial_async.py -q` 通过（`42 passed in 2.49s`），`python -m compileall pages/feasibility_assessment_results_page.py pages/platform_strength_page.py tests/test_feasibility_assessment_results_page.py tests/test_platform_strength_page_initial_async.py` 通过，最终推送 `main -> origin/main` 成功。

- 2026-06-06：记录已提交并推送的 `cf5aea9 完善可行性评估结果缓存校验`：本次围绕可行性评估结果缓存/旧结果误读风险补充服务端结果元数据与客户端校验逻辑，涉及 `client_api/api_client.py`、`server/routers/feasibility.py`、`server/schemas.py`、`services/feasibility_runtime.py`、`pages/feasibility_assessment_results_page.py`、报告 `path_config.json` 及相关测试；新增 `tests/test_feasibility_runtime_result_cache.py`，并扩展 `tests/test_feasibility_assessment_results_page.py`。推送前验证 `python -m pytest tests/test_feasibility_runtime_result_cache.py tests/test_feasibility_assessment_results_page.py -q` 通过（39 passed），`python -m compileall client_api server services pages\feasibility_assessment_results_page.py` 通过，随后推送 `main -> origin/main` 成功。
- 2026-06-07：按当前对话追加平台载荷信息页曲线图联调记录（2 文件，涉及 `pages/platform_load_information_page.py`、`tests/test_platform_load_chart_visibility.py`）：为平台重量中心变化曲线新增 X 轴改造次序刻度抽稀逻辑，保留全部数据点绘制并固定保留首个与最新改造次序，避免改造次数持续增加时横轴文字重叠；将 `MultiLineChart` 左右 Y 轴边距由固定 `subplots_adjust` 改为根据实际刻度文本和轴标题渲染宽度动态计算，修复大数量级科学计数法下 Y 轴标题被挤出画布的问题；悬停提示补充显示系列名、改造次序与完整数值，确保抽稀后仍可查看每个数据点详情；新增/更新图表可见性回归测试，已执行 `python -m pytest tests\test_platform_load_information_async.py tests\test_platform_load_chart_visibility.py -q` 通过（18 passed），并执行 `python -m py_compile pages\platform_load_information_page.py tests\test_platform_load_chart_visibility.py` 通过。
- 2026-06-07：按当前对话追加上部组块分项目计算表交互记录（2 文件，涉及 `pages/upper_block_subproject_calculation_table_page.py`、`tests/test_platform_load_upper_block_context.py`）：在上部组块分项目计算表顶部新增“返回”按钮，点击后仅切回“平台载荷信息”Tab，不保存、不回填、不触发 `saved` 信号，解决用户不保存时缺少页面内返回入口的问题；同步将按钮顺序调整为“保存 / 返回”，并将两个按钮样式统一为平台载荷信息页“保存”按钮的蓝色主题（`#2563eb`、`#1d4ed8`、`#1e40af`），保持主流程视觉一致；新增返回行为、按钮顺序和按钮样式一致性测试，已执行 `python -m pytest tests/test_platform_load_upper_block_context.py -q` 通过（9 passed），并执行 `python -m py_compile pages\upper_block_subproject_calculation_table_page.py tests\test_platform_load_upper_block_context.py` 通过。
- 2026-06-07：按当前对话追加主菜单“汇总信息”与“载荷信息 > 汇总信息”联动修复记录（5 文件，涉及 `services/platform_summary_source.py`、`pages/platform_summary_page.py`、`pages/summary_information_table_page.py`、`tests/test_platform_summary_source.py`、`tests/test_summary_information_table_page.py`）：新增公共平台汇总数据源入口 `load_platform_summary_source()`，统一“优先读取 `platform_summary_snapshots/latest` 完整快照，快照不存在或为空时回退读取 `facility_profiles`”的规则；主菜单汇总页和载荷汇总页均改为调用该公共入口，确保即使主菜单汇总页未先打开，载荷汇总页也能与随后打开的主菜单汇总页保持平台基础信息来源一致；同时移除载荷汇总页 `_apply_data()` 中首条数据行绿色字体渲染逻辑，所有数据行恢复默认表格字体颜色；新增/更新公共数据源优先级与首条数据行非绿色渲染回归测试，已执行 `python -m pytest tests/test_platform_summary_source.py tests/test_summary_information_table_page.py -q` 通过（4 passed），并执行 `python -m compileall services\platform_summary_source.py pages\platform_summary_page.py pages\summary_information_table_page.py` 通过。
- 2026-06-07：记录本轮安全推送：提交并推送 `a717603 统一平台汇总数据源` 到 `origin/main`，推送前执行 `git fetch origin` 并确认 `HEAD...origin/main` 为 `0 0`，无远端新提交需要合并；提交范围仅包含 5 个代码/测试文件（`pages/platform_summary_page.py`、`pages/summary_information_table_page.py`、`services/platform_summary_source.py`、`tests/test_platform_summary_source.py`、`tests/test_summary_information_table_page.py`），未纳入本地记录文件 `AGENTS.md` 与未跟踪 `image.png`；推送前验证 `python -m pytest tests/test_platform_summary_source.py tests/test_summary_information_table_page.py -q` 通过（4 passed），`python -m compileall services\platform_summary_source.py pages\platform_summary_page.py pages\summary_information_table_page.py` 通过，推送后确认 `HEAD`、`origin/main`、`origin/HEAD` 均指向 `a717603` 且 ahead/behind 为 `0 0`。
- 2026-06-07：按甲方截图意见追加平台载荷曲线量级转换记录（2 文件，涉及 `pages/platform_load_information_page.py`、`tests/test_platform_load_chart_visibility.py`）：在 `MultiLineChart` 中新增按曲线系列自动计算显示倍率的逻辑，绘图时使用缩放后的显示值（如 `×1e5`、`×1e6`），解决同一张组合曲线图内不同量级曲线差异过大导致小量级曲线贴底/重叠的问题；图例追加倍率说明（如 `Fx (×1e5)`），同时保留 `_points` 原始真实值用于悬停提示与业务追溯，确保仅改变图表显示层、不影响表格、保存、导出和数据库数据；同步调整大数值边距测试，并新增缩放绘图、原始值保留和图例倍率回归测试。已执行 `python -m pytest tests/test_platform_load_information_async.py tests/test_platform_load_chart_visibility.py -q` 通过（20 passed），并执行 `python -m compileall pages\platform_load_information_page.py tests\test_platform_load_chart_visibility.py` 通过。
- 2026-06-07：记录本轮安全推送：提交并推送 `b4f2a4f 优化载荷曲线量级显示` 到 `origin/main`，推送前执行 `git fetch origin` 并确认 `HEAD...origin/main` 为 `0 0`，无远端新提交需要合并；提交范围仅包含 2 个图表相关文件（`pages/platform_load_information_page.py`、`tests/test_platform_load_chart_visibility.py`），未纳入本地记录文件 `AGENTS.md` 与未跟踪图片 `image.png`、`image1.png`；推送前验证 `python -m pytest tests/test_platform_load_information_async.py tests/test_platform_load_chart_visibility.py -q` 通过（20 passed），`python -m compileall pages\platform_load_information_page.py tests\test_platform_load_chart_visibility.py` 通过，推送后确认 `HEAD`、`origin/main`、`origin/HEAD` 均指向 `b4f2a4f` 且 ahead/behind 为 `0 0`。
- 2026-06-07：按当前对话追加平台载荷信息表历次改造项目合并修复记录（3 文件，涉及 `pages/platform_load_information_page.py`、`tests/test_platform_load_history_rebuild_sync.py`、`tests/test_platform_load_information_async.py`）：修复历次改造项目导入数据按行号兜底匹配导致覆盖用户手动编辑项目的问题，合并逻辑改为仅按项目名称匹配；匹配成功时更新历次改造项目名称/时间/内容并保留该行后续载荷数据，匹配失败时新增历次改造项目行，未匹配的用户手动行按原数据追加保留；同时将 `_load_current_platform_data()` 从主线程同步读取数据库与历次改造目录，调整为显示加载占位后调用既有 `_start_async_current_platform_load()`，继续通过 `QThread + worker` 子线程读取平台载荷信息与历次改造目录，避免 UI 线程 I/O。已执行 `python -m pytest tests/test_platform_load_history_rebuild_sync.py tests/test_platform_load_information_async.py tests/test_platform_load_overall_assessment.py tests/test_platform_load_upper_block_context.py -q` 通过（29 passed），并执行 `python -m compileall pages/platform_load_information_page.py services/platform_load_preheat.py tests/test_platform_load_history_rebuild_sync.py tests/test_platform_load_information_async.py` 通过。

- 2026-06-07：按当前对话追加顶部平台下拉数据源与级联修复记录（6 文件，涉及 `pages/file_management_platforms.py`、`pages/construction_docs_page.py`、`pages/platform_load_information_page.py`、`pages/platform_strength_page.py`、`pages/special_inspection_strategy.py`、`tests/test_file_management_platforms.py`，另新增 `tests/test_special_inspection_strategy_dropdown.py`）：将顶部平台下拉统一改为从 `facility_profiles` 读取，并仅保留 `WC19-1D`、`WC9-7` 两个平台，数据库不可用或缺记录时回退到原 `FILE_MANAGEMENT_PLATFORMS`；`sync_platform_dropdowns()` 新增 `branch/division`、`op_company/company`、`oilfield/field`、`design_life/design_years` 别名同步，油气田等关联字段从两个平台档案去重生成候选项，并支持选择 `WC9-7油田` 反向级联选中 `WC9-7`；移除“设计文件”“平台载荷信息”“结构强度”页面在共享同步后把字段重新压缩为单项的覆盖逻辑；修复“特检策略”页此前只响应设施编码/名称变化的问题，使选择油气田也会触发级联同步。已执行 `python -m pytest tests/test_file_management_platforms.py -q`、`python -m pytest tests/test_special_inspection_strategy_dropdown.py -q`、`python -m pytest tests/test_platform_strength_page_initial_async.py -q`、`python -m pytest tests/test_platform_load_information_async.py -q` 通过，并执行相关 `python -m compileall` 语法检查通过。

- 2026-06-08：按当前对话追加平台载荷信息表与历次改造项目强联动改造记录（7 文件，涉及 `pages/platform_load_information_page.py`、`pages/important_history_rebuild_info_page.py`、`services/file_db_adapter.py`、`shiyou_db/models.py`、`shiyou_db/service.py`、`tests/test_platform_load_history_rebuild_sync.py`、`tests/test_platform_load_information_async.py`）：平台载荷信息表新增隐藏关联字段 `rebuild_directory_id`，复用历次改造项目 `document_rebuild_directories.id`；加载时第 0 行固定为“详细设计”且不绑定历次改造项目，历次改造项目从第 1 行开始按 `rebuild_directory_id` 同步名称/时间/内容并保留后续用户输入；历次改造项目改名后平台载荷行跟随改名、删除后对应行不再显示，未绑定 ID 的手动新增行继续保留并排在同步项目之后；第 0 行“详细设计”增加不可删除保护；历次改造项目新增/编辑/删除后同步清除平台载荷预热缓存，并在平台载荷信息页已打开时调用 `refresh_from_rebuild_projects()` 立即刷新，若当前表格存在未保存修改则提示先保存再刷新；本次未执行任何旧数据删除操作。已执行 `python -m pytest tests/test_platform_load_history_rebuild_sync.py tests/test_platform_load_information_async.py tests/test_platform_load_overall_assessment.py tests/test_platform_load_upper_block_context.py tests/test_summary_information_table_page.py tests/test_schema_ensure_once.py -q` 通过（37 passed），`python -m compileall pages services shiyou_db tests` 通过，`git diff --check` 无空白错误（仅提示 LF/CRLF 转换）。

- 2026-06-08：按当前对话追加平台载荷信息页上部组块重心曲线数量级修复记录（2 文件，涉及 `pages/platform_load_information_page.py`、`tests/test_platform_load_chart_visibility.py`）：定位到 `MultiLineChart` 此前会对所有大数值曲线逐系列除以 `10^n` 并在图例标注倍率，该显示缩放用于载荷图时可减轻大数值坐标轴挤占，但套用到“上部组块重心”图会导致 Gx/Gy 纵坐标显示数量级与表格实际米值不一致；本次为多线图新增 `scale_values` 显示开关，并在内嵌曲线区仅对 `center`（上部组块重心）图关闭缩放，使干/操作重心 Gx/Gy/Gz 按表格原始米值绘制，载荷图继续保留原有大数值缩放逻辑；同步新增回归测试覆盖重心大坐标不缩放、图例不追加倍率。已执行 `python -m pytest tests/test_platform_load_chart_visibility.py -q` 通过（9 passed），并执行 `python -m pytest tests/test_platform_load_history_rebuild_sync.py tests/test_platform_load_information_async.py tests/test_platform_load_overall_assessment.py tests/test_platform_load_upper_block_context.py -q` 通过（30 passed）。

- 2026-06-08：按当前对话追加平台载荷信息页重心曲线列映射验证记录（1 文件，涉及 `tests/test_platform_load_information_async.py`）：新增 `test_curve_series_reads_dry_and_operation_center_columns`，显式验证主表第 8 列“上部组块干重心 (x,y,z)”写入 `dry_cgx/dry_cgy/dry_cgz`，第 9 列“上部组块操作重心 (x,y,z)”写入 `op_cgx/op_cgy/op_cgz`，用于防止后续维护时将重心曲线误接到不可超越半径或其他载荷列。已执行该单测通过。

- 2026-06-08：按当前对话追加平台载荷信息页保存成功弹窗修复记录（2 文件，涉及 `pages/platform_load_information_page.py`、`tests/test_platform_load_information_async.py`）：修复保存按钮点击后无“保存成功”提示的问题；根因为 `QPushButton.clicked` 会向槽函数传入 `checked=False`，此前按钮直接连接 `_on_save(show_message=True)`，导致该布尔值覆盖 `show_message` 参数，手动点击也变成静默保存；本次将保存按钮连接改为 `lambda _checked=False: self._on_save()`，保留 `refresh_from_rebuild_projects()` 中显式 `show_message=False` 的静默保存行为；新增 `test_save_button_click_shows_success_message` 回归测试覆盖按钮点击路径。

- 2026-06-09：按当前对话追加快速评估页三张输入表 Excel 式编辑接入记录（2 文件，涉及 `pages/feasibility_assessment_page.py`，新增 `tests/test_feasibility_assessment_table_clipboard.py`）：使用本地 `pyqt-table-excel-editing` skill 的通用方案，复用 `core.table_clipboard.TableClipboardController` 为“新增井槽信息”“新增立管/电缆信息”“新增组块载荷信息”三张表接入 `Ctrl+C` 复制、`Ctrl+V` 粘贴、`Ctrl+X` 剪切、`Delete/Backspace` 多选清空能力；将三张表选择模式从单选改为 `ExtendedSelection`，编辑触发改为双击、选中点击与编辑键，避免单击即进入编辑影响多选；新增 `_install_input_table_clipboard()`、`_can_paste_input_table_cell()` 与 `_show_input_table_tip()`，粘贴仅允许写入数据区普通可编辑单元格，跳过表头、编号列、第 1/2 张表的“高程及连接形式”下拉框单元格以及只读/控件单元格；当粘贴内容超出当前数据区或遇到不可粘贴单元格时，通过 `QToolTip` 给出轻量提示，不新增右键菜单，保留既有序号列行新增/删除右键菜单和下拉框悬停交互。新增测试覆盖三张表控制器安装、多选模式、表头/编号列/下拉框跳过策略以及普通单元格粘贴行为；已执行 `python -m pytest tests\test_table_clipboard.py tests\test_feasibility_assessment_table_clipboard.py -q` 通过（13 passed），并执行 `python -m compileall core\table_clipboard.py pages\feasibility_assessment_page.py tests\test_feasibility_assessment_table_clipboard.py` 通过。

- 2026-06-09：记录本轮安全推送：按 `safe-git-push` 流程将快速评估页 Excel 式表格编辑提交并推送到 `origin/main`。推送前先执行 `git fetch origin`，发现远端 `main` 从 `77cf94d` 前进到 `f6b878a`，本地处于 `ahead 1, behind 3`；本次仅提交相关 4 个文件：`core/table_clipboard.py`、`pages/feasibility_assessment_page.py`、`tests/test_table_clipboard.py`、`tests/test_feasibility_assessment_table_clipboard.py`，提交信息为 `接入快速评估表格复制粘贴`。为保护无关本地改动，临时 `stash` 了 `AGENTS.md`、`pages/nav_config.py`、`pages/platform_load_information_page.py`、`pages/platform_strength_page.py`、`tests/test_platform_load_upper_block_context.py`、`tests/test_platform_strength_page_initial_async.py`、`docs/superpowers/`、`image.png`、`image1.png`，随后 `git rebase origin/main` 无冲突完成；变基后重新执行 `python -m pytest tests\test_table_clipboard.py tests\test_feasibility_assessment_table_clipboard.py -q` 通过（13 passed），`python -m compileall core\table_clipboard.py pages\feasibility_assessment_page.py tests\test_table_clipboard.py tests\test_feasibility_assessment_table_clipboard.py` 通过；最终推送 `5144669 接入快速评估表格复制粘贴` 到 `origin/main` 成功，并已 `git stash pop` 恢复上述未提交本地改动，当前 `main` 与 `origin/main` 同步。

- 2026-06-09：按用户要求补充推送剩余代码改动：在 `5144669` 已同步远端后，再次按 `safe-git-push` 执行 `git fetch origin` 确认 `main` 与 `origin/main` 为 `0/0`；本次仅纳入有改动的代码/测试文件 `pages/nav_config.py`、`pages/platform_load_information_page.py`、`pages/platform_strength_page.py`、`tests/test_platform_load_upper_block_context.py`、`tests/test_platform_strength_page_initial_async.py`，未纳入本地记录 `AGENTS.md`、未跟踪 `docs/superpowers/` 及图片 `image.png`/`image1.png`。改动内容包括将“汇总信息”移动到“文件管理”分组下、为平台载荷信息主表接入 `TableClipboardController` 与粘贴跳过/提示逻辑、为结构强度桩基编辑弹窗接入 Excel 式复制粘贴且新增行为空行、将水平层高程弹窗的“删除最后一列”改为“删除选中列”并支持多列删除/浅蓝选中/双击编辑，以及补充对应回归测试。推送前执行 `python -m pytest tests\test_platform_load_upper_block_context.py tests\test_platform_strength_page_initial_async.py tests\test_table_clipboard.py -q` 通过（31 passed），`python -m compileall pages\nav_config.py pages\platform_load_information_page.py pages\platform_strength_page.py tests\test_platform_load_upper_block_context.py tests\test_platform_strength_page_initial_async.py` 通过，`git diff --check` 无空白错误；最终提交并推送 `a6373ec 补充表格复制粘贴与列删除交互` 到 `origin/main` 成功，推送后 `main` 与 `origin/main` 同步。
- 2026-06-09：修复可行性分析结果页 `psilst.M1` 大文件关键段读取逻辑（2 文件，涉及 `pages/output_feasibility_analysis_report/src/parsers/psilst_reader.py`、`tests/test_feasibility_factor_diagnostics.py`）：根据 `ReadPSIlist.xlsm` 原始 VBA 的“命中 summary 标题后读取到换页符”策略，为 UI 解析读取器新增按 marker 逐页截取 `M E M B E R  G R O U P  S U M M A R Y`、`J O I N T   C A N   S U M M A R Y`、`P I L E  G R O U P  S U M M A R Y` 段落的逻辑，避免 300MB+ `psilst.M1` 因只读取桩承载力/桩头力段而漏掉构件、节点冲剪数据；新增回归测试覆盖构件/节点多页 summary 截取，并用根目录 `psilst.M1` 验证 `build_analysis_results_for_ui()` 可解析出构件 588 行、节点冲剪 294 行、桩应力 201 行。已执行 `python -m pytest tests/test_feasibility_factor_diagnostics.py::FeasibilityFactorParserChainTests -q` 通过（5 passed），`python -m pytest tests/test_report_service_analysis_ui.py -q` 通过（1 passed），`python -m compileall pages\output_feasibility_analysis_report\src\parsers\psilst_reader.py tests\test_feasibility_factor_diagnostics.py` 通过。
- 2026-06-09：修复可行性评估报告 `psilst.M1` 大文件读取导致报告数据不全的问题（4 文件，涉及 `pages/output_feasibility_analysis_report/src/parsers/psilst_reader.py`、`pages/output_feasibility_analysis_report/src/parsers/member_group_summary_parser.py`、`pages/output_feasibility_analysis_report/src/parsers/joint_can_summary_parser.py`、`tests/test_feasibility_factor_diagnostics.py`）：在大文件分段读取中补充报告所需的 `SEASTATE BASIC LOAD CASE DESCRIPTIONS`、`SEASTATE BASIC LOAD CASE SUMMARY`、`SEASTATE COMBINED LOAD CASES`、`SEASTATE COMBINED LOAD CASE SUMMARY` 段，避免为节省资源裁剪掉报告工况表；同时将构件/节点 summary 的 `raw_block` 改为使用完整多页 block，不再遇到第二个相同 summary marker 就截断，确保报告 4.5.1/4.5.2 原文段与结果页 rows 一样覆盖多页数据。已用共享 `psilst.M1` 验证：`basic_desc/basic_loads` 从 0 恢复为 154，`member_raw_lines` 从 53 增至 1408，`joint_raw_lines` 从 57 增至 346，且构件/节点/桩应力行数仍为 588/294/201；已执行 `python -m pytest tests/test_feasibility_factor_diagnostics.py::FeasibilityFactorParserChainTests -q` 通过（7 passed）、`python -m pytest tests/test_report_service_analysis_ui.py -q` 通过（1 passed），并执行相关 `python -m compileall` 通过。
- 2026-06-09：修复可行性评估报告“海生物信息”表列数与页面不一致问题：`pages/output_feasibility_analysis_report/src/renderers/table_writer.py` 为 Word 表格新增按需扩列/裁列能力，`write_environment_marine_growth_table()` 改为按有效最大 `layer_no` 生成 `2 + 实际层数` 列，少于模板 9 层时移除多余物理列，多于 9 层时动态补列并写入后续层，避免为了固定模板列数截断真实层数据；同时跳过空、非法或小于 1 的层号，保留负数不换行连字符处理。`tests/test_report_table_writer.py` 新增海生物 4 层裁列与 12 层扩列回归测试，已执行 `python -m pytest tests/test_report_table_writer.py tests/test_report_service_analysis_ui.py -q` 通过（5 passed），`python -m compileall pages\output_feasibility_analysis_report\src\renderers\table_writer.py tests\test_report_table_writer.py` 通过。
- 2026-06-09：按当前对话修正可行性评估结果页与报告的数据读取口径（5 文件，涉及 `pages/feasibility_assessment_results_page.py`、`pages/output_feasibility_analysis_report/src/parsers/joint_can_summary_builder.py`、`tests/test_feasibility_assessment_results_page.py`、`tests/test_feasibility_factor_diagnostics.py`、`tests/test_feasibility_runtime_result_cache.py`）：取消结果页使用远端预解析结果缓存，改为优先读取本地运行 state/result，其次使用客户端可访问的服务端结果路径，最后下载服务端原始输出包到 `.client_cache/feasibility/.../feasibility_outputs/...` 后在客户端解析；报告 payload 复用结果页解析得到的 `_factor_path`，保证查看结果与报告使用同一份 `psilst` 文件。根据 `ReadPSIlist` VBA 固定列 `Mid(a,36,6)/Mid(a,44,6)` 与 `FindMaxJointUC` 排序逻辑，将节点冲剪 UC 统计和结果页明细从 `design_*` 改回 `orig_load_uc/orig_strn_uc`，并新增 original/design 不同值的回归测试防止口径再次误改。已用最新客户端缓存 `psilst.M1` 验证节点冲剪 294 行，最大 ORIGINAL Strength UC 为 `636W / EL1A / 2.6`，与当前 builder 输出一致；已执行 `python -m pytest tests\test_feasibility_assessment_results_page.py tests\test_feasibility_factor_diagnostics.py tests\test_feasibility_runtime_result_cache.py -q` 通过（48 passed, 2 skipped），并执行相关 `python -m compileall` 通过。
- 2026-06-09：继续修正可行性评估结果页“节点冲剪/Joint Can”UC 过百的解析问题：明确截图中 `Load UC=202.68`、`Strength UC=14.04` 不是合理结果，而是把非 `(UNITY CHECK ORDER)` 的 `JOINT CAN SUMMARY` 段或错误列当成节点冲剪结果读取的表现；`pages/output_feasibility_analysis_report/src/parsers/joint_can_summary_parser.py` 现在只解析带 `(UNITY CHECK ORDER)` 的 JOINT CAN 块，并按 VBA 固定列读取 ORIGINAL `Load UC/Strength UC`，跳过明显越界的 UC 值。`tests/test_feasibility_factor_diagnostics.py` 补齐真实 JOINT 块头夹具，并新增非 `UNITY CHECK ORDER` 块含 `202.68` 时不解析的回归测试；已执行 `python -m pytest tests\test_feasibility_assessment_results_page.py tests\test_feasibility_factor_diagnostics.py tests\test_feasibility_runtime_result_cache.py -q` 通过（51 passed, 2 skipped），`python -m compileall pages\feasibility_assessment_results_page.py pages\output_feasibility_analysis_report\src\parsers\joint_can_summary_parser.py tests\test_feasibility_assessment_results_page.py tests\test_feasibility_factor_diagnostics.py` 通过。
- 2026-06-09：推送前验证时补充表格粘贴起点修复：`core/table_clipboard.py` 的 `_paste_start_cell()` 在存在旧选区但当前单元格已切到选区外、或仅单格选中时改为优先使用当前单元格，多选区域仍按左上角粘贴，避免结构强度桩基/海生物编辑弹窗组合测试中旧选区残留导致粘贴落到错误位置；同步调整 `tests/test_platform_strength_page_initial_async.py` 中弹窗表格复制/粘贴断言，直接验证已安装的 `TableClipboardController` 行为。已执行 `python -m pytest tests\test_table_clipboard.py tests\test_feasibility_assessment_results_page.py tests\test_feasibility_factor_diagnostics.py tests\test_feasibility_runtime_result_cache.py tests\test_platform_strength_page_initial_async.py tests\test_report_table_writer.py -q` 通过（79 passed, 2 skipped），并执行相关 `python -m compileall` 通过。
- 2026-06-10：记录本轮安全推送结果：按 `safe-git-push` 流程将可行性评估结果/报告解析口径修正、结构强度海生物层动态化、报告海生物表动态列、表格粘贴起点修复及相关测试合并为提交 `ddf9fb3 修正可行性评估结果解析口径` 并推送到 `origin/main`。推送前先提交本地改动，随后 `git fetch origin` 发现远端新增 5 个提交（至 `0f8f8e0 调整 SACS 输出文件清理策略`），已执行 `git rebase origin/main` 且无冲突；验证阶段发现并修复 `core.table_clipboard.TableClipboardController` 旧选区残留导致粘贴起点不稳定的问题，随后 amend 到同一提交。推送前最终执行 `python -m pytest tests\test_table_clipboard.py tests\test_feasibility_assessment_results_page.py tests\test_feasibility_factor_diagnostics.py tests\test_feasibility_runtime_result_cache.py tests\test_platform_strength_page_initial_async.py tests\test_report_table_writer.py -q` 通过（79 passed, 2 skipped），并执行相关 `python -m compileall` 通过；最后一次 `git fetch origin` 后确认本地仅 ahead 1、不 behind，执行 `git push origin main` 成功，推送后 `HEAD`、`origin/main`、`origin/HEAD` 均指向 `ddf9fb3`，ahead/behind 为 `0/0`。未跟踪的 `.codex_tmp_vba/`、`docs/superpowers/`、`image.png`、`image1.png`、`image2.png` 保留本地，未纳入提交。
- 2026-06-10：修复可行性评估报告生成失败 `tuple index out of range`：根因是报告模板“海生物信息”表最后一行“海生物密度”使用横向合并单元格，`write_environment_marine_growth_table()` 动态裁列时原先通过 `row.cells[column_index]` 删除列，`python-docx` 在合并单元格映射下会抛 `IndexError`。本次在 `pages/output_feasibility_analysis_report/src/renderers/table_writer.py` 中新增基于 Word XML 网格列的裁列逻辑：普通单元格删除对应 `tc`，横向合并单元格只缩短 `gridSpan`；保留已有按 `2 + 实际层数` 扩列/裁列语义。`tests/test_report_table_writer.py` 新增直接打开真实报告纯净版模板海生物表的回归测试，覆盖少于 9 层时裁列不会崩溃；已执行 `python -m pytest tests\test_report_table_writer.py tests\test_report_service_analysis_ui.py -q` 通过（6 passed），`python -m compileall pages\output_feasibility_analysis_report\src\renderers\table_writer.py tests\test_report_table_writer.py` 通过，并用真实模板额外验证 1 层、4 层、12 层海生物数据均可正常写入。
