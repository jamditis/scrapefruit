"""Database inspection endpoints for viewing raw data."""

from flask import Blueprint, request, jsonify
from sqlalchemy import text, inspect

from database.connection import get_session, engine

database_bp = Blueprint("database", __name__)

# Allowed tables for browsing
ALLOWED_TABLES = ["jobs", "urls", "extraction_rules", "results", "app_settings", "templates"]


@database_bp.route("/tables", methods=["GET"])
def list_tables():
    """List all tables with row counts."""
    session = get_session()
    tables = []

    for table_name in ALLOWED_TABLES:
        try:
            result = session.execute(text(f"SELECT COUNT(*) FROM {table_name}"))
            count = result.scalar()
            tables.append({"name": table_name, "row_count": count})
        except Exception:
            # Table might not exist yet
            pass

    return jsonify({"tables": tables})


@database_bp.route("/tables/<table_name>/schema", methods=["GET"])
def get_table_schema(table_name: str):
    """Get column info for a table."""
    if table_name not in ALLOWED_TABLES:
        return jsonify({"error": f"Table '{table_name}' not allowed"}), 400

    try:
        inspector = inspect(engine)
        columns = inspector.get_columns(table_name)

        schema = []
        for col in columns:
            schema.append({
                "name": col["name"],
                "type": str(col["type"]),
                "nullable": col.get("nullable", True),
                "primary_key": col.get("primary_key", False),
            })

        return jsonify({"table": table_name, "columns": schema})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@database_bp.route("/tables/<table_name>/rows", methods=["GET"])
def get_table_rows(table_name: str):
    """Get paginated rows from a table."""
    if table_name not in ALLOWED_TABLES:
        return jsonify({"error": f"Table '{table_name}' not allowed"}), 400

    limit = min(request.args.get("limit", 50, type=int), 500)
    offset = request.args.get("offset", 0, type=int)

    session = get_session()

    try:
        # Get total count
        count_result = session.execute(text(f"SELECT COUNT(*) FROM {table_name}"))
        total = count_result.scalar()

        # Get rows
        result = session.execute(
            text(f"SELECT * FROM {table_name} LIMIT :limit OFFSET :offset"),
            {"limit": limit, "offset": offset}
        )

        # Convert to list of dicts
        columns = result.keys()
        rows = []
        for row in result:
            rows.append(dict(zip(columns, row)))

        return jsonify({
            "table": table_name,
            "rows": rows,
            "total": total,
            "limit": limit,
            "offset": offset,
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@database_bp.route("/query", methods=["POST"])
def execute_query():
    """Execute a raw SQL query (SELECT only for safety)."""
    data = request.get_json()
    sql = data.get("sql", "").strip()

    if not sql:
        return jsonify({"error": "No SQL query provided"}), 400

    # Security: Only allow SELECT statements
    sql_upper = sql.upper()
    if not sql_upper.startswith("SELECT"):
        return jsonify({"error": "Only SELECT queries are allowed"}), 400

    # Block dangerous keywords
    dangerous = ["INSERT", "UPDATE", "DELETE", "DROP", "ALTER", "CREATE", "TRUNCATE", "EXEC", "EXECUTE"]
    for keyword in dangerous:
        if keyword in sql_upper:
            return jsonify({"error": f"Query contains forbidden keyword: {keyword}"}), 400

    session = get_session()

    try:
        result = session.execute(text(sql))
        columns = list(result.keys())
        rows = []

        for row in result:
            rows.append(dict(zip(columns, row)))

        return jsonify({
            "success": True,
            "columns": columns,
            "rows": rows,
            "row_count": len(rows),
        })
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 400
