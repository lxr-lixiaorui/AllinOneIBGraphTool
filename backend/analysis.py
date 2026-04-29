from typing import List, Union
import math
import re

from fastapi import HTTPException
import numpy as np
from scipy.optimize import linprog
import sympy as sp

try:
    from .models import AnalyzeRequest
except ImportError:
    from models import AnalyzeRequest


x_sym = sp.Symbol("x")
ALLOWED_FUNCS = {
    "x": x_sym,
    "sqrt": sp.sqrt,
    "log": sp.log,
    "ln": sp.log,
    "exp": sp.exp,
    "sin": sp.sin,
    "cos": sp.cos,
    "tan": sp.tan,
    "Abs": sp.Abs,
}


def to_error_list(err: Union[float, List[float]], n: int) -> List[float]:
    if isinstance(err, list):
        return [float(v) for v in err]
    return [float(err)] * n


def round_uncertainty_1sf(u: float) -> float:
    u = abs(float(u))
    if u == 0:
        return 0.0
    exponent = math.floor(math.log10(u))
    factor = 10 ** exponent
    return round(u / factor) * factor


def round_to_uncertainty(value: float, uncertainty: float):
    if uncertainty == 0:
        return float(value), 0.0
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
    if error == 0:
        return 0.0
    xs = np.linspace(value - error, value + error, samples)
    ys = np.array(fn(xs), dtype=float)
    ys = ys[np.isfinite(ys)]
    if ys.size == 0:
        return 0.0
    return float((ys.max() - ys.min()) / 2.0)


def derive_unit(unit: str, expr: str) -> str:
    unit = (unit or "").strip()
    if not unit:
        return ""
    sym, _ = parse_expr(expr)
    if sym == x_sym:
        return unit
    if sym.func in (sp.log, sp.exp):
        return ""
    if sym.func == sp.sqrt:
        return f"({unit})^(1/2)"
    if isinstance(sym, sp.Pow) and sym.base == x_sym and sym.exp.is_number:
        return f"({unit})^({sp.sstr(sym.exp)})"
    if sym == 1 / x_sym:
        return f"({unit})^(-1)"
    return unit


def transform_label(symbol: str, expr: str) -> str:
    expr = (expr or "x").strip()
    if expr == "x":
        return symbol
    return re.sub(r"(?<![A-Za-z0-9_])x(?![A-Za-z0-9_])", symbol, expr)


def finite_array(values: List[float], label: str) -> np.ndarray:
    arr = np.array(values, dtype=float)
    if arr.size == 0:
        raise HTTPException(status_code=422, detail=f"{label} has no data.")
    if not np.all(np.isfinite(arr)):
        bad_rows = [str(i + 1) for i, value in enumerate(arr) if not np.isfinite(value)]
        shown = ", ".join(bad_rows[:5])
        suffix = "..." if len(bad_rows) > 5 else ""
        raise HTTPException(
            status_code=422,
            detail=f"{label} contains NaN or Infinity at row(s) {shown}{suffix}. Check linearization domain or overflow.",
        )
    return arr


def fit_line(x: List[float], y: List[float]):
    x_arr = finite_array(x, "Linearized X")
    y_arr = finite_array(y, "Linearized Y")
    if x_arr.size < 2 or np.unique(x_arr).size < 2:
        raise HTTPException(status_code=422, detail="At least two different X values are required for linear fit.")
    try:
        m, b = np.polyfit(x_arr, y_arr, 1)
    except np.linalg.LinAlgError as exc:
        raise HTTPException(
            status_code=422,
            detail=f"Linear fit failed. Check transformed data for invalid or numerically unstable values. ({exc})",
        ) from exc
    yhat = m * x_arr + b
    ss_res = float(np.sum((y_arr - yhat) ** 2))
    ss_tot = float(np.sum((y_arr - np.mean(y_arr)) ** 2))
    r2 = 1 - ss_res / ss_tot if ss_tot != 0 else 1.0
    return float(m), float(b), float(r2)


def linprog_extreme_lines(x: List[float], y: List[float], ex: List[float], ey: List[float]):
    x_arr = finite_array(x, "Linearized X")
    y_arr = finite_array(y, "Linearized Y")
    ex_arr = np.abs(finite_array(ex, "Linearized X uncertainty"))
    ey_arr = np.abs(finite_array(ey, "Linearized Y uncertainty"))

    if x_arr.size < 2:
        raise HTTPException(status_code=422, detail="At least two points are required for max/min lines.")

    def build_constraints(slope_sign: int):
        a_ub = []
        b_ub = []
        for xi, yi, dxi, dyi in zip(x_arr, y_arr, ex_arr, ey_arr):
            if slope_sign >= 0:
                a_ub.append([xi - dxi, 1.0])
                b_ub.append(yi + dyi)
                a_ub.append([-(xi + dxi), -1.0])
                b_ub.append(-(yi - dyi))
            else:
                a_ub.append([xi + dxi, 1.0])
                b_ub.append(yi + dyi)
                a_ub.append([-(xi - dxi), -1.0])
                b_ub.append(-(yi - dyi))
        return a_ub, b_ub

    def solve_extreme(maximize: bool, slope_sign: int):
        objective = [-1.0, 0.0] if maximize else [1.0, 0.0]
        bounds = [(0.0, None), (None, None)] if slope_sign >= 0 else [(None, 0.0), (None, None)]
        a_ub, b_ub = build_constraints(slope_sign)
        return linprog(objective, A_ub=a_ub, b_ub=b_ub, bounds=bounds, method="highs")

    def candidates_for(maximize: bool):
        candidates = []
        statuses = []
        for slope_sign in (1, -1):
            res = solve_extreme(maximize, slope_sign)
            statuses.append(res.message)
            if res.success and np.all(np.isfinite(res.x)):
                candidates.append((float(res.x[0]), float(res.x[1])))
        return candidates, statuses

    max_candidates, max_statuses = candidates_for(maximize=True)
    min_candidates, min_statuses = candidates_for(maximize=False)

    if not max_candidates or not min_candidates:
        detail = (
            "No bounded straight max/min line can pass through all error bars. "
            f"Max solver: {'; '.join(max_statuses)}. Min solver: {'; '.join(min_statuses)}."
        )
        raise HTTPException(status_code=422, detail=detail)

    max_m, max_b = max(max_candidates, key=lambda params: params[0])
    min_m, min_b = min(min_candidates, key=lambda params: params[0])
    return max_m, max_b, min_m, min_b


def format_eq(m: float, b: float) -> str:
    sign = "+" if b >= 0 else "-"
    return f"y = {m:.4g}x {sign} {abs(b):.4g}"


def analyze_data(req: AnalyzeRequest):
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

    _, x_fn = parse_expr(req.x_transform)
    _, y_fn = parse_expr(req.y_transform)

    stage2 = []
    for row in stage1:
        x0, ex0 = row["iv"], row["error_iv"]
        y0, ey0 = row["dv"], row["error_dv"]

        tx, ty = float(np.array(x_fn(x0)).item()), float(np.array(y_fn(y0)).item())
        tex, tey = propagated_error_interval(x_fn, x0, ex0), propagated_error_interval(y_fn, y0, ey0)
        finite_array([tx, ty, tex, tey], f"Transformed row {len(stage2) + 1}")

        tx_r, tex_r = round_to_uncertainty(tx, tex) if tex != 0 else (tx, 0.0)
        ty_r, tey_r = round_to_uncertainty(ty, tey) if tey != 0 else (ty, 0.0)
        stage2.append({"x": tx_r, "error_x": tex_r, "y": ty_r, "error_y": tey_r})

    x_vals = [r["x"] for r in stage2]
    ex_vals = [r["error_x"] for r in stage2]
    y_vals = [r["y"] for r in stage2]
    ey_vals = [r["error_y"] for r in stage2]

    best_m, best_b, r2 = fit_line(x_vals, y_vals)
    max_m, max_b, min_m, min_b = linprog_extreme_lines(x_vals, y_vals, ex_vals, ey_vals)

    dm, db = abs(max_m - min_m) / 2, abs(max_b - min_b) / 2
    m_show, dm_show = round_to_uncertainty(best_m, dm) if dm != 0 else (best_m, 0.0)
    b_show, db_show = round_to_uncertainty(best_b, db) if db != 0 else (best_b, 0.0)

    return {
        "stage1": stage1,
        "stage2": stage2,
        "meta": {
            "x_label": transform_label(req.iv_symbol, req.x_transform),
            "y_label": transform_label(req.dv_symbol, req.y_transform),
            "x_unit": derive_unit(req.iv_unit, req.x_transform),
            "y_unit": derive_unit(req.dv_unit, req.y_transform),
        },
        "plot": {
            "x": x_vals,
            "error_x": ex_vals,
            "y": y_vals,
            "error_y": ey_vals,
            "best_fit": {"m": best_m, "b": best_b, "eq": format_eq(best_m, best_b), "r2": r2},
            "max_line": {"m": max_m, "b": max_b, "eq": format_eq(max_m, max_b)},
            "min_line": {"m": min_m, "b": min_b, "eq": format_eq(min_m, min_b)},
            "reported": {"m": m_show, "dm": dm_show, "b": b_show, "db": db_show},
        },
    }
