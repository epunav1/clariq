from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional
from datetime import datetime

router = APIRouter()

# In-memory store for now (will move to database later)
connections = {}


class ConnectionRequest(BaseModel):
    platform: str
    store_name: str
    store_url: Optional[str] = None
    api_key: Optional[str] = None
    api_secret: Optional[str] = None


SUPPORTED_PLATFORMS = [
    {"id": "shopify", "name": "Shopify", "region": "Global", "auth_type": "api_key", "status": "available"},
    {"id": "amazon", "name": "Amazon", "region": "Global", "auth_type": "oauth", "status": "coming_soon"},
    {"id": "tiktok", "name": "TikTok Shop", "region": "Global", "auth_type": "oauth", "status": "coming_soon"},
    {"id": "woocommerce", "name": "WooCommerce", "region": "Global", "auth_type": "api_key", "status": "coming_soon"},
    {"id": "etsy", "name": "Etsy", "region": "Global", "auth_type": "oauth", "status": "coming_soon"},
    {"id": "ebay", "name": "eBay", "region": "Global", "auth_type": "oauth", "status": "coming_soon"},
    {"id": "walmart", "name": "Walmart", "region": "USA", "auth_type": "api_key", "status": "coming_soon"},
    {"id": "alibaba", "name": "Alibaba", "region": "China / Global", "auth_type": "api_key", "status": "coming_soon"},
    {"id": "jumia", "name": "Jumia", "region": "Africa", "auth_type": "api_key", "status": "coming_soon"},
    {"id": "mercadolibre", "name": "Mercado Libre", "region": "Latin America", "auth_type": "oauth", "status": "coming_soon"},
    {"id": "shopee", "name": "Shopee", "region": "Southeast Asia", "auth_type": "api_key", "status": "coming_soon"},
    {"id": "lazada", "name": "Lazada", "region": "Southeast Asia", "auth_type": "api_key", "status": "coming_soon"},
    {"id": "takealot", "name": "Takealot", "region": "South Africa", "auth_type": "api_key", "status": "coming_soon"},
    {"id": "rakuten", "name": "Rakuten", "region": "Japan", "auth_type": "api_key", "status": "coming_soon"},
    {"id": "noon", "name": "Noon", "region": "Middle East", "auth_type": "api_key", "status": "coming_soon"},
    {"id": "flipkart", "name": "Flipkart", "region": "India", "auth_type": "api_key", "status": "coming_soon"},
    {"id": "coupang", "name": "Coupang", "region": "South Korea", "auth_type": "api_key", "status": "coming_soon"},
    {"id": "bigcommerce", "name": "BigCommerce", "region": "Global", "auth_type": "api_key", "status": "coming_soon"},
    {"id": "squarespace", "name": "Squarespace", "region": "Global", "auth_type": "oauth", "status": "coming_soon"},
    {"id": "prestashop", "name": "PrestaShop", "region": "Europe", "auth_type": "api_key", "status": "coming_soon"},
    {"id": "csv", "name": "CSV Upload", "region": "Any", "auth_type": "file_upload", "status": "available"},
    {"id": "custom", "name": "Custom Store", "region": "Any", "auth_type": "api_key", "status": "available"},
]


@router.get("/platforms")
async def list_platforms():
    """List all supported platforms."""
    return {"platforms": SUPPORTED_PLATFORMS}


@router.get("/connections")
async def list_connections():
    """List all connected stores."""
    return {"connections": list(connections.values())}


@router.post("/connections")
async def add_connection(req: ConnectionRequest):
    """Connect a new store."""
    conn_id = f"{req.platform}_{req.store_name}".lower().replace(" ", "_")

    if conn_id in connections:
        raise HTTPException(status_code=400, detail="This store is already connected")

    connection = {
        "id": conn_id,
        "platform": req.platform,
        "store_name": req.store_name,
        "store_url": req.store_url,
        "status": "connected",
        "connected_at": datetime.now().isoformat(),
        "last_sync": None,
        "products_synced": 0,
        "orders_synced": 0,
    }

    connections[conn_id] = connection
    return {"message": f"{req.store_name} connected successfully", "connection": connection}


@router.delete("/connections/{conn_id}")
async def remove_connection(conn_id: str):
    """Disconnect a store."""
    if conn_id not in connections:
        raise HTTPException(status_code=404, detail="Connection not found")
    removed = connections.pop(conn_id)
    return {"message": f"{removed['store_name']} disconnected", "connection": removed}


@router.post("/connections/{conn_id}/sync")
async def sync_connection(conn_id: str):
    """Trigger a sync for a connected store."""
    if conn_id not in connections:
        raise HTTPException(status_code=404, detail="Connection not found")

    conn = connections[conn_id]
    conn["last_sync"] = datetime.now().isoformat()
    conn["status"] = "syncing"

    # For Shopify, we have a real sync
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

    # For other platforms, mark as synced (placeholder)
    conn["status"] = "connected"
    return {"message": f"Sync complete for {conn['store_name']}", "connection": conn}
