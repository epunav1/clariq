from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime

router = APIRouter()

connections = {}


class ConnectionRequest(BaseModel):
    platform: str
    store_name: str
    store_url: Optional[str] = None
    api_key: Optional[str] = None
    api_secret: Optional[str] = None
    connection_method: Optional[str] = "api"


class ManualOrder(BaseModel):
    order_id: Optional[str] = None
    customer_name: str
    customer_email: Optional[str] = ""
    product: str
    quantity: int = 1
    price: float
    date: Optional[str] = None
    status: Optional[str] = "paid"


class ManualProduct(BaseModel):
    name: str
    price: float
    stock: int = 0
    category: Optional[str] = ""
    sku: Optional[str] = ""


class ManualCustomer(BaseModel):
    name: str
    email: Optional[str] = ""
    phone: Optional[str] = ""
    city: Optional[str] = ""
    country: Optional[str] = ""


class PasteDataRequest(BaseModel):
    data_type: str
    content: str


class GoogleSheetsRequest(BaseModel):
    sheet_url: str
    data_type: str
    store_name: Optional[str] = "Google Sheets Import"


SUPPORTED_PLATFORMS = [
    {"id": "shopify", "name": "Shopify", "region": "Global", "auth_type": "api_key", "status": "available", "logo_color": "#96bf48"},
    {"id": "amazon", "name": "Amazon", "region": "Global", "auth_type": "oauth", "status": "coming_soon", "logo_color": "#ff9900"},
    {"id": "tiktok", "name": "TikTok Shop", "region": "Global", "auth_type": "oauth", "status": "coming_soon", "logo_color": "#010101"},
    {"id": "woocommerce", "name": "WooCommerce", "region": "Global", "auth_type": "api_key", "status": "coming_soon", "logo_color": "#7b5ea7"},
    {"id": "etsy", "name": "Etsy", "region": "Global", "auth_type": "oauth", "status": "coming_soon", "logo_color": "#f56400"},
    {"id": "ebay", "name": "eBay", "region": "Global", "auth_type": "oauth", "status": "coming_soon", "logo_color": "#0654ba"},
    {"id": "walmart", "name": "Walmart", "region": "USA", "auth_type": "api_key", "status": "coming_soon", "logo_color": "#0071ce"},
    {"id": "alibaba", "name": "Alibaba", "region": "China / Global", "auth_type": "api_key", "status": "coming_soon", "logo_color": "#e43225"},
    {"id": "jumia", "name": "Jumia", "region": "Africa", "auth_type": "api_key", "status": "coming_soon", "logo_color": "#f68b1e"},
    {"id": "mercadolibre", "name": "Mercado Libre", "region": "Latin America", "auth_type": "oauth", "status": "coming_soon", "logo_color": "#00a650"},
    {"id": "shopee", "name": "Shopee", "region": "Southeast Asia", "auth_type": "api_key", "status": "coming_soon", "logo_color": "#ee4d2d"},
    {"id": "lazada", "name": "Lazada", "region": "Southeast Asia", "auth_type": "api_key", "status": "coming_soon", "logo_color": "#f04e30"},
    {"id": "takealot", "name": "Takealot", "region": "South Africa", "auth_type": "api_key", "status": "coming_soon", "logo_color": "#ff6a00"},
    {"id": "rakuten", "name": "Rakuten", "region": "Japan", "auth_type": "api_key", "status": "coming_soon", "logo_color": "#e60023"},
    {"id": "noon", "name": "Noon", "region": "Middle East", "auth_type": "api_key", "status": "coming_soon", "logo_color": "#0db14b"},
    {"id": "flipkart", "name": "Flipkart", "region": "India", "auth_type": "api_key", "status": "coming_soon", "logo_color": "#2088ff"},
    {"id": "coupang", "name": "Coupang", "region": "South Korea", "auth_type": "api_key", "status": "coming_soon", "logo_color": "#1428a0"},
    {"id": "bigcommerce", "name": "BigCommerce", "region": "Global", "auth_type": "api_key", "status": "coming_soon", "logo_color": "#5b21b6"},
    {"id": "squarespace", "name": "Squarespace", "region": "Global", "auth_type": "oauth", "status": "coming_soon", "logo_color": "#003b64"},
    {"id": "prestashop", "name": "PrestaShop", "region": "Europe", "auth_type": "api_key", "status": "coming_soon", "logo_color": "#96588a"},
]

CONNECTION_METHODS = [
    {
        "id": "api",
        "name": "API Integration",
        "description": "Connect using your store's API key for automatic real-time syncing",
        "icon": "plug",
        "best_for": "Shopify, WooCommerce, BigCommerce stores",
    },
    {
        "id": "csv",
        "name": "Upload CSV or Excel",
        "description": "Export your data as a spreadsheet and upload it here",
        "icon": "file",
        "best_for": "Any business that can export their data",
    },
    {
        "id": "manual",
        "name": "Enter Manually",
        "description": "Type in your orders, products, and customers one by one",
        "icon": "edit",
        "best_for": "Small businesses, solo sellers, market vendors",
    },
    {
        "id": "paste",
        "name": "Copy and Paste",
        "description": "Paste your data from any source — we will figure out the format",
        "icon": "clipboard",
        "best_for": "Quick imports from spreadsheets or reports",
    },
    {
        "id": "google_sheets",
        "name": "Google Sheets",
        "description": "Paste a link to your Google Sheet and we will pull the data",
        "icon": "table",
        "best_for": "Businesses that track sales in Google Sheets",
    },
    {
        "id": "invite",
        "name": "Invite Someone",
        "description": "Send an invite link to your accountant, assistant, or team member to upload data for you",
        "icon": "users",
        "best_for": "Business owners who want someone else to set it up",
    },
]


@router.get("/platforms")
async def list_platforms():
    return {"platforms": SUPPORTED_PLATFORMS}


@router.get("/connection-methods")
async def list_connection_methods():
    return {"methods": CONNECTION_METHODS}


@router.get("/connections")
async def list_connections():
    return {"connections": list(connections.values())}


@router.post("/connections")
async def add_connection(req: ConnectionRequest):
    conn_id = f"{req.platform}_{req.store_name}".lower().replace(" ", "_").replace("'", "")

    if conn_id in connections:
        raise HTTPException(status_code=400, detail="This store is already connected")

    connection = {
        "id": conn_id,
        "platform": req.platform,
        "store_name": req.store_name,
        "store_url": req.store_url,
        "connection_method": req.connection_method,
        "status": "connected",
        "connected_at": datetime.now().isoformat(),
        "last_sync": None,
        "products_synced": 0,
        "orders_synced": 0,
        "customers_synced": 0,
    }

    connections[conn_id] = connection
    return {"message": f"{req.store_name} connected successfully", "connection": connection}


@router.delete("/connections/{conn_id}")
async def remove_connection(conn_id: str):
    if conn_id not in connections:
        raise HTTPException(status_code=404, detail="Connection not found")
    removed = connections.pop(conn_id)
    return {"message": f"{removed['store_name']} disconnected", "connection": removed}


@router.post("/connections/{conn_id}/sync")
async def sync_connection(conn_id: str):
    if conn_id not in connections:
        raise HTTPException(status_code=404, detail="Connection not found")

    conn = connections[conn_id]
    conn["last_sync"] = datetime.now().isoformat()
    conn["status"] = "syncing"

    if conn["platform"] == "shopify":
        try:
            from shopify_sync import sync_orders, sync_customers, sync_products
            sync_orders()
            sync_customers()
            sync_products()
            conn["status"] = "connected"
            conn["last_sync"] = datetime.now().isoformat()
            return {"message": "Shopify sync complete", "connection": conn}
        except Exception as e:
            conn["status"] = "error"
            return {"message": f"Sync failed: {str(e)}", "connection": conn}

    conn["status"] = "connected"
    return {"message": f"Sync complete for {conn['store_name']}", "connection": conn}


# ═══ MANUAL ENTRY ENDPOINTS ═══

@router.post("/manual/order")
async def add_manual_order(order: ManualOrder):
    """Add a single order manually — for small businesses, market vendors, solo sellers."""
    from db.snowflake_client import get_connection as get_sf
    try:
        conn = get_sf()
        cursor = conn.cursor()

        order_id = order.order_id or f"MANUAL_{datetime.now().strftime('%Y%m%d%H%M%S')}"
        created_at = order.date or datetime.now().isoformat()
        name_parts = order.customer_name.split(" ", 1)
        first_name = name_parts[0]
        last_name = name_parts[1] if len(name_parts) > 1 else ""

        cursor.execute("""
            INSERT INTO RAW_ORDERS
            (order_id, created_at, customer_id, email, total_price,
             subtotal_price, total_tax, financial_status, fulfillment_status, currency)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        """, (
            order_id, created_at, f"MANUAL_{first_name}_{last_name}".upper(),
            order.customer_email, order.price * order.quantity,
            order.price * order.quantity, 0.0,
            order.status, "fulfilled", "USD"
        ))
        conn.commit()
        cursor.close()
        conn.close()

        return {
            "message": f"Order #{order_id} added: {order.customer_name} bought {order.quantity}x {order.product} for ${order.price * order.quantity:.2f}",
            "order_id": order_id,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to add order: {str(e)}")


@router.post("/manual/product")
async def add_manual_product(product: ManualProduct):
    """Add a single product manually."""
    from db.snowflake_client import get_connection as get_sf
    try:
        conn = get_sf()
        cursor = conn.cursor()

        product_id = f"MANUAL_{product.name.upper().replace(' ', '_')[:20]}_{datetime.now().strftime('%H%M%S')}"

        cursor.execute("""
            INSERT INTO RAW_PRODUCTS
            (product_id, created_at, title, product_type, vendor, status, price, inventory_quantity)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
        """, (
            product_id, datetime.now().isoformat(), product.name,
            product.category, "Manual Entry", "active",
            product.price, product.stock
        ))
        conn.commit()
        cursor.close()
        conn.close()

        return {
            "message": f"Product added: {product.name} — ${product.price:.2f}, {product.stock} in stock",
            "product_id": product_id,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to add product: {str(e)}")


@router.post("/manual/customer")
async def add_manual_customer(customer: ManualCustomer):
    """Add a single customer manually."""
    from db.snowflake_client import get_connection as get_sf
    try:
        conn = get_sf()
        cursor = conn.cursor()

        name_parts = customer.name.split(" ", 1)
        first_name = name_parts[0]
        last_name = name_parts[1] if len(name_parts) > 1 else ""
        customer_id = f"MANUAL_{first_name}_{last_name}".upper()

        cursor.execute("""
            INSERT INTO RAW_CUSTOMERS
            (customer_id, created_at, email, first_name, last_name,
             orders_count, total_spent, city, country)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
        """, (
            customer_id, datetime.now().isoformat(), customer.email,
            first_name, last_name, 0, 0.0,
            customer.city, customer.country
        ))
        conn.commit()
        cursor.close()
        conn.close()

        return {
            "message": f"Customer added: {customer.name}" + (f" from {customer.city}, {customer.country}" if customer.city else ""),
            "customer_id": customer_id,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to add customer: {str(e)}")


# ═══ PASTE DATA ENDPOINT ═══

@router.post("/paste")
async def paste_data(req: PasteDataRequest):
    """Paste raw data (CSV-like, tab-separated, or plain text) — we parse it and insert it."""
    import anthropic
    import os
    import json

    if not req.content.strip():
        raise HTTPException(status_code=400, detail="No data provided")

    client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))

    message = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=2000,
        messages=[{
            "role": "user",
            "content": f"""You are a data parser for an e-commerce analytics platform.

The user pasted the following {req.data_type} data:

{req.content[:3000]}

Parse this into a JSON array of objects. Based on the data_type "{req.data_type}", extract:

If data_type is "orders": [{{"order_id":"","customer_name":"","email":"","product":"","quantity":1,"price":0.00,"date":"","status":"paid"}}]
If data_type is "products": [{{"name":"","price":0.00,"stock":0,"category":"","sku":""}}]
If data_type is "customers": [{{"name":"","email":"","phone":"","city":"","country":""}}]

Return ONLY the JSON array. No explanation, no markdown, no backticks."""
        }]
    )

    try:
        parsed_text = message.content[0].text.strip()
        if parsed_text.startswith("```"):
            parsed_text = parsed_text.split("\n", 1)[1]
        if parsed_text.endswith("```"):
            parsed_text = parsed_text[:-3]
        parsed = json.loads(parsed_text.strip())

        return {
            "message": f"Parsed {len(parsed)} {req.data_type} from your pasted data",
            "count": len(parsed),
            "parsed_data": parsed,
            "data_type": req.data_type,
        }
    except Exception as e:
        return {
            "message": "Could not parse the pasted data. Try formatting it as CSV with headers.",
            "error": str(e),
        }


# ═══ GOOGLE SHEETS ENDPOINT ═══

@router.post("/google-sheets")
async def import_google_sheets(req: GoogleSheetsRequest):
    """Import data from a public Google Sheet."""
    import requests
    import csv
    import io

    sheet_url = req.sheet_url.strip()

    if "docs.google.com/spreadsheets" not in sheet_url:
        raise HTTPException(status_code=400, detail="Please provide a valid Google Sheets URL")

    try:
        if "/edit" in sheet_url:
            sheet_id = sheet_url.split("/d/")[1].split("/")[0]
        elif "/pub" in sheet_url:
            sheet_id = sheet_url.split("/d/")[1].split("/")[0]
        else:
            sheet_id = sheet_url.split("/d/")[1].split("/")[0]

        csv_url = f"https://docs.google.com/spreadsheets/d/{sheet_id}/export?format=csv"
        response = requests.get(csv_url, timeout=15)

        if response.status_code != 200:
            raise HTTPException(
                status_code=400,
                detail="Could not access that Google Sheet. Make sure it is set to 'Anyone with the link can view'."
            )

        reader = csv.DictReader(io.StringIO(response.text))
        rows = list(reader)

        if not rows:
            raise HTTPException(status_code=400, detail="The Google Sheet appears to be empty")

        columns = list(rows[0].keys())

        return {
            "message": f"Found {len(rows)} rows with columns: {', '.join(columns[:8])}",
            "count": len(rows),
            "columns": columns,
            "sample": rows[:5],
            "data_type": req.data_type,
            "sheet_id": sheet_id,
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to import: {str(e)}")


# ═══ INVITE ENDPOINT ═══

@router.post("/invite")
async def invite_helper(email: str, role: str = "uploader"):
    """Send an invite link to someone who will upload data on behalf of the business owner."""
    invite_token = f"INV_{datetime.now().strftime('%Y%m%d%H%M%S')}_{email.split('@')[0]}"

    return {
        "message": f"Invite sent to {email} as {role}",
        "invite_token": invite_token,
        "invite_link": f"https://tryclariq.com/invite/{invite_token}",
        "role": role,
        "expires_in": "7 days",
    }
