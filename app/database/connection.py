"""Database connection utility and health check."""
import logging
from sqlalchemy import text
from app.extensions import db

logger = logging.getLogger(__name__)

def check_db_connection():
    """
    Test whether the database connection is alive and working.
    Returns:
        tuple (bool, str): (True, "Connection successful") or (False, error_message)
    """
    try:
        with db.engine.connect() as connection:
            result = connection.execute(text("SELECT 1")).scalar()
            if result == 1:
                return True, "Database connection successful."
            return False, "Unexpected result from database."
    except Exception as exc:
        logger.error(f"Database connection error: {exc}")
        return False, str(exc)
