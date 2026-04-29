from pydantic import BaseModel
from typing import Any, List, Union


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


class RawTableDocxRequest(BaseModel):
    title: str = "Raw data table"
    headers: List[str]
    rows: List[List[Any]]
