from fastapi import APIRouter, UploadFile, File, HTTPException
from db.snowflake_client import get_connection
import csv
import io

router = APIRouter()


@router.post("/upload/orders")
async def upload_orders(file: UploadFile = File(...)):
    """Upload orders via CSV. Expected columns: order_id, created_at, customer_id, email, total_price, subtotal_price, total_tax, financial_status, fulfillment_status, currency"""
    if not file.filename.endswith(('.csv', '.CSV')):
        raise HTTPException(status_code=400, detail="Only CSV files are accepted")

    try:
        content = await file.read()
        decoded = content.decode('utf-8')
        reader = csv.DictReader(io.StringIO(decoded))
        rows = list(reader)

        if not rows:
            raise HTTPException(status_code=400, detail="CSV file is empty")

        conn = get_connection()
        cursor = conn.cursor()
        count = 0

        for row in rows:
            cursor.execute("""
                INSERT INTO RAW_ORDERS
                (order_id, created_at, customer_id, email, total_price,
                 subtotal_price, total_tax, financial_status, fulfillment_status, currency)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """, (
                str(row.get('order_id', '')),
                row.get('created_at', ''),
                str(row.get('customer_id', '')),
                row.get('email', ''),
                float(row.get('total_price', 0)),
                float(row.get('subtotal_price', 0)),
                float(row.get('total_tax', 0)),
                row.get('financial_status', ''),
                row.get('fulfillment_status', ''),
                row.get('currency', 'USD'),
            ))
            count += 1

        conn.commit()
        cursor.close()
        conn.close()

        return {"message": f"Uploaded {count} orders successfully", "count": count}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Upload failed: {str(e)}")


@router.post("/upload/customers")
async def upload_customers(file: UploadFile = File(...)):
    """Upload customers via CSV. Expected columns: customer_id, created_at, email, first_name, last_name, orders_count, total_spent, city, country"""
    if not file.filename.endswith(('.csv', '.CSV')):
        raise HTTPException(status_code=400, detail="Only CSV files are accepted")

    try:
        content = await file.read()
        decoded = content.decode('utf-8')
        reader = csv.DictReader(io.StringIO(decoded))
        rows = list(reader)

        if not rows:
            raise HTTPException(status_code=400, detail="CSV file is empty")

        conn = get_connection()
        cursor = conn.cursor()
        count = 0

        for row in rows:
            cursor.execute("""
                INSERT INTO RAW_CUSTOMERS
                (customer_id, created_at, email, first_name, last_name,
                 orders_count, total_spent, city, country)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
            """, (
                str(row.get('customer_id', '')),
                row.get('created_at', ''),
                row.get('email', ''),
                row.get('first_name', ''),
                row.get('last_name', ''),
                int(row.get('orders_count', 0)),
                float(row.get('total_spent', 0)),
                row.get('city', ''),
                row.get('country', ''),
            ))
            count += 1

        conn.commit()
        cursor.close()
        conn.close()

        return {"message": f"Uploaded {count} customers successfully", "count": count}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Upload failed: {str(e)}")


@router.post("/upload/products")
async def upload_products(file: UploadFile = File(...)):
    """Upload products via CSV. Expected columns: product_id, created_at, title, product_type, vendor, status, price, inventory_quantity"""
    if not file.filename.endswith(('.csv', '.CSV')):
        raise HTTPException(status_code=400, detail="Only CSV files are accepted")

    try:
        content = await file.read()
        decoded = content.decode('utf-8')
        reader = csv.DictReader(io.StringIO(decoded))
        rows = list(reader)

        if not rows:
            raise HTTPException(status_code=400, detail="CSV file is empty")

        conn = get_connection()
        cursor = conn.cursor()
        count = 0

        for row in rows:
            cursor.execute("""
                INSERT INTO RAW_PRODUCTS
                (product_id, created_at, title, product_type, vendor, status, price, inventory_quantity)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            """, (
                str(row.get('product_id', '')),
                row.get('created_at', ''),
                row.get('title', ''),
                row.get('product_type', ''),
                row.get('vendor', ''),
                row.get('status', 'active'),
                float(row.get('price', 0)),
                int(row.get('inventory_quantity', 0)),
            ))
            count += 1

        conn.commit()
        cursor.close()
        conn.close()

        return {"message": f"Uploaded {count} products successfully", "count": count}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Upload failed: {str(e)}")
