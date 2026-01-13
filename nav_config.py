# -*- coding: utf-8 -*-
# nav_config.py

"""
左侧导航配置：
- text: 树节点显示文字
- page: 该节点对应的页面类（叶子节点）
- children: 子节点列表
"""

from pages.dashboard_page import DashboardPage
from pages.oilfield_water_level_page import OilfieldWaterLevelPage
from pages.construction_docs_page import ConstructionDocsPage
from pages.platform_summary_page import PlatformSummaryPage
from pages.platform_basic_info_page import PlatformBasicInfoPage
from pages.platform_structure_info_page import PlatformStructureInfoPage
from pages.special_inspection_strategy import SpecialInspectionStrategy
from pages.summary_information_table_page import SummaryInformationTablePage
from pages.platform_load_information_page import PlatformLoadInformationPage
from pages.upper_block_subproject_calculation_table_page import UpperBlockSubprojectCalculationTablePage
from pages.platform_strength_page import PlatformStrengthPage
from pages.feasibility_assessment_page import FeasibilityAssessmentPage
from pages.feasibility_assessment_results_page import FeasibilityAssessmentResultsPage
from pages.model_files_page import ModelFilesPage
from pages.history_rebuild_files_page import HistoryRebuildFilesPage
from pages.important_history_rebuild_info_page import ImportantHistoryEventsPage
from pages.history_inspection_summary_page import HistoryInspectionSummaryPage
from pages.personal_center_page import PersonalCenterPage

NAV_CONFIG = [
    {
        "text": "个人中心","page": PersonalCenterPage
    },
    {
        "text": "平台载荷管理",
        "children": [
            {
                "text": "平台信息",
                "children": [
                    {"text": "汇总信息","page":PlatformSummaryPage},
                    {"text": "油气田信息", "page": OilfieldWaterLevelPage},
                    {
                        "text": "平台基本信息",
                        "children":[
                            {"text":"基本信息","page":PlatformBasicInfoPage},
                            {"text":"结构信息","page":PlatformStructureInfoPage},

                        ]
                     },
                ],
            },
            {"text": "载荷信息",
             "children":[
                 {"text":"汇总信息表","page":SummaryInformationTablePage},
                 {"text":"平台载荷信息表","page":PlatformLoadInformationPage}
             ]},
            {"text": "状态检测（结构和腐蚀性检测）",},
            {"text": "结构强度/改造可行性评估",
             "children":[{"text":"平台强度/改造可行性评估","page":PlatformStrengthPage},
                         {"text":"WC19-1DPPA平台强度/改造可行性评估","page":FeasibilityAssessmentPage},
                         {"text": "WC19-1DPPA平台强度/改造可行性评估评估结果", "page": FeasibilityAssessmentResultsPage},
                         ]},

            {"text": "特检策略","page": SpecialInspectionStrategy},
            # 后续可以在这里继续增加其他功能菜单
        ],
    },
    {
        "text": "文件管理",
        "children": [
            {
                "text": "建设阶段完工文件",
                "page": ConstructionDocsPage,
                "children": [
                    {
                        "text": "湛江分公司",
                        "children": [
                            {
                                "text": "1.润洲作业公司",
                                "children": [
                                    {
                                        "text": "1.2 作业公司",
                                        "children": [
                                            {"text": "1.2.1 WC19-1DPA"},
                                            {"text": "1.2.2 WC19-1WHPC"},
                                            {"text": "1.2.3 WC9-7DPP"},
                                        ],
                                    },
                                ],
                            },
                            {
                                "text": "1.3 乌石作业公司",
                            },
                        ],
                    },
                    {"text": "天津分公司"},
                    {"text": "上海分公司"},
                    {"text": "深圳分公司"},
                    {"text": "海南分公司"},
                ],
            },
            {"text": "历史改造文件", "page": HistoryRebuildFilesPage},
            {"text": "模型文件", "page": ModelFilesPage},
            {"text": "重要历史事件记录", "page": ImportantHistoryEventsPage},
            {"text": "历史检测及结论", "page": HistoryInspectionSummaryPage},
        ],
    }

    # 还可以继续增加「文件管理」等大类
]
