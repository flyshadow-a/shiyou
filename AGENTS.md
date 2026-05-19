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
