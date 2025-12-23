from fastapi import FastAPI, APIRouter, HTTPException, Query, UploadFile, File
from fastapi.responses import FileResponse, JSONResponse
from dotenv import load_dotenv
from starlette.middleware.cors import CORSMiddleware
import os
import logging
from pathlib import Path
from pydantic import BaseModel, Field
from typing import List, Optional
from datetime import datetime, timezone
import aiosqlite
import json
import tempfile
import shutil
import bcrypt

# Google Drive imports
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
from google_auth_oauthlib.flow import Flow
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request as GoogleRequest

# Configure logging first
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / '.env')

# Import database
from database import db_instance, DB_PATH

# Create the main app
app = FastAPI()
api_router = APIRouter(prefix="/api")

# Models
class PinLogin(BaseModel):
    pin: str
    full_name: str

class User(BaseModel):
    id: Optional[int] = None
    phone_number: str
    first_name: str
    last_name: str
    email: str
    created_at: Optional[str] = None

class UserRegister(BaseModel):
    phone_number: str
    first_name: str
    last_name: str
    email: str

class UserLogin(BaseModel):
    phone_number: str

class PatientRecord(BaseModel):
    id: Optional[int] = None
    user_id: int
    patient_id: str
    patient_name: str
    diagnosis_details: str
    medicine_names: str
    created_at: Optional[str] = None
    updated_at: Optional[str] = None

class PatientRecordCreate(BaseModel):
    patient_name: str
    diagnosis_details: str
    medicine_names: str

class PatientRecordUpdate(BaseModel):
    patient_name: Optional[str] = None
    diagnosis_details: Optional[str] = None
    medicine_names: Optional[str] = None

class StorageStats(BaseModel):
    total_records: int
    storage_used_mb: float
    storage_percentage: float
    needs_backup: bool

class VoiceSearchRequest(BaseModel):
    audio_base64: str
    

# Initialize database on startup
@app.on_event("startup")
async def startup():
    await db_instance.init_db()
    logger.info("Application started, database initialized")
    
    # Initialize PIN if not exists
    try:
        async with aiosqlite.connect(DB_PATH) as db:
            async with db.execute('SELECT setting_value FROM settings WHERE setting_key = ?', ('app_pin',)) as cursor:
                pin_row = await cursor.fetchone()
                
                if not pin_row:
                    # Hash the default PIN 258411
                    default_pin = "258411"
                    hashed_pin = bcrypt.hashpw(default_pin.encode('utf-8'), bcrypt.gensalt())
                    
                    await db.execute(
                        'INSERT INTO settings (setting_key, setting_value) VALUES (?, ?)',
                        ('app_pin', hashed_pin.decode('utf-8'))
                    )
                    await db.commit()
                    logger.info("Default PIN initialized")
    except Exception as e:
        logger.error(f"Error initializing PIN: {e}")


# Routes
@api_router.get("/")
async def root():
    return {"message": "Medical History System API with SQLite & Google Drive"}


# PIN Authentication
@api_router.post("/auth/validate-pin")
async def validate_pin(pin_data: PinLogin):
    """Validate PIN for app access"""
    try:
        async with aiosqlite.connect(DB_PATH) as db:
            async with db.execute(
                'SELECT setting_value FROM settings WHERE setting_key = ?',
                ('app_pin',)
            ) as cursor:
                row = await cursor.fetchone()
                
                if not row:
                    raise HTTPException(status_code=500, detail="PIN not configured")
                
                stored_hash = row[0].encode('utf-8')
                entered_pin = pin_data.pin.encode('utf-8')
                
                if bcrypt.checkpw(entered_pin, stored_hash):
                    return {"success": True, "message": "PIN validated successfully"}
                else:
                    return {"success": False, "message": "Incorrect PIN"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error validating PIN: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# Authentication Routes
@api_router.post("/auth/check-phone")
async def check_phone(login_data: UserLogin):
    """Check if phone number exists"""
    try:
        async with aiosqlite.connect(DB_PATH) as db:
            async with db.execute(
                'SELECT * FROM users WHERE phone_number = ?',
                (login_data.phone_number,)
            ) as cursor:
                row = await cursor.fetchone()
                
                if row:
                    return {
                        "exists": True,
                        "user": User(
                            id=row[0],
                            phone_number=row[1],
                            first_name=row[2],
                            last_name=row[3],
                            email=row[4],
                            created_at=row[5]
                        )
                    }
                else:
                    return {"exists": False}
    except Exception as e:
        logger.error(f"Error checking phone: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@api_router.post("/auth/register", response_model=User)
async def register_user(user_data: UserRegister):
    """Register a new user"""
    try:
        async with aiosqlite.connect(DB_PATH) as db:
            # Check if phone already exists
            async with db.execute(
                'SELECT id FROM users WHERE phone_number = ?',
                (user_data.phone_number,)
            ) as cursor:
                existing = await cursor.fetchone()
                if existing:
                    raise HTTPException(status_code=400, detail="Phone number already registered")
            
            # Insert new user
            cursor = await db.execute(
                '''
                INSERT INTO users (phone_number, first_name, last_name, email)
                VALUES (?, ?, ?, ?)
                ''',
                (user_data.phone_number, user_data.first_name, user_data.last_name, user_data.email)
            )
            await db.commit()
            user_id = cursor.lastrowid
            
            # Fetch the created user
            async with db.execute(
                'SELECT * FROM users WHERE id = ?',
                (user_id,)
            ) as cursor:
                row = await cursor.fetchone()
                if row:
                    return User(
                        id=row[0],
                        phone_number=row[1],
                        first_name=row[2],
                        last_name=row[3],
                        email=row[4],
                        created_at=row[5]
                    )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error registering user: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@api_router.post("/auth/login", response_model=User)
async def login_user(login_data: UserLogin):
    """Login with phone number"""
    try:
        async with aiosqlite.connect(DB_PATH) as db:
            async with db.execute(
                'SELECT * FROM users WHERE phone_number = ?',
                (login_data.phone_number,)
            ) as cursor:
                row = await cursor.fetchone()
                
                if not row:
                    raise HTTPException(status_code=404, detail="User not found")
                
                return User(
                    id=row[0],
                    phone_number=row[1],
                    first_name=row[2],
                    last_name=row[3],
                    email=row[4],
                    created_at=row[5]
                )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error during login: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@api_router.post("/patients", response_model=PatientRecord)
async def create_patient_record(record: PatientRecordCreate, user_id: Optional[int] = 1):
    try:
        # Generate patient ID
        patient_id = await db_instance.get_next_patient_id(record.patient_name)
        
        async with aiosqlite.connect(DB_PATH) as db:
            cursor = await db.execute(
                '''
                INSERT INTO patient_records (user_id, patient_id, patient_name, diagnosis_details, medicine_names)
                VALUES (?, ?, ?, ?, ?)
                ''',
                (user_id, patient_id, record.patient_name, record.diagnosis_details, record.medicine_names)
            )
            await db.commit()
            record_id = cursor.lastrowid
            
            # Fetch the created record
            async with db.execute(
                'SELECT * FROM patient_records WHERE id = ?',
                (record_id,)
            ) as cursor:
                row = await cursor.fetchone()
                if row:
                    return PatientRecord(
                        id=row[0],
                        user_id=row[1],
                        patient_id=row[2],
                        patient_name=row[3],
                        diagnosis_details=row[4],
                        medicine_names=row[5],
                        created_at=row[6],
                        updated_at=row[7]
                    )
        
        # Check if backup needed
        await check_and_backup_if_needed()
        
    except Exception as e:
        logger.error(f"Error creating patient record: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@api_router.get("/patients", response_model=List[PatientRecord])
async def get_all_patients(user_id: Optional[int] = None, search: Optional[str] = None):
    try:
        async with aiosqlite.connect(DB_PATH) as db:
            if user_id:
                # Filter by user_id if provided
                if search:
                    # When searching, show ALL matching records (no date filter)
                    query = '''
                        SELECT * FROM patient_records 
                        WHERE user_id = ?
                        AND (LOWER(patient_name) LIKE LOWER(?) 
                        OR LOWER(patient_id) LIKE LOWER(?)
                        OR LOWER(diagnosis_details) LIKE LOWER(?)
                        OR LOWER(medicine_names) LIKE LOWER(?))
                        ORDER BY id DESC
                    '''
                    search_pattern = f"%{search}%"
                    async with db.execute(query, (user_id, search_pattern, search_pattern, search_pattern, search_pattern)) as cursor:
                        rows = await cursor.fetchall()
                else:
                    # No search - show only last 7 days records
                    query = '''
                        SELECT * FROM patient_records 
                        WHERE user_id = ?
                        AND created_at >= datetime('now', '-7 days')
                        ORDER BY id DESC
                    '''
                    async with db.execute(query, (user_id,)) as cursor:
                        rows = await cursor.fetchall()
            else:
                # No user_id provided, return all records (for backward compatibility)
                if search:
                    # When searching, show ALL matching records (no date filter)
                    query = '''
                        SELECT * FROM patient_records 
                        WHERE LOWER(patient_name) LIKE LOWER(?) 
                        OR LOWER(patient_id) LIKE LOWER(?)
                        OR LOWER(diagnosis_details) LIKE LOWER(?)
                        OR LOWER(medicine_names) LIKE LOWER(?)
                        ORDER BY id DESC
                    '''
                    search_pattern = f"%{search}%"
                    async with db.execute(query, (search_pattern, search_pattern, search_pattern, search_pattern)) as cursor:
                        rows = await cursor.fetchall()
                else:
                    # No search - show only last 7 days records
                    query = '''
                        SELECT * FROM patient_records 
                        WHERE created_at >= datetime('now', '-7 days')
                        ORDER BY id DESC
                    '''
                    async with db.execute(query) as cursor:
                        rows = await cursor.fetchall()
            
            records = []
            for row in rows:
                records.append(PatientRecord(
                    id=row[0],
                    user_id=row[1],
                    patient_id=row[2],
                    patient_name=row[3],
                    diagnosis_details=row[4],
                    medicine_names=row[5],
                    created_at=row[6],
                    updated_at=row[7]
                ))
            
            return records
    except Exception as e:
        logger.error(f"Error fetching patient records: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@api_router.get("/patients/{record_id}", response_model=PatientRecord)
async def get_patient_record(record_id: int):
    try:
        async with aiosqlite.connect(DB_PATH) as db:
            async with db.execute('SELECT * FROM patient_records WHERE id = ?', (record_id,)) as cursor:
                row = await cursor.fetchone()
                if not row:
                    raise HTTPException(status_code=404, detail="Record not found")
                
                return PatientRecord(
                    id=row[0],
                    patient_id=row[1],
                    patient_name=row[2],
                    diagnosis_details=row[3],
                    medicine_names=row[4],
                    created_at=row[5],
                    updated_at=row[6]
                )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching patient record: {e}")
        raise HTTPException(status_code=404, detail="Record not found")


@api_router.put("/patients/{record_id}", response_model=PatientRecord)
async def update_patient_record(record_id: int, update_data: PatientRecordUpdate):
    try:
        update_fields = []
        values = []
        
        if update_data.patient_name:
            update_fields.append('patient_name = ?')
            values.append(update_data.patient_name)
        if update_data.diagnosis_details:
            update_fields.append('diagnosis_details = ?')
            values.append(update_data.diagnosis_details)
        if update_data.medicine_names:
            update_fields.append('medicine_names = ?')
            values.append(update_data.medicine_names)
        
        if not update_fields:
            raise HTTPException(status_code=400, detail="No fields to update")
        
        update_fields.append('updated_at = CURRENT_TIMESTAMP')
        values.append(record_id)
        
        async with aiosqlite.connect(DB_PATH) as db:
            query = f"UPDATE patient_records SET {', '.join(update_fields)} WHERE id = ?"
            await db.execute(query, tuple(values))
            await db.commit()
            
            # Fetch updated record
            async with db.execute('SELECT * FROM patient_records WHERE id = ?', (record_id,)) as cursor:
                row = await cursor.fetchone()
                if not row:
                    raise HTTPException(status_code=404, detail="Record not found")
                
                return PatientRecord(
                    id=row[0],
                    patient_id=row[1],
                    patient_name=row[2],
                    diagnosis_details=row[3],
                    medicine_names=row[4],
                    created_at=row[5],
                    updated_at=row[6]
                )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating patient record: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@api_router.delete("/patients/{record_id}")
async def delete_patient_record(record_id: int):
    try:
        async with aiosqlite.connect(DB_PATH) as db:
            cursor = await db.execute('DELETE FROM patient_records WHERE id = ?', (record_id,))
            await db.commit()
            
            if cursor.rowcount == 0:
                raise HTTPException(status_code=404, detail="Record not found")
            
            return {"message": "Record deleted successfully"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting patient record: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@api_router.get("/storage-stats", response_model=StorageStats)
async def get_storage_stats():
    try:
        stats = await db_instance.get_storage_stats()
        return StorageStats(
            total_records=stats['total_records'],
            storage_used_mb=stats['storage_used_mb'],
            storage_percentage=stats['storage_percentage'],
            needs_backup=stats['storage_percentage'] >= 80
        )
    except Exception as e:
        logger.error(f"Error getting storage stats: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@api_router.post("/export-records")
async def export_records():
    try:
        async with aiosqlite.connect(DB_PATH) as db:
            async with db.execute('SELECT * FROM patient_records ORDER BY id ASC') as cursor:
                rows = await cursor.fetchall()
        
        export_data = []
        for row in rows:
            export_data.append({
                "ID": row[0],
                "Patient ID": row[1],
                "Patient Name": row[2],
                "Diagnosis Details": row[3],
                "Medicine Names": row[4],
                "Created At": row[5]
            })
        
        return {"records": export_data, "total": len(export_data)}
    except Exception as e:
        logger.error(f"Error exporting records: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# Google Drive Integration
@api_router.get("/drive/auth-url")
async def get_drive_auth_url():
    """Get Google Drive OAuth URL"""
    try:
        client_id = os.getenv("GOOGLE_CLIENT_ID")
        client_secret = os.getenv("GOOGLE_CLIENT_SECRET")
        redirect_uri = os.getenv("GOOGLE_DRIVE_REDIRECT_URI")
        
        if not all([client_id, client_secret, redirect_uri]):
            raise HTTPException(
                status_code=500,
                detail="Google Drive credentials not configured. Please set GOOGLE_CLIENT_ID, GOOGLE_CLIENT_SECRET, and GOOGLE_DRIVE_REDIRECT_URI in .env file"
            )
        
        flow = Flow.from_client_config(
            {
                "web": {
                    "client_id": client_id,
                    "client_secret": client_secret,
                    "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                    "token_uri": "https://oauth2.googleapis.com/token",
                    "redirect_uris": [redirect_uri]
                }
            },
            scopes=['https://www.googleapis.com/auth/drive.file'],
            redirect_uri=redirect_uri
        )
        
        authorization_url, state = flow.authorization_url(
            access_type='offline',
            include_granted_scopes='true',
            prompt='consent'
        )
        
        return {"authorization_url": authorization_url, "state": state}
    except Exception as e:
        logger.error(f"Failed to generate auth URL: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to generate auth URL: {str(e)}")


@api_router.get("/drive/callback")
async def drive_callback(code: str = Query(...), state: str = Query(...)):
    """Handle Google Drive OAuth callback"""
    try:
        client_id = os.getenv("GOOGLE_CLIENT_ID")
        client_secret = os.getenv("GOOGLE_CLIENT_SECRET")
        redirect_uri = os.getenv("GOOGLE_DRIVE_REDIRECT_URI")
        
        flow = Flow.from_client_config(
            {
                "web": {
                    "client_id": client_id,
                    "client_secret": client_secret,
                    "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                    "token_uri": "https://oauth2.googleapis.com/token",
                    "redirect_uris": [redirect_uri]
                }
            },
            scopes=None,
            redirect_uri=redirect_uri
        )
        
        flow.fetch_token(code=code)
        credentials = flow.credentials
        
        # Store credentials
        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute(
                '''
                INSERT OR REPLACE INTO drive_credentials 
                (user_id, access_token, refresh_token, token_uri, client_id, client_secret, scopes, expiry)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ''',
                (
                    'default_user',
                    credentials.token,
                    credentials.refresh_token,
                    credentials.token_uri,
                    credentials.client_id,
                    credentials.client_secret,
                    json.dumps(credentials.scopes),
                    credentials.expiry.isoformat() if credentials.expiry else None
                )
            )
            await db.commit()
        
        logger.info("Drive credentials stored successfully")
        
        # Redirect to frontend
        frontend_url = os.getenv("FRONTEND_URL") or os.getenv("EXPO_PUBLIC_BACKEND_URL")
        return JSONResponse({
            "success": True,
            "message": "Google Drive connected successfully",
            "redirect": f"{frontend_url}?drive_connected=true"
        })
    except Exception as e:
        logger.error(f"OAuth callback failed: {str(e)}")
        raise HTTPException(status_code=400, detail=f"OAuth failed: {str(e)}")


@api_router.get("/drive/status")
async def check_drive_status():
    """Check if Google Drive is connected"""
    try:
        async with aiosqlite.connect(DB_PATH) as db:
            async with db.execute(
                'SELECT access_token, expiry FROM drive_credentials WHERE user_id = ?',
                ('default_user',)
            ) as cursor:
                row = await cursor.fetchone()
                
                if not row or not row[0]:
                    return {"connected": False}
                
                return {"connected": True, "expires_at": row[1]}
    except Exception as e:
        logger.error(f"Error checking drive status: {e}")
        return {"connected": False}


async def get_drive_service():
    """Get Google Drive service with auto-refresh"""
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute(
            'SELECT * FROM drive_credentials WHERE user_id = ?',
            ('default_user',)
        ) as cursor:
            row = await cursor.fetchone()
            
            if not row:
                raise HTTPException(status_code=400, detail="Google Drive not connected")
            
            creds = Credentials(
                token=row[2],
                refresh_token=row[3],
                token_uri=row[4],
                client_id=row[5],
                client_secret=row[6],
                scopes=json.loads(row[7]) if row[7] else []
            )
            
            # Auto-refresh if expired
            if creds.expired and creds.refresh_token:
                logger.info("Refreshing expired token")
                creds.refresh(GoogleRequest())
                
                # Update in database
                await db.execute(
                    'UPDATE drive_credentials SET access_token = ?, expiry = ?, updated_at = CURRENT_TIMESTAMP WHERE user_id = ?',
                    (creds.token, creds.expiry.isoformat() if creds.expiry else None, 'default_user')
                )
                await db.commit()
            
            return build('drive', 'v3', credentials=creds)


@api_router.post("/drive/backup")
async def backup_to_drive():
    """Backup database to Google Drive"""
    try:
        service = await get_drive_service()
        
        # Create backup file
        backup_filename = f"medical_records_backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.db"
        
        file_metadata = {
            'name': backup_filename,
            'mimeType': 'application/x-sqlite3'
        }
        
        media = MediaFileUpload(
            str(DB_PATH),
            mimetype='application/x-sqlite3',
            resumable=True
        )
        
        file = service.files().create(
            body=file_metadata,
            media_body=media,
            fields='id, name, size'
        ).execute()
        
        # Log sync
        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute(
                '''
                INSERT INTO sync_log (sync_type, file_name, file_size, drive_file_id, status)
                VALUES (?, ?, ?, ?, ?)
                ''',
                ('backup', backup_filename, file.get('size'), file.get('id'), 'success')
            )
            await db.commit()
        
        logger.info(f"Backup successful: {backup_filename}")
        
        return {
            "success": True,
            "message": "Database backed up to Google Drive",
            "file_id": file.get('id'),
            "file_name": backup_filename,
            "file_size": file.get('size')
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Backup failed: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Backup failed: {str(e)}")


async def check_and_backup_if_needed():
    """Check storage and backup if needed"""
    try:
        stats = await db_instance.get_storage_stats()
        if stats['storage_percentage'] >= 80:
            # Check if Drive is connected
            status = await check_drive_status()
            if status['connected']:
                await backup_to_drive()
                logger.info("Auto-backup triggered at 80% storage")
    except Exception as e:
        logger.error(f"Auto-backup check failed: {str(e)}")


# Voice search endpoint (placeholder for future speech-to-text integration)
@api_router.post("/voice-search")
async def voice_search(request: VoiceSearchRequest):
    """Process voice search (placeholder for speech-to-text)"""
    # This would integrate with Google Speech-to-Text API
    # For now, return a placeholder response
    return {
        "success": False,
        "message": "Voice search requires Google Speech-to-Text API integration",
        "text": ""
    }


# Include router
app.include_router(api_router)

app.add_middleware(
    CORSMiddleware,
    allow_credentials=True,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.on_event("shutdown")
async def shutdown():
    logger.info("Application shutting down")