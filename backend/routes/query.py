from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from ai.nl_to_sql import question_to_sql, generate_answer
from db.snowflake_client import run_query, test_connection

router = APIRouter()


class QuestionRequest(BaseModel):
    question: str


@router.post("/ask")
async def ask_clariq(request: QuestionRequest):
    """Human-friendly endpoint — returns a plain English answer. Used by the dashboard."""
    if not request.question or not request.question.strip():
        raise HTTPException(status_code=400, detail="Question cannot be empty")

    try:
        # Convert question to SQL
        sql = question_to_sql(request.question)
        
        # Execute the SQL
        result = run_query(sql)
        
        # Generate human-readable answer
        answer = generate_answer(
            request.question,
            result.get("columns", []),
            result.get("rows", [])
        )
        
        return {
            "question": request.question,
            "answer": answer,
            "sql": sql,
            "data": result.get("rows", []),
            "columns": result.get("columns", [])
        }
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
        # Convert question to SQL
        sql = question_to_sql(request.question)
        
        # Execute the SQL
        result = run_query(sql)
        
        return {
            "question": request.question,
            "sql": sql,
            "data": result.get("rows", []),
            "columns": result.get("columns", [])
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/health")
async def health_check():
    """Health check endpoint."""
    try:
        # Test Snowflake connection
        test_connection()
        return {
            "api": "healthy",
            "snowflake": "connected"
        }
    except Exception as e:
        return {
            "api": "healthy",
            "snowflake": f"disconnected: {str(e)}"
        }