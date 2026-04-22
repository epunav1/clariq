import anthropic
import os
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv(dotenv_path=os.path.expanduser("~/Downloads/clariq/backend-complete/.env"))

SCHEMA = """
Tables in CLARIQ_DB.SHOPIFY_RAW:

RAW_ORDERS: order_id (VARCHAR), created_at (TIMESTAMP), customer_id (VARCHAR), 
            email (VARCHAR), total_price (FLOAT), subtotal_price (FLOAT), 
            total_tax (FLOAT), financial_status (VARCHAR), 
            fulfillment_status (VARCHAR), currency (VARCHAR), source_name (VARCHAR)

RAW_CUSTOMERS: customer_id (VARCHAR), created_at (TIMESTAMP), email (VARCHAR), 
               first_name (VARCHAR), last_name (VARCHAR), orders_count (INT), 
               total_spent (FLOAT), city (VARCHAR), country (VARCHAR), tags (VARCHAR)

RAW_PRODUCTS: product_id (VARCHAR), created_at (TIMESTAMP), title (VARCHAR), 
              product_type (VARCHAR), vendor (VARCHAR), status (VARCHAR), 
              price (FLOAT), inventory_quantity (INT)

RAW_ORDER_LINE_ITEMS: line_item_id (VARCHAR), order_id (VARCHAR), 
                      product_id (VARCHAR), title (VARCHAR), quantity (INT), 
                      price (FLOAT), sku (VARCHAR), fulfillment_status (VARCHAR)
"""


def get_client():
    """Get Anthropic client with API key from environment."""
    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        raise ValueError("ANTHROPIC_API_KEY not set in environment")
    return anthropic.Anthropic(api_key=api_key)


def question_to_sql(question: str) -> str:
    """Convert a natural language question to Snowflake SQL."""
    client = get_client()
    
    message = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=1000,
        messages=[
            {
                "role": "user",
                "content": f"""You are a Snowflake SQL expert for an e-commerce store.

Given this schema:
{SCHEMA}

Convert this question to a Snowflake SQL query.

Rules:
- Return ONLY the SQL query, nothing else
- No explanation, no markdown, no backticks
- Use proper Snowflake syntax
- Always use fully qualified table names: CLARIQ_DB.SHOPIFY_RAW.TABLE_NAME
- For date filters, use CURRENT_DATE() and DATEADD()
- Limit results to 50 rows max unless the question asks for a specific number
- For "this month" use WHERE created_at >= DATE_TRUNC('MONTH', CURRENT_DATE())
- For "this year" use WHERE created_at >= DATE_TRUNC('YEAR', CURRENT_DATE())

Question: {question}"""
            }
        ]
    )
    sql = message.content[0].text.strip()
    # Remove any markdown backticks if Claude adds them anyway
    if sql.startswith("```"):
        sql = sql.split("\n", 1)[1] if "\n" in sql else sql[3:]
    if sql.endswith("```"):
        sql = sql[:-3]
    return sql.strip()


def generate_answer(question: str, columns: list, rows: list) -> str:
    """Take raw SQL results and generate a human-readable answer."""
    client = get_client()
    
    # Format the data for Claude
    if not rows:
        return "No data found for your question. Try rephrasing or check if your store has data for that time period."

    # Limit data sent to Claude to avoid token waste
    sample_rows = rows[:20]
    data_str = f"Columns: {columns}\nRows:\n"
    for row in sample_rows:
        data_str += str(row) + "\n"
    if len(rows) > 20:
        data_str += f"... and {len(rows) - 20} more rows\n"

    message = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=500,
        messages=[
            {
                "role": "user",
                "content": f"""You are clariq, a friendly commerce analytics assistant.

A store owner asked: "{question}"

Here is the data from their store:
{data_str}

Give a clear, concise answer in plain English. Include the key numbers.
Format currency with $ and commas. Keep it to 2-3 sentences max.
Do NOT mention SQL, databases, tables, or technical terms.
Speak directly to the store owner as "you" / "your"."""
            }
        ]
    )
    return message.content[0].text.strip()


if __name__ == "__main__":
    test_questions = [
        "What are my top 5 customers by total spending?",
        "What is my total revenue?",
        "Which products have the most orders?"
    ]

    for q in test_questions:
        print(f"\nQuestion: {q}")
        sql = question_to_sql(q)
        print(f"SQL: {sql}")
