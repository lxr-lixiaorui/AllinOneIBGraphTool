import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response

try:
    from .analysis import analyze_data
    from .exports.cmbl import build_cmbl
    from .exports.docx import build_docx_table
    from .models import AnalyzeRequest, ExportCmblRequest, RawTableDocxRequest
except ImportError:
    from analysis import analyze_data
    from exports.cmbl import build_cmbl
    from exports.docx import build_docx_table
    from models import AnalyzeRequest, ExportCmblRequest, RawTableDocxRequest


app = FastAPI(title="IB Graph Tool API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["https://graphtool.ruiyuan.me", "http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.post("/api/analyze")
def analyze(req: AnalyzeRequest):
    return analyze_data(req)


@app.post("/api/export-raw-table-docx")
def export_raw_table_docx(req: RawTableDocxRequest):
    content = build_docx_table(req.title, req.headers, req.rows)
    return Response(
        content=content,
        media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        headers={"Content-Disposition": 'attachment; filename="raw_data_table.docx"'},
    )


@app.post("/api/export-cmbl")
def export_cmbl(req: ExportCmblRequest):
    template_path = os.path.join(os.path.dirname(__file__), "template.cmbl")
    output = build_cmbl(req, template_path)
    return Response(
        content=output,
        media_type="application/octet-stream",
        headers={"Content-Disposition": f'attachment; filename="{req.y_name}_vs_{req.x_name}.cmbl"'},
    )
