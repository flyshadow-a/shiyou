# -*- coding: utf-8 -*-
# summary_excel_provider.py

from __future__ import annotations

import os
from typing import Dict, List, Optional, Any

import pandas as pd


class ReadTableXls:
    """从《平台汇总信息样表.xls》读取并提取下拉框选项（可复用）。"""

    EXCEL_NAME = "平台汇总信息样表.xls"

    FIELD_CANDIDATES: Dict[str, List[str]] = {
        "分公司": ["分公司", "所属分公司"],
        "作业公司": ["作业公司", "作业单位", "作业单元", "作业公司/单元"],
        "油气田": ["油气田", "油田", "油气田(田)", "所属油气田"],
        "设施编码": ["设施编码", "设施编号", "设施代码", "平台编码", "平台代码"],
        "设施名称": ["设施名称", "平台名称"],
        "设施类型": ["设施类型", "平台类型", "设施类别"],
        "分类": ["分类", "平台分类", "类别"],
        "投产时间": ["投产时间", "投产日期"],
        "设计年限": ["设计年限", "设计寿命"],
    }

    def __init__(self):
        self.df: Optional[pd.DataFrame] = None
        self._resolved_cols: Dict[str, Optional[str]] = {}

    def default_excel_path(self) -> str:
        data_dir = os.path.join(os.getcwd(), "data")
        p1 = os.path.join(data_dir, self.EXCEL_NAME)
        if os.path.exists(p1):
            return p1
        p2 = os.path.join(os.getcwd(), self.EXCEL_NAME)
        if os.path.exists(p2):
            return p2
        return p1

    def load(self, excel_path: Optional[str] = None, header: int = 1) -> pd.DataFrame:
        path = excel_path or self.default_excel_path()
        if not os.path.exists(path):
            raise FileNotFoundError(f"未找到 Excel：{path}")

        df = None
        last_err: Optional[Exception] = None

        try:
            df = pd.read_excel(path, header=header, engine="xlrd")
        except Exception as e:
            last_err = e

        if df is None:
            try:
                df = pd.read_excel(path, header=header)
                last_err = None
            except Exception as e:
                last_err = e

        if df is None:
            raise RuntimeError(f"读取 Excel 失败：{last_err}")

        df.columns = [str(c).strip() for c in df.columns]
        self.df = df
        self._resolved_cols = {}
        return df

    def _resolve_col(self, field: str) -> Optional[str]:
        if field in self._resolved_cols:
            return self._resolved_cols[field]
        if self.df is None:
            self._resolved_cols[field] = None
            return None

        candidates = self.FIELD_CANDIDATES.get(field, [field])
        cols = set(self.df.columns)

        for c in candidates:
            if c in cols:
                self._resolved_cols[field] = c
                return c

        norm = {str(col).replace(" ", ""): col for col in self.df.columns}
        for c in candidates:
            key = str(c).replace(" ", "")
            if key in norm:
                self._resolved_cols[field] = norm[key]
                return norm[key]

        self._resolved_cols[field] = None
        return None

    def _clean(self, v: Any) -> str:
        if v is None:
            return ""
        try:
            if pd.isna(v):
                return ""
        except Exception:
            pass
        if hasattr(v, "strftime"):
            return v.strftime("%Y-%m-%d")
        return str(v).strip()

    def options_for(self, field: str, *, limit: int = 500) -> List[str]:
        if self.df is None:
            return []
        col = self._resolve_col(field)
        if not col:
            return []

        seen = set()
        out: List[str] = []
        for v in self.df[col].tolist():
            s = self._clean(v)
            if not s or s in seen:
                continue
            seen.add(s)
            out.append(s)
            if len(out) >= limit:
                break
        return out

    def default_for(self, field: str, fallback: str = "") -> str:
        opts = self.options_for(field, limit=1)
        return opts[0] if opts else fallback
