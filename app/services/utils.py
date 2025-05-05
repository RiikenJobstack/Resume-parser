import re
import base64
import importlib.metadata
from typing import Dict, Any

def validate_base64(data: str) -> bool:
    """
    Validate if a string is base64 encoded
    
    Args:
        data: Base64 encoded string
        
    Returns:
        True if valid base64, False otherwise
    """
    try:
        if not data:
            return False
        # Try to decode the base64 string
        base64.b64decode(data)
        return True
    except Exception:
        return False

def get_app_version() -> str:
    """
    Get the application version
    
    Returns:
        Application version string
    """
    try:
        return importlib.metadata.version("resume-parser")
    except importlib.metadata.PackageNotFoundError:
        return "0.1.0"  # Default version if not installed as package

def create_extraction_metadata(
    file_type: str, 
    text_length: int, 
    processing_time: float, 
    complexity: str, 
    model_used: str
) -> Dict[str, Any]:
    """
    Create metadata about the extraction process
    
    Args:
        file_type: Type of the file (pdf, docx, etc.)
        text_length: Length of the extracted text
        processing_time: Processing time in seconds
        complexity: 'simple' or 'complex'
        model_used: Name of the model used
        
    Returns:
        Dictionary containing metadata
    """
    import time
    
    return {
        "fileType": file_type,
        "textLength": text_length,
        "processingTimeSeconds": round(processing_time, 2),
        "complexity": complexity,
        "modelUsed": model_used,
        "timestamp": time.time()
    }