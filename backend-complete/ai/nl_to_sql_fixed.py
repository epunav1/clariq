import os
from anthropic import Anthropic
from db.snowflake_client import SnowflakeClient

client = Anthropic()
snowflake_client = SnowflakeClient()

# System prompt for Claude to convert natural language to SQL
NL_TO_SQL_SYSTEM = """You are an expert SQL analyst. Your job is to convert natural language questions into accurate Snowflake SQL queries.

Database schema:
- CLARIQ_DB.SHOPIFY_RAW.RAW_ORDERS: order_id, created_at, customer_id, email, total_price, subtotal_price, total_tax, financial_status, fulfillment_status, currency
- CLARIQ_DB.SHOPIFY_RAW.RAW_CUSTOMERS: customer_id, created_at, email, first_name, last_name, orders_count, total_spent, city, country, tags
- CLARIQ_DB.SHOPIFY_RAW.RAW_PRODUCTS: product_id, created_at, title, product_type, vendor, status, price, inventory_quantity
- CLARIQ_DB.SHOPIFY_RAW.RAW_ORDER_LINE_ITEMS: line_item_id, order_id, product_id, title, quantity, price, sku, fulfillment_status

Rules:
1. Always use exact table and column names (case-sensitive for Snowflake)
2. Use DATE functions for date filtering
3. Use SUM, COUNT, AVG, MAX, MIN for aggregations
4. Include WHERE clauses for filtering
5. Return only the SQL query, no explanation
6. Always format: SELECT ... FROM CLARIQ_DB.SHOPIFY_RAW.TABLE_NAME"""

ANSWER_SYSTEM = """You are a business intelligence assistant. Your job is to take SQL query results and explain them in clear, friendly business language.

Rules:
1. Be concise and direct
2. Highlight key numbers and trends
3. Use currency formatting ($X,XXX.XX) for money
4. Use percentage formatting (X.X%) for rates
5. Be actionable - suggest next steps if relevant"""


def nl_to_sql(question: str) -> str:
    """Convert natural language question to SQL using Claude."""
    try:
        response = client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=500,
            system=NL_TO_SQL_SYSTEM,
            messages=[
                {"role": "user", "content": question}
            ]
        )
        sql = response.content[0].text.strip()
        # Clean up SQL if wrapped in markdown
        if sql.startswith("```"):
            sql = sql.split("\n", 1)[1]
        if sql.endswith("```"):
            sql = sql.rsplit("\n", 1)[0]
        return sql
    except Exception as e:
        raise Exception(f"Error generating SQL: {str(e)}")


def execute_query(sql: str) -> dict:
    """Execute SQL query and return results."""
    try:
        results = snowflake_client.execute_query(sql)
        return results
    except Exception as e:
        raise Exception(f"Error executing query: {str(e)}")


def generate_answer(question: str, sql: str, data: dict) -> str:
    """Generate a human-readable answer from query results."""
    try:
        # Format data for Claude
        if data.get("rows"):
            data_summary = f"Query returned {len(data['rows'])} rows with columns: {', '.join(data['columns'])}\n\nData: {str(data['rows'][:10])}"
        else:
            data_summary = "No data returned from query."
        
        response = client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=300,
            system=ANSWER_SYSTEM,
            messages=[
                {
                    "role": "user",
                    "content": f"Question: {question}\n\nSQL Query: {sql}\n\n{data_summary}\n\nProvide a clear, business-friendly answer."
                }
            ]
        )
        answer = response.content[0].text.strip()
        return answer
    except Exception as e:
        raise Exception(f"Error generating answer: {str(e)}")


def process_question(question: str) -> dict:
    """Main function: question -> SQL -> results -> human answer."""
    try:
        # Step 1: Convert question to SQL
        sql = nl_to_sql(question)
        
        # Step 2: Execute SQL
        data = execute_query(sql)
        
        # Step 3: Generate human-readable answer
        answer = generate_answer(question, sql, data)
        
        return {
            "question": question,
            "sql": sql,
            "answer": answer,
            "data": data.get("rows", []),
            "columns": data.get("columns", [])
        }
    except Exception as e:
        return {
            "question": question,
            "error": str(e),
            "answer": "Something went wrong while processing your question. Please try again."
        }
