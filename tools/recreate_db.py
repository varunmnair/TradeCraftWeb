"""Recreate database with fresh schema. Admin user must be created via /auth/register endpoint."""
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from db.database import engine, Base
from db import models  # noqa: F401 - ensures all models are registered

print("Models imported")

Base.metadata.create_all(bind=engine)
print("Tables created successfully")
print("NOTE: Create admin user via POST /auth/register endpoint")
