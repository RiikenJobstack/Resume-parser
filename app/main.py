from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from io import BytesIO
import logging
from datetime import datetime
import re
from typing import Dict, Any, Optional
import io
import redis
import asyncio
from concurrent.futures import ThreadPoolExecutor
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
from app.resumeParser import ResumeParser
from app.parserService import EnhancedDocumentService
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

# Thread pool for CPU-intensive tasks (ADDED)
executor = ThreadPoolExecutor(max_workers=4)

async def process_document_with_timeout(file_buffer: BytesIO, ext: str, timeout_seconds: int = 180):
    """
    Process document with timeout protection
    """
    loop = asyncio.get_event_loop()
    
    def sync_processing():
        try:
            # Extract text
            raw_text = DocumentService.extract_text_from_file(file_buffer, ext)
            return raw_text
        except Exception as e:
            logger.error(f"Document processing failed: {e}")
            raise
    
    try:
        # Run with timeout
        raw_text = await asyncio.wait_for(
            loop.run_in_executor(executor, sync_processing), 
            timeout=timeout_seconds
        )
        return raw_text
    except asyncio.TimeoutError:
        logger.error(f"Document processing timed out after {timeout_seconds} seconds")
        raise HTTPException(
            status_code=408, 
            detail=f"Document processing timed out after {timeout_seconds} seconds. File may be too complex or large."
        )

async def ai_parsing_with_timeout(preprocessed_text: str, complexity: str, timeout_seconds: int = 120):
    """
    AI parsing with timeout protection
    """
    try:
        ai_service = EnhancedDocumentService(openai_api_key=settings.OPENAI_API_KEY)
        parsed_data = await asyncio.wait_for(
            ai_service.parse_resume_with_ai(preprocessed_text, complexity),
            timeout=timeout_seconds
        )
        return parsed_data
    except asyncio.TimeoutError:
        logger.error(f"AI parsing timed out after {timeout_seconds} seconds")
        raise HTTPException(
            status_code=408, 
            detail=f"AI parsing timed out after {timeout_seconds} seconds. Please try again or contact support."
        )

@app.get("/health", response_model=HealthResponse)
async def health_check():
    """Basic health check endpoint"""
    return {
        "status": "ok",
        "version": get_app_version(),
        "timestamp": datetime.utcnow().isoformat() + "Z"
    }

@app.post("/extract-text")
async def extract_text(file: UploadFile = File(...)):
    start_time = datetime.utcnow()
    
    try:
        filename = file.filename
        if not filename:
            raise HTTPException(status_code=400, detail="No file uploaded")

        ext = '.' + filename.split('.')[-1].lower()
        if ext not in ['.pdf', '.docx', '.txt']:
            raise HTTPException(status_code=400, detail="Unsupported file type")

        file_bytes = await file.read()
        file_size = len(file_bytes)
        
        # Check file size (optional)
        max_size = 50 * 1024 * 1024  # 50MB limit
        if file_size > max_size:
            raise HTTPException(
                status_code=400, 
                detail=f"File too large ({file_size / (1024*1024):.1f}MB). Maximum size: {max_size / (1024*1024)}MB"
            )
        
        file_buffer = BytesIO(file_bytes)
        
        logger.info(f"Processing {ext} file: {filename} ({file_size / 1024:.1f}KB)")

        # Step 1: Extract text with timeout (3 minutes for complex PDFs)
        raw_text = await process_document_with_timeout(file_buffer, ext, timeout_seconds=180)
        
        # Step 2: Preprocess text (fast operation)
        preprocessed_text = DocumentService.preprocess_text(raw_text)
        complexity = DocumentService.classify_resume_complexity(preprocessed_text)
        
        logger.info(f"Text extracted: {len(preprocessed_text)} chars, complexity: {complexity}")
        
        # Step 3: AI parsing with timeout (2 minutes for AI processing)
        parsed_data = await ai_parsing_with_timeout(preprocessed_text, complexity, timeout_seconds=120)
        
        # Calculate processing time
        processing_time = (datetime.utcnow() - start_time).total_seconds()
        
        logger.info(f"Resume parsed successfully in {processing_time:.2f} seconds")
        
        return JSONResponse({
            "extracted_text": preprocessed_text,
            "complexity": complexity,
            "resumeData": parsed_data,
            "metadata": {
                "filename": filename,
                "file_size_kb": round(file_size / 1024, 2),
                "processing_time_seconds": round(processing_time, 2),
                "text_length": len(preprocessed_text)
            }
        })
        
    except HTTPException:
        # Re-raise HTTP exceptions (including timeouts)
        raise
    except Exception as e:
        logger.exception(f"Unexpected error processing {filename}")
        raise HTTPException(status_code=500, detail=f"Extraction error: {str(e)}")