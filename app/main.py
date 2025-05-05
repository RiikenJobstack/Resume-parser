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

# Configure logging
logging.basicConfig(
    level=logging.INFO if settings.DEBUG else logging.WARNING,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Initialize FastAPI app
app = FastAPI(
    title=settings.API_TITLE,
    version=get_app_version(),
    docs_url="/docs" if settings.DEBUG else None,
    redoc_url="/redoc" if settings.DEBUG else None,
)

# Rate limiting setup
limiter = Limiter(key_func=get_remote_address)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.ALLOWED_ORIGINS,
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

# Add this new endpoint to your app/main.py file
@app.post(
    "/api/upload-resume", 
    response_model=ParseResponse,
    responses={
        400: {"model": ErrorResponse},
        422: {"model": ErrorResponse},
        500: {"model": ErrorResponse}
    }
)
@limiter.limit("100/hour")
async def upload_resume(
    request: Request,
    file: UploadFile = File(...),
):
    """
    Parse a resume from direct file upload
    """
    start_time = time.time()
    
    try:
        # Validate file name
        if not file.filename:
            raise HTTPException(status_code=400, detail="Missing filename")
        
        # Get file extension
        file_extension = os.path.splitext(file.filename)[1].lower()
        supported_extensions = ['.pdf', '.docx', '.txt']
        
        if file_extension not in supported_extensions:
            raise HTTPException(
                status_code=400,
                detail=f"Unsupported file type. Supported formats: {', '.join(supported_extensions)}"
            )
        
        # Read the file
        try:
            file_content = await file.read()
            file_size = len(file_content)
            
            # Check file size
            if file_size > settings.MAX_FILE_SIZE:
                max_mb = settings.MAX_FILE_SIZE / (1024 * 1024)
                raise HTTPException(
                    status_code=400, 
                    detail=f"File too large. Maximum size: {max_mb} MB"
                )
                
            # Create BytesIO object from file content
            file_buffer = io.BytesIO(file_content)
        except Exception as e:
            raise HTTPException(status_code=400, detail=f"Error reading file: {str(e)}")
        
        # Extract text from file
        try:
            extracted_text = DocumentService.extract_text_from_file(file_buffer, file_extension)
        except ValueError as e:
            raise HTTPException(status_code=422, detail=str(e))
        
        # Check if text was extracted
        if not extracted_text:
            raise HTTPException(status_code=422, detail="No text could be extracted from the file")
        
        # Preprocess the extracted text
        processed_text = DocumentService.preprocess_text(extracted_text)
        
        # Classify complexity
        complexity = DocumentService.classify_resume_complexity(processed_text)
        
        # Select appropriate model
        model = settings.OPENAI_MODEL_SIMPLE if complexity == 'simple' else settings.OPENAI_MODEL_COMPLEX
        
        # Parse the resume
        try:
            parsed_data = await parser_service.parse_resume_with_ai(
                processed_text, 
                complexity
            )
        except ValueError as e:
            raise HTTPException(status_code=500, detail=f"Failed to parse resume: {str(e)}")
        
        # Calculate processing time
        processing_time = time.time() - start_time
        
        # Create response
        return {
            "success": True,
            "parsed": parsed_data,
            "extractionMetadata": create_extraction_metadata(
                file_extension[1:],  # Remove the dot
                len(processed_text),
                processing_time,
                complexity,
                model
            )
        }
        
    except HTTPException:
        # Re-raise HTTP exceptions
        raise
    except Exception as e:
        # Log the full error
        logger.exception("Unexpected error")
        # Return a friendly error
        raise HTTPException(status_code=500, detail=f"Failed to parse resume: {str(e)}")

# Define routes
@app.get("/health", response_model=HealthResponse)
async def health_check():
    """Health check endpoint"""
    return {
        "status": "ok",
        "version": get_app_version()
    }

@app.post(
    "/api/parse-resume", 
    response_model=ParseResponse,
    responses={
        400: {"model": ErrorResponse},
        422: {"model": ErrorResponse},
        500: {"model": ErrorResponse}
    }
)
@limiter.limit("100/hour")
async def parse_resume(request: Request, file_data: FileUploadRequest):
    """
    Parse a resume from a base64-encoded file
    """
    start_time = time.time()
    
    try:
        # Validate file name
        if not file_data.fileName:
            raise HTTPException(status_code=400, detail="Missing fileName")
        
        # Get file extension
        file_extension = os.path.splitext(file_data.fileName)[1].lower()
        supported_extensions = ['.pdf', '.docx', '.txt']
        
        if file_extension not in supported_extensions:
            raise HTTPException(
                status_code=400,
                detail=f"Unsupported file type. Supported formats: {', '.join(supported_extensions)}"
            )
        
        # Validate base64 data
        if not validate_base64(file_data.fileData):
            raise HTTPException(status_code=400, detail="Invalid base64 encoded file")
        
        # Decode base64 data
        try:
            file_bytes = base64.b64decode(file_data.fileData)
            file_size = len(file_bytes)
            
            # Check file size
            if file_size > settings.MAX_FILE_SIZE:
                max_mb = settings.MAX_FILE_SIZE / (1024 * 1024)
                raise HTTPException(
                    status_code=400, 
                    detail=f"File too large. Maximum size: {max_mb} MB"
                )
                
            file_buffer = BytesIO(file_bytes)
        except Exception as e:
            raise HTTPException(status_code=400, detail=f"Invalid base64 encoded file: {str(e)}")
        
        # Extract text from file
        try:
            extracted_text = DocumentService.extract_text_from_file(file_buffer, file_extension)
        except ValueError as e:
            raise HTTPException(status_code=422, detail=str(e))
        
        # Check if text was extracted
        if not extracted_text:
            raise HTTPException(status_code=422, detail="No text could be extracted from the file")
        
        # Preprocess the extracted text
        processed_text = DocumentService.preprocess_text(extracted_text)
        
        # Classify complexity
        complexity = DocumentService.classify_resume_complexity(processed_text)
        
        # Select appropriate model
        model = settings.OPENAI_MODEL_SIMPLE if complexity == 'simple' else settings.OPENAI_MODEL_COMPLEX
        
        # Parse the resume
        try:
            parsed_data = await parser_service.parse_resume_with_ai(processed_text, complexity)
        except ValueError as e:
            raise HTTPException(status_code=500, detail=f"Failed to parse resume: {str(e)}")
        
        # Calculate processing time
        processing_time = time.time() - start_time
        
        # Create response
        return {
            "success": True,
            "parsed": parsed_data,
            "extractionMetadata": create_extraction_metadata(
                file_extension[1:],  # Remove the dot
                len(processed_text),
                processing_time,
                complexity,
                model
            )
        }
        
    except HTTPException:
        # Re-raise HTTP exceptions
        raise
    except Exception as e:
        # Log the full error
        logger.exception("Unexpected error")
        # Return a friendly error
        raise HTTPException(status_code=500, detail=f"Failed to parse resume: {str(e)}")

# Batch processing endpoint for high volume
@app.post("/api/batch-parse-resumes")
@limiter.limit("20/hour")
async def batch_parse_resumes(request: Request, files: list[FileUploadRequest], background_tasks: BackgroundTasks):
    """Parse multiple resumes in batch mode (asynchronous processing)"""
    # Implementation details omitted for brevity
    pass