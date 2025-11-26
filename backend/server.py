from fastapi import FastAPI, APIRouter, HTTPException
from dotenv import load_dotenv
from starlette.middleware.cors import CORSMiddleware
from motor.motor_asyncio import AsyncIOMotorClient
import os
import logging
from pathlib import Path
from pydantic import BaseModel, Field
from typing import List, Optional
from datetime import datetime
from bson import ObjectId

# Configure logging first
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / '.env')

# MongoDB connection
mongo_url = os.environ['MONGO_URL']
client = AsyncIOMotorClient(mongo_url)
db = client[os.environ['DB_NAME']]

# Create the main app without a prefix
app = FastAPI()

# Create a router with the /api prefix
api_router = APIRouter(prefix="/api")


# Define Models
class PatientRecord(BaseModel):
    id: Optional[str] = None
    slno: Optional[int] = None
    patient_name: str
    diagnosis_details: str
    medicine_names: str
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

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

class EmailBackup(BaseModel):
    email: str


# Helper function to get next serial number
async def get_next_slno():
    last_record = await db.patient_records.find_one(sort=[("slno", -1)])
    if last_record and "slno" in last_record:
        return last_record["slno"] + 1
    return 1

# Routes
@api_router.get("/")
async def root():
    return {"message": "Medical History System API"}


@api_router.post("/patients", response_model=PatientRecord)
async def create_patient_record(record: PatientRecordCreate):
    try:
        slno = await get_next_slno()
        record_dict = record.dict()
        record_dict["slno"] = slno
        record_dict["created_at"] = datetime.utcnow()
        record_dict["updated_at"] = datetime.utcnow()
        
        result = await db.patient_records.insert_one(record_dict)
        record_dict["id"] = str(result.inserted_id)
        
        return PatientRecord(**record_dict)
    except Exception as e:
        logger.error(f"Error creating patient record: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@api_router.get("/patients", response_model=List[PatientRecord])
async def get_all_patients(search: Optional[str] = None):
    try:
        query = {}
        if search:
            query = {
                "$or": [
                    {"patient_name": {"$regex": search, "$options": "i"}},
                    {"diagnosis_details": {"$regex": search, "$options": "i"}},
                    {"medicine_names": {"$regex": search, "$options": "i"}}
                ]
            }
        
        records = await db.patient_records.find(query).sort("slno", -1).to_list(1000)
        
        result = []
        for record in records:
            record["id"] = str(record["_id"])
            result.append(PatientRecord(**record))
        
        return result
    except Exception as e:
        logger.error(f"Error fetching patient records: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@api_router.get("/patients/{record_id}", response_model=PatientRecord)
async def get_patient_record(record_id: str):
    try:
        record = await db.patient_records.find_one({"_id": ObjectId(record_id)})
        if not record:
            raise HTTPException(status_code=404, detail="Record not found")
        
        record["id"] = str(record["_id"])
        return PatientRecord(**record)
    except Exception as e:
        logger.error(f"Error fetching patient record: {e}")
        raise HTTPException(status_code=404, detail="Record not found")


@api_router.put("/patients/{record_id}", response_model=PatientRecord)
async def update_patient_record(record_id: str, update_data: PatientRecordUpdate):
    try:
        update_dict = {k: v for k, v in update_data.dict().items() if v is not None}
        update_dict["updated_at"] = datetime.utcnow()
        
        result = await db.patient_records.find_one_and_update(
            {"_id": ObjectId(record_id)},
            {"$set": update_dict},
            return_document=True
        )
        
        if not result:
            raise HTTPException(status_code=404, detail="Record not found")
        
        result["id"] = str(result["_id"])
        return PatientRecord(**result)
    except Exception as e:
        logger.error(f"Error updating patient record: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@api_router.delete("/patients/{record_id}")
async def delete_patient_record(record_id: str):
    try:
        result = await db.patient_records.delete_one({"_id": ObjectId(record_id)})
        if result.deleted_count == 0:
            raise HTTPException(status_code=404, detail="Record not found")
        
        return {"message": "Record deleted successfully"}
    except HTTPException:
        raise  # Re-raise HTTPException as-is
    except Exception as e:
        logger.error(f"Error deleting patient record: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@api_router.get("/storage-stats", response_model=StorageStats)
async def get_storage_stats():
    try:
        total_records = await db.patient_records.count_documents({})
        
        # Estimate storage used (rough calculation)
        # Average record size estimation
        storage_used_mb = (total_records * 2) / 1024  # Rough estimate: 2KB per record
        
        # Assume max storage is 100MB for demonstration
        max_storage_mb = 100
        storage_percentage = (storage_used_mb / max_storage_mb) * 100
        
        return StorageStats(
            total_records=total_records,
            storage_used_mb=round(storage_used_mb, 2),
            storage_percentage=round(storage_percentage, 2)
        )
    except Exception as e:
        logger.error(f"Error getting storage stats: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@api_router.post("/export-records")
async def export_records():
    try:
        records = await db.patient_records.find().sort("slno", 1).to_list(1000)
        
        # Format records for export
        export_data = []
        for record in records:
            export_data.append({
                "SlNo": record.get("slno", ""),
                "Patient Name": record.get("patient_name", ""),
                "Diagnosis Details": record.get("diagnosis_details", ""),
                "Medicine Names": record.get("medicine_names", ""),
                "Created At": record.get("created_at", "").isoformat() if record.get("created_at") else ""
            })
        
        return {"records": export_data, "total": len(export_data)}
    except Exception as e:
        logger.error(f"Error exporting records: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# Include the router in the main app
app.include_router(api_router)

app.add_middleware(
    CORSMiddleware,
    allow_credentials=True,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.on_event("shutdown")
async def shutdown_db_client():
    client.close()