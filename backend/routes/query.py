from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from ai.nl_to_sql import question_to_sql, generate_answer
from db.snowflake_client import run_query, test_connection

router = APIRouter()


class QuestionRequest(BaseModel):
    question: str


@router.post("/query")
async def query_data(request: QuestionRequest):
    """Raw query endpoint — returns SQL + raw data. Used by developer tools."""
    if not request.question or not request.question.strip():
        raise HTTPException(status_code=400, detail="Question cannot be empty")

    try:
        sql = question_to_sql(request.question)
        result = run_query(sql)

        if "error" in result:
            return {
                "question": request.question,
                "sql": sql,
                "error": result["error"]
            }

        return {
            "question": request.question,
            "sql": sql,
            "result": result
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/ask")
async def ask_clariq(request: QuestionRequest):
    """Human-friendly endpoint — returns a plain English answer. Used by the dashboard."""
    if not request.question or not request.question.strip():
        raise HTTPException(status_code=400, detail="Question cannot be empty")

    try:
        # Step 1: Convert question to SQL
        sql = question_to_sql(request.question)

        # Step 2: Run the SQL against Snowflake
        result = run_query(sql)

        if "error" in result:
            return {
                "question": request.question,
                "answer": f"I had trouble getting that data. The issue was: {result['error']}. Try rephrasing your question.",
                "sql": sql,
                "data": None
            }

        # Step 3: Generate a human-readable answer
        answer = generate_answer(
            request.question,
            result.get("columns", []),
            result.get("rows", [])
        )

        return {
            "question": request.question,
            "answer": answer,
            "sql": sql,
            "data": result
        }
    except Exception as e:
        return {
            "question": request.question,
            "answer": "Something went wrong while processing your question. Please try again.",
            "error": str(e)
        }


@router.get("/health")
async def api_health():
    """Check if the API and Snowflake connection are healthy."""
    sf_ok = test_connection()
    return {
        "api": "healthy",
        "snowflake": "connected" if sf_ok else "disconnected"
    }
