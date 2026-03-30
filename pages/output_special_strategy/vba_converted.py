# -*- coding: utf-8 -*-
"""
Auto-converted from VBA in the workbook:
检测策略- wc9-7-10.30.1.xlsm

This file is a full-coverage syntactic translation of all extracted VBA modules.
"""

from __future__ import annotations

from dataclasses import dataclass
import fnmatch
import math
import os
from pathlib import Path
from typing import Any


def create_object(_name: str):
    return VbaPlaceholder()


def msg_box(message: Any) -> None:
    print(f"[MsgBox] {message}")


def vb_assign(lhs: str, value: Any) -> Any:
    # Placeholder for VBA left-values that are not valid Python assignment targets,
    # such as Sheet.Cells(r, c) = value.
    return value


def vb_like(value: Any, pattern: str) -> bool:
    return fnmatch.fnmatch(str(value), pattern.replace("#", "[0-9]"))


def vb_trim(value: Any) -> str:
    return str(value).strip()


def vb_left(value: Any, n: int) -> str:
    return str(value)[: int(n)]


def vb_right(value: Any, n: int) -> str:
    n_i = int(n)
    s = str(value)
    return s[-n_i:] if n_i > 0 else ""


def vb_mid(value: Any, start: int, length: int | None = None) -> str:
    s = str(value)
    i = max(int(start) - 1, 0)
    if length is None:
        return s[i:]
    return s[i : i + int(length)]


def vb_instr(*args: Any) -> int:
    if len(args) == 2:
        start, text, sub = 1, args[0], args[1]
    elif len(args) == 3:
        start, text, sub = args[0], args[1], args[2]
    else:
        return 0
    idx = str(text).find(str(sub), max(int(start) - 1, 0))
    return idx + 1 if idx >= 0 else 0


def vb_split(text: Any, sep: str = " ") -> list[str]:
    return str(text).split(sep)


def vb_isnumeric(value: Any) -> bool:
    try:
        float(str(value))
        return True
    except Exception:
        return False


def vb_array(*items: Any) -> list[Any]:
    return list(items)


def vb_match(value: Any, arr: Any, _mode: int = 0) -> int:
    seq = list(arr) if hasattr(arr, "__iter__") else []
    for idx, item in enumerate(seq, start=1):
        if item == value:
            return idx
    raise ValueError("value not found")


def vba_for_range(start: Any, end: Any, step: Any = 1):
    s = int(start)
    e = int(end)
    st = int(step)
    if st == 0:
        st = 1
    if st > 0:
        return range(s, e + 1, st)
    return range(s, e - 1, st)


def vba_lbound(_arr: Any) -> int:
    return 1


def vba_ubound(arr: Any) -> int:
    if arr is None:
        return 0
    try:
        return len(arr)
    except Exception:
        return 0


def vba_redim(arr: Any, bounds: list[tuple[Any, Any]], preserve: bool = False):
    if not bounds:
        return []
    dims = []
    for lo, hi in bounds:
        lo_i = int(lo)
        hi_i = int(hi)
        dims.append(max(0, hi_i - lo_i + 1))
    if len(dims) == 1:
        size = dims[0]
        if preserve and isinstance(arr, list):
            out = arr[:size]
            out.extend([None] * max(0, size - len(out)))
            return out
        return [None] * size
    rows, cols = dims[0], dims[1]
    if preserve and isinstance(arr, list):
        out = [r[:] if isinstance(r, list) else [None] * cols for r in arr[:rows]]
        while len(out) < rows:
            out.append([None] * cols)
        for r in out:
            if len(r) < cols:
                r.extend([None] * (cols - len(r)))
            elif len(r) > cols:
                del r[cols:]
        return out
    return [[None] * cols for _ in range(rows)]


_VB_FILES: dict[int, str] = {}
_VB_FILE_POS: dict[int, int] = {}
_VB_OUT_PATH: dict[int, str] = {}
_VB_OUT_BUF: dict[int, list[str]] = {}


def vb_open_input(fid: int, file_path: Any) -> None:
    path = str(file_path)
    fid_i = int(fid)
    _VB_FILES[fid_i] = Path(path).read_text(encoding="utf-8", errors="ignore")
    _VB_FILE_POS[fid_i] = 0


def vb_open_output(fid: int, file_path: Any) -> None:
    fid_i = int(fid)
    _VB_OUT_PATH[fid_i] = str(file_path)
    _VB_OUT_BUF[fid_i] = []


def vb_lof(fid: int) -> int:
    return len(_VB_FILES.get(int(fid), ""))


def vb_input(_count: int, fid: int) -> str:
    return _VB_FILES.get(int(fid), "")


def vb_line_input(fid: int) -> str:
    fid_i = int(fid)
    content = _VB_FILES.get(fid_i, "")
    pos = _VB_FILE_POS.get(fid_i, 0)
    if pos >= len(content):
        return ""
    end = content.find("\n", pos)
    if end < 0:
        _VB_FILE_POS[fid_i] = len(content)
        return content[pos:].rstrip("\r")
    _VB_FILE_POS[fid_i] = end + 1
    return content[pos:end].rstrip("\r")


def vb_file_close(fid: int) -> None:
    fid_i = int(fid)
    _VB_FILES.pop(fid_i, None)
    _VB_FILE_POS.pop(fid_i, None)
    out_path = _VB_OUT_PATH.pop(fid_i, None)
    out_buf = _VB_OUT_BUF.pop(fid_i, None)
    if out_path is not None and out_buf is not None:
        try:
            Path(out_path).write_text("\n".join(out_buf), encoding="utf-8")
        except Exception:
            pass


def vb_file_print(fid: int, value: Any) -> None:
    fid_i = int(fid)
    if fid_i not in _VB_OUT_BUF:
        _VB_OUT_BUF[fid_i] = []
    _VB_OUT_BUF[fid_i].append(str(value))


def vb_dir(path: Any) -> str:
    p = str(path)
    return p if os.path.exists(p) else ""


class VbaPlaceholder:
    def __call__(self, *args, **kwargs):
        return self

    def __getattr__(self, _name: str):
        return self

    def __getitem__(self, _key):
        return self

    def __setitem__(self, _key, _value) -> None:
        return None

    def __iter__(self):
        return iter(())

    def __bool__(self):
        return False

    def __str__(self):
        return ""

    def __repr__(self):
        return "<VbaPlaceholder>"


ThisWorkbook = VbaPlaceholder()
Application = VbaPlaceholder()
ActiveWindow = VbaPlaceholder()
WorksheetFunction = VbaPlaceholder()
Range = VbaPlaceholder()
Cells = VbaPlaceholder()

for _sheet_idx in range(1, 30):
    globals()[f"Sheet{_sheet_idx}"] = VbaPlaceholder()

xlUp = -4162
xlYes = 1
xlSortOnValues = 0
xlDescending = 2
xlContinuous = 1


@dataclass
class Elevation:
    Z: Any = None
    Connection: Any = None

@dataclass
class Group:
    ID: Any = None
    OD: Any = None
    WT: Any = None
    Skip: Any = None

@dataclass
class Joint:
    ID: Any = None
    X: Any = None
    Y: Any = None
    Z: Any = None
    Remark: Any = None

@dataclass
class Joint_Offset:
    Off_X: Any = None
    Off_Y: Any = None
    Off_Z: Any = None

@dataclass
class Member:
    Joint_A: Any = None
    Joint_B: Any = None
    MemberGroup: Any = None
    A_Offset: Any = None
    B_Offset: Any = None


# ===== Module: Elevation =====
Z = None
Connection = None


# ===== Module: Group =====
ID = None
OD = None
WT = None
Skip = None


# ===== Module: Joint =====
ID = None
X = None
Y = None
Z = None
Remark = None


# ===== Module: Joint_Offset =====
Off_X = None
Off_Y = None
Off_Z = None


# ===== Module: Member =====
Joint_A = None
Joint_B = None
MemberGroup = None
A_Offset = None
B_Offset = None


# ===== Module: Sheet1 =====

def Sheet1_ClearData(ShowNoMsg=None):
    Sheet2.Cells.ClearContents()
    vb_assign('Sheet2.Cells(1, 1)', 'Joint')
    vb_assign('Sheet2.Columns(1).NumberFormat', '@')
    vb_assign('Sheet2.Cells(1, 2)', 'X')
    vb_assign('Sheet2.Cells(1, 3)', 'Y')
    vb_assign('Sheet2.Cells(1, 4)', 'Z')
    vb_assign('Sheet2.Cells(1, 5)', 'JointType')
    vb_assign('Sheet2.Columns(5).NumberFormat', '@')
    Sheet3.Cells.ClearContents()
    vb_assign('Sheet3.Cells(1, 1)', 'A')
    vb_assign('Sheet3.Columns(1).NumberFormat', '@')
    vb_assign('Sheet3.Cells(1, 2)', 'B')
    vb_assign('Sheet3.Columns(2).NumberFormat', '@')
    vb_assign('Sheet3.Cells(1, 3)', 'ID')
    vb_assign('Sheet3.Cells(1, 4)', 'OD')
    vb_assign('Sheet3.Cells(1, 5)', 'MemberType')
    vb_assign('Sheet2.Columns(5).NumberFormat', '@')
    vb_assign('Sheet3.Cells(1, 6)', 'Z1')
    vb_assign('Sheet3.Cells(1, 7)', 'Z2')
    Sheet4.Cells.ClearContents()
    vb_assign('Sheet4.Cells(1, 1)', 'ID')
    vb_assign('Sheet4.Cells(1, 2)', 'OD')
    vb_assign('Sheet4.Cells(1, 3)', 'Type')
    vb_assign('Sheet4.Columns(3).NumberFormat', '@')
    Sheet6.Cells.ClearContents()
    vb_assign('Sheet6.Cells(1, 1)', 'ID')
    vb_assign('Sheet6.Cells(1, 2)', 'Type')
    vb_assign('Sheet6.Columns(2).NumberFormat', '@')
    vb_assign('Sheet6.Cells(1, 3)', 'OD')
    vb_assign('Sheet6.Columns(3).NumberFormat', '@')
    if not ShowNoMsg:
        msg_box('DONE')

def Sheet1_ReadSACS():
    ModelFile = Cells(2, 2)
    SeaFile = Cells(3, 2)
    if vb_dir(ModelFile) == '':
        msg_box('文件不存在，请检查后重试')
        return
    Sheet1_ClearData(True)
    s_i = 2
    G_i = 2
    M_i = 2
    J_i = 2
    L_i = 2
    conn = None
    rs = None
    strConn = None
    strSQL = None
    conn = create_object('ADODB.Connection')
    rs = create_object('ADODB.Recordset')
    strConn = 'Provider=Microsoft.ACE.OLEDB.12.0;' + 'Data Source=' + ThisWorkbook.FullName + ';' + 'Extended Properties="Excel 12.0;HDR=Yes;";'
    conn.Open(strConn)
    vb_open_input(1, ModelFile)
    while not EOF(1):
        A = vb_line_input(1)
        keyword = 'SECT'
        if vb_left(A, len(keyword)) == keyword:
            if vb_trim(vb_mid(A, 6, 7)) != '':
                vb_assign('Sheet6.Cells(s_i, 1).NumberFormat', '@')
                vb_assign('Sheet6.Cells(s_i, 1)', vb_trim(vb_mid(A, 6, 7)))
                vb_assign('Sheet6.Cells(s_i, 2).NumberFormat', '@')
                if vb_trim(vb_mid(A, 16, 3)) != '':
                    vb_assign('Sheet6.Cells(s_i, 2)', vb_trim(vb_mid(A, 16, 3)))
                if Sheet6.Cells(s_i, 2) == 'TUB' or Sheet6.Cells(s_i, 2) == 'CON':
                    vb_assign('Sheet6.Cells(s_i, 3)', float(vb_mid(A, 50, 6)))
                s_i = s_i + 1
        keyword = 'GRUP'
        if vb_left(A, len(keyword)) == keyword:
            if vb_trim(vb_mid(A, 6, 3)) != '':
                vb_assign('Sheet4.Cells(G_i, 1).NumberFormat', '@')
                vb_assign('Sheet4.Cells(G_i, 1)', vb_trim(vb_mid(A, 6, 3)))
                if vb_trim(vb_mid(A, 18, 6)) != '':
                    vb_assign('Sheet4.Cells(G_i, 2)', float(vb_trim(vb_mid(A, 18, 6))))
                else:
                    strSQL = "SELECT * FROM [Sections$] Where ID='" + vb_trim(vb_mid(A, 10, 7)) + "'"
                    rs.Open(strSQL, conn)
                    if not rs.EOF:
                        if not IsNull(rs.Fields(2).Value):
                            vb_assign('Sheet4.Cells(G_i, 2)', float(rs.Fields(2).Value))
                    rs.Close()
                G_i = G_i + 1
        keyword = 'MEMBER'
        if vb_left(A, len(keyword)) == keyword:
            if vb_trim(vb_mid(A, 8, 8)) != '' and vb_trim(vb_mid(A, 8, 7)) != 'OFFSETS':
                vb_assign('Sheet3.Cells(M_i, 1).NumberFormat', '@')
                vb_assign('Sheet3.Cells(M_i, 2).NumberFormat', '@')
                vb_assign('Sheet3.Cells(M_i, 3).NumberFormat', '@')
                vb_assign('Sheet3.Cells(M_i, 1)', vb_trim(str(vb_mid(A, 8, 4))))
                vb_assign('Sheet3.Cells(M_i, 2)', vb_trim(str(vb_mid(A, 12, 4))))
                vb_assign('Sheet3.Cells(M_i, 3)', vb_trim(str(vb_mid(A, 17, 3))))
                strSQL = "SELECT MAX(OD) FROM [Groups$] Where ID='" + Sheet3.Cells(M_i, 3) + "'"
                rs.Open(strSQL, conn)
                if not rs.EOF:
                    if not IsNull(rs.Fields(0).Value):
                        vb_assign('Sheet3.Cells(M_i, 4)', float(rs.Fields(0).Value))
                rs.Close()
                M_i = M_i + 1
        keyword = 'JOINT'
        if vb_left(A, len(keyword)) == keyword:
            if vb_trim(vb_mid(A, 7, 8)) != '' and vb_trim(vb_mid(A, 8, 7)) != 'OFFSETS':
                vb_assign('Sheet2.Cells(J_i, 1).NumberFormat', '@')
                vb_assign('Sheet2.Cells(J_i, 1)', vb_trim(str(vb_mid(A, 7, 4))))
                if vb_trim(vb_mid(A, 12, 7)) == '':
                    X = 0
                else:
                    X = float(vb_mid(A, 12, 7))
                if vb_trim(vb_mid(A, 33, 7)) != '':
                    X = X + float(vb_mid(A, 33, 7)) / 100
                if vb_trim(vb_mid(A, 19, 7)) == '':
                    Y = 0
                else:
                    Y = float(vb_mid(A, 19, 7))
                if vb_trim(vb_mid(A, 40, 7)) != '':
                    Y = Y + float(vb_mid(A, 40, 7)) / 100
                if vb_trim(vb_mid(A, 26, 7)) == '':
                    Z = 0
                else:
                    Z = float(vb_mid(A, 26, 7))
                if vb_trim(vb_mid(A, 47, 7)) != '':
                    Z = Z + float(vb_mid(A, 47, 7)) / 100
                vb_assign('Sheet2.Cells(J_i, 2)', X)
                vb_assign('Sheet2.Cells(J_i, 3)', Y)
                vb_assign('Sheet2.Cells(J_i, 4)', Z)
                J_i = J_i + 1
        if vb_instr(A, 'CENTER') + vb_instr(A, 'SURFID') + vb_instr(A, 'WGTFP') + vb_instr(A, 'LOADCN') > 0:
            pass
            # GoTo Finish_Data
    # VBA: Finish_Data
    vb_file_close(1)
    for i in vba_for_range(2, Sheet3.UsedRange.Rows.Count, 1):
        if vb_trim(Sheet3.Cells(i, 1)) != '':
            strSQL = "SELECT * FROM [Joints$] Where Joint='" + Sheet3.Cells(i, 1) + "'"
            rs.Open(strSQL, conn)
            vb_assign('Sheet3.Cells(i, 6)', rs.Fields(3).Value)
            rs.Close()
            strSQL = "SELECT * FROM [Joints$] Where Joint='" + Sheet3.Cells(i, 2) + "'"
            rs.Open(strSQL, conn)
            vb_assign('Sheet3.Cells(i, 7)', rs.Fields(3).Value)
            rs.Close()
    # VBA: SetFormat
    msg_box('DONE')
    return
    # VBA: errOut
    A = 0
    msg_box('ERROR')

def Sheet1_CheckMemberVerticality(JA, JB):
    _return_value = None
    _return_value = False
    MinSlope = Sheet1.Cells(6, 2)
    conn = None
    rs = None
    strConn = None
    strSQL = None
    conn = create_object('ADODB.Connection')
    rs = create_object('ADODB.Recordset')
    strConn = 'Provider=Microsoft.ACE.OLEDB.12.0;' + 'Data Source=' + ThisWorkbook.FullName + ';' + 'Extended Properties="Excel 12.0;HDR=Yes;";'
    conn.Open(strConn)
    strSQL = "SELECT * FROM [Joints$] Where Joint='" + JA + "'"
    rs.Open(strSQL, conn)
    XA = rs.Fields(1).Value
    YA = rs.Fields(2).Value
    ZA = rs.Fields(3).Value
    rs.Close()
    strSQL = "SELECT * FROM [Joints$] Where Joint='" + JB + "'"
    rs.Open(strSQL, conn)
    XB = rs.Fields(1).Value
    YB = rs.Fields(2).Value
    ZB = rs.Fields(3).Value
    rs.Close()
    rs = None
    conn.Close()
    conn = None
    if Sqr((XB - XA) * (XB - XA) + (YB - YA) * (YB - YA)) == 0:
        Slope = 1000
    else:
        Slope = Abs(ZB - ZA) / Sqr((XB - XA) * (XB - XA) + (YB - YA) * (YB - YA))
    if Slope > MinSlope:
        _return_value = True
    return _return_value

def Sheet1_CheckMemberOD(JA, JB):
    _return_value = None
    _return_value = False
    MinOD = Sheet1.Cells(7, 2) / 10
    conn = None
    rs = None
    strConn = None
    strSQL = None
    conn = create_object('ADODB.Connection')
    rs = create_object('ADODB.Recordset')
    strConn = 'Provider=Microsoft.ACE.OLEDB.12.0;' + 'Data Source=' + ThisWorkbook.FullName + ';' + 'Extended Properties="Excel 12.0;HDR=Yes;";'
    conn.Open(strConn)
    strSQL = "SELECT * FROM [Members$] Where (A='" + JA + "'and B='" + JB + "') Or  (B='" + JA + "'and A='" + JB + "') "
    rs.Open(strSQL, conn)
    GRP = rs.Fields(2).Value
    rs.Close()
    strSQL = "SELECT * FROM [Groups$] Where ID='" + GRP + "'"
    rs.Open(strSQL, conn)
    OD = rs.Fields(1).Value
    rs.Close()
    rs = None
    conn.Close()
    conn = None
    if OD > MinOD:
        _return_value = True
    return _return_value

def Sheet1_CheckMemberIsLeg(JA, JB):
    _return_value = None
    # On Error GoTo errOut
    _return_value = True
    MinSlope = Sheet1.Cells(6, 2)
    MyOD = 0
    conn = None
    rs = None
    rs2 = None
    strConn = None
    strSQL = None
    conn = create_object('ADODB.Connection')
    rs = create_object('ADODB.Recordset')
    rs2 = create_object('ADODB.Recordset')
    strConn = 'Provider=Microsoft.ACE.OLEDB.12.0;' + 'Data Source=' + ThisWorkbook.FullName + ';' + 'Extended Properties="Excel 12.0;HDR=Yes;";'
    conn.Open(strConn)
    strSQL = "SELECT * FROM [Members$] Where (A='" + JA + "'and B='" + JB + "') Or  (B='" + JA + "'and A='" + JB + "') "
    rs.Open(strSQL, conn)
    GRP = rs.Fields(2).Value
    rs.Close()
    strSQL = "SELECT * FROM [Groups$] Where ID='" + GRP + "'"
    rs.Open(strSQL, conn)
    MyOD = rs.Fields(1).Value
    rs.Close()
    strSQL = "SELECT * FROM [Joints$] Where Joint='" + JA + "'"
    rs.Open(strSQL, conn)
    XA = rs.Fields(1).Value
    YA = rs.Fields(2).Value
    ZA = rs.Fields(3).Value
    rs.Close()
    strSQL = "SELECT * FROM [Joints$] Where Joint='" + JB + "'"
    rs.Open(strSQL, conn)
    XB = rs.Fields(1).Value
    YB = rs.Fields(2).Value
    ZB = rs.Fields(3).Value
    rs.Close()
    strSQL = "SELECT * FROM [Members$] Where ( A='" + JA + "' Or  B='" + JA + "'OR  A='" + JB + "' Or  B='" + JB + "') and (A<>'" + JA + "'and B<>'" + JB + "')"
    rs.Open(strSQL, conn)
    while not rs.EOF:
        J_A = vb_trim(rs.Fields(0).Value)
        J_B = vb_trim(rs.Fields(1).Value)
        Gp = rs.Fields(2).Value
        strSQL = "SELECT * FROM [Joints$] Where Joint='" + J_A + "'"
        rs2.Open(strSQL, conn)
        X_A = rs2.Fields(1).Value
        Y_A = rs2.Fields(2).Value
        Z_A = rs2.Fields(3).Value
        rs2.Close()
        strSQL = "SELECT * FROM [Joints$] Where Joint='" + J_B + "'"
        rs2.Open(strSQL, conn)
        X_B = rs2.Fields(1).Value
        Y_B = rs2.Fields(2).Value
        Z_B = rs2.Fields(3).Value
        rs2.Close()
        in_line = False
        if Sqr((XB - XA) * (XB - XA) + (YB - YA) * (YB - YA)) == 0:
            if Sqr((X_B - X_A) * (X_B - X_A) + (Y_B - Y_A) * (Y_B - Y_A)) == 0:
                in_line = True
            elif Abs(Z_B - Z_A) / Sqr((X_B - X_A) * (X_B - X_A) + (Y_B - Y_A) * (Y_B - Y_A)) > MinSlope:
                in_line = True
            else:
                in_line = False
        else:
            if Sqr((X_B - X_A) * (X_B - X_A) + (Y_B - Y_A) * (Y_B - Y_A)) == 0:
                in_line = True
            else:
                Slope1 = Abs(ZB - ZA) / Sqr((XB - XA) * (XB - XA) + (YB - YA) * (YB - YA))
                Slope2 = Abs(Z_B - Z_A) / Sqr((X_B - X_A) * (X_B - X_A) + (Y_B - Y_A) * (Y_B - Y_A))
                if Abs(Slope1 - Slope2) / Slope1 < 0.001:
                    in_line = True
                else:
                    in_line = False
        if not in_line:
            strSQL = "SELECT * FROM [Groups$] Where ID='" + Gp + "'"
            rs2.Open(strSQL, conn)
            OD = rs2.Fields(1).Value
            rs2.Close()
            if OD >= MyOD:
                _return_value = False
        rs.MoveNext()
    rs = None
    rs2 = None
    conn.Close()
    conn = None
    return _return_value
    # VBA: errOut
    A = Err.Description
    return _return_value

def Sheet1_FindLegMemberOld():
    # On Error GoTo errOut
    JA = None
    JB = None
    for i in vba_for_range(2, Sheet3.UsedRange.Rows.Count, 1):
        vb_assign('Sheet3.Cells(i, 6)', 1)
        JA = Sheet3.Cells(i, 1)
        JB = Sheet3.Cells(i, 2)
        if Sheet1_CheckMemberVerticality(JA, JB):
            if Sheet1_CheckMemberOD(JA, JB):
                if Sheet1_CheckMemberIsLeg(JA, JB):
                    vb_assign('Sheet3.Cells(i, 5)', 'LEG')
    msg_box('DONE')
    return
    # VBA: errOut
    A = 1
    msg_box(Err.Description)

def Sheet1_FindLegMember():
    conn = None
    rs = None
    rs2 = None
    strConn = None
    strSQL = None
    conn = create_object('ADODB.Connection')
    rs = create_object('ADODB.Recordset')
    rs2 = create_object('ADODB.Recordset')
    strConn = 'Provider=Microsoft.ACE.OLEDB.12.0;' + 'Data Source=' + ThisWorkbook.FullName + ';' + 'Extended Properties="Excel 12.0;HDR=Yes;";'
    conn.Open(strConn)
    # On Error GoTo errOut
    s_i = 1
    No_Legs = Sheet1.Cells(9, 2)
    WP_Z = float(Sheet1.Cells(8, 2))
    for i in vba_for_range(1, No_Legs, 1):
        WP_X = float(Sheet1.Cells(10 + i, 2))
        WP_Y = float(Sheet1.Cells(10 + i, 3))
        strSQL = "SELECT * FROM [Joints$] where (Joint<>'' and Joint is Not NULL) Order By (X - (" + WP_X + '))* (X - (' + WP_X + ')) + (Y - (' + WP_Y + '))*(Y - (' + WP_Y + ')) + (Z - (' + WP_Z + '))*(Z - (' + WP_Z + ')) asc'
        rs.Open(strSQL, conn)
        J1_ID = rs.Fields(0).Value
        J1_X = rs.Fields(1).Value
        J1_Y = rs.Fields(2).Value
        J1_Z = rs.Fields(3).Value
        J0_X = J1_X
        J0_Y = J1_Y
        J0_Z = J1_Z
        rs.Close()
        DownEnd = False
        UpEnd = False
        while DownEnd == False:
            strSQL = 'SELECT * FROM [Joints$] where X=' + J1_X + ' and Y=' + J1_Y + ' and Z=' + J1_Z
            rs.Open(strSQL, conn)
            J_List = ''
            while not rs.EOF:
                J_List = J_List + "'" + rs.Fields(0).Value + "',"
                rs.MoveNext()
            J_List = vb_left(J_List, len(J_List) - 1)
            rs.Close()
            strSQL = 'SELECT * FROM [Members$] where (A in (' + J_List + ') or B in (' + J_List + ')) and (Z1+Z2) < ' + 2 * J1_Z + ' Order by OD desc'
            rs.Open(strSQL, conn)
            r_i = 0
            Max_OD_i = 0
            while not rs.EOF:
                r_i = r_i + 1
                if not IsNull(rs.Fields(3).Value):
                    if float(rs.Fields(3).Value) > Max_OD_i:
                        JA = rs.Fields(0).Value
                        JB = rs.Fields(1).Value
                        Max_OD_i = float(rs.Fields(3).Value)
                rs.MoveNext()
            if r_i == 0 or Max_OD_i < 100:
                rs.Close()
                DownEnd = True
            else:
                rs.Close()
                strSQL = "Update [Members$] set MemberType= 'LEG' where A = '" + JA + "' And B = '" + JB + "'"
                rs.Open(strSQL, conn)
                if vb_instr(J_List, "'" + JA + "'") > 0:
                    strSQL = "SELECT * FROM [Joints$] where Joint = '" + JB + "'"
                else:
                    strSQL = "SELECT * FROM [Joints$] where Joint = '" + JA + "'"
                rs.Open(strSQL, conn)
                J1_X = rs.Fields(1).Value
                J1_Y = rs.Fields(2).Value
                J1_Z = rs.Fields(3).Value
                rs.Close()
        J1_X = J0_X
        J1_Y = J0_Y
        J1_Z = J0_Z
        while UpEnd == False:
            strSQL = 'SELECT * FROM [Joints$] where X=' + J1_X + ' and Y=' + J1_Y + ' and Z=' + J1_Z
            rs.Open(strSQL, conn)
            J_List = ''
            while not rs.EOF:
                J_List = J_List + "'" + rs.Fields(0).Value + "',"
                rs.MoveNext()
            J_List = vb_left(J_List, len(J_List) - 1)
            rs.Close()
            strSQL = 'SELECT * FROM [Members$] where (A in (' + J_List + ') or B in (' + J_List + ')) and (Z1+Z2) > ' + 2 * J1_Z + ' Order by OD desc'
            rs.Open(strSQL, conn)
            r_i = 0
            Max_OD_i = 0
            while not rs.EOF:
                r_i = r_i + 1
                if not IsNull(rs.Fields(3).Value):
                    if float(rs.Fields(3).Value) > Max_OD_i:
                        JA = rs.Fields(0).Value
                        JB = rs.Fields(1).Value
                        Max_OD_i = float(rs.Fields(3).Value)
                rs.MoveNext()
            if r_i == 0 or Max_OD_i < 100:
                rs.Close()
                UpEnd = True
            else:
                rs.Close()
                strSQL = "Update [Members$] set MemberType= 'LEG' where A = '" + JA + "' And B = '" + JB + "'"
                rs.Open(strSQL, conn)
                if vb_instr(J_List, "'" + JA + "'") > 0:
                    strSQL = "SELECT * FROM [Joints$] where Joint = '" + JB + "'"
                else:
                    strSQL = "SELECT * FROM [Joints$] where Joint = '" + JA + "'"
                rs.Open(strSQL, conn)
                J1_X = rs.Fields(1).Value
                J1_Y = rs.Fields(2).Value
                J1_Z = rs.Fields(3).Value
                rs.Close()
    s_i = 2
    strSQL = "Select * from [Joints$] where Joint in (SELECT A FROM [Members$] WHERE MemberType = 'LEG')"
    rs.Open(strSQL, conn)
    while not rs.EOF:
        JID = rs.Fields(0).Value
        s_i = 2.1
        strSQL2 = "select * from [Members$] where (A='" + JID + "' or B='" + JID + "') "
        rs2.Open(strSQL2, conn)
        Max_OD = 0
        while not rs2.EOF:
            if not IsNull(rs2.Fields(3).Value):
                if float(rs2.Fields(3).Value) > Max_OD:
                    Max_OD = float(rs2.Fields(3).Value)
            rs2.MoveNext()
        rs2.Close()
        min_OD = max(0.2 * Max_OD, Sheet1.Cells(7, 2) / 10)
        s_i = 2.2
        Count_Member = 0
        strSQL2 = "select count(*) from [Members$] where (A='" + JID + "' or B='" + JID + "') and OD >=  " + min_OD
        rs2.Open(strSQL2, conn)
        Count_Member = rs2.Fields(0).Value
        rs2.Close()
        s_i = 2.3
        if Count_Member > 2:
            strSQL2 = "Update [Joints$] set JointType = 'LegJoint' where Joint  = '" + JID + "'"
            rs2.Open(strSQL2, conn)
        rs.MoveNext()
    rs.Close()
    s_i = 3
    strSQL = "Select * from [Joints$] where Joint in (SELECT B FROM [Members$] WHERE MemberType = 'LEG')"
    rs.Open(strSQL, conn)
    while not rs.EOF:
        JID = rs.Fields(0).Value
        s_i = 3.1
        strSQL2 = "select * from [Members$] where (A='" + JID + "' or B='" + JID + "') "
        rs2.Open(strSQL2, conn)
        Max_OD = 0
        while not rs2.EOF:
            if not IsNull(rs2.Fields(3).Value):
                if float(rs2.Fields(3).Value) > Max_OD:
                    Max_OD = float(rs2.Fields(3).Value)
            rs2.MoveNext()
        rs2.Close()
        min_OD = max(0.2 * Max_OD, Sheet1.Cells(7, 2) / 10)
        s_i = 3.2
        Count_Member = 0
        strSQL2 = "select count(*) from [Members$] where (A='" + JID + "' or B='" + JID + "') and OD >= " + min_OD
        rs2.Open(strSQL2, conn)
        Count_Member = rs2.Fields(0).Value
        rs2.Close()
        s_i = 3.3
        if Count_Member > 2:
            strSQL2 = "Update [Joints$] set JointType = 'LegJoint' where Joint  = '" + JID + "'"
            rs2.Open(strSQL2, conn)
        rs.MoveNext()
    rs.Close()
    rs = None
    conn.Close()
    conn = None
    msg_box('DONE')
    return
    # VBA: errOut
    s_i = 100
    msg_box(Err.Description)

def Sheet1_Find_X_Joint():
    conn = None
    rs = None
    rs2 = None
    rs3 = None
    strConn = None
    strSQL = None
    conn = create_object('ADODB.Connection')
    rs = create_object('ADODB.Recordset')
    rs2 = create_object('ADODB.Recordset')
    rs3 = create_object('ADODB.Recordset')
    strConn = 'Provider=Microsoft.ACE.OLEDB.12.0;' + 'Data Source=' + ThisWorkbook.FullName + ';' + 'Extended Properties="Excel 12.0;HDR=Yes;";'
    conn.Open(strConn)
    # On Error GoTo errOut
    strSQL = "SELECT * FROM [Joints$] Where (JointType <> 'LegJoint' or JointType is NULL) and Z<=" + Sheet1.Cells(8, 2)
    rs.Open(strSQL, conn)
    X_Joint_List = ''
    while not rs.EOF:
        JID = rs.Fields(0).Value
        if JID == '218F':
            Aa = 1
        strSQL2 = "SELECT Max(OD) FROM [Members$] Where (A='" + JID + "' or B='" + JID + "') "
        rs2.Open(strSQL2, conn)
        if not rs2.EOF and not IsNull(rs2.Fields(0).Value):
            Max_OD = rs2.Fields(0).Value
            rs2.Close()
            Num_M = 0
            strSQL2 = "SELECT * FROM [Members$] Where (A='" + JID + "' or B='" + JID + "') and OD>= " + Max_OD - 2
            rs2.Open(strSQL2, conn)
            P1 = None
            P2 = None
            while not rs2.EOF:
                Num_M = Num_M + 1
                P1 = vba_redim(P1, [(1, Num_M)], preserve=True)
                strSQL3 = "SELECT * from [Joints$]  where Joint='" + rs2.Fields(0).Value + "'"
                rs3.Open(strSQL3, conn)
                vb_assign('P1(Num_M)', Joint())
                vb_assign('P1(Num_M).ID', rs3.Fields(0).Value)
                vb_assign('P1(Num_M).X', rs3.Fields(1).Value)
                vb_assign('P1(Num_M).Y', rs3.Fields(2).Value)
                vb_assign('P1(Num_M).Z', rs3.Fields(3).Value)
                rs3.Close()
                P2 = vba_redim(P2, [(1, Num_M)], preserve=True)
                strSQL3 = "SELECT * from [Joints$]  where Joint='" + rs2.Fields(1).Value + "'"
                rs3.Open(strSQL3, conn)
                vb_assign('P2(Num_M)', Joint())
                vb_assign('P2(Num_M).ID', rs3.Fields(0).Value)
                vb_assign('P2(Num_M).X', rs3.Fields(1).Value)
                vb_assign('P2(Num_M).Y', rs3.Fields(2).Value)
                vb_assign('P2(Num_M).Z', rs3.Fields(3).Value)
                rs3.Close()
                rs2.MoveNext()
            Angle_Deviation = 2
            X_Angle_Deviation = Cells(6, 2)
            if Num_M >= 4:
                Num_Collinear = 0
                if JID == 'L234':
                    A = 1
                for i in vba_for_range(1, Num_M - 1, 1):
                    VX1 = P2(i).X - P1(i).X
                    VY1 = P2(i).Y - P1(i).Y
                    VZ1 = P2(i).Z - P1(i).Z
                    for j in vba_for_range(i + 1, Num_M, 1):
                        VX2 = P2(j).X - P1(j).X
                        VY2 = P2(j).Y - P1(j).Y
                        VZ2 = P2(j).Z - P1(j).Z
                        theAngle = Sheet1_VectorAngleDegree(vb_array(VX1, VY1, VZ1), vb_array(VX2, VY2, VZ2))
                        if theAngle > 90:
                            theAngle = 180 - theAngle
                        if theAngle <= Angle_Deviation and Abs(VZ2) != 0:
                            Num_Collinear = Num_Collinear + 1
                            vb_assign('P2(i).Remark', 'Pair-' + Num_Collinear)
                            vb_assign('P1(i).Remark', 'Pair-' + Num_Collinear)
                            vb_assign('P2(j).Remark', 'Pair-' + Num_Collinear)
                            vb_assign('P1(j).Remark', 'Pair-' + Num_Collinear)
                if Num_Collinear == 2:
                    X_Joint_List = X_Joint_List + JID + ','
                    strSQL3 = "Update [Joints$] set JointType= 'X Joint' where Joint = '" + JID + "'"
                    rs3.Open(strSQL3, conn)
                    if JID == 'L124':
                        A = 1
                    for i in vba_for_range(1, Num_M, 1):
                        if vb_instr(P1(i).Remark, 'Pair'):
                            strSQL3 = "Update [Members$] set MemberType= 'X-Brace' where A = '" + P1(i).ID + "' and B = '" + P2(i).ID + "'"
                            rs3.Open(strSQL3, conn)
                            Start_Joint = JID
                            to_End = FLASE
                            if P1(i).ID == JID:
                                End_Joint = P2(i).ID
                            else:
                                End_Joint = P1(i).ID
                        strSQL3 = "SELECT * from [Joints$]  where Joint='" + Start_Joint + "'"
                        rs3.Open(strSQL3, conn)
                        X_S = rs3.Fields(1).Value
                        Y_S = rs3.Fields(2).Value
                        Z_S = rs3.Fields(3).Value
                        rs3.Close()
                        strSQL3 = "SELECT * from [Joints$]  where Joint='" + End_Joint + "'"
                        rs3.Open(strSQL3, conn)
                        X_E = rs3.Fields(1).Value
                        Y_E = rs3.Fields(2).Value
                        Z_E = rs3.Fields(3).Value
                        rs3.Close()
                        strSQL3 = "SELECT count(*) FROM [Members$] Where (A = '" + End_Joint + "' or B = '" + End_Joint + "') and OD>= " + Max_OD - 2 + ' and OD<= ' + Max_OD + 2 + " and (MemberType<>'X-Brace' or MemberType is NULL)"
                        rs3.Open(strSQL3, conn)
                        M_i = rs3.Fields(0).Value
                        rs3.Close()
                        if M_i == 0:
                            continue  # GoTo Next_Brace
                        elif M_i >= 1:
                            strSQL3 = "SELECT * FROM [Members$] Where (A = '" + End_Joint + "' or B = '" + End_Joint + "') and OD>= " + Max_OD - 2 + ' and OD<= ' + Max_OD + 2 + " and  (MemberType<>'X-Brace' or MemberType is NULL)"
                            rs3.Open(strSQL3, conn)
                            JAs = None
                            JBs = None
                            mm_i = None
                            JAs = vba_redim(None, [(1, 1)], preserve=False)
                            JBs = vba_redim(None, [(1, 1)], preserve=False)
                            mm_i = 0
                            while not rs3.EOF:
                                mm_i = mm_i + 1
                                JAs = vba_redim(JAs, [(1, mm_i)], preserve=True)
                                JBs = vba_redim(JBs, [(1, mm_i)], preserve=True)
                                vb_assign('JAs(mm_i)', rs3.Fields(0).Value)
                                vb_assign('JBs(mm_i)', rs3.Fields(1).Value)
                                rs3.MoveNext()
                            rs3.Close()
                            for k in vba_for_range(vba_lbound(JAs), vba_ubound(JAs), 1):
                                strSQL3 = "SELECT * from [Joints$]  where Joint='" + JAs(k) + "'"
                                rs3.Open(strSQL3, conn)
                                X1 = rs3.Fields(1).Value
                                Y1 = rs3.Fields(2).Value
                                Z1 = rs3.Fields(3).Value
                                rs3.Close()
                                strSQL3 = "SELECT * from [Joints$]  where Joint='" + JBs(k) + "'"
                                rs3.Open(strSQL3, conn)
                                X2 = rs3.Fields(1).Value
                                Y2 = rs3.Fields(2).Value
                                Z2 = rs3.Fields(3).Value
                                rs3.Close()
                                theAngle = Sheet1_VectorAngleDegree(vb_array(X2 - X1, Y2 - Y1, Z2 - Z1), vb_array(X_E - X_S, Y_E - Y_S, Z_E - Z_S))
                                if theAngle > 90:
                                    theAngle = 180 - theAngle
                                if theAngle <= X_Angle_Deviation:
                                    if JA == End_Joint:
                                        Start_Joint = JAs(k)
                                        End_Joint = JBs(k)
                                    else:
                                        Start_Joint = JBs(k)
                                        End_Joint = JAs(k)
                                    strSQL3 = "Update [Members$] set MemberType= 'X-Brace' where A = '" + JAs(k) + "' and B = '" + JBs(k) + "'"
                                    rs3.Open(strSQL3, conn)
                                    continue  # GoTo Next_Seg
    rs2.Close()
    rs.MoveNext()
    vb_open_output(1, 'D:\\1.txt')
    vb_file_print(1, X_Joint_List)
    vb_file_close(1)
    rs.Close()
    rs = None
    conn.Close()
    conn = None
    msg_box('DONE')
    return
    # VBA: errOut
    s_i = 1000
    msg_box(Err.Description)

def Sheet1_PlaneVector(P1, P2, P3):
    _return_value = None
    Nx = (P2(1) - P1(1)) * (P3(2) - P1(2)) - (P2(2) - P1(2)) * (P3(1) - P1(1))
    Ny = (P2(2) - P1(2)) * (P3(0) - P1(0)) - (P2(0) - P1(0)) * (P3(2) - P1(2))
    Nz = (P2(0) - P1(0)) * (P3(1) - P1(1)) - (P2(1) - P1(1)) * (P3(0) - P1(0))
    l = Sqr(Nx * Nx + Ny * Ny + Nz * Nz)
    _return_value = vb_array(Nx / l, Ny / l, Nz / l)
    return _return_value

def Sheet1_VectorAngleDegree(V1, V2):
    _return_value = None
    VV = V1(0) * V2(0) + V1(1) * V2(1) + V1(2) * V2(2)
    L_V1 = Sqr(V1(0) * V1(0) + V1(1) * V1(1) + V1(2) * V1(2))
    L_V2 = Sqr(V2(0) * V2(0) + V2(1) * V2(1) + V2(2) * V2(2))
    if L_V1 != 0 and L_V2 != 0:
        Cosine = Application.WorksheetFunction.Round(VV / (L_V1 * L_V2), 5)
        _return_value = Application.WorksheetFunction.Degrees(Application.WorksheetFunction.Acos(Cosine))
    else:
        _return_value = 0
    return _return_value

def Sheet1_SetFormat():
    vb_assign('Sheet2.Columns("B:D").NumberFormatLocal', '0.00_ ')
    vb_assign('Sheet3.Columns("D:D").NumberFormatLocal', '0.00_ ')
    vb_assign('Sheet4.Columns("B:B").NumberFormatLocal', '0.00_ ')
    vb_assign('Sheet6.Columns("C:C").NumberFormatLocal', '0.00_ ')

def Sheet1_UpdateMemberRisk():
    conn = None
    rs = None
    strConn = None
    strSQL = None
    conn = create_object('ADODB.Connection')
    rs = create_object('ADODB.Recordset')
    strConn = 'Provider=Microsoft.ACE.OLEDB.12.0;' + 'Data Source=' + ThisWorkbook.FullName + ';' + 'Extended Properties="Excel 12.0;HDR=Yes;";'
    conn.Open(strConn)
    wz = Sheet1.Cells(8, 2)
    globalLv = None
    localLv = None
    RSR = min(Sheet5.Range('F2:F13'))
    # select case Cells(44, 2)
    if (Cells(44, 2) == 'L-1'):
        globalLv = 0
    elif (Cells(44, 2) == 'L-2'):
        globalLv = 1
    elif (Cells(44, 2) == 'L-3'):
        globalLv = 2
    # VBA: Sheet10.Range("A3:K" & Sheet10.UsedRange.Rows.Count).ClearContents
    R = 2
    for i in vba_for_range(2, Sheet3.UsedRange.Rows.Count, 1):
        if Sheet3.Cells(i, 1) != '' and (Sheet3.Cells(i, 7) + Sheet3.Cells(i, 8)) < wz:
            R = R + 1
            vb_assign('Sheet10.Cells(R, 1)', Sheet3.Cells(i, 1))
            vb_assign('Sheet10.Cells(R, 2)', Sheet3.Cells(i, 2))
            vb_assign('Sheet10.Cells(R, 3)', Sheet3.Cells(i, 5))
            if vb_trim(Sheet10.Cells(R, 3)) == '':
                vb_assign('Sheet10.Cells(R, 3)', 'Other')
            # select case Sheet10.Cells(R, 3)
            if (Sheet10.Cells(R, 3) == 'LEG'):
                localLv = 1
            elif (Sheet10.Cells(R, 3) == 'X-Brace'):
                localLv = 2
            elif (Sheet10.Cells(R, 3) == 'Other'):
                localLv = 3
            vb_assign('Sheet10.Cells(R, 4)', globalLv + localLv)
            vb_assign('Sheet10.Cells(R, 5)', Sheet1.Cells(46, 2))
            vb_assign('Sheet10.Cells(R, 6)', Sheet1.Cells(47, 2))
            strSQL = 'SELECT min(FACTOR) FROM [倒塌分析结果$A15:E' + Sheet5.UsedRange.Rows.Count + "] Where LOCATION='" + Sheet10.Cells(R, 1) + '-' + Sheet10.Cells(R, 2) + "'"
            rs.Open(strSQL, conn)
            if not rs.EOF and not IsNull(rs.Fields(0).Value):
                vb_assign('Sheet10.Cells(R, 7)', rs.Fields(0).Value)
            else:
                vb_assign('Sheet10.Cells(R, 7)', RSR)
            rs.Close()
            vb_assign('Sheet10.Cells(R, 8)', 0.1)
            vb_assign('Sheet10.Cells(R, 8).NumberFormat', '0%')
            vb_assign('Sheet10.Cells(R, 9).FormulaR1C1', '=EXP((RC[-4]-RC[-2])/RC[-3]+RC[-1]^2*RC[-2]^2/2/RC[-3]^2)*(1-NORM.DIST(RC[-1]*RC[-2]/RC[-3]-1/RC[-1],0,1,FALSE))')
            vb_assign('Sheet10.Cells(R, 10).FormulaR1C1', '=INDEX(风险评级矩阵!R39C3:R39C7,MATCH(RC[-1],风险评级矩阵!R37C3:R37C7,1))')
            vb_assign('Sheet10.Cells(R, 11).FormulaR1C1', '=INDEX(风险评级矩阵!R40C3:R44C7,MATCH(构件失效风险等级!RC[-7],风险评级矩阵!R40C2:R44C2,0),MATCH(构件失效风险等级!RC[-1],风险评级矩阵!R39C3:R39C7,0))')
    msg_box('DONE')

def Sheet1_UpdateJointRisk():
    Application.ScreenUpdating = False
    globalLv = None
    localLv = None
    Last8 = None
    Last2 = None
    Rng2 = None
    Rng8 = None
    Rng5 = None
    last5 = None
    Factor = None
    Fuyi = None
    Life = None
    Dic = None
    Dic2 = None
    RSR = min(Sheet5.Range('F2:F13'))
    # select case Cells(44, 2)
    if (Cells(44, 2) == 'L-1'):
        globalLv = 0
    elif (Cells(44, 2) == 'L-2'):
        globalLv = 1
    elif (Cells(44, 2) == 'L-2'):
        globalLv = 2
    Dic2 = create_object('SCRIPTING.DICTIONARY')
    last5 = Sheet5.UsedRange.Rows.Count
    Rng5 = Sheet5.Range('C16:D' + last5)
    for i in vba_for_range(vba_lbound(Rng5), vba_ubound(Rng5), 1):
        if not Dic2.exists(Rng5(i, 1)):
            Dic2.Add(vb_trim(Rng5(i, 1)), Rng5(i, 2))
        else:
            Factor = Dic2.Item(Rng5(i, 1))
            if Factor > Rng5(i, 2):
                vb_assign('Dic2.Item(Rng5(i, 1))', Rng5(i, 2))
    wz = Sheet1.Cells(8, 2)
    Last2 = Sheet2.Range('b10000').End(xlUp).Row
    Rng2 = Sheet2.Range('A2:E' + Last2)
    Dic = create_object('SCRIPTING.DICTIONARY')
    for i in vba_for_range(vba_lbound(Rng2), vba_ubound(Rng2), 1):
        if Rng2(i, 4) < wz:
            if Rng2(i, 5) == '':
                vb_assign('Rng2(i, 5)', 'Other')
            Dic.Add(Rng2(i, 1), Rng2(i, 5))
    R = 2
    Last8 = Sheet8.Range('b10000').End(xlUp).Row
    Rng8 = Sheet8.Range('A1:T' + Last8)
    # VBA: Sheet11.Range("A3:T10000").ClearContents
    ws1 = Sheet1
    Fuyi = ws1.Cells(48, 2)
    Life = ws1.Cells(49, 2)
    if True:  # with Sheet11
        for i in vba_for_range(5, vba_ubound(Rng8), 1):
            if Dic.exists(Rng8(i, 1)):
                R = R + 1
                vb_assign('Sheet11.Cells(R, 1)', Rng8(i, 1))
                vb_assign('Sheet11.Cells(R, 2)', Rng8(i, 4))
                vb_assign('Sheet11.Cells(R, 3)', Dic.Item(Rng8(i, 1)))
                # select case vb_trim(Dic.Item(Rng8(i, 1)))
                if (vb_trim(Dic.Item(Rng8(i, 1))) == 'LegJoint'):
                    localLv = 1
                elif (vb_trim(Dic.Item(Rng8(i, 1))) == 'X Joint'):
                    localLv = 2
                elif (vb_trim(Dic.Item(Rng8(i, 1))) == 'Other'):
                    localLv = 3
                vb_assign('Sheet11.Cells(R, 4)', globalLv + localLv)
                vb_assign('Sheet11.Cells(R, 5)', ws1.Cells(46, 2))
                vb_assign('Sheet11.Cells(R, 6)', ws1.Cells(47, 2))
                if Dic2.exists(vb_trim(Rng8(i, 1))):
                    vb_assign('Sheet11.Cells(R, 7)', Dic2.Item(vb_trim(Rng8(i, 1))))
                else:
                    vb_assign('Sheet11.Cells(R, 7)', RSR)
                vb_assign('Sheet11.Cells(R, 8)', 0.1)
                vb_assign('Sheet11.Cells(R, 8).NumberFormat', '0%')
                vb_assign('Sheet11.Cells(R, 9).FormulaR1C1', '=EXP((RC[-4]-RC[-2])/RC[-3]+RC[-1]^2*RC[-2]^2/2/RC[-3]^2)*(1-NORM.DIST(RC[-1]*RC[-2]/RC[-3]-1/RC[-1],0,1,FALSE))')
                vb_assign('Sheet11.Cells(R, 10).FormulaR1C1', '=INDEX(风险评级矩阵!R39C3:R39C7,MATCH(RC[-1],风险评级矩阵!R37C3:R37C7,1))')
                D = max(Sheet8.Range('E' + i + ':T' + i))
                vb_assign('Sheet11.Cells(R, 11)', D)
                vb_assign('Sheet11.Cells(R, 12)', 0.3)
                vb_assign('Sheet11.Cells(R, 13)', 0.73)
                vb_assign('Sheet11.Cells(R, 14)', 0.3)
                vb_assign('Sheet11.Cells(R, 15)', 4)
                vb_assign('Sheet11.Cells(R, 16).FormulaR1C1', '=((1+RC[-4]^2)*(1+RC[-3]^2)*(1+RC[-2]^2)^(RC[-1]^2)-1)^(1/2)')
                vb_assign('Sheet11.Cells(R, 17).FormulaR1C1', '=LN(' + Life + '/RC[-6]/' + Fuyi + ')/((LN(1+RC[-1]^2))^(1/2))')
                vb_assign('Sheet11.Cells(R, 18).FormulaR1C1', '=NORM.DIST(-RC[-1],0,1,TRUE)')
                vb_assign('Sheet11.Cells(R, 19).FormulaR1C1', '=INDEX(风险评级矩阵!R39C3:R39C7,MATCH(RC[-1],风险评级矩阵!R37C3:R37C7,1))')
                vb_assign('Sheet11.Cells(R, 20).FormulaR1C1', '=MIN(RC[-10],RC[-1])')
                vb_assign('Sheet11.Cells(R, 21).FormulaR1C1', '=INDEX(风险评级矩阵!R40C3:R44C7,MATCH(RC[-17],风险评级矩阵!R40C2:R44C2,0),MATCH(RC[-1],风险评级矩阵!R39C3:R39C7,0))')
    Application.ScreenUpdating = True
    msg_box('DONE')

def Sheet1_JointRiskForeCast():
    ws11 = None
    Fuyi = None
    Life = None
    D = None
    Application.ScreenUpdating = False
    ws11 = Sheet11
    Fuyi = Sheet1.Cells(48, 2)
    Life = Sheet1.Cells(49, 2)
    if True:  # with Sheet12
        # VBA: Sheet12.Range("A4:BS" & Sheet12.UsedRange.Rows.Count).ClearContents
        for i in vba_for_range(3, Sheet11.UsedRange.Rows.Count, 1):
            D = ws11.Cells(i, 11)
            if ws11.Cells(i, 1) != '':
                vb_assign('Sheet12.Cells(i + 1, 1)', ws11.Cells(i, 1))
                vb_assign('Sheet12.Cells(i + 1, 2)', ws11.Cells(i, 2))
                vb_assign('Sheet12.Cells(i + 1, 3)', ws11.Cells(i, 3))
                vb_assign('Sheet12.Cells(i + 1, 4)', ws11.Cells(i, 4))
                vb_assign('Sheet12.Cells(i + 1, 5)', ws11.Cells(i, 10))
                vb_assign('Sheet12.Cells(i + 1, 6)', Fuyi * D / Life)
                vb_assign('Sheet12.Cells(i + 1, 7)', 0.3)
                vb_assign('Sheet12.Cells(i + 1, 8)', 0.73)
                vb_assign('Sheet12.Cells(i + 1, 9)', 0.3)
                vb_assign('Sheet12.Cells(i + 1, 10)', 4)
                vb_assign('Sheet12.Cells(i + 1, 11).FormulaR1C1', '=((1+RC[-4]^2)*(1+RC[-3]^2)*(1+RC[-2]^2)^(RC[-1]^2)-1)^(1/2)')
                vb_assign('Sheet12.Cells(i + 1, 12).FormulaR1C1', '=LN(1/RC[-6])/((LN(1+RC[-1]^2))^(1/2))')
                vb_assign('Sheet12.Cells(i + 1, 13).FormulaR1C1', '=NORM.DIST(-RC[-1],0,1,TRUE)')
                vb_assign('Sheet12.Cells(i + 1, 14).FormulaR1C1', '=INDEX(风险评级矩阵!R39C3:R39C7,MATCH(RC[-1],风险评级矩阵!R37C3:R37C7,1))')
                vb_assign('Sheet12.Cells(i + 1, 15)', min(Sheet12.Cells(i + 1, 5), Sheet12.Cells(i + 1, 14)))
                vb_assign('Sheet12.Cells(i + 1, 16).FormulaR1C1', '=INDEX(风险评级矩阵!R40C3:R44C7,MATCH(RC[-12],风险评级矩阵!R40C2:R44C2,0),MATCH(RC[-1],风险评级矩阵!R39C3:R39C7,0))')
                vb_assign('Sheet12.Cells(i + 1, 17)', (Fuyi + 5) * D / Life)
                vb_assign('Sheet12.Cells(i + 1, 18)', 0.3)
                vb_assign('Sheet12.Cells(i + 1, 19)', 0.73)
                vb_assign('Sheet12.Cells(i + 1, 20)', 0.3)
                vb_assign('Sheet12.Cells(i + 1, 21)', 4)
                vb_assign('Sheet12.Cells(i + 1, 22).FormulaR1C1', '=((1+RC[-4]^2)*(1+RC[-3]^2)*(1+RC[-2]^2)^(RC[-1]^2)-1)^(1/2)')
                vb_assign('Sheet12.Cells(i + 1, 23).FormulaR1C1', '=LN(1/RC[-6])/((LN(1+RC[-1]^2))^(1/2))')
                vb_assign('Sheet12.Cells(i + 1, 24).FormulaR1C1', '=NORM.DIST(-RC[-1],0,1,TRUE)')
                vb_assign('Sheet12.Cells(i + 1, 25).FormulaR1C1', '=INDEX(风险评级矩阵!R39C3:R39C7,MATCH(RC[-1],风险评级矩阵!R37C3:R37C7,1))')
                vb_assign('Sheet12.Cells(i + 1, 26)', min(Sheet12.Cells(i + 1, 5), Sheet12.Cells(i + 1, 25)))
                vb_assign('Sheet12.Cells(i + 1, 27).FormulaR1C1', '=INDEX(风险评级矩阵!R40C3:R44C7,MATCH(RC[-23],风险评级矩阵!R40C2:R44C2,0),MATCH(RC[-1],风险评级矩阵!R39C3:R39C7,0))')
                vb_assign('Sheet12.Cells(i + 1, 28)', (Fuyi + 10) * D / Life)
                vb_assign('Sheet12.Cells(i + 1, 29)', 0.3)
                vb_assign('Sheet12.Cells(i + 1, 30)', 0.73)
                vb_assign('Sheet12.Cells(i + 1, 31)', 0.3)
                vb_assign('Sheet12.Cells(i + 1, 32)', 4)
                vb_assign('Sheet12.Cells(i + 1, 33).FormulaR1C1', '=((1+RC[-4]^2)*(1+RC[-3]^2)*(1+RC[-2]^2)^(RC[-1]^2)-1)^(1/2)')
                vb_assign('Sheet12.Cells(i + 1, 34).FormulaR1C1', '=LN(1/RC[-6])/((LN(1+RC[-1]^2))^(1/2))')
                vb_assign('Sheet12.Cells(i + 1, 35).FormulaR1C1', '=NORM.DIST(-RC[-1],0,1,TRUE)')
                vb_assign('Sheet12.Cells(i + 1, 36).FormulaR1C1', '=INDEX(风险评级矩阵!R39C3:R39C7,MATCH(RC[-1],风险评级矩阵!R37C3:R37C7,1))')
                vb_assign('Sheet12.Cells(i + 1, 37)', min(Sheet12.Cells(i + 1, 5), Sheet12.Cells(i + 1, 36)))
                vb_assign('Sheet12.Cells(i + 1, 38).FormulaR1C1', '=INDEX(风险评级矩阵!R40C3:R44C7,MATCH(RC[-34],风险评级矩阵!R40C2:R44C2,0),MATCH(RC[-1],风险评级矩阵!R39C3:R39C7,0))')
                vb_assign('Sheet12.Cells(i + 1, 39)', (Fuyi + 15) * D / Life)
                vb_assign('Sheet12.Cells(i + 1, 40)', 0.3)
                vb_assign('Sheet12.Cells(i + 1, 41)', 0.73)
                vb_assign('Sheet12.Cells(i + 1, 42)', 0.3)
                vb_assign('Sheet12.Cells(i + 1, 43)', 4)
                vb_assign('Sheet12.Cells(i + 1, 44).FormulaR1C1', '=((1+RC[-4]^2)*(1+RC[-3]^2)*(1+RC[-2]^2)^(RC[-1]^2)-1)^(1/2)')
                vb_assign('Sheet12.Cells(i + 1, 45).FormulaR1C1', '=LN(1/RC[-6])/((LN(1+RC[-1]^2))^(1/2))')
                vb_assign('Sheet12.Cells(i + 1, 46).FormulaR1C1', '=NORM.DIST(-RC[-1],0,1,TRUE)')
                vb_assign('Sheet12.Cells(i + 1, 47).FormulaR1C1', '=INDEX(风险评级矩阵!R39C3:R39C7,MATCH(RC[-1],风险评级矩阵!R37C3:R37C7,1))')
                vb_assign('Sheet12.Cells(i + 1, 48)', min(Sheet12.Cells(i + 1, 5), Sheet12.Cells(i + 1, 47)))
                vb_assign('Sheet12.Cells(i + 1, 49).FormulaR1C1', '=INDEX(风险评级矩阵!R40C3:R44C7,MATCH(RC[-45],风险评级矩阵!R40C2:R44C2,0),MATCH(RC[-1],风险评级矩阵!R39C3:R39C7,0))')
                vb_assign('Sheet12.Cells(i + 1, 50)', (Fuyi + 20) * D / Life)
                vb_assign('Sheet12.Cells(i + 1, 51)', 0.3)
                vb_assign('Sheet12.Cells(i + 1, 52)', 0.73)
                vb_assign('Sheet12.Cells(i + 1, 53)', 0.3)
                vb_assign('Sheet12.Cells(i + 1, 54)', 4)
                vb_assign('Sheet12.Cells(i + 1, 55).FormulaR1C1', '=((1+RC[-4]^2)*(1+RC[-3]^2)*(1+RC[-2]^2)^(RC[-1]^2)-1)^(1/2)')
                vb_assign('Sheet12.Cells(i + 1, 56).FormulaR1C1', '=LN(1/RC[-6])/((LN(1+RC[-1]^2))^(1/2))')
                vb_assign('Sheet12.Cells(i + 1, 57).FormulaR1C1', '=NORM.DIST(-RC[-1],0,1,TRUE)')
                vb_assign('Sheet12.Cells(i + 1, 58).FormulaR1C1', '=INDEX(风险评级矩阵!R39C3:R39C7,MATCH(RC[-1],风险评级矩阵!R37C3:R37C7,1))')
                vb_assign('Sheet12.Cells(i + 1, 59)', min(Sheet12.Cells(i + 1, 5), Sheet12.Cells(i + 1, 58)))
                vb_assign('Sheet12.Cells(i + 1, 60).FormulaR1C1', '=INDEX(风险评级矩阵!R40C3:R44C7,MATCH(RC[-56],风险评级矩阵!R40C2:R44C2,0),MATCH(RC[-1],风险评级矩阵!R39C3:R39C7,0))')
                vb_assign('Sheet12.Cells(i + 1, 61)', (Fuyi + 25) * D / Life)
                vb_assign('Sheet12.Cells(i + 1, 62)', 0.3)
                vb_assign('Sheet12.Cells(i + 1, 63)', 0.73)
                vb_assign('Sheet12.Cells(i + 1, 64)', 0.3)
                vb_assign('Sheet12.Cells(i + 1, 65)', 4)
                vb_assign('Sheet12.Cells(i + 1, 66).FormulaR1C1', '=((1+RC[-4]^2)*(1+RC[-3]^2)*(1+RC[-2]^2)^(RC[-1]^2)-1)^(1/2)')
                vb_assign('Sheet12.Cells(i + 1, 67).FormulaR1C1', '=LN(1/RC[-6])/((LN(1+RC[-1]^2))^(1/2))')
                vb_assign('Sheet12.Cells(i + 1, 68).FormulaR1C1', '=NORM.DIST(-RC[-1],0,1,TRUE)')
                vb_assign('Sheet12.Cells(i + 1, 69).FormulaR1C1', '=INDEX(风险评级矩阵!R39C3:R39C7,MATCH(RC[-1],风险评级矩阵!R37C3:R37C7,1))')
                vb_assign('Sheet12.Cells(i + 1, 70)', min(Sheet12.Cells(i + 1, 5), Sheet12.Cells(i + 1, 69)))
                vb_assign('Sheet12.Cells(i + 1, 71).FormulaR1C1', '=INDEX(风险评级矩阵!R40C3:R44C7,MATCH(RC[-67],风险评级矩阵!R40C2:R44C2,0),MATCH(RC[-1],风险评级矩阵!R39C3:R39C7,0))')
    Application.ScreenUpdating = True
    msg_box('DONE')

def Sheet1_FindMaxD(JID):
    _return_value = None
    _return_value = 0.000000001
    # On Error GoTo errOut
    r_i = Application.vb_match(JID, Sheet8.Range('A:A'), 0)
    for i in vba_for_range(0, 20, 1):
        R = r_i + i
        if Sheet8.Cells(R, 1) != JID:
            return _return_value
        maxD = max(Sheet8.Range('E' + R + ':T' + R))
        if FindMaxD < maxD:
            _return_value = maxD
    return _return_value
    # VBA: errOut
    A = 1
    return _return_value

def Sheet1_isTubJoint(JID):
    _return_value = None
    _return_value = False
    conn = None
    rs = None
    strConn = None
    strSQL = None
    conn = create_object('ADODB.Connection')
    rs = create_object('ADODB.Recordset')
    strConn = 'Provider=Microsoft.ACE.OLEDB.12.0;' + 'Data Source=' + ThisWorkbook.FullName + ';' + 'Extended Properties="Excel 12.0;HDR=Yes;";'
    conn.Open(strConn)
    strSQL = "select count(*) from [Members$] where (A='" + JID + "' or B='" + JID + "') and OD >=27.3"
    rs.Open(strSQL, conn)
    if rs.Fields(0).Value >= 3:
        _return_value = True
    rs.Close()
    rs = None
    conn.Close()
    conn = None
    return _return_value


# ===== Module: Sheet10 =====

def Sheet10_删除MEMBER():
    CK = None
    A = None
    B = None
    n = None
    CK = FLASE
    Application.ScreenUpdating = False
    n = 0
    if True:  # with Sheet10
        for i in vba_for_range(3, 10000, 1):
            if CK:
                i = i - 1
            A = Cells(i, 1)
            B = Cells(i, 2)
            if vb_like(A, 'C*') or vb_like(B, 'C*'):
                # VBA: Sheet10.Rows(i).Delete Shift:=xlUp
                n = n + 1
                CK = True
            elif vb_like(A, 'B*') and vb_like(B, 'B*'):
                # VBA: Sheet10.Rows(i).Delete Shift:=xlUp
                n = n + 1
                CK = True
            elif vb_like(A, 'J*') or vb_like(B, 'J*'):
                # VBA: Sheet10.Rows(i).Delete Shift:=xlUp
                n = n + 1
                CK = True
            elif vb_like(A, 'O*') or vb_like(B, 'O*'):
                # VBA: Sheet10.Rows(i).Delete Shift:=xlUp
                n = n + 1
                CK = True
            elif vb_like(A, 'K###') and vb_like(B, 'K###'):
                # VBA: Sheet10.Rows(i).Delete Shift:=xlUp
                n = n + 1
                CK = True
            elif vb_like(A, 'R*') or vb_like(B, 'R*'):
                # VBA: Sheet10.Rows(i).Delete Shift:=xlUp
                CK = True
            elif vb_like(A, '0*L') and vb_like(B, '0*L'):
                # VBA: Sheet10.Rows(i).Delete Shift:=xlUp
                n = n + 1
                CK = True
            elif vb_like(A, '*W*') and vb_like(B, '*W*'):
                # VBA: Sheet10.Rows(i).Delete Shift:=xlUp
                n = n + 1
                CK = True
            elif vb_like(A, '*C') and vb_like(B, '*C'):
                # VBA: Sheet10.Rows(i).Delete Shift:=xlUp
                n = n + 1
                CK = True
            elif A == '':
                break
            else:
                CK = False
    Application.ScreenUpdating = True
    msg_box(n + '构件已删除')


# ===== Module: Sheet11 =====

def Sheet11_删除JOINT():
    CK = None
    A = None
    B = None
    i = None
    n = None
    CK = False
    Application.ScreenUpdating = False
    n = 0
    if True:  # with Sheet11
        for i in vba_for_range(3, 10000, 1):
            if CK:
                i = i - 1
            A = Cells(i, 1)
            if vb_like(A, 'C*'):
                # VBA: Sheet11.Rows(i).Delete Shift:=xlUp
                n = n + 1
                CK = True
            elif vb_like(A, 'B*'):
                # VBA: Sheet11.Rows(i).Delete Shift:=xlUp
                n = n + 1
                CK = True
            elif vb_like(A, 'J*'):
                # VBA: Sheet11.Rows(i).Delete Shift:=xlUp
                n = n + 1
                CK = True
            elif vb_like(A, 'O*'):
                # VBA: Sheet11.Rows(i).Delete Shift:=xlUp
                n = n + 1
                CK = True
            elif vb_like(A, 'K###'):
                # VBA: Sheet11.Rows(i).Delete Shift:=xlUp
                n = n + 1
                CK = True
            elif vb_like(A, 'R*'):
                # VBA: Sheet11.Rows(i).Delete Shift:=xlUp
                n = n + 1
                CK = True
            elif vb_like(A, '*W*'):
                # VBA: Sheet11.Rows(i).Delete Shift:=xlUp
                n = n + 1
                CK = True
            elif A == '':
                break
            else:
                CK = False
    Application.ScreenUpdating = True
    msg_box(n + '删除无用节点')


# ===== Module: Sheet12 =====

def Sheet12_删除JOINT1():
    CK = None
    A = None
    B = None
    i = None
    CK = False
    Application.ScreenUpdating = False
    for i in vba_for_range(4, 10000, 1):
        if CK:
            i = i - 1
        A = Cells(i, 1)
        if vb_like(A, 'C*'):
            # VBA: Rows(i).Select
            Selection.Delete(Shift=xlUp)
            CK = True
        elif vb_like(A, 'B*'):
            # VBA: Rows(i).Select
            Selection.Delete(Shift=xlUp)
            CK = True
        elif vb_like(A, 'J*'):
            # VBA: Rows(i).Select
            Selection.Delete(Shift=xlUp)
            CK = True
        elif vb_like(A, 'O*'):
            # VBA: Rows(i).Select
            Selection.Delete(Shift=xlUp)
            CK = True
        elif A == '':
            break
        else:
            CK = False
    Application.ScreenUpdating = True
    msg_box('DONE')


# ===== Module: Sheet13 =====


# ===== Module: Sheet14 =====


# ===== Module: Sheet15 =====


# ===== Module: Sheet16 =====


# ===== Module: Sheet17 =====


# ===== Module: Sheet18 =====

def Sheet18_JIANYAN():
    ws18 = None
    ws12 = None
    ws9 = None
    ws11 = None
    R = None
    last = None
    Dj = None
    str = None
    js = None
    up = None
    Dt = None
    Fg = None
    trun = None
    Arr = None
    Application.ScreenUpdating = False
    ws12 = Sheet12
    ws18 = Sheet18
    ws9 = Sheet9
    ws1 = Sheet1
    # VBA: ws18.Range("A3:R100000").Clear
    R = 2
    last = ws12.Cells(10000, 1).End(xlUp).Row
    fy = Sheet1.Cells(48, 2)
    Life = Sheet1.Cells(49, 2)
    trun = (Life - fy) / 5 + 1
    Arr = vba_redim(None, [(1, 4), (1, 1)], preserve=False)
    for Y in vba_for_range(1, trun, 1):
        if Y == 1:
            str = '当前'
        else:
            str = '第' + (Y - 1) * 5 + '年'
        js = 0
        if True:  # with ws18
            for i in vba_for_range(4, last, 1):
                R = R + 1
                js = js + 1
                vb_assign('ws18.Cells(R, 1)', ws12.Cells(i, 1))
                vb_assign('ws18.Cells(R, 2)', ws12.Cells(i, 2))
                vb_assign('ws18.Cells(R, 3)', ws12.Cells(i, 3))
                vb_assign('ws18.Cells(R, 4)', ws12.Cells(i, 4))
                vb_assign('ws18.Cells(R, 5)', ws12.Cells(i, 5))
                vb_assign('ws18.Cells(R, 6)', ws12.Cells(i, 6 + 11 * (Y - 1)))
                vb_assign('ws18.Cells(R, 7)', ws12.Cells(i, 7 + 11 * (Y - 1)))
                vb_assign('ws18.Cells(R, 8)', ws12.Cells(i, 8 + 11 * (Y - 1)))
                vb_assign('ws18.Cells(R, 9)', ws12.Cells(i, 9 + 11 * (Y - 1)))
                vb_assign('ws18.Cells(R, 10)', ws12.Cells(i, 10 + 11 * (Y - 1)))
                vb_assign('ws18.Cells(R, 11)', ws12.Cells(i, 11 + 11 * (Y - 1)))
                vb_assign('ws18.Cells(R, 12)', ws12.Cells(i, 12 + 11 * (Y - 1)))
                vb_assign('ws18.Cells(R, 13)', ws12.Cells(i, 13 + 11 * (Y - 1)))
                vb_assign('ws18.Cells(R, 14)', ws12.Cells(i, 14 + 11 * (Y - 1)))
                vb_assign('ws18.Cells(R, 15)', ws12.Cells(i, 15 + 11 * (Y - 1)))
                vb_assign('ws18.Cells(R, 16)', ws12.Cells(i, 16 + 11 * (Y - 1)))
                vb_assign('ws18.Cells(R, 18)', str)
        up = R - js + 1
        Arr = vba_redim(Arr, [(1, 4), (1, Y)], preserve=True)
        vb_assign('Arr(1, Y)', Y)
        vb_assign('Arr(2, Y)', up)
        vb_assign('Arr(3, Y)', R)
        vb_assign('Arr(4, Y)', str)
    Arr = WorksheetFunction.Transpose(Arr)
    totalEr = None
    totalSan = None
    targetCount2 = None
    targetCount3 = None
    totalYi = None
    totalSi = None
    totalWu = None
    modifiedCount2 = None
    modifiedCount3 = None
    Jt = None
    Dic2 = None
    Dic3 = None
    Arr2 = None
    Arr3 = None
    n2 = None
    n3 = None
    Dic2 = create_object('scripting.dictionary')
    Dic3 = create_object('scripting.dictionary')
    Arr2 = vba_redim(None, [(1, 2), (1, 1)], preserve=False)
    Arr3 = vba_redim(None, [(1, 2), (1, 1)], preserve=False)
    if True:  # with ws18
        for Y in vba_for_range(vba_lbound(Arr), vba_ubound(Arr), 1):
            totalYi = 0
            totalEr = 0
            totalSan = 0
            totalSi = 0
            totalWu = 0
            for i in vba_for_range(Arr(Y, 2), Arr(Y, 3), 1):
                if ws18.Cells(i, 16) == '二':
                    totalEr = totalEr + 1
                elif ws18.Cells(i, 16) == '三':
                    totalSan = totalSan + 1
                elif ws18.Cells(i, 16) == '四':
                    totalSi = totalSi + 1
                elif ws18.Cells(i, 16) == '五':
                    totalWu = totalWu + 1
                elif ws18.Cells(i, 16) == '一':
                    totalYi = totalYi + 1
            targetCount2 = Int(totalEr * 0.2)
            modifiedCount2 = 0
            targetCount3 = Int(totalSan * 0.2)
            modifiedCount3 = 0
            # VBA: Randomize
            for i in vba_for_range(Arr(Y, 2), Arr(Y, 3), 1):
                if ws18.Cells(i, 16) == '二':
                    randomNum = Rnd()
                    Jt = ws18.Cells(i, 1) + ws18.Cells(i, 2)
                    if modifiedCount2 < targetCount2:
                        if not Dic2.exists(Jt):
                            if randomNum <= 0.2:
                                vb_assign('ws18.Cells(i, 17)', 'IV')
                                modifiedCount2 = modifiedCount2 + 1
                                n2 = n2 + 1
                                Arr2 = vba_redim(Arr2, [(1, 2), (1, n2)], preserve=True)
                                vb_assign('Arr2(1, n2)', ws18.Cells(i, 1) + ws18.Cells(i, 2))
                                vb_assign('Arr2(2, n2)', Y)
                            else:
                                vb_assign('ws18.Cells(i, 17)', 'III')
                        else:
                            vb_assign('ws18.Cells(i, 17)', 'III')
                    else:
                        vb_assign('ws18.Cells(i, 17)', 'III')
                elif ws18.Cells(i, 16) == '三':
                    randomNum = Rnd()
                    Jt = ws18.Cells(i, 1) + ws18.Cells(i, 2)
                    if modifiedCount3 < targetCount3:
                        if randomNum <= 0.2:
                            if not Dic3.exists(Jt):
                                vb_assign('ws18.Cells(i, 17)', 'III')
                                n3 = n3 + 1
                                Arr3 = vba_redim(Arr3, [(1, 2), (1, n3)], preserve=True)
                                vb_assign('Arr3(1, n3)', ws18.Cells(i, 1) + ws18.Cells(i, 2))
                                vb_assign('Arr3(2, n3)', Y)
                                modifiedCount3 = modifiedCount3 + 1
                            else:
                                vb_assign('ws18.Cells(i, 17)', 'II  ')
                        else:
                            vb_assign('ws18.Cells(i, 17)', 'II')
                    else:
                        vb_assign('ws18.Cells(i, 17)', 'II')
                elif ws18.Cells(i, 16) == '一':
                    vb_assign('ws18.Cells(i, 17)', 'IV')
                elif ws18.Cells(i, 16) == '四' or ws18.Cells(i, 16) == '五':
                    vb_assign('ws18.Cells(i, 17)', 'II')
                elif ws18.Cells(i, 16) == '':
                    break
                stp = None
                Aa = None
                Bb = None
                gl = None
                if Y % 2 == 0:
                    Aa = Arr(Y, 2)
                    Bb = Arr(Y, 3)
                    stp = 1
                else:
                    Aa = Arr(Y, 3)
                    Bb = Arr(Y, 2)
                    stp = -1
                if Y > 4:
                    gl = 0.8
                elif Y > 3:
                    gl = 0.4
                else:
                    gl = 0.25
                if i == Arr(Y, 3) and modifiedCount2 < 0.95 * targetCount2:
                    for ii in vba_for_range(Aa, Bb, stp):
                        if ws18.Cells(ii, 16) == '二':
                            randomNum = Rnd()
                            Jt = ws18.Cells(ii, 1) + ws18.Cells(ii, 2)
                            if modifiedCount2 < targetCount2:
                                if not Dic2.exists(Jt) and ws18.Cells(ii, 17) != 'IV':
                                    if randomNum <= gl:
                                        vb_assign('ws18.Cells(ii, 17)', 'IV')
                                        modifiedCount2 = modifiedCount2 + 1
                                        n2 = n2 + 1
                                        Arr2 = vba_redim(Arr2, [(1, 2), (1, n2)], preserve=True)
                                        vb_assign('Arr2(1, n2)', ws18.Cells(ii, 1) + ws18.Cells(ii, 2))
                                        vb_assign('Arr2(2, n2)', Y)
                            else:
                                break
                if i == Arr(Y, 3) and modifiedCount3 < 0.95 * targetCount3:
                    for ii in vba_for_range(Aa, Bb, stp):
                        if ws18.Cells(ii, 16) == '三':
                            randomNum = Rnd()
                            Jt = ws18.Cells(ii, 1) + ws18.Cells(ii, 2)
                            if modifiedCount3 < targetCount3:
                                if not Dic3.exists(Jt) and ws18.Cells(ii, 17) != 'III':
                                    if randomNum <= gl:
                                        vb_assign('ws18.Cells(ii, 17)', 'III')
                                        modifiedCount3 = modifiedCount3 + 1
                                        n3 = n3 + 1
                                        Arr3 = vba_redim(Arr3, [(1, 2), (1, n3)], preserve=True)
                                        vb_assign('Arr3(1, n3)', ws18.Cells(ii, 1) + ws18.Cells(ii, 2))
                                        vb_assign('Arr3(2, n3)', Y)
                            else:
                                break
            Dic2.RemoveAll()
            Dic3.RemoveAll()
            for j in vba_for_range(vba_lbound(Arr2, 2), vba_ubound(Arr2, 2), 1):
                if Arr2(2, j) > Y - 4:
                    vb_assign('Dic2.Item(Arr2(1, j))', Y)
            for j in vba_for_range(vba_lbound(Arr3, 2), vba_ubound(Arr3, 2), 1):
                if Arr3(2, j) > Y - 4:
                    vb_assign('Dic3.Item(Arr3(1, j))', Y)
            Sheet18_快速排序(Arr(Y, 2), Arr(Y, 3))
            if True:  # with ws1
                vb_assign('ws1.Cells(85 + 8 * (Y - 1), 1)', Arr(Y, 4))
                vb_assign('ws1.Cells(87 + 8 * (Y - 1), 2)', totalYi)
                vb_assign('ws1.Cells(87 + 8 * (Y - 1), 5)', totalYi)
                vb_assign('ws1.Cells(88 + 8 * (Y - 1), 2)', totalEr)
                vb_assign('ws1.Cells(88 + 8 * (Y - 1), 5)', modifiedCount2)
                vb_assign('ws1.Cells(88 + 8 * (Y - 1), 4)', totalEr - modifiedCount2)
                vb_assign('ws1.Cells(89 + 8 * (Y - 1), 2)', totalSan)
                vb_assign('ws1.Cells(89 + 8 * (Y - 1), 4)', modifiedCount3)
                vb_assign('ws1.Cells(89 + 8 * (Y - 1), 3)', totalSan - modifiedCount3)
                vb_assign('ws1.Cells(90 + 8 * (Y - 1), 2)', totalSi)
                vb_assign('ws1.Cells(90 + 8 * (Y - 1), 3)', totalSi)
                vb_assign('ws1.Cells(91 + 8 * (Y - 1), 2)', totalWu)
                vb_assign('ws1.Cells(91 + 8 * (Y - 1), 3)', totalWu)
    Application.ScreenUpdating = True
    Sheet19.MemberCheck()

def Sheet18_合并(i, str):
    if True:  # with Range('A' + i + ':N' + i)
        pass
        # VBA: Range(
    if True:  # with Range('A' + i + ':N' + i).Interior
        pass
        # VBA: Range(
        # VBA: Range(
        # VBA: Range(
        # VBA: Range(
        # VBA: Range(
    vb_assign('Cells(i, 1)', str)

def Sheet18_快速排序(u, l):
    if True:  # with Sheet18.Sort
        Sheet18.Sort.SortFields.Clear()
        Sheet18.Sort.SortFields.Add(Key=Range('Q' + u + ':Q' + l), SortOn=xlSortOnValues, Order=xlDescending)
        Sheet18.Sort.SetRange(Range('A' + u + ':R' + l))
        Sheet18.Sort.Header = xlNo
        Sheet18.Sort.Apply()


# ===== Module: Sheet19 =====

def Sheet19_MemberCheck():
    Ws19 = None
    Ws10 = None
    last = None
    trun = None
    Life = None
    fy = None
    str = None
    totalEr = None
    totalSan = None
    targetCount2 = None
    targetCount3 = None
    totalYi = None
    totalSi = None
    totalWu = None
    modifiedCount2 = None
    modifiedCount3 = None
    Jt = None
    R = None
    js = None
    Dic2 = None
    Dic3 = None
    Arr2 = None
    Arr3 = None
    n2 = None
    n3 = None
    Dic2 = create_object('scripting.dictionary')
    Dic3 = create_object('scripting.dictionary')
    ws1 = Sheet1
    Ws10 = Sheet10
    Ws19 = Sheet19
    Arr2 = vba_redim(None, [(1, 2), (1, 1)], preserve=False)
    Arr3 = vba_redim(None, [(1, 2), (1, 1)], preserve=False)
    if True:  # with Ws19
        pass
        # VBA: Ws19.Range("A2:G100000").Clear
    Application.ScreenUpdating = False
    last = Ws10.Cells(20000, 1).End(xlUp).Row
    fy = Sheet1.Cells(48, 2)
    Life = Sheet1.Cells(49, 2)
    trun = (Life - fy) / 5 + 1
    R = 1
    if True:  # with Ws19
        totalYi = 0
        totalEr = 0
        totalSan = 0
        totalSi = 0
        totalWu = 0
        for i in vba_for_range(3, last, 1):
            if Ws10.Cells(i, 11) == '二':
                totalEr = totalEr + 1
            elif Ws10.Cells(i, 11) == '三':
                totalSan = totalSan + 1
            elif Ws10.Cells(i, 11) == '四':
                totalSi = totalSi + 1
            elif Ws10.Cells(i, 11) == '五':
                totalWu = totalWu + 1
            elif Ws10.Cells(i, 11) == '一':
                totalYi = totalYi + 1
        targetCount2 = Int(totalEr * 0.2)
        targetCount3 = Int(totalSan * 0.2)
        for Y in vba_for_range(1, trun, 1):
            if Y == 1:
                str = '当前'
            else:
                str = '第' + (Y - 1) * 5 + '年'
            modifiedCount2 = 0
            modifiedCount3 = 0
            # VBA: Randomize
            js = 0
            for i in vba_for_range(3, last, 1):
                R = R + 1
                js = js + 1
                vb_assign('Ws19.Cells(R, 1)', Ws10.Cells(i, 1))
                vb_assign('Ws19.Cells(R, 2)', Ws10.Cells(i, 2))
                vb_assign('Ws19.Cells(R, 3)', Ws10.Cells(i, 3))
                vb_assign('Ws19.Cells(R, 4)', Ws10.Cells(i, 4))
                vb_assign('Ws19.Cells(R, 5)', Ws10.Cells(i, 11))
                vb_assign('Ws19.Cells(R, 7)', str)
                gl = None
                # select case Y
                if (Y == 1):
                    gl = 0.2
                elif (Y == 2):
                    gl = 0.25
                elif (Y == 3):
                    gl = 0.34
                elif (Y == 4):
                    gl = 0.5
                elif (Y > 4):
                    gl = 1
                if Ws10.Cells(i, 11) == '二':
                    randomNum = Rnd()
                    Jt = Ws10.Cells(i, 1) + Ws10.Cells(i, 2)
                    if modifiedCount2 < targetCount2:
                        if not Dic2.exists(Jt):
                            if randomNum <= gl:
                                vb_assign('Ws19.Cells(R, 6)', 'IV')
                                modifiedCount2 = modifiedCount2 + 1
                                n2 = n2 + 1
                                Arr2 = vba_redim(Arr2, [(1, 2), (1, n2)], preserve=True)
                                vb_assign('Arr2(1, n2)', Jt)
                                vb_assign('Arr2(2, n2)', Y)
                            else:
                                vb_assign('Ws19.Cells(R, 6)', 'III')
                        else:
                            vb_assign('Ws19.Cells(R, 6)', 'III')
                    else:
                        vb_assign('Ws19.Cells(R, 6)', 'III')
                elif Ws10.Cells(i, 11) == '三':
                    randomNum = Rnd()
                    Jt = Ws10.Cells(i, 1) + Ws10.Cells(i, 2)
                    if modifiedCount3 < targetCount3:
                        if not Dic3.exists(Jt):
                            if randomNum <= gl:
                                vb_assign('Ws19.Cells(R, 6)', 'III')
                                modifiedCount3 = modifiedCount3 + 1
                                n3 = n3 + 1
                                Arr3 = vba_redim(Arr3, [(1, 2), (1, n3)], preserve=True)
                                vb_assign('Arr3(1, n3)', Jt)
                                vb_assign('Arr3(2, n3)', Y)
                            else:
                                vb_assign('Ws19.Cells(R, 6)', 'II  ')
                        else:
                            vb_assign('Ws19.Cells(R, 6)', 'II')
                    else:
                        vb_assign('Ws19.Cells(R, 6)', 'II')
                elif Ws10.Cells(i, 11) == '一':
                    vb_assign('Ws19.Cells(R, 6)', 'IV')
                elif Ws10.Cells(i, 11) == '四' or Ws10.Cells(i, 11) == '五':
                    vb_assign('Ws19.Cells(R, 6)', 'II')
                elif Ws10.Cells(i, 11) == '':
                    break
            Sheet19_快速排序(R - js, R)
            Dic2.RemoveAll()
            Dic3.RemoveAll()
            for j in vba_for_range(vba_lbound(Arr2, 2), vba_ubound(Arr2, 2), 1):
                if Arr2(2, j) > Y - 4:
                    vb_assign('Dic2.Item(Arr2(1, j))', Y)
            for j in vba_for_range(vba_lbound(Arr3, 2), vba_ubound(Arr3, 2), 1):
                if Arr3(2, j) > Y - 4:
                    vb_assign('Dic3.Item(Arr3(1, j))', Y)
    if True:  # with ws1
        vb_assign('ws1.Cells(135, 2)', totalYi)
        vb_assign('ws1.Cells(135, 5)', totalYi)
        vb_assign('ws1.Cells(136, 2)', totalEr)
        vb_assign('ws1.Cells(136, 5)', modifiedCount2)
        vb_assign('ws1.Cells(136, 4)', totalEr - modifiedCount2)
        vb_assign('ws1.Cells(137, 2)', totalSan)
        vb_assign('ws1.Cells(137, 4)', modifiedCount3)
        vb_assign('ws1.Cells(137, 3)', totalSan - modifiedCount3)
        vb_assign('ws1.Cells(138, 2)', totalSi)
        vb_assign('ws1.Cells(138, 3)', totalSi)
        vb_assign('ws1.Cells(139, 2)', totalWu)
        vb_assign('ws1.Cells(139, 3)', totalWu)
    msg_box('检验策略已生成')
    Application.ScreenUpdating = True

def Sheet19_快速排序(u, l):
    if True:  # with Sheet19.Sort
        Sheet19.Sort.SortFields.Clear()
        Sheet19.Sort.SortFields.Add(Key=Range('F' + u + ':F' + l), SortOn=xlSortOnValues, Order=xlDescending)
        Sheet19.Sort.SetRange(Range('A' + u + ':G' + l))
        Sheet19.Sort.Header = xlNo
        Sheet19.Sort.Apply()


# ===== Module: Sheet2 =====
UpdateByChange = None

def Sheet2_RunSQLAgainstSheet():
    UpdateByChange = False
    # VBA: Sheet1.Range("B16:AZ18").ClearContents
    conn = None
    rs = None
    strConn = None
    strSQL = None
    conn = create_object('ADODB.Connection')
    rs = create_object('ADODB.Recordset')
    strConn = 'Provider=Microsoft.ACE.OLEDB.12.0;' + 'Data Source=' + ThisWorkbook.FullName + ';' + 'Extended Properties="Excel 12.0;HDR=Yes;";'
    conn.Open(strConn)
    strSQL = 'SELECT Z, Count(*) as Occurrence FROM [Joints$] ' + 'Group By Z HAVING COUNT(*)>' + Sheet1.Cells(14, 8) + ' ' + 'ORDER BY Z DESC'
    rs.Open(strSQL, conn)
    rs_i = 0
    while not rs.EOF:
        vb_assign('Sheet1.Cells(16, rs_i + 2)', rs.Fields('Z').Value)
        vb_assign('Sheet1.Cells(17, rs_i + 2)', rs.Fields('Occurrence').Value)
        rs.MoveNext()
        rs_i = rs_i + 1
    Debug.Print('记录数量：' + rs_i)
    k = 1
    rs.Close()
    rs = None
    conn.Close()
    conn = None
    for i in vba_for_range(2, 21, 1):
        if Sheet1.Cells(17, i) != '':
            vb_assign('Sheet1.Cells(18, i)', '√')
            k = i
    UpdateByChange = True
    vb_assign('Sheet1.Cells(18, k)', '√')

def Sheet2_JointTYPE():
    El = None
    last = None
    Application.ScreenUpdating = False
    El = Sheet1.Cells(8, 2)
    last = Sheet2.Cells(100000, 1).End(xlUp).Row
    if True:  # with Sheet2
        # VBA: Sheet2.Range("E2:E" & last).ClearContents
        for i in vba_for_range(3, last, 1):
            if Sheet2.Cells(i, 4) < El:
                A = Sheet2.Cells(i, 1)
                if vb_like(A, '*L'):
                    vb_assign('Sheet2.Cells(i, 5)', 'LegJoint')
                elif vb_like(A, '*X'):
                    vb_assign('Sheet2.Cells(i, 5)', 'X Joint')
                elif A == '':
                    break
    Application.ScreenUpdating = True
    msg_box('DONE')


# ===== Module: Sheet3 =====

def Sheet3_MemberTYPE():
    A = None
    B = None
    El = None
    last = None
    El = Sheet1.Cells(8, 2)
    last = Sheet3.Cells(100000, 1).End(xlUp).Row
    if True:  # with Sheet3
        # VBA: Sheet3.Range("E2:E" & last).ClearContents
        for i in vba_for_range(2, last, 1):
            A = Sheet3.Cells(i, 1)
            B = Sheet3.Cells(i, 2)
            if Sheet3.Cells(i, 6) < El and Sheet3.Cells(i, 7) < El:
                if vb_like(A, '*L') and vb_like(B, '*L'):
                    if vb_mid(A, len(A) - 1, 1) == vb_mid(B, len(B) - 1, 1):
                        vb_assign('Sheet3.Cells(i, 5)', 'LEG')
                elif vb_like(A, 'P*') and vb_like(B, 'P*'):
                    if (not vb_like(A, 'P#8#')) and (not vb_like(A, 'P#9#')) and (not vb_like(B, 'P#8#')) and (not vb_like(B, 'P#9#')):
                        vb_assign('Sheet3.Cells(i, 5)', 'LEG')
                elif vb_like(B, '*X'):
                    if (not vb_like(A, '#12L')) and (not vb_like(A, '#13L')) and (not vb_like(A, '16#L')):
                        vb_assign('Sheet3.Cells(i, 5)', 'X-Brace')
                elif vb_like(A, '*X'):
                    if (not vb_like(B, '#12L')) and (not vb_like(B, '#13L')) and (not vb_like(B, '16#L')):
                        vb_assign('Sheet3.Cells(i, 5)', 'X-Brace')
    msg_box('done')


# ===== Module: Sheet4 =====


# ===== Module: Sheet5 =====

def Sheet5_ParseCollapseAnalysis():
    ws = None
    FilePath = None
    fileContent = None
    lines = None
    i = None
    outputRow = None
    loadFactor = None
    lastLoadFactor = None
    jointInfo = None
    memberInfo = None
    ws = ThisWorkbook.Sheets('倒塌分析结果')
    ws.Activate()
    ActiveWindow.FreezePanes = False
    # VBA: ws.Range("F2:F13").ClearContents
    i = ws.UsedRange.Rows.Count
    # VBA: ws.Rows("15:" & i).Delete
    vb_assign('ws.Range("A15:E15")', vb_array('LOADID', 'TYPE', 'LOCATION', 'FACTOR', 'REMARK'))
    outputRow = 16
    for f_i in vba_for_range(2, 13, 1):
        FilePath = ws.Cells(f_i, 2)
        if vb_trim(FilePath) != '':
            vb_open_input(1, FilePath)
            fileContent = vb_input(vb_lof(1), 1)
            vb_file_close(1)
            lines = vb_split(fileContent, vbCrLf)
            Application.ScreenUpdating = False
            for i in vba_for_range(0, vba_ubound(lines), 1):
                currentLine = None
                currentLine = vb_trim(lines(i))
                if vb_isnumeric(vb_left(currentLine, 2)):
                    parts = None
                    parts = vb_split(vb_trim(currentLine), ' ')
                    if vba_ubound(parts) >= 4:
                        lastLoadFactor = vb_mid(lines(i), 25, 5)
                if vb_left(currentLine, len('*** WARNING - JOINT')) == '*** WARNING - JOINT':
                    jointInfo = vb_mid(currentLine, vb_instr(currentLine, 'AT JOINT') + 9)
                    jointInfo = vb_left(jointInfo, vb_instr(jointInfo, ' ') - 1)
                    vb_assign('ws.Cells(outputRow, 1)', f_i - 1)
                    vb_assign('ws.Cells(outputRow, 2)', '节点失效')
                    vb_assign('ws.Cells(outputRow, 3)', jointInfo)
                    vb_assign('ws.Cells(outputRow, 4)', lastLoadFactor)
                    remarkinof = vb_mid(currentLine, vb_instr(currentLine, 'FOR BRACE'))
                    vb_assign('ws.Cells(outputRow, 5)', vb_left(remarkinof, vb_instr(remarkinof, ' AT LOAD')))
                    outputRow = outputRow + 1
                if vb_left(currentLine, len('*** MEMBER')) == '*** MEMBER':
                    memberInfo = vb_mid(currentLine, vb_instr(currentLine, 'MEMBER') + 7)
                    memberInfo = vb_left(memberInfo, vb_instr(memberInfo, ' HAS') - 1)
                    vb_assign('ws.Cells(outputRow, 1)', f_i - 1)
                    vb_assign('ws.Cells(outputRow, 2)', '构件失效')
                    vb_assign('ws.Cells(outputRow, 3)', memberInfo)
                    vb_assign('ws.Cells(outputRow, 4)', lastLoadFactor)
                    vb_assign('ws.Cells(outputRow, 5)', vb_mid(currentLine, vb_instr(currentLine, 'AT SEGMENT')))
                    outputRow = outputRow + 1
            vb_assign('ws.Cells(f_i, 6)', lastLoadFactor)
    if True:  # with ws
        # VBA: ws.Columns("A:D").AutoFit
        vb_assign('ws.Rows(15).Font.Bold', True)
        vb_assign('ws.ListObjects.Add(xlSrcRange, ws.Range("A15:E" & outputRow - 1), , xlYes).Name', 'AnalysisTable')
    # VBA: Range("A16").Select
    ActiveWindow.FreezePanes = True
    Sheet1.Activate()
    Application.ScreenUpdating = True
    msg_box('解析完成！共处理' + outputRow - 15 + '条失效记录', vbInformation)
    return
    # VBA: errOut
    A = 1


# ===== Module: Sheet6 =====


# ===== Module: Sheet7 =====


# ===== Module: Sheet8 =====

def Sheet8_FatiguePickup():
    FilePath = None
    TextLine = None
    bReportSection = None
    JointNum = None
    CHD = None
    BRC = None
    TotalDamage = None
    ws = None
    ws1 = None
    RowCount = None
    i = None
    trun = None
    cl = None
    Jck = None
    ky = None
    Rng = None
    Dic = None
    Dic2 = None
    Dic_FT = None
    arrValues = None
    Aaas = None
    CP = None
    Arr = None
    ARR1 = None
    str = None
    Item_Arr = None
    Factor = None
    ARR1 = vba_redim(None, [(1, 20), (1, 1)], preserve=False)
    Dic = create_object('scripting.dictionary')
    Dic2 = create_object('scripting.dictionary')
    Dic_FT = create_object('scripting.dictionary')
    ws = ThisWorkbook.Sheets('疲劳分析结果')
    i = ws.UsedRange.Rows.Count
    ws.Activate()
    ActiveWindow.FreezePanes = False
    if i >= 5:
        pass
        # VBA: ws.Rows("5:" & i).Delete
    RowCount = 1
    Rng = Sheet1.Range('b39:h39')
    for FilePath in Rng:
        if FilePath != '':
            if vb_dir(FilePath) == '':
                msg_box(FilePath + '不存在')
                return
            Brace_Data = True
            vb_open_input(1, FilePath)
            fileContent = vb_input(vb_lof(1), 1)
            vb_file_close(1)
            lines = None
            lines = vb_split(fileContent, vbCrLf)
            cl = 12 + trun * 4
            trun = trun + 1
            Dic.RemoveAll()
            Dic2.RemoveAll()
            Dic_FT.RemoveAll()
            CP = ''
            ws1 = ThisWorkbook.Sheets('控制页面')
            for i in vba_for_range(38, 300, 1):
                if True:  # with ws1
                    if vb_trim(ws1.Cells(i, cl)) == '':
                        break
                    if vb_trim(ws1.Cells(i, cl)) != '':
                        Dic_FT.Add(ws1.Cells(i, cl), ws1.Cells(i, cl + 1))
            if trun != 1:
                for i in vba_for_range(38, 300, 1):
                    if True:  # with ws1
                        if vb_trim(ws1.Cells(i, cl + 2)) != '':
                            ky = ws1.Cells(i, cl + 2) + ws1.Cells(i, cl + 3)
                            Dic.Add(ky, ky)
                        if vb_trim(ws1.Cells(i, cl + 2)) == '':
                            break
            for i in vba_for_range(0, vba_ubound(lines), 1):
                Factor = Sheet1.Cells(38, 1 + trun)
                TextLine = lines(i)
                if vb_instr(TextLine, ' *  *  *  M E M B E R  F A T I G U E  R E P O R T  *  *  *') > 0:
                    break
                if trun == 1:
                    if vb_instr(TextLine, '* *  M E M B E R  F A T I G U E  D E T A I L  R E P O R T  * *') > 0:
                        bReportSection = True
                    if bReportSection:
                        if vb_trim(vb_left(TextLine, 4)) != '' and vb_instr(TextLine, '*') == 0:
                            if Brace_Data:
                                JointNum = str(vb_mid(TextLine, 1, 4))
                                BRC = str(vb_mid(TextLine, 12, 4))
                            else:
                                chd_a = str(vb_mid(TextLine, 7, 4))
                                chd_b = str(vb_mid(TextLine, 12, 4))
                        if vb_instr(TextLine, '*** TOTAL DAMAGE ***') > 0:
                            arrValues = vb_split(Application.WorksheetFunction.vb_trim(Replace(TextLine, '***', '')), ' ')
                            TotalDamage = vba_redim(None, [(1, 8)], preserve=False)
                            k = 1
                            for j in vba_for_range(1, 8, 1):
                                if j <= vba_ubound(arrValues) + 1:
                                    vb_assign('TotalDamage(j)', Sheet8_ExtractScientificNumber(arrValues(j + 1)))
                                else:
                                    vb_assign('TotalDamage(j)', 0)
                            if Brace_Data:
                                ARR1 = vba_redim(ARR1, [(1, 20), (1, RowCount)], preserve=True)
                                vb_assign('ARR1(1, RowCount)', JointNum)
                                vb_assign('ARR1(4, RowCount)', BRC)
                            else:
                                vb_assign('ARR1(2, RowCount)', chd_a)
                                vb_assign('ARR1(3, RowCount)', chd_b)
                            if Dic_FT.exists(JointNum):
                                Factor = Dic_FT.Item(JointNum)
                            k = 0
                            if not Brace_Data:
                                k = k + 8
                            for j in vba_for_range(4, 11, 1):
                                vb_assign('ARR1(j + k + 1, RowCount)', TotalDamage(j - 3) / Factor)
                            if not Brace_Data:
                                RowCount = RowCount + 1
                            Brace_Data = not Brace_Data
                else:
                    if vb_instr(TextLine, '* *  M E M B E R  F A T I G U E  D E T A I L  R E P O R T  * *') > 0:
                        bReportSection = True
                    Aaas = vb_left(TextLine, 4) + vb_mid(TextLine, 12, 4)
                    if CP != Aaas and Aaas != '':
                        if Dic.exists(Aaas) and bReportSection:
                            CP = Dic.Item(Aaas)
                            Jck = True
                            Arr = vba_redim(None, [(1, 20)], preserve=False)
                    if bReportSection and Jck:
                        if vb_mid(TextLine, 4, 20) == '*** TOTAL DAMAGE ***':
                            ch = ch + 1
                        if ch == 2:
                            ch = 0
                            Jck = False
                        if vb_trim(vb_left(TextLine, 4)) != '' and vb_instr(TextLine, '*') == 0:
                            if Brace_Data:
                                JointNum = str(vb_mid(TextLine, 1, 4))
                                BRC = str(vb_mid(TextLine, 12, 4))
                            else:
                                chd_a = str(vb_mid(TextLine, 7, 4))
                                chd_b = str(vb_mid(TextLine, 12, 4))
                        if vb_instr(TextLine, '*** TOTAL DAMAGE ***') > 0:
                            arrValues = vb_split(Application.WorksheetFunction.vb_trim(Replace(TextLine, '***', '')), ' ')
                            TotalDamage = vba_redim(None, [(1, 8)], preserve=False)
                            k = 1
                            for j in vba_for_range(1, 8, 1):
                                if j <= vba_ubound(arrValues) + 1:
                                    vb_assign('TotalDamage(j)', Sheet8_ExtractScientificNumber(arrValues(j + 1)))
                                else:
                                    vb_assign('TotalDamage(j)', 0)
                            if Brace_Data:
                                vb_assign('Arr(1)', JointNum)
                                vb_assign('Arr(4)', BRC)
                            else:
                                vb_assign('Arr(2)', chd_a)
                                vb_assign('Arr(3)', chd_b)
                            if Dic_FT.exists(JointNum):
                                Factor = Dic_FT.Item(JointNum)
                            k = 0
                            if not Brace_Data:
                                k = k + 8
                            for j in vba_for_range(4, 11, 1):
                                vb_assign('Arr(j + k + 1)', TotalDamage(j - 3) / Factor)
                            if Brace_Data == False:
                                ky2 = JointNum + chd_a + chd_b + BRC
                                Dic2.Add(ky2, Arr)
                            Brace_Data = not Brace_Data
        if trun > 1:
            for jj in vba_for_range(vba_lbound(ARR1, 2), vba_ubound(ARR1, 2), 1):
                str = ARR1(1, jj) + ARR1(2, jj) + ARR1(3, jj) + ARR1(4, jj)
                if Dic2.exists(str):
                    Item_Arr = Dic2.Item(str)
                    for ii in vba_for_range(5, 20, 1):
                        vb_assign('ARR1(ii, jj)', Item_Arr(ii))
    fileContent = ''
    ARR1 = Application.WorksheetFunction.Transpose(ARR1)
    vb_assign('ws.Range("A5").Resize(UBound(ARR1), 20)', ARR1)
    Application.ScreenUpdating = FLASE
    if True:  # with ws
        LastRow = None
        LastRow = ws.Cells(ws.Rows.Count, 1).End(xlUp).Row
        if LastRow > 1:
            currentColor = None
            previousJoint = None
            colorSwitch = None
            currentColor = RGB(197, 217, 241)
            colorSwitch = True
            for i in vba_for_range(5, LastRow, 1):
                if ws.Cells(i, 1).Value != previousJoint:
                    colorSwitch = not colorSwitch
                    previousJoint = ws.Cells(i, 1).Value
                if colorSwitch:
                    currentColor = RGB(197, 217, 241)
                else:
                    currentColor = RGB(255, 255, 255)
                vb_assign('ws.Range("A" & i & ":T" & i).Interior.Color', currentColor)
        if True:  # with ws.Range('A1:T' + LastRow).Borders
            pass
            # VBA: ws.Range(
            # VBA: ws.Range(
    msg_box('疲劳数据提取完成')
    Application.ScreenUpdating = True

def Sheet8_Ringmember():
    path2 = None
    fileContent = None
    Jt = None
    ws = None
    lines = None
    First = None
    Insect = None
    Dic = None
    trun = None
    CK = None
    Rw = None
    R = None
    ws = ThisWorkbook.Sheets('控制页面')
    cl = 12
    Dic = create_object('scripting.dictionary')
    # VBA: Sheet1.Range("L38:AO500").Clear
    # VBA: Sheet1.Range("B38:H38").ClearContents
    First = True
    for j in vba_for_range(2, 9, 1):
        Rw = 38
        R = 38
        trun = 0
        path2 = ws.Cells(40, j)
        if path2 == '':
            break
        if vb_dir(path2) == '':
            msg_box(path2 + '不存在')
            return
        # On Error Resume Next
        vb_open_input(5, path2)
        fileContent = vb_input(vb_lof(5), 5)
        vb_file_close(5)
        lines = vb_split(fileContent, vbCrLf)
        if True:  # with ws
            vb_assign('ws.Cells(36, cl)', vb_mid(path2, InStrRev(path2, '\\') + 1, 100))
            vb_assign('ws.Cells(37, cl)', 'JOINT')
            vb_assign('ws.Cells(37, cl + 1)', 'FACTOR')
            vb_assign('ws.Cells(37, cl + 2)', '节点')
            vb_assign('ws.Cells(37, cl + 3)', '撑杆')
            Dic.RemoveAll()
            n = 0
            Insect = True
            for i in vba_for_range(vba_lbound(lines), vba_ubound(lines), 1):
                if vb_left(lines(i), 6) == 'CONRST':
                    Jt = vb_trim(vb_mid(lines(i), 16, 4))
                    if not Dic.exists(Jt):
                        Dic.Add(Jt, Jt)
                    vb_assign('ws.Cells(Rw, cl + 2)', Jt)
                    if vb_mid(lines(i), 8, 4) != Jt:
                        vb_assign('ws.Cells(Rw, cl + 3)', vb_trim(vb_mid(lines(i), 8, 4)))
                    else:
                        vb_assign('ws.Cells(Rw, cl + 3)', vb_trim(vb_mid(lines(i), 12, 4)))
                    Rw = Rw + 1
                elif vb_left(lines(i), 6) == 'CONSCF':
                    vb_assign('ws.Cells(Rw, cl + 2)', vb_trim(vb_mid(lines(i), 16, 4)))
                    vb_assign('ws.Cells(Rw, cl + 3)', vb_trim(vb_mid(lines(i), 12, 4)))
                    Rw = Rw + 1
                    if not Dic.exists(Jt):
                        Dic.Add(Jt, Jt)
                elif vb_left(lines(i), 4) == 'JSLC':
                    for ii in vba_for_range(1, 100, 1):
                        Jt = vb_trim(vb_mid(lines(i), 7 + trun * 4, 4))
                        if Jt == '':
                            break
                        if not Dic.exists(Jt):
                            vb_assign('ws.Cells(Rw + n, cl + 2)', Jt)
                            vb_assign('ws.Cells(Rw + n, cl + 3).Interior.Color', RGB(255, 0, 0))
                            CK = True
                            n = n + 1
                        trun = trun + 1
                elif Insect and vb_left(lines(i), 5) == 'FTOPT':
                    vb_assign('ws.Cells(38, j)', vb_trim(vb_mid(lines(i), 22, 7)))
                    Insect = False
                elif vb_left(lines(i), 6) == 'JNTOVR':
                    if vb_mid(lines(i), 8, 4) != '':
                        vb_assign('ws.Cells(R, cl)', vb_mid(lines(i), 8, 4))
                        vb_assign('ws.Cells(R, cl + 1)', vb_mid(lines(i), 38, 6))
                        R = R + 1
                elif vb_left(lines(i), 6) == 'FTCASE':
                    break
    cl = cl + 4
    if CK:
        msg_box('请检查O、Q、S等列在38行后是否有撑杆未填入，以标红，请手动填入')
    msg_box('完成')

def Sheet8_ExtractScientificNumber(str):
    _return_value = None
    str = Replace(str, 'E', 'D')
    # On Error Resume Next
    _return_value = float(vb_trim(str))
    return _return_value


# ===== Module: Sheet9 =====


# ===== Module: ThisWorkbook =====


class WellSlot:
    def __init__(self) -> None:
        self.CX = None
        self.CY = None
        self.CZ = None
        self.Condutor_OD = None
        self.Condutor_WT = None
        self.Support_OD = None
        self.Support_WT = None
        self.Top_F = None
        self.Elevation_Array = None
        self.Group_Array = None
        self.Member_Array = None
        self.C_Joints_Array = None
        self.W_Joints_Array = None

    def Initialize(self, R):
        self.CX = Sheet1.Cells(R, 2)
        self.CY = Sheet1.Cells(R, 3)
        self.CZ = Sheet1.Cells(6, 2) - 6 * Sheet1.Cells(R, 4) / 1000
        self.Condutor_OD = Sheet1.Cells(R, 4)
        self.Condutor_WT = Sheet1.Cells(R, 5)
        self.Support_OD = Sheet1.Cells(R, 6)
        self.Support_WT = Sheet1.Cells(R, 7)
        self.Top_F = Sheet1.Cells(R, 8)
        myElevation = None
        i = 1
        for C in vba_for_range(9, 28, 1):
            if Sheet1.Cells(23, C) != '':
                myElevation = vba_redim(myElevation, [(1, i)], preserve=True)
                vb_assign('myElevation(i)', Elevation())
                vb_assign('myElevation(i).Z', float(Sheet1.Cells(23, C)))
                vb_assign('myElevation(i).Connection', Sheet1.Cells(R, C))
                i = i + 1
        self.Elevation_Array = myElevation

    def CreateModel(self):
        NewGroup = None
        vb_assign('NewGroup(1)', Group())
        vb_assign('NewGroup(1).ID', Get_ID_Available(TableName='Groups', FieldName='Group', FirstLetter='CN', width=3))
        vb_assign('NewGroup(1).OD', self.Condutor_OD)
        vb_assign('NewGroup(1).WT', self.Condutor_WT)
        vb_assign('NewGroup(1).Skip', True)
        G_n = Sheet4.Cells(Sheet4.Rows.Count, 'A').End(xlUp).Row
        G_n = G_n + 1
        vb_assign('Sheet4.Cells(G_n, 1)', NewGroup(1).ID)
        vb_assign('Sheet4.Cells(G_n, 2)', NewGroup(1).OD)
        vb_assign('Sheet4.Cells(G_n, 3)', 'New')
        vb_assign('NewGroup(2)', Group())
        vb_assign('NewGroup(2).ID', Get_ID_Available(TableName='Groups', FieldName='Group', FirstLetter='CN', width=3))
        vb_assign('NewGroup(2).OD', self.Support_OD)
        vb_assign('NewGroup(2).WT', self.Support_WT)
        vb_assign('NewGroup(2).Skip', True)
        G_n = Sheet4.Cells(Sheet4.Rows.Count, 'A').End(xlUp).Row
        G_n = G_n + 1
        vb_assign('Sheet4.Cells(G_n, 1)', NewGroup(2).ID)
        vb_assign('Sheet4.Cells(G_n, 2)', NewGroup(2).OD)
        vb_assign('Sheet4.Cells(G_n, 3)', 'New')
        vb_assign('NewGroup(3)', Group())
        vb_assign('NewGroup(3).ID', Get_ID_Available(TableName='Groups', FieldName='Group', FirstLetter='WB', width=3))
        vb_assign('NewGroup(3).OD', self.Condutor_OD)
        vb_assign('NewGroup(3).WT', self.Condutor_WT)
        vb_assign('NewGroup(3).Skip', True)
        G_n = Sheet4.Cells(Sheet4.Rows.Count, 'A').End(xlUp).Row
        G_n = G_n + 1
        vb_assign('Sheet4.Cells(G_n, 1)', NewGroup(3).ID)
        vb_assign('Sheet4.Cells(G_n, 2)', NewGroup(3).OD)
        vb_assign('Sheet4.Cells(G_n, 3)', 'New')
        self.Group_Array = NewGroup
        Conducter_Joints = None
        Wb_Joints = None
        Model_Members = None
        J_n = 0
        M_n = 0
        W_n = 0
        J_n = J_n + 1
        Conducter_Joints = vba_redim(Conducter_Joints, [(1, J_n)], preserve=True)
        vb_assign('Conducter_Joints(J_n)', Joint())
        vb_assign('Conducter_Joints(J_n).ID', Get_ID_Available(TableName='Joints', FieldName='Joint', FirstLetter='CN'))
        vb_assign('Conducter_Joints(J_n).X', self.CX)
        vb_assign('Conducter_Joints(J_n).Y', self.CY)
        vb_assign('Conducter_Joints(J_n).Z', self.CZ)
        r_J = Sheet2.Cells(Sheet2.Rows.Count, 'A').End(xlUp).Row
        r_J = r_J + 1
        vb_assign('Sheet2.Cells(r_J, 1)', Conducter_Joints(J_n).ID)
        vb_assign('Sheet2.Cells(r_J, 2)', Conducter_Joints(J_n).X)
        vb_assign('Sheet2.Cells(r_J, 3)', Conducter_Joints(J_n).Y)
        vb_assign('Sheet2.Cells(r_J, 4)', Conducter_Joints(J_n).Z)
        vb_assign('Sheet2.Cells(r_J, 5)', 'New')
        for i in vba_for_range(vba_ubound(self.Elevation_Array), vba_lbound(self.Elevation_Array), -1):
            J_n = J_n + 1
            Conducter_Joints = vba_redim(Conducter_Joints, [(1, J_n)], preserve=True)
            vb_assign('Conducter_Joints(J_n)', Joint())
            vb_assign('Conducter_Joints(J_n).ID', Get_ID_Available(TableName='Joints', FieldName='Joint', FirstLetter='CN'))
            vb_assign('Conducter_Joints(J_n).X', self.CX)
            vb_assign('Conducter_Joints(J_n).Y', self.CY)
            vb_assign('Conducter_Joints(J_n).Z', self.Elevation_Array(i).Z)
            r_J = Sheet2.Cells(Sheet2.Rows.Count, 'A').End(xlUp).Row
            r_J = r_J + 1
            vb_assign('Sheet2.Cells(r_J, 1)', Conducter_Joints(J_n).ID)
            vb_assign('Sheet2.Cells(r_J, 2)', Conducter_Joints(J_n).X)
            vb_assign('Sheet2.Cells(r_J, 3)', Conducter_Joints(J_n).Y)
            vb_assign('Sheet2.Cells(r_J, 4)', Conducter_Joints(J_n).Z)
            vb_assign('Sheet2.Cells(r_J, 5)', 'New')
            M_n = M_n + 1
            Model_Members = vba_redim(Model_Members, [(1, M_n)], preserve=True)
            vb_assign('Model_Members(M_n)', Member())
            vb_assign('Model_Members(M_n).Joint_A', Conducter_Joints(J_n - 1))
            vb_assign('Model_Members(M_n).Joint_B', Conducter_Joints(J_n))
            vb_assign('Model_Members(M_n).MemberGroup', NewGroup(1))
            vb_assign('Model_Members(M_n).A_Offset', Joint_Offset())
            vb_assign('Model_Members(M_n).A_Offset.Off_X', 0)
            vb_assign('Model_Members(M_n).A_Offset.Off_Y', 0)
            vb_assign('Model_Members(M_n).A_Offset.Off_Z', 0)
            vb_assign('Model_Members(M_n).B_Offset', Joint_Offset())
            vb_assign('Model_Members(M_n).B_Offset.Off_X', 0)
            vb_assign('Model_Members(M_n).B_Offset.Off_Y', 0)
            vb_assign('Model_Members(M_n).B_Offset.Off_Z', 0)
            r_M = Sheet3.Cells(Sheet3.Rows.Count, 'A').End(xlUp).Row
            r_M = r_M + 1
            vb_assign('Sheet3.Cells(r_M, 1)', Model_Members(M_n).Joint_A.ID)
            vb_assign('Sheet3.Cells(r_M, 2)', Model_Members(M_n).Joint_B.ID)
            vb_assign('Sheet3.Cells(r_M, 3)', Model_Members(M_n).MemberGroup.ID)
            vb_assign('Sheet3.Cells(r_M, 4)', 'New')
            ClosetJoint = Joint()
            ClosetJoint = self.Get_Closet_Joint(Conducter_Joints(J_n))
            # select case self.Elevation_Array(i).Connection
            if (self.Elevation_Array(i).Connection == '导向连接'):
                W_n = W_n + 1
                Wb_Joints = vba_redim(Wb_Joints, [(1, W_n)], preserve=True)
                vb_assign('Wb_Joints(W_n)', Joint())
                vb_assign('Wb_Joints(W_n).ID', Get_ID_Available(TableName='Joints', FieldName='Joint', FirstLetter='CN'))
                vb_assign('Wb_Joints(W_n).X', self.CX)
                vb_assign('Wb_Joints(W_n).Y', self.CY)
                vb_assign('Wb_Joints(W_n).Z', self.Elevation_Array(i).Z)
                r_J = Sheet2.Cells(Sheet2.Rows.Count, 'A').End(xlUp).Row
                r_J = r_J + 1
                vb_assign('Sheet2.Cells(r_J, 1)', Wb_Joints(W_n).ID)
                vb_assign('Sheet2.Cells(r_J, 2)', Wb_Joints(W_n).X)
                vb_assign('Sheet2.Cells(r_J, 3)', Wb_Joints(W_n).Y)
                vb_assign('Sheet2.Cells(r_J, 4)', Wb_Joints(W_n).Z)
                vb_assign('Sheet2.Cells(r_J, 5)', 'New')
                M_n = M_n + 1
                Model_Members = vba_redim(Model_Members, [(1, M_n)], preserve=True)
                vb_assign('Model_Members(M_n)', Member())
                vb_assign('Model_Members(M_n).Joint_A', Conducter_Joints(J_n))
                vb_assign('Model_Members(M_n).Joint_B', Wb_Joints(W_n))
                vb_assign('Model_Members(M_n).MemberGroup', NewGroup(3))
                vb_assign('Model_Members(M_n).A_Offset', Joint_Offset())
                vb_assign('Model_Members(M_n).A_Offset.Off_X', 0)
                vb_assign('Model_Members(M_n).A_Offset.Off_Y', 0)
                vb_assign('Model_Members(M_n).A_Offset.Off_Z', NewGroup(3).OD)
                vb_assign('Model_Members(M_n).B_Offset', Joint_Offset())
                vb_assign('Model_Members(M_n).B_Offset.Off_X', 0)
                vb_assign('Model_Members(M_n).B_Offset.Off_Y', 0)
                vb_assign('Model_Members(M_n).B_Offset.Off_Z', 0)
                r_M = Sheet3.Cells(Sheet3.Rows.Count, 'A').End(xlUp).Row
                r_M = r_M + 1
                vb_assign('Sheet3.Cells(r_M, 1)', Model_Members(M_n).Joint_A.ID)
                vb_assign('Sheet3.Cells(r_M, 2)', Model_Members(M_n).Joint_B.ID)
                vb_assign('Sheet3.Cells(r_M, 3)', Model_Members(M_n).MemberGroup.ID)
                vb_assign('Sheet3.Cells(r_M, 4)', 'New')
                M_n = M_n + 1
                Model_Members = vba_redim(Model_Members, [(1, M_n)], preserve=True)
                vb_assign('Model_Members(M_n)', Member())
                vb_assign('Model_Members(M_n).Joint_A', Wb_Joints(W_n))
                vb_assign('Model_Members(M_n).Joint_B', ClosetJoint)
                vb_assign('Model_Members(M_n).MemberGroup', NewGroup(2))
                vb_assign('Model_Members(M_n).A_Offset', Joint_Offset())
                vb_assign('Model_Members(M_n).A_Offset.Off_X', 0)
                vb_assign('Model_Members(M_n).A_Offset.Off_Y', 0)
                vb_assign('Model_Members(M_n).A_Offset.Off_Z', 0)
                vb_assign('Model_Members(M_n).B_Offset', Joint_Offset())
                vb_assign('Model_Members(M_n).B_Offset.Off_X', 0)
                vb_assign('Model_Members(M_n).B_Offset.Off_Y', 0)
                vb_assign('Model_Members(M_n).B_Offset.Off_Z', 0)
                r_M = Sheet3.Cells(Sheet3.Rows.Count, 'A').End(xlUp).Row
                r_M = r_M + 1
                vb_assign('Sheet3.Cells(r_M, 1)', Model_Members(M_n).Joint_A.ID)
                vb_assign('Sheet3.Cells(r_M, 2)', Model_Members(M_n).Joint_B.ID)
                vb_assign('Sheet3.Cells(r_M, 3)', Model_Members(M_n).MemberGroup.ID)
                vb_assign('Sheet3.Cells(r_M, 4)', 'New')
            elif (self.Elevation_Array(i).Connection == '焊接'):
                M_n = M_n + 1
                Model_Members = vba_redim(Model_Members, [(1, M_n)], preserve=True)
                vb_assign('Model_Members(M_n)', Member())
                vb_assign('Model_Members(M_n).Joint_A', Conducter_Joints(J_n))
                vb_assign('Model_Members(M_n).Joint_B', ClosetJoint)
                vb_assign('Model_Members(M_n).MemberGroup', NewGroup(2))
                vb_assign('Model_Members(M_n).A_Offset', Joint_Offset())
                vb_assign('Model_Members(M_n).A_Offset.Off_X', 0)
                vb_assign('Model_Members(M_n).A_Offset.Off_Y', 0)
                vb_assign('Model_Members(M_n).A_Offset.Off_Z', 0)
                vb_assign('Model_Members(M_n).B_Offset', Joint_Offset())
                vb_assign('Model_Members(M_n).B_Offset.Off_X', 0)
                vb_assign('Model_Members(M_n).B_Offset.Off_Y', 0)
                vb_assign('Model_Members(M_n).B_Offset.Off_Z', 0)
                r_M = Sheet3.Cells(Sheet3.Rows.Count, 'A').End(xlUp).Row
                r_M = r_M + 1
                vb_assign('Sheet3.Cells(r_M, 1)', Model_Members(M_n).Joint_A.ID)
                vb_assign('Sheet3.Cells(r_M, 2)', Model_Members(M_n).Joint_B.ID)
                vb_assign('Sheet3.Cells(r_M, 3)', Model_Members(M_n).MemberGroup.ID)
                vb_assign('Sheet3.Cells(r_M, 4)', 'New')
            elif (self.Elevation_Array(i).Connection == '无连接'):
                pass
        self.C_Joints_Array = Conducter_Joints
        self.W_Joints_Array = Wb_Joints
        self.Member_Array = Model_Members

    def Get_Closet_Joint(self, T_Joint):
        _return_value = None
        TX = T_Joint.X
        TY = T_Joint.Y
        TZ = T_Joint.Z
        Get_Closet_Joint = Joint()
        conn = None
        rs = None
        strConn = None
        strSQL = None
        conn = create_object('ADODB.Connection')
        rs = create_object('ADODB.Recordset')
        strConn = 'Provider=Microsoft.ACE.OLEDB.12.0;' + 'Data Source=' + ThisWorkbook.FullName + ';' + 'Extended Properties="Excel 12.0;HDR=Yes;";'
        conn.Open(strConn)
        strSQL = "SELECT Top 1 * From [Joints$] Where Mark<> 'New' and Z=" + TZ + ' ORDER BY (X - ' + TX + ')*(X - ' + TX + ') + (Y - ' + TY + ')*(Y - ' + TY + ') + (Z - ' + TZ + ')*(Z - ' + TZ + ')'
        rs.Open(strSQL, conn)
        Get_Closet_Joint.ID = rs.Fields('Joint').Value
        Get_Closet_Joint.X = rs.Fields('X').Value
        Get_Closet_Joint.Y = rs.Fields('Y').Value
        Get_Closet_Joint.Z = rs.Fields('Z').Value
        rs.Close()
        conn.Close()
        rs = None
        conn = None
        return _return_value


# ===== Module: 模块1 =====

def 模块1_Get_ID_Available(TableName, FieldName, FirstLetter, width=4):
    _return_value = None
    ID_Created = False
    conn = None
    rs = None
    strConn = None
    strSQL = None
    conn = create_object('ADODB.Connection')
    rs = create_object('ADODB.Recordset')
    strConn = 'Provider=Microsoft.ACE.OLEDB.12.0;' + 'Data Source=' + ThisWorkbook.FullName + ';' + 'Extended Properties="Excel 12.0;HDR=Yes;";'
    conn.Open(strConn)
    MyLetter = FirstLetter
    i = None
    max_i = math.pow(10, width - len(MyLetter))
    for i in vba_for_range(1, max_i, 1):
        if i == max_i:
            # select case len(MyLetter)
            if (len(MyLetter) == 1):
                MyLetter = Chr(Asc(MyLetter) + 1)
            else:
                MyLetter = vb_left(MyLetter, len(MyLetter) - 1) + Chr(Asc(vb_right(MyLetter, 1)) + 1)
            i = 1
        NewID = MyLetter + 模块1_FillString(i, width - len(MyLetter))
        strSQL = 'SELECT * FROM [' + TableName + '$] Where [' + FieldName + "]='" + NewID + "'"
        rs.Open(strSQL, conn)
        rs_i = 0
        while not rs.EOF:
            rs.MoveNext()
            rs_i = rs_i + 1
        rs.Close()
        if rs_i == 0:
            _return_value = NewID
            return _return_value
    return _return_value

def 模块1_FillString(i, n):
    _return_value = None
    s = str(i)
    if len(s) < n:
        for k in vba_for_range(len(s) + 1, n, 1):
            s = '0' + s
        _return_value = s
    elif len(s) == n:
        _return_value = s
    else:
        _return_value = '-1'
    return _return_value


# ===== Module: 模块2 =====

def 模块2_MinLevel(A, B):
    _return_value = None
    Lv1 = 模块2_Level2Number(A)
    Lv2 = 模块2_Level2Number(B)
    MinL = min(Lv1, Lv2)
    # select case MinL
    if (MinL == 1):
        _return_value = 'I'
    elif (MinL == 2):
        _return_value = 'II'
    elif (MinL == 3):
        _return_value = 'III'
    elif (MinL == 4):
        _return_value = 'IV'
    return _return_value

def 模块2_Level2Number(Lv):
    _return_value = None
    # select case Lv
    if (Lv == 'I'):
        _return_value = 1
    elif (Lv == 'II'):
        _return_value = 2
    elif (Lv == 'III'):
        _return_value = 3
    elif (Lv == 'IV'):
        _return_value = 4
    return _return_value


# ===== Module: 模块3 =====

