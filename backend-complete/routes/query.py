from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from ai.nl_to_sql import process_question
from db.snowflake_client import execute_query

router = APIRouter()


class QuestionRequest(BaseModel):
    question: str


@router.post("/ask")
async def ask_clariq(request: QuestionRequest):
    """Human-friendly endpoint — returns a plain English answer. Used by the dashboard."""
    if not request.question or not request.question.strip():
        raise HTTPException(status_code=400, detail="Question cannot be empty")

    try:
        result = process_question(request.question)
        return result
    except Exception as e:
        return {
            "question": request.question,
            "answer": "Something went wrong while processing your question. Please try again.",
            "error": str(e)
        }


@router.post("/query")
async def query_data(request: QuestionRequest):
    """Raw query endpoint — returns SQL + raw data. Used by developer tools."""
    if not request.question or not request.question.strip():
        raise HTTPException(status_code=400, detail="Question cannot be empty")

    try:
        result = process_question(request.question)
        return {
            "question": result.get("question"),
            "sql": result.get("sql"),
            "data": result.get("data", []),
            "columns": result.get("columns", [])
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/health")
async def health_check():
    """Health check endpoint."""
    try:
        # Test Snowflake connection
        test_result = execute_query("SELECT 1")
        return {
            "api": "healthy",
            "snowflake": "connected"
        }
    except Exception as e:
        return {
            "api": "healthy",
            "snowflake": f"disconnected: {str(e)}"
        }