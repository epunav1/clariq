import snowflake.connector
import os

def get_connection():
    return snowflake.connector.connect(
        account=os.getenv("SNOWFLAKE_ACCOUNT"),
        user=os.getenv("SNOWFLAKE_USER"),
        password=os.getenv("SNOWFLAKE_PASSWORD"),
        warehouse=os.getenv("SNOWFLAKE_WAREHOUSE"),
        database=os.getenv("SNOWFLAKE_DATABASE"),
        schema=os.getenv("SNOWFLAKE_SCHEMA"),
        login_timeout=15,
        network_timeout=30,
    )


def run_query(sql: str):
    conn = None
    cursor = None
    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute(sql)
        columns = [desc[0] for desc in cursor.description]
        rows = cursor.fetchall()
        # Convert rows to serializable format
        clean_rows = []
        for row in rows:
            clean_row = []
            for val in row:
                if val is None:
                    clean_row.append(None)
                elif isinstance(val, (int, float, str, bool)):
                    clean_row.append(val)
                else:
                    clean_row.append(str(val))
            clean_rows.append(clean_row)
        return {"columns": columns, "rows": clean_rows}
    except snowflake.connector.errors.ProgrammingError as e:
        return {"error": f"Query error: {str(e)}"}
    except snowflake.connector.errors.DatabaseError as e:
        return {"error": f"Database error: {str(e)}"}
    except Exception as e:
        return {"error": f"Unexpected error: {str(e)}"}
    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()


def test_connection():
    """Test if Snowflake connection works."""
    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT 1")
        cursor.close()
        conn.close()
        return True
    except Exception:
        return False


if __name__ == "__main__":
    if test_connection():
        print("Snowflake connected successfully")
    else:
        print("Connection failed")
