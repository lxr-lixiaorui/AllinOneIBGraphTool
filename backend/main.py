from fastapi import FastAPI, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from typing import List, Union, Dict, Any
import numpy as np
import xml.etree.ElementTree as ET
import sympy as sp
import math
import time

app = FastAPI(title="IB Graph Tool API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

x_sym = sp.Symbol("x")
ALLOWED_FUNCS = {
    "x": x_sym, "sqrt": sp.sqrt, "log": sp.log, "ln": sp.log, 
    "exp": sp.exp, "sin": sp.sin, "cos": sp.cos, "tan": sp.tan, "Abs": sp.Abs,
}

class AnalyzeRequest(BaseModel):
    iv_symbol: str = "x"
    iv_unit: str = ""
    dv_symbol: str = "y"
    dv_unit: str = ""
    iv_values: List[float]
    iv_error: Union[float, List[float]] = 0.0
    dv_trials: List[List[float]]
    dv_trial_error: float = 0.0
    x_transform: str = "x"
    y_transform: str = "x"

class ExportCmblRequest(BaseModel):
    x_name: str
    x_unit: str
    y_name: str
    y_unit: str
    x_data: List[float]
    y_data: List[float]
    error_x: List[float]
    error_y: List[float]
    best_fit: dict
    max_line: dict
    min_line: dict

# === 工具函数 ===
def to_error_list(err: Union[float, List[float]], n: int) -> List[float]:
    if isinstance(err, list):
        return [float(v) for v in err]
    return [float(err)] * n

def round_uncertainty_1sf(u: float) -> float:
    u = abs(float(u))
    if u == 0: return 0.0
    exponent = math.floor(math.log10(u))
    factor = 10 ** exponent
    return round(u / factor) * factor

def round_to_uncertainty(value: float, uncertainty: float):
    if uncertainty == 0: return float(value), 0.0
    u = round_uncertainty_1sf(uncertainty)
    exponent = math.floor(math.log10(abs(u)))
    ndigits = -exponent
    return round(float(value), ndigits), round(float(u), ndigits)

def parse_expr(expr: str):
    sym = sp.sympify(expr, locals=ALLOWED_FUNCS)
    fn = sp.lambdify(x_sym, sym, modules=["numpy"])
    return sym, fn

def propagated_error_interval(fn, value: float, error: float, samples: int = 401) -> float:
    error = abs(float(error))
    if error == 0: return 0.0
    xs = np.linspace(value - error, value + error, samples)
    ys = np.array(fn(xs), dtype=float)
    ys = ys[np.isfinite(ys)]
    if ys.size == 0: return 0.0
    return float((ys.max() - ys.min()) / 2.0)

def derive_unit(unit: str, expr: str) -> str:
    unit = (unit or "").strip()
    if not unit: return ""
    sym, _ = parse_expr(expr)
    if sym == x_sym: return unit
    if sym.func in (sp.log, sp.exp): return ""
    if sym.func == sp.sqrt: return f"({unit})^(1/2)"
    if isinstance(sym, sp.Pow) and sym.base == x_sym and sym.exp.is_number:
        return f"({unit})^({sp.sstr(sym.exp)})"
    if sym == 1 / x_sym: return f"({unit})^(-1)"
    return unit

def fit_line(x: List[float], y: List[float]):
    m, b = np.polyfit(np.array(x, dtype=float), np.array(y, dtype=float), 1)
    yhat = m * np.array(x) + b
    ss_res = float(np.sum((np.array(y) - yhat) ** 2))
    ss_tot = float(np.sum((np.array(y) - np.mean(y)) ** 2))
    r2 = 1 - ss_res / ss_tot if ss_tot != 0 else 1.0
    return float(m), float(b), float(r2)

def endpoint_lines(x: List[float], y: List[float], ex: List[float], ey: List[float]):
    pts = sorted(zip(x, y, ex, ey), key=lambda t: t[0])
    x1, y1, ex1, ey1 = pts[0]
    x2, y2, ex2, ey2 = pts[-1]

    # 【逻辑修复】
    # Max Line: 第一个点的右下角 -> 最后一个点的左上角
    max_p1 = (x1 + ex1, y1 - ey1)
    max_p2 = (x2 - ex2, y2 + ey2)
    # Min Line: 第一个点的左上角 -> 最后一个点的右下角
    min_p1 = (x1 - ex1, y1 + ey1)
    min_p2 = (x2 + ex2, y2 - ey2)

    def line_from_points(p1, p2):
        if p2[0] == p1[0]: return 0.0, 0.0
        m = (p2[1] - p1[1]) / (p2[0] - p1[0])
        b = p1[1] - m * p1[0]
        return float(m), float(b)

    max_m, max_b = line_from_points(max_p1, max_p2)
    min_m, min_b = line_from_points(min_p1, min_p2)
    return max_m, max_b, min_m, min_b

def format_eq(m: float, b: float) -> str:
    sign = "+" if b >= 0 else "-"
    return f"y = {m:.4g}x {sign} {abs(b):.4g}"

# === API 接口 ===
@app.post("/api/analyze")
def analyze(req: AnalyzeRequest):
    n = len(req.iv_values)
    iv_errors = to_error_list(req.iv_error, n)
    stage1 = []

    for i in range(n):
        trials = [float(v) for v in req.dv_trials[i] if v is not None]
        mean_dv = float(np.mean(trials))
        range_half = (max(trials) - min(trials)) / 2 if len(trials) > 1 else 0.0
        dv_err = max(float(req.dv_trial_error), float(range_half))

        iv_val_r, iv_err_r = round_to_uncertainty(req.iv_values[i], iv_errors[i]) if iv_errors[i] != 0 else (req.iv_values[i], 0.0)
        dv_val_r, dv_err_r = round_to_uncertainty(mean_dv, dv_err) if dv_err != 0 else (mean_dv, 0.0)
        stage1.append({"iv": iv_val_r, "error_iv": iv_err_r, "dv": dv_val_r, "error_dv": dv_err_r, "trials": trials})

    x_expr, x_fn = parse_expr(req.x_transform)
    y_expr, y_fn = parse_expr(req.y_transform)

    stage2 = []
    for row in stage1:
        x0, ex0 = row["iv"], row["error_iv"]
        y0, ey0 = row["dv"], row["error_dv"]

        tx, ty = float(np.array(x_fn(x0)).item()), float(np.array(y_fn(y0)).item())
        tex, tey = propagated_error_interval(x_fn, x0, ex0), propagated_error_interval(y_fn, y0, ey0)

        tx_r, tex_r = round_to_uncertainty(tx, tex) if tex != 0 else (tx, 0.0)
        ty_r, tey_r = round_to_uncertainty(ty, tey) if tey != 0 else (ty, 0.0)
        stage2.append({"x": tx_r, "error_x": tex_r, "y": ty_r, "error_y": tey_r})

    x_vals = [r["x"] for r in stage2]
    ex_vals = [r["error_x"] for r in stage2]
    y_vals = [r["y"] for r in stage2]
    ey_vals = [r["error_y"] for r in stage2]

    best_m, best_b, r2 = fit_line(x_vals, y_vals)
    max_m, max_b, min_m, min_b = endpoint_lines(x_vals, y_vals, ex_vals, ey_vals)

    dm, db = abs(max_m - min_m) / 2, abs(max_b - min_b) / 2
    m_show, dm_show = round_to_uncertainty(best_m, dm) if dm != 0 else (best_m, 0.0)
    b_show, db_show = round_to_uncertainty(best_b, db) if db != 0 else (best_b, 0.0)

    return {
        "stage1": stage1,
        "stage2": stage2,
        "meta": {
            "x_label": req.iv_symbol if req.x_transform == "x" else f"f({req.iv_symbol})",
            "y_label": req.dv_symbol if req.y_transform == "x" else f"f({req.dv_symbol})",
            "x_unit": derive_unit(req.iv_unit, req.x_transform),
            "y_unit": derive_unit(req.dv_unit, req.y_transform),
        },
        "plot": {
            "x": x_vals, "error_x": ex_vals, "y": y_vals, "error_y": ey_vals,
            "best_fit": {"m": best_m, "b": best_b, "eq": format_eq(best_m, best_b), "r2": r2},
            "max_line": {"m": max_m, "b": max_b, "eq": format_eq(max_m, max_b)},
            "min_line": {"m": min_m, "b": min_b, "eq": format_eq(min_m, min_b)},
            "reported": {"m": m_show, "dm": dm_show, "b": b_show, "db": db_show}
        }
    }

import xml.etree.ElementTree as ET
import os

import re, os
from fastapi.responses import Response

@app.post("/api/export-cmbl")
def export_cmbl(req: ExportCmblRequest):
    template_path = os.path.join(os.path.dirname(__file__), "template.cmbl")
    if not os.path.exists(template_path):
        from fastapi import HTTPException
        raise HTTPException(status_code=500, detail="template.cmbl not found in backend/")

    with open(template_path, "rb") as f:
        raw = f.read()

    bom = b'\xef\xbb\xbf' if raw[:3] == b'\xef\xbb\xbf' else b''
    text = raw[len(bom):].decode('utf-8')

    # ── 辅助函数 ──────────────────────────────────────────────────

    def replace_cells(t: str, col_id: str, values: list) -> str:
        new_content = "\n" + "\n".join(str(v) for v in values) + "\n"
        def replacer(block_match):
            block = block_match.group(0)
            block = re.sub(
                r'<ColumnCells>.*?</ColumnCells>',
                f'<ColumnCells>{new_content}</ColumnCells>',
                block, flags=re.DOTALL
            )
            return block
        # 关键：\s* 而不是 .*?，确保 <ID> 是 <DataColumn> 的第一个子元素
        pattern = rf'<DataColumn>\s*<ID>\s*{re.escape(col_id)}\s*</ID>.*?</DataColumn>'
        return re.sub(pattern, replacer, t, flags=re.DOTALL)

    def replace_tag_in_col(t: str, col_id: str, tag: str, new_val: str) -> str:
        def replacer(block_match):
            block = block_match.group(0)
            block = re.sub(
                rf'(<{tag}>)(.*?)(</{tag}>)',
                lambda m: m.group(1) + new_val + m.group(3),
                block, flags=re.DOTALL
            )
            return block
        pattern = rf'<DataColumn>\s*<ID>\s*{re.escape(col_id)}\s*</ID>.*?</DataColumn>'
        return re.sub(pattern, replacer, t, flags=re.DOTALL)

    def replace_coeff(t: str, func_id: str, m_val: float, b_val: float) -> str:
        def replacer(block_match):
            block = block_match.group(0)
            block = re.sub(
                r'(<FunctionCoefficientArray>)(.*?)(</FunctionCoefficientArray>)',
                lambda mm: mm.group(1) + f"2 {m_val} {b_val} " + mm.group(3),
                block, flags=re.DOTALL
            )
            return block
        # FunctionModel 同理，<ID> 也是第一个子元素
        pattern = rf'<FunctionModel>\s*<ID>\s*{re.escape(func_id)}\s*</ID>.*?</FunctionModel>'
        return re.sub(pattern, replacer, t, flags=re.DOTALL)

    def replace_tag_in_func(t: str, func_id: str, tag: str, new_val: str) -> str:
        def replacer(block_match):
            block = block_match.group(0)
            block = re.sub(
                rf'(<{tag}>)(.*?)(</{tag}>)',
                lambda m: m.group(1) + new_val + m.group(3),
                block, flags=re.DOTALL
            )
            return block
        pattern = rf'<FunctionModel>\s*<ID>\s*{re.escape(func_id)}\s*</ID>.*?</FunctionModel>'
        return re.sub(pattern, replacer, t, flags=re.DOTALL)

    # ── 替换数据 ──────────────────────────────────────────────────

    # 1. 数据列 (102=X, 104=Y)
    text = replace_cells(text, "102", req.x_data)
    text = replace_cells(text, "104", req.y_data)

    # 2. 误差列 (115=ErrorX, 118=ErrorY)
    text = replace_cells(text, "115", req.error_x)
    text = replace_cells(text, "118", req.error_y)

    # 3. X 列名称和单位
    text = replace_tag_in_col(text, "102", "DataObjectName", req.x_name)
    text = replace_tag_in_col(text, "102", "DataObjectShortName", req.x_name[:8])
    text = replace_tag_in_col(text, "102", "ColumnUnits", req.x_unit)

    # 4. Y 列名称和单位
    text = replace_tag_in_col(text, "104", "DataObjectName", req.y_name)
    text = replace_tag_in_col(text, "104", "DataObjectShortName", req.y_name[:8])
    text = replace_tag_in_col(text, "104", "ColumnUnits", req.y_unit)

    # 5. 误差列单位（与主列保持一致）
    text = replace_tag_in_col(text, "115", "ColumnUnits", req.x_unit)
    text = replace_tag_in_col(text, "118", "ColumnUnits", req.y_unit)

    # 6. 三条拟合线系数 (110=Best Fit, 158=Max Line, 161=Min Line)
    text = replace_coeff(text, "110", req.best_fit["m"], req.best_fit["b"])
    text = replace_coeff(text, "158", req.max_line["m"], req.max_line["b"])
    text = replace_coeff(text, "161", req.min_line["m"], req.min_line["b"])

    # 7. 拟合线名称（让 Logger Pro 里显示正确）
    text = replace_tag_in_func(text, "110", "DataObjectName", "Best Fit")
    text = replace_tag_in_func(text, "158", "DataObjectName", "Max Line")
    text = replace_tag_in_func(text, "161", "DataObjectName", "Min Line")

    # 8. 更新 ManualCurveFitIncrements 为合理步长（m和b各取值的1%）
    def replace_manual_increments(t: str, helper_fit_id: str, m_val: float, b_val: float) -> str:
        m_step = max(abs(m_val) * 0.01, 0.001)
        b_step = max(abs(b_val) * 0.01, 0.001)
        def replacer(block_match):
            block = block_match.group(0)
            block = re.sub(
                r'(<ManualCurveFitIncrements>)(.*?)(</ManualCurveFitIncrements>)',
                lambda mm: mm.group(1) + f"2 {m_step:.4f} {b_step:.4f} " + mm.group(3),
                block, flags=re.DOTALL
            )
            return block
        pattern = rf'<PageHelperDataCurveFit>.*?<CurveFitFunctionID>{re.escape(helper_fit_id)}</CurveFitFunctionID>.*?</PageHelperDataCurveFit>'
        return re.sub(pattern, replacer, t, flags=re.DOTALL)

    text = replace_manual_increments(text, "158", req.max_line["m"], req.max_line["b"])
    text = replace_manual_increments(text, "161", req.min_line["m"], req.min_line["b"])

    # ── 输出 ──────────────────────────────────────────────────────
    output = bom + text.encode('utf-8')
    return Response(
        content=output,
        media_type="application/octet-stream",
        headers={"Content-Disposition": f'attachment; filename="{req.y_name}_vs_{req.x_name}.cmbl"'}
    )