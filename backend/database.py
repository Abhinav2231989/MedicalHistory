import aiosqlite
import os
from pathlib import Path
import logging
from datetime import datetime

logger = logging.getLogger(__name__)

DB_PATH = Path(__file__).parent / 'medical_records.db'

class Database:
    def __init__(self):
        self.db_path = DB_PATH
        
    async def init_db(self):
        """Initialize database with required tables"""
        async with aiosqlite.connect(self.db_path) as db:
            # Users table
            await db.execute('''
                CREATE TABLE IF NOT EXISTS users (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    phone_number TEXT UNIQUE NOT NULL,
                    first_name TEXT NOT NULL,
                    last_name TEXT NOT NULL,
                    email TEXT NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            # Settings table for PIN
            await db.execute('''
                CREATE TABLE IF NOT EXISTS settings (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    setting_key TEXT UNIQUE NOT NULL,
                    setting_value TEXT NOT NULL,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            # Patient records table (with user_id foreign key)
            await db.execute('''
                CREATE TABLE IF NOT EXISTS patient_records (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL,
                    patient_id TEXT NOT NULL,
                    patient_name TEXT NOT NULL,
                    diagnosis_details TEXT NOT NULL,
                    medicine_names TEXT NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (user_id) REFERENCES users (id)
                )
            ''')
            
            # Google Drive credentials table
            await db.execute('''
                CREATE TABLE IF NOT EXISTS drive_credentials (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id TEXT UNIQUE NOT NULL,
                    access_token TEXT,
                    refresh_token TEXT,
                    token_uri TEXT,
                    client_id TEXT,
                    client_secret TEXT,
                    scopes TEXT,
                    expiry TEXT,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            # Storage sync log
            await db.execute('''
                CREATE TABLE IF NOT EXISTS sync_log (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    sync_type TEXT NOT NULL,
                    file_name TEXT,
                    file_size INTEGER,
                    drive_file_id TEXT,
                    status TEXT,
                    synced_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            await db.commit()
            logger.info("Database initialized successfully")
    
    async def get_next_patient_id(self, patient_name: str) -> str:
        """Generate or retrieve patient ID based on patient name"""
        async with aiosqlite.connect(self.db_path) as db:
            # Check if patient name already exists
            async with db.execute(
                'SELECT patient_id FROM patient_records WHERE LOWER(patient_name) = LOWER(?) LIMIT 1',
                (patient_name,)
            ) as cursor:
                row = await cursor.fetchone()
                if row:
                    return row[0]
            
            # Generate new patient ID
            async with db.execute('SELECT COUNT(DISTINCT patient_id) FROM patient_records') as cursor:
                count = await cursor.fetchone()
                next_id = (count[0] if count else 0) + 1
                return f"P{next_id:04d}"  # P0001, P0002, etc.
    
    async def get_db_size(self) -> int:
        """Get database file size in bytes"""
        if self.db_path.exists():
            return self.db_path.stat().st_size
        return 0
    
    async def get_storage_stats(self):
        """Get storage statistics"""
        async with aiosqlite.connect(self.db_path) as db:
            async with db.execute('SELECT COUNT(*) FROM patient_records') as cursor:
                total_records = (await cursor.fetchone())[0]
        
        db_size_bytes = await self.get_db_size()
        storage_used_mb = db_size_bytes / (1024 * 1024)
        
        # Assume max mobile storage allocation is 50MB
        max_storage_mb = 50
        storage_percentage = (storage_used_mb / max_storage_mb) * 100
        
        return {
            'total_records': total_records,
            'storage_used_mb': round(storage_used_mb, 2),
            'storage_percentage': round(storage_percentage, 2),
            'db_size_bytes': db_size_bytes
        }

db_instance = Database()