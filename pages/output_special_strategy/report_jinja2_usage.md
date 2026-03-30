# Jinja2 报告生成使用方式

## 1. 直接生成报告

```bash
python pages/output_special_strategy/report_jinja2_generator.py \
  --workbook "pages/output_special_strategy/检测策略- wc9-7-10.30.1.xlsm" \
  --template "pages/output_special_strategy/xxx平台风险评级及检测策略报告.docx" \
  --output "pages/output_special_strategy/xxx平台风险评级及检测策略报告_自动生成.docx" \
  --platform-name "文昌9-7DPPA" \
  --report-date "2026年3月12日"
```

## 2. 使用 metadata json

`metadata.json` 示例：

```json
{
  "platform_name": "文昌9-7DPPA",
  "report_date": "2026年3月12日"
}
```

执行：

```bash
python pages/output_special_strategy/report_jinja2_generator.py \
  --workbook "pages/output_special_strategy/检测策略- wc9-7-10.30.1.xlsm" \
  --template "pages/output_special_strategy/xxx平台风险评级及检测策略报告.docx" \
  --output "pages/output_special_strategy/xxx平台风险评级及检测策略报告_自动生成.docx" \
  --metadata-json "pages/output_special_strategy/metadata.json"
```

## 3. 已实现的模板自动填充

- 封面平台名、封面日期
- 节点焊缝疲劳失效概率表
- 构件倒塌失效概率表
- 节点倒塌失效概率表
- 节点风险等级表（当前）
- 构件风险等级表
- 构件检验计划（附件C）
- 节点检验计划（附件C）
- 风险/检验汇总统计表

## 4. 仍需人工输入或维护的内容

- 概述中的项目背景与描述性文字
- 规范说明、检测手段说明等静态说明段落
- 非结构化文字结论（如果每个平台需要不同表述）

## 5. 一键运行（SACS 输入包 -> Word 报告）

```bash
python pages/output_special_strategy/sacs_to_report.py \
  --template-xlsm "pages/output_special_strategy/检测策略- wc9-7-10.30.1.xlsm" \
  --model "pages/sacs/sacinp.JKnew" \
  --clplog "pages/sacs/clplog" \
  --ftglst "pages/sacs/ftglst" \
  --report-template "pages/output_special_strategy/xxx平台风险评级及检测策略报告.docx" \
  --output-report "pages/output_special_strategy/xxx平台风险评级及检测策略报告_JKnew_自动生成.docx" \
  --platform-name "{{platform_name}}" \
  --report-date "{{report_date}}"
```

可选参数：
- `--metadata-json`：传入 JSON 后可覆盖占位符（键名：`platform_name`、`report_date`）
- `--intermediate-workbook`：指定中间 `xlsx` 输出路径（默认跟随 `output-report`）
- 默认启用“明细表限行”以避免 Word 卡顿；如需全量导出可加 `--full-rows`（文件会显著变大）

## 6. 导出后自动核对（建议）

```bash
python pages/output_special_strategy/validate_report_tables.py \
  --workbook "pages/output_special_strategy/xxx平台风险评级及检测策略报告_JKnew_自动生成_轻量_v3.pipeline.xlsx" \
  --docx "pages/output_special_strategy/xxx平台风险评级及检测策略报告_JKnew_自动生成_轻量_v3.docx" \
  --platform-name "{{platform_name}}" \
  --report-date "{{report_date}}"
```

输出中 `Checks failed: 0` 表示表格写入与上下文数据一致，并通过来源一致性校验。
