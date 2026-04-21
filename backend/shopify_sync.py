import requests
import snowflake.connector
import os
from dotenv import load_dotenv

load_dotenv()

SHOP = "shop-wit-sazy.myshopify.com"
TOKEN = os.getenv("SHOPIFY_TOKEN")
HEADERS = {"X-Shopify-Access-Token": TOKEN}

def get_connection():
    return snowflake.connector.connect(
        account=os.getenv("SNOWFLAKE_ACCOUNT"),
        user=os.getenv("SNOWFLAKE_USER"),
        password=os.getenv("SNOWFLAKE_PASSWORD"),
        warehouse=os.getenv("SNOWFLAKE_WAREHOUSE"),
        database=os.getenv("SNOWFLAKE_DATABASE"),
        schema=os.getenv("SNOWFLAKE_SCHEMA")
    )

def sync_orders():
    url = f"https://{SHOP}/admin/api/2024-01/orders.json?limit=250&status=any"
    r = requests.get(url, headers=HEADERS)
    orders = r.json().get("orders", [])
    conn = get_connection()
    cursor = conn.cursor()
    for o in orders:
        cursor.execute("""
            INSERT INTO RAW_ORDERS
            (order_id, created_at, customer_id, email, total_price,
             subtotal_price, total_tax, financial_status, fulfillment_status, currency)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        """, (
            str(o.get("id")), o.get("created_at"),
            str(o.get("customer", {}).get("id", "")), o.get("email", ""),
            float(o.get("total_price", 0)), float(o.get("subtotal_price", 0)),
            float(o.get("total_tax", 0)), o.get("financial_status", ""),
            o.get("fulfillment_status", ""), o.get("currency", "")
        ))
    conn.commit()
    cursor.close()
    conn.close()

def sync_customers():
    url = f"https://{SHOP}/admin/api/2024-01/customers.json?limit=250"
    r = requests.get(url, headers=HEADERS)
    customers = r.json().get("customers", [])
    conn = get_connection()
    cursor = conn.cursor()
    for c in customers:
        cursor.execute("""
            INSERT INTO RAW_CUSTOMERS
            (customer_id, created_at, email, first_name, last_name,
             orders_count, total_spent, city, country)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
        """, (
            str(c.get("id")), c.get("created_at"), c.get("email", ""),
            c.get("first_name", ""), c.get("last_name", ""),
            int(c.get("orders_count", 0)), float(c.get("total_spent", 0)),
            c.get("default_address", {}).get("city", ""),
            c.get("default_address", {}).get("country", "")
        ))
    conn.commit()
    cursor.close()
    conn.close()

def sync_products():
    url = f"https://{SHOP}/admin/api/2024-01/products.json?limit=250"
    r = requests.get(url, headers=HEADERS)
    products = r.json().get("products", [])
    conn = get_connection()
    cursor = conn.cursor()
    for p in products:
        variant = p.get("variants", [{}])[0]
        cursor.execute("""
            INSERT INTO RAW_PRODUCTS
            (product_id, created_at, title, product_type, vendor, status, price, inventory_quantity)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
        """, (
            str(p.get("id")), p.get("created_at"), p.get("title", ""),
            p.get("product_type", ""), p.get("vendor", ""),
            p.get("status", ""), float(variant.get("price", 0)),
            int(variant.get("inventory_quantity", 0))
        ))
    conn.commit()
    cursor.close()
    conn.close()

if __name__ == "__main__":
    sync_orders()
    sync_customers()
    sync_products()
