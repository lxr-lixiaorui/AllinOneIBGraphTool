# All-in-one IB Graph Tool

[Direct Link](https://graphtool.ruiyuan.me)

All-in-one IB Graph Tool turns repeated trial data into polished analysis outputs in one place. It handles uncertainty rounding, linearization, best-fit and max/min gradient lines, publication-ready tables, and Logger Pro export, so you can focus on interpreting the graph instead of rebuilding the same spreadsheet workflow every time.

## Features

- Raw data table input from CSV/TSV-style text.
- Automatic mean, uncertainty, and significant-figure rounding.
- X/Y linearization using Python-style math expressions such as `x`, `x**2`, `sqrt(x)`, `log(x)`, and `exp(x)`.
- Best-fit line, R2, gradient/intercept uncertainty, and max/min error-bar lines.
- Plot export support through Logger Pro `.cmbl`.
- Raw/linearized table export as CSV, DOCX, and LaTeX.

## Run Locally

Backend:

```bash
cd backend
pip install -r requirements.txt
pip install uvicorn
uvicorn main:app --reload
```

Frontend:

```bash
cd frontend
npm install
npm run dev
```

In development, the frontend calls `http://127.0.0.1:8000`.

## Project Structure

```txt
backend/
  main.py              FastAPI routes
  analysis.py          data processing and fitting logic
  models.py            request models
  exports/             DOCX and CMBL export helpers

frontend/
  src/App.vue          main Vue UI
  src/api.ts           API client
```
