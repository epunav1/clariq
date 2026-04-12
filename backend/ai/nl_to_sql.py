import anthropic
import os
from dotenv import load_dotenv

load_dotenv()

client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))

SCHEMA = """
Tables in CLARIQ_DB.SHOPIFY_RAW:

RAW_ORDERS: order_id, created_at, customer_id, email, total_price,
            subtotal_price, total_tax, financial_status,
            fulfillment_status, currency, source_name

RAW_CUSTOMERS: customer_id, created_at, email, first_name, last_name,
               orders_count, total_spent, city, country, tags

RAW_PRODUCTS: product_id, created_at, title, product_type, vendor,
              status, price, inventory_quantity

RAW_ORDER_LINE_ITEMS: line_item_id, order_id, product_id, title,
                      quantity, price, sku, fulfillment_status
"""

def question_to_sql(question: str) -> str:
    message = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=1000,
        messages=[
            {
                "role": "user",
                "content": f"""You are a Snowflake SQL expert for a Shopify store.
                
Given this schema:
{SCHEMA}

Convert this question to a Snowflake SQL query.
Return ONLY the SQL query, nothing else. No explanation, no markdown, no backticks.

Question: {question}"""
            }
        ]
    )
    return message.content[0].text.strip()

if __name__ == "__main__":
    test_questions = [
        "What are my top 5 customers by total spending?",
        "What is my total revenue this year?",
        "Which products have the most orders?"
    ]
    
    for q in test_questions:
        print(f"\nQuestion: {q}")
        sql = question_to_sql(q)
        print(f"SQL: {sql}")