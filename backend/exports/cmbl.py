import os
import re

from fastapi import HTTPException

try:
    from ..models import ExportCmblRequest
except ImportError:
    from models import ExportCmblRequest


def build_cmbl(req: ExportCmblRequest, template_path: str) -> bytes:
    if not os.path.exists(template_path):
        raise HTTPException(status_code=500, detail="template.cmbl not found in backend/")

    with open(template_path, "rb") as f:
        raw = f.read()

    bom = b"\xef\xbb\xbf" if raw[:3] == b"\xef\xbb\xbf" else b""
    text = raw[len(bom):].decode("utf-8")

    def replace_cells(t: str, col_id: str, values: list) -> str:
        new_content = "\n" + "\n".join(str(v) for v in values) + "\n"

        def replacer(block_match):
            block = block_match.group(0)
            return re.sub(
                r"<ColumnCells>.*?</ColumnCells>",
                f"<ColumnCells>{new_content}</ColumnCells>",
                block,
                flags=re.DOTALL,
            )

        pattern = rf"<DataColumn>\s*<ID>\s*{re.escape(col_id)}\s*</ID>.*?</DataColumn>"
        return re.sub(pattern, replacer, t, flags=re.DOTALL)

    def replace_tag_in_col(t: str, col_id: str, tag: str, new_val: str) -> str:
        def replacer(block_match):
            block = block_match.group(0)
            return re.sub(
                rf"(<{tag}>)(.*?)(</{tag}>)",
                lambda m: m.group(1) + new_val + m.group(3),
                block,
                flags=re.DOTALL,
            )

        pattern = rf"<DataColumn>\s*<ID>\s*{re.escape(col_id)}\s*</ID>.*?</DataColumn>"
        return re.sub(pattern, replacer, t, flags=re.DOTALL)

    def replace_coeff(t: str, func_id: str, m_val: float, b_val: float) -> str:
        def replacer(block_match):
            block = block_match.group(0)
            return re.sub(
                r"(<FunctionCoefficientArray>)(.*?)(</FunctionCoefficientArray>)",
                lambda mm: mm.group(1) + f"2 {m_val} {b_val} " + mm.group(3),
                block,
                flags=re.DOTALL,
            )

        pattern = rf"<FunctionModel>\s*<ID>\s*{re.escape(func_id)}\s*</ID>.*?</FunctionModel>"
        return re.sub(pattern, replacer, t, flags=re.DOTALL)

    def replace_tag_in_func(t: str, func_id: str, tag: str, new_val: str) -> str:
        def replacer(block_match):
            block = block_match.group(0)
            return re.sub(
                rf"(<{tag}>)(.*?)(</{tag}>)",
                lambda m: m.group(1) + new_val + m.group(3),
                block,
                flags=re.DOTALL,
            )

        pattern = rf"<FunctionModel>\s*<ID>\s*{re.escape(func_id)}\s*</ID>.*?</FunctionModel>"
        return re.sub(pattern, replacer, t, flags=re.DOTALL)

    def replace_manual_increments(t: str, helper_fit_id: str, m_val: float, b_val: float) -> str:
        m_step = max(abs(m_val) * 0.01, 0.001)
        b_step = max(abs(b_val) * 0.01, 0.001)

        def replacer(block_match):
            block = block_match.group(0)
            return re.sub(
                r"(<ManualCurveFitIncrements>)(.*?)(</ManualCurveFitIncrements>)",
                lambda mm: mm.group(1) + f"2 {m_step:.4f} {b_step:.4f} " + mm.group(3),
                block,
                flags=re.DOTALL,
            )

        pattern = rf"<PageHelperDataCurveFit>.*?<CurveFitFunctionID>{re.escape(helper_fit_id)}</CurveFitFunctionID>.*?</PageHelperDataCurveFit>"
        return re.sub(pattern, replacer, t, flags=re.DOTALL)

    text = replace_cells(text, "102", req.x_data)
    text = replace_cells(text, "104", req.y_data)
    text = replace_cells(text, "115", req.error_x)
    text = replace_cells(text, "118", req.error_y)

    text = replace_tag_in_col(text, "102", "DataObjectName", req.x_name)
    text = replace_tag_in_col(text, "102", "DataObjectShortName", req.x_name[:8])
    text = replace_tag_in_col(text, "102", "ColumnUnits", req.x_unit)

    text = replace_tag_in_col(text, "104", "DataObjectName", req.y_name)
    text = replace_tag_in_col(text, "104", "DataObjectShortName", req.y_name[:8])
    text = replace_tag_in_col(text, "104", "ColumnUnits", req.y_unit)

    text = replace_tag_in_col(text, "115", "ColumnUnits", req.x_unit)
    text = replace_tag_in_col(text, "118", "ColumnUnits", req.y_unit)

    text = replace_coeff(text, "110", req.best_fit["m"], req.best_fit["b"])
    text = replace_coeff(text, "158", req.max_line["m"], req.max_line["b"])
    text = replace_coeff(text, "161", req.min_line["m"], req.min_line["b"])

    text = replace_tag_in_func(text, "110", "DataObjectName", "Best Fit")
    text = replace_tag_in_func(text, "158", "DataObjectName", "Max Line")
    text = replace_tag_in_func(text, "161", "DataObjectName", "Min Line")

    text = replace_manual_increments(text, "158", req.max_line["m"], req.max_line["b"])
    text = replace_manual_increments(text, "161", req.min_line["m"], req.min_line["b"])

    return bom + text.encode("utf-8")
