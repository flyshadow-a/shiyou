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
from pages.history_events_inspection_page import HistoryEventsInspectionPage
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
                    
                    {"text": "油气田信息", "page": OilfieldWaterLevelPage},
                    {
                        "text": "平台基本结构信息","page":PlatformStructureInfoPage}
                        
                            #{"text":"基本信息","page":PlatformBasicInfoPage},
                            

                        
                     
                ],
            },
            {"text": "载荷信息",
             "children":[
                 {"text":"汇总信息表","page":SummaryInformationTablePage},
                 {"text":"平台载荷信息表","page":PlatformLoadInformationPage}
             ]},
            {"text": "状态检测（结构和腐蚀性检测）",},
            {"text": "结构强度/改造可行性评估","page":PlatformStrengthPage},

            {"text": "特检策略","page": SpecialInspectionStrategy},
            # 后续可以在这里继续增加其他功能菜单
        ],
    },
    {
        "text": "文件管理",
        "children": [
            {"text": "汇总信息","page":PlatformSummaryPage},
            {
                "text": "建设阶段完工文件",
                "page": ConstructionDocsPage,
            },
            {"text": "历史改造文件", "page": HistoryRebuildFilesPage},
            {"text": "\u5386\u53f2\u4e8b\u4ef6\u53ca\u68c0\u6d4b", "page": HistoryEventsInspectionPage},
            {"text": "模型文件", "page": ModelFilesPage},
        ],
    }

    # 还可以继续增加「文件管理」等大类
]
