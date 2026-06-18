from functools import lru_cache

from pymongo import MongoClient
from pymongo.database import Database

from app.core.config import settings


@lru_cache
def get_client() -> MongoClient:
    client = MongoClient(settings.mongo_uri, serverSelectionTimeoutMS=5000)
    client.admin.command("ping")
    return client


def get_db() -> Database:
    return get_client()[settings.mongo_db_name]
