import os
from urllib.parse import quote_plus
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

class Config:
    """Base configuration class."""
    SECRET_KEY = os.getenv("SECRET_KEY", "default-dev-secret-key-12345")
    
    # Database configuration
    DB_HOST = os.getenv("DB_HOST", "127.0.0.1")
    DB_PORT = os.getenv("DB_PORT", "3306")
    DB_NAME = os.getenv("DB_NAME", "ppw_pagerank")
    DB_USER = os.getenv("DB_USER", "root")
    DB_PASSWORD = os.getenv("DB_PASSWORD", "")
    
    # Construct MySQL SQLAlchemy database URI
    if DB_PASSWORD:
        _password_part = f":{quote_plus(DB_PASSWORD)}"
    else:
        _password_part = ""
        
    SQLALCHEMY_DATABASE_URI = (
        f"mysql+pymysql://{quote_plus(DB_USER)}{_password_part}@"
        f"{DB_HOST}:{DB_PORT}/{DB_NAME}?charset=utf8mb4"
    )
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SQLALCHEMY_ENGINE_OPTIONS = {
        "pool_recycle": 280,
        "pool_pre_ping": True,
    }

    # Crawler settings
    DEFAULT_START_URL = os.getenv("DEFAULT_START_URL", "https://trunojoyo.ac.id/")
    MAX_CRAWL_PAGES = int(os.getenv("MAX_CRAWL_PAGES", "300"))
    CRAWL_REQUEST_TIMEOUT = int(os.getenv("CRAWL_REQUEST_TIMEOUT", "10"))
    CRAWL_REQUEST_DELAY = float(os.getenv("CRAWL_REQUEST_DELAY", "0.5"))
    CRAWL_USER_AGENT = os.getenv(
        "CRAWL_USER_AGENT",
        "Mozilla/5.0 (compatible; PPW-PageRankBot/1.0; +https://trunojoyo.ac.id/)"
    )

    # PageRank settings
    PAGERANK_DAMPING_FACTOR = float(os.getenv("PAGERANK_DAMPING_FACTOR", "0.85"))
    PAGERANK_MAX_ITER = int(os.getenv("PAGERANK_MAX_ITER", "100"))
    PAGERANK_TOL = float(os.getenv("PAGERANK_TOL", "1e-6"))


class DevelopmentConfig(Config):
    DEBUG = True


class ProductionConfig(Config):
    DEBUG = False


class TestingConfig(Config):
    TESTING = True
    DEBUG = True


config_by_name = {
    "development": DevelopmentConfig,
    "production": ProductionConfig,
    "testing": TestingConfig,
    "default": DevelopmentConfig,
}
