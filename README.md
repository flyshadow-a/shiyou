## 1. 基础环境与依赖

### Python 版本
- 推荐：Python 3.8+

### 必须安装的库

```bash
pip install PyQt5
```
### 快速运行
python main.py

### 核心结构
```
project_root/
├─ main.py                # 入口：创建主窗口，加载导航 & 页面
├─ base_page.py           # 页面基类 BasePage
├─ nav_config.py          # 左侧导航配置（菜单 → 页面类）
├─ dropdown_bar.py        # 可复用的筛选条控件
├─ pages/
│  ├─ dashboard_page.py           # 示例：首页
#平台载荷管理
│  ├─ platform_summary_page.py          #汇总信息
│  ├─ oilfield_water_level_page.py      #油气田信息
│  ├─ platform_structure_info_page.py   #平台结构信息
│  ├─ platform_basic_info_page.py       # 平台基本信息
│  ├─ special_inspection_strategy.py    #特检策略
│    ├─ upgrade_special_inspection_result_page.py#特检升级结果
│    ├─new_special_inspection_page.py    #新特检信息
#文件管理    
│  ├─ construction_docs_page.py   # “建设阶段完工文件”页面
│     ├─ construction_docs_widget.py    #文件管理组件
│  ├─ important_history_rebuild_info_page.py  #重要历史事件
│  ├─ history_rebuild_files_page.py     #历史改造文件
│  ├─ model_files_page.py           #模型文件
│  ├─history_inspection_summary_page.py  #历史检测及结论
│  └─ 
├─ pict/
│  ├─ logo.png
│  ├─ wenjian.png
│  └─ ...                        # 所有图标统一放这里
└─ uploads/                       # 运行时上传文件的存储目录
```

## 新建一个页面
### 第一步 例如新建：pages/platform_info_page.py：
```
# -*- coding: utf-8 -*-
# pages/platform_info_page.py

from PyQt5.QtWidgets import QLabel
from base_page import BasePage

class PlatformInfoPage(BasePage):
    def __init__(self, parent=None):
        # 页签 / 标题显示的名字
        super().__init__("平台基本信息", parent)
        self.build_ui()

    def build_ui(self):
        # 所有页面内容都往 self.main_layout 里加
        label = QLabel("这里是平台基本信息页面，可以在此继续堆组件。")
        self.main_layout.addWidget(label)
```
规则：
必须继承 BasePage
super().__init__("页面标题", parent) 中的标题会显示在右侧标签/标题上
所有控件都加到 self.main_layout 中


### 第二步：在 nav_config.py 中注册这个页面

打开 nav_config.py，先导入这个类：
from pages.platform_info_page import PlatformInfoPage
然后在对应的分组里添加一项，例如加到“平台管理”下：
```
NAV_CONFIG = [
    {
        "group": "平台管理",
        "items": [
            {
                "id": "platform_info",
                "text": "平台基本信息",
                "page_cls": PlatformInfoPage,   # ← 指向你刚写的页面类
            },
            # 其他菜单...
        ],
    },
    # 其他 group...
]
```
保存后重新运行 main.py，左侧导航中就会出现“平台基本信息”，点击即可打开你写的页面。
