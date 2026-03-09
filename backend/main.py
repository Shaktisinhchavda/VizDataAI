"""
Quadratic AI — FastAPI Backend
Serves the frontend, handles file uploads, and routes chat queries to CrewAI agents.
"""

import os
import json
import traceback
import pandas as pd
from pathlib import Path
from dotenv import load_dotenv
from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import uvicorn

from session import store
from agents.data_agent import run_data_agent
from agents.analytics_agent import run_analytics_agent

# Load environment variables from the root directory (.env)
env_path = Path(__file__).parent.parent / ".env"
load_dotenv(dotenv_path=env_path, override=True)

# Ensure GEMINI API key is set for LiteLLM/CrewAI
api_key = os.getenv("GEMINI_API_KEY")

# For local Ollama models (if used), we force Langchain/CrewAI into OpenAI compatibility mode
os.environ["OPENAI_API_BASE"] = "http://localhost:11434/v1"
os.environ["OPENAI_API_KEY"] = "ollama"

if api_key:
    os.environ["GOOGLE_API_KEY"] = api_key  # LiteLLM also checks this
    print(f"✅ Gemini API Key loaded: {api_key[:10]}...")
    print(f"✅ Gemini API Key loaded: {api_key[:8]}...{api_key[-4:]}")
else:
    print("⚠️  WARNING: No GEMINI_API_KEY found in .env file!")

app = FastAPI(title="VizData AI", version="1.0.0")

# CORS for local development
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ═══════════════════════════════════════════
# MODELS
# ═══════════════════════════════════════════

class ChatRequest(BaseModel):
    sheet_id: str
    message: str


from typing import Optional, List

class ChatResponse(BaseModel):
    response: str
    sheet_updated: bool = False
    sheet_data: Optional[dict] = None
    charts: Optional[List[str]] = None


class UpdateCellRequest(BaseModel):
    sheet_id: str
    row_idx: int
    col_idx: int
    value: str


# ═══════════════════════════════════════════
# ENDPOINTS
# ═══════════════════════════════════════════

@app.post("/upload")
async def upload_file(file: UploadFile = File(...)):
    """Upload a CSV or XLSX file."""
    if not file.filename:
        raise HTTPException(400, "No file provided.")
    
    ext = file.filename.rsplit(".", 1)[-1].lower()
    if ext not in ("csv", "xlsx", "xls"):
        raise HTTPException(400, "Only CSV and XLSX files are supported.")
    
    try:
        contents = await file.read()
        
        if ext == "csv":
            df = pd.read_csv(pd.io.common.BytesIO(contents))
        else:
            df = pd.read_excel(pd.io.common.BytesIO(contents))
        
        sheet_id = store.add_sheet(df, file.filename)
        
        return {
            "sheet_id": sheet_id,
            "filename": file.filename,
            "rows": len(df),
            "columns": len(df.columns),
            "column_names": list(df.columns),
            "preview": json.loads(df.head(50).to_json(orient="records", date_format="iso")),
            "dtypes": {col: str(dtype) for col, dtype in df.dtypes.items()},
        }
    except Exception as e:
        raise HTTPException(500, f"Error processing file: {str(e)}")


@app.get("/sheet/{sheet_id}")
async def get_sheet(sheet_id: str, page: int = 0, page_size: int = 100):
    """Get the current state of a sheet with pagination."""
    df = store.get_sheet(sheet_id)
    if df is None:
        raise HTTPException(404, "Sheet not found.")
    
    start = page * page_size
    end = min(start + page_size, len(df))
    page_df = df.iloc[start:end]
    
    return {
        "sheet_id": sheet_id,
        "filename": store.get_filename(sheet_id),
        "total_rows": len(df),
        "total_columns": len(df.columns),
        "column_names": list(df.columns),
        "dtypes": {col: str(dtype) for col, dtype in df.dtypes.items()},
        "page": page,
        "page_size": page_size,
        "data": json.loads(page_df.to_json(orient="records", date_format="iso")),
    }


@app.get("/download/{sheet_id}")
async def download_sheet(sheet_id: str):
    """Download the spreadsheet as a CSV file."""
    df = store.get_sheet(sheet_id)
    if df is None:
        raise HTTPException(404, "Sheet not found.")
    
    filename = store.get_filename(sheet_id)
    if not filename.endswith(".csv"):
        filename = f"{filename}.csv"
        
    csv_str = df.to_csv(index=False)
    from fastapi.responses import Response
    return Response(
        content=csv_str,
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename={filename}"}
    )


@app.post("/update_cell")
async def update_cell(req: UpdateCellRequest):
    """Update a specific cell by row and column indices."""
    df = store.get_sheet(req.sheet_id)
    if df is None:
        raise HTTPException(404, "Sheet not found.")
    
    try:
        # Update the cell by integer positioning
        df.iat[req.row_idx, req.col_idx] = req.value
        store.update_sheet(req.sheet_id, df)
        return {"status": "success"}
    except Exception as e:
        raise HTTPException(500, f"Error updating cell: {str(e)}")


@app.post("/chat/data", response_model=ChatResponse)
async def chat_data(req: ChatRequest):
    """Send a message to the Data Manager agent."""
    df = store.get_sheet(req.sheet_id)
    if df is None:
        raise HTTPException(404, "Sheet not found.")
    
    try:
        result = run_data_agent(req.message, df)
        
        # Update the stored DataFrame if modified
        if result["modified"]:
            store.update_sheet(req.sheet_id, result["df"])
        
        # Get updated sheet data
        updated_df = store.get_sheet(req.sheet_id)
        sheet_data = {
            "total_rows": len(updated_df),
            "total_columns": len(updated_df.columns),
            "column_names": list(updated_df.columns),
            "data": json.loads(updated_df.head(100).to_json(orient="records", date_format="iso")),
        }

        
        return ChatResponse(
            response=result["response"],
            sheet_updated=result["modified"],
            sheet_data=sheet_data,
        )
    except Exception as e:
        traceback.print_exc()
        return ChatResponse(
            response=f"I encountered an error processing your request: {str(e)}",
            sheet_updated=False,
        )


@app.post("/chat/analytics", response_model=ChatResponse)
async def chat_analytics(req: ChatRequest):
    """Send a message to the Analytics agent."""
    df = store.get_sheet(req.sheet_id)
    if df is None:
        raise HTTPException(404, "Sheet not found.")
    
    try:
        result = run_analytics_agent(req.message, df)
        
        return ChatResponse(
            response=result["response"],
            charts=result.get("charts", []),
        )
    except Exception as e:
        traceback.print_exc()
        return ChatResponse(
            response=f"I encountered an error processing your request: {str(e)}",
        )

@app.post("/create")
async def create_dataset(req: dict):
    """Create a new empty dataset."""
    name = req.get("name", "untitled.csv")
    if not name.endswith(".csv"):
        name += ".csv"
    
    columns = req.get("columns", [])
    if columns:
        df = pd.DataFrame(columns=columns)
    else:
        df = pd.DataFrame()
    
    sheet_id = store.add_sheet(df, name)
    
    return {
        "sheet_id": sheet_id,
        "filename": name,
        "rows": 0,
        "columns": len(columns),
        "column_names": columns,
        "preview": [],
        "dtypes": {},
    }


@app.get("/sheets")
async def list_sheets():
    """List all uploaded sheets."""
    return {"sheets": store.list_sheets()}


# ═══════════════════════════════════════════
# STATIC FILES & ENTRY POINT
# ═══════════════════════════════════════════

# Serve frontend
frontend_dir = Path(__file__).parent.parent / "frontend"
if frontend_dir.exists():
    app.mount("/", StaticFiles(directory=str(frontend_dir), html=True), name="frontend")


if __name__ == "__main__":
    print("\n🚀 VizData AI is starting...")
    print("📊 Open http://localhost:8000 in your browser\n")
    uvicorn.run(app, host="0.0.0.0", port=8000, reload=False)
