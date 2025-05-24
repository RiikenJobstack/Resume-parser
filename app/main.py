from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from io import BytesIO
import os
import base64
import time
import logging
import re
from typing import Dict, Any, Optional
import io
import redis
from fastapi import FastAPI, HTTPException, Depends, Request, BackgroundTasks, File, UploadFile, Form
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded

from app.config import settings
from app.models import FileUploadRequest, ParseResponse, ErrorResponse, HealthResponse
from app.services.document_service import DocumentService
from app.services.parser_service import ParserService
from app.services.utils import validate_base64, get_app_version, create_extraction_metadata
from app.config import settings

from app.services.parser_service import ParserService
from .document_service import DocumentService  # Assuming your service is in document_service.py

# Configure logging
logging.basicConfig(
    level=logging.INFO if settings.DEBUG else logging.WARNING,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)
app = FastAPI(title="Resume Text Extraction API")

# Allow all origins - adjust for production as needed
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize Redis client (if enabled)
redis_client = None
if settings.REDIS_ENABLED:
    try:
        redis_client = redis.from_url(settings.REDIS_URL)
        redis_client.ping()  # Test connection
        logger.info("Redis connected successfully")
    except (redis.ConnectionError, redis.RedisError) as e:
        logger.warning(f"Redis not available, continuing without caching: {e}")
        redis_client = None

# Initialize services
parser_service = ParserService(redis_client)

@app.post("/extract-text")
async def extract_text(file: UploadFile = File(...)):
    filename = file.filename
    if not filename:
        raise HTTPException(status_code=400, detail="No file uploaded")

    ext = '.' + filename.split('.')[-1].lower()
    if ext not in ['.pdf', '.docx', '.txt']:
        raise HTTPException(status_code=400, detail="Unsupported file type")

    file_bytes = await file.read()
    file_buffer = BytesIO(file_bytes)

    try:
        raw_text = DocumentService.extract_text_from_file(file_buffer, ext)
        preprocessed_text = DocumentService.preprocess_text(raw_text)
        complexity = DocumentService.classify_resume_complexity(preprocessed_text)
        try:
            parsed_data = await parser_service.parse_resume_with_ai(preprocessed_text, complexity)
        except ValueError as e:
            raise HTTPException(status_code=500, detail=f"Failed to parse resume: {str(e)}")
        
        return JSONResponse({
            "extracted_text": parsed_data.dict(),  # Convert to dict
            "complexity": complexity
        })
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Extraction error: {str(e)}")
