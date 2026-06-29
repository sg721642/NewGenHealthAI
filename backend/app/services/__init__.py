"""
NewGenHealthAI — services/__init__.py
Exports service singletons.
"""

from app.services.chat_service import ClinicalEngine, clinical_engine
from app.services.database_service import DatabaseService, db_service

__all__ = ["DatabaseService", "db_service", "ClinicalEngine", "clinical_engine"]
