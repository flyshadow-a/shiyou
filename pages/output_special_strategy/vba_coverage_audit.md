# VBA Coverage Audit

## Scope

This note audits the extracted VBA procedures in
`pages/output_special_strategy/vba_converted.py`
against the active Python pipeline:

- `pages/output_special_strategy/inspection_tool.py`
- `pages/output_special_strategy/report_jinja2_generator.py`
- `pages/output_special_strategy/sacs_to_report.py`
- `pages/output_special_strategy/run_sacs_report_from_config.py`

## Active Python Runtime Chain

`run_sacs_report_from_config.py -> sacs_to_report.py -> inspection_tool.py`

## Final-Flow Coverage

These VBA procedures are part of the final risk/report workflow and do have a
Python implementation in the active runtime path.

| VBA procedure | Purpose | Python equivalent | Status |
|---|---|---|---|
| `Sheet1_ReadSACS` | Read `sacinp.*` into joints/groups/members/sections | `parse_sacinp` + workbook write-back | Covered |
| `Sheet1_FindLegMember` | LEG tracing from work points | `classify_structure` | Covered |
| `Sheet1_Find_X_Joint` | X-joint / X-brace identification | `classify_structure` | Covered |
| `Sheet2_JointTYPE` | Naming-rule joint overwrite | `classify_structure` | Covered |
| `Sheet3_MemberTYPE` | Naming-rule member overwrite | `classify_structure` | Covered |
| `Sheet5_ParseCollapseAnalysis` | Parse `clplog.*` | `parse_clplog` / `parse_clplogs` | Covered |
| `Sheet8_Ringmember` | Parse `ftginp.*` factors/selectors | `parse_ftginp_ringmember` / `build_fatigue_merge_cfg_from_ftginp` | Covered |
| `Sheet8_FatiguePickup` | Parse `ftglst.*` and merge fatigue rows | `parse_ftglst_detail` / `parse_ftglst_details` | Covered |
| `Sheet1_UpdateMemberRisk` | Member consequence + collapse + overall risk | `build_member_risk_vba` | Covered |
| `Sheet1_UpdateJointRisk` | Joint consequence + fatigue + collapse + overall risk | `build_joint_risk_vba` | Covered |
| `Sheet1_JointRiskForeCast` | Joint future fatigue/risk forecast | `build_joint_forecast_vba` / `build_joint_forecast_vba_wide` | Covered |
| `Sheet18_JIANYAN` | Node inspection plan | `build_node_plan_vba` | Covered |
| `Sheet19_MemberCheck` | Member inspection plan | `build_member_plan_vba` | Covered |

## Report-Stage Coverage

These VBA procedures affect what the user finally sees, but in Python they are
handled in the report/context layer rather than the workbook-building core.

| VBA procedure | Purpose | Python equivalent | Status |
|---|---|---|---|
| `Sheet10_删除MEMBER` | Filter member risk table before summary/report | `is_deleted_member_by_vba_rule` + `load_context_from_workbook` | Covered |
| `Sheet11_删除JOINT` | Filter current joint risk table before summary/report | `is_deleted_joint_by_vba_rule` + `load_context_from_workbook` | Covered |
| `Sheet12_删除JOINT1` | Filter future joint inspection table before summary/report | `is_deleted_joint_by_vba_rule` + `load_context_from_workbook` | Covered |

## Auxiliary / Obsolete / Non-final-flow VBA

These procedures exist in the workbook code, but they are either old versions,
formatting helpers, UI helpers, or model-building utilities that are not part
of the current 9-module business pipeline.

| VBA procedure | Notes | Python status |
|---|---|---|
| `Sheet1_ClearData` | Clears intermediate workbook sheets before re-read | Not ported literally; Python writes fresh workbook blocks instead |
| `Sheet1_CheckMemberVerticality` | Helper for old leg logic | Not needed in final path |
| `Sheet1_CheckMemberOD` | Helper for old leg logic | Not needed in final path |
| `Sheet1_CheckMemberIsLeg` | Helper for old leg logic | Not needed in final path |
| `Sheet1_FindLegMemberOld` | Explicitly old version | Intentionally not used |
| `Sheet1_PlaneVector` | Geometry helper | Not used in active Python path |
| `Sheet1_VectorAngleDegree` | Geometry helper | Equivalent behavior exists as `vector_angle_degree_vba` |
| `Sheet1_SetFormat` | Excel number formatting helper | Not ported as a standalone VBA-equivalent routine |
| `Sheet1_FindMaxD` | Older helper for fatigue max damage lookup | Final VBA path uses direct `Max(E:T)` inside `UpdateJointRisk`; Python matches final path |
| `Sheet1_isTubJoint` | Auxiliary query helper | Not used in final risk path |
| `Sheet2_RunSQLAgainstSheet` | UI/helper sheet to count repeated Z elevations | Not ported into active pipeline |
| `Sheet18_合并` | Sheet18 helper | Behavior handled inline in Python plan build / sorting |
| `Sheet18_快速排序` | Sheet18 helper | Behavior handled by Python sorting |
| `Sheet19_快速排序` | Sheet19 helper | Behavior handled by Python sorting |
| `模块1_Get_ID_Available` | New-ID helper for model editing utilities | Not in active reporting flow |
| `模块1_FillString` | Helper for above | Not in active reporting flow |
| `模块2_MinLevel` | Helper for inspection utilities | Equivalent concept handled inline, not ported as standalone |
| `模块2_Level2Number` | Helper for inspection utilities | Equivalent concept handled inline, not ported as standalone |
| `WellSlot` and related generated-model logic | Model augmentation utility, not final report path | Not in active reporting flow |

## Accuracy Risks Still Requiring Table-by-Table Verification

Reading the VBA code is necessary, but by itself it is not sufficient to claim
full numeric parity. The following items still need output-level verification
against a clean VBA run if strict parity is required:

1. `Sheet8_FatiguePickup` multi-file replacement state machine
2. `Sheet1_UpdateMemberRisk` waterline filter and consequence/collapse join
3. `Sheet1_UpdateJointRisk` fatigue row matching and collapse fallback
4. `Sheet1_JointRiskForeCast` time-node expansion
5. `Sheet18_JIANYAN` and `Sheet19_MemberCheck` random-selection and sorting behavior
6. Report-stage deletion timing relative to summaries/tables

## Current Conclusion

The active Python pipeline covers the final 9 business modules and their
report-stage delete rules. The remaining non-covered VBA is concentrated in:

- obsolete routines
- UI / formatting helpers
- workbook-only helper tools
- non-report model-generation utilities

For strict confidence in data accuracy, the remaining task is no longer
"find missing code paths", but "run table-by-table parity checks on outputs".
