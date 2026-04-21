from fastapi import APIRouter
from pydantic import BaseModel
from ai.nl_to_sql import question_to_sql
from db.snowflake_client import run_query

router = APIRouter()

class QuestionRequest(BaseModel):
    question: str

@router.post("/query")
async def query_data(request: QuestionRequest):
    try:
        sql = question_to_sql(request.question)
        result = run_query(sql)
        return {
            "question": request.question,
            "sql": sql,
            "result": result
        }
    except Exception as e:
        return {"error": str(e)}