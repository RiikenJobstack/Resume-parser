from typing import Dict, List, Optional, Any, Union
from pydantic import BaseModel, Field

class FileUploadRequest(BaseModel):
    """Request model for file upload"""
    fileName: str
    fileData: str  # Base64 encoded file data

class WorkExperience(BaseModel):
    """Work experience model"""
    role: str = "Not provided"
    company: str = "Not provided"
    location: str = "Not provided"
    duration: str = "Not provided"
    description: List[str] = Field(default_factory=list)

class Education(BaseModel):
    """Education model"""
    institution: str = "Not provided"
    degree: str = "Not provided"
    major: str = "Not provided"
    score: str = "Not provided"
    years: str = "Not provided"

class Skills(BaseModel):
    """Skills model"""
    languages: List[str] = Field(default_factory=list)
    frameworks_libraries: List[str] = Field(default_factory=list)
    cloud_databases_tech_stack: List[str] = Field(default_factory=list)
    tools: List[str] = Field(default_factory=list)

class Project(BaseModel):
    """Project model"""
    name: str = "Not provided"
    description: str = "Not provided"
    technologies: List[str] = Field(default_factory=list)
    url: str = "Not provided"

class ResumeData(BaseModel):
    """Resume data model"""
    name: str = "Not provided"
    email: str = "Not provided"
    phone: str = "Not provided"
    linkedin: str = "Not provided"
    github: str = "Not provided"
    portfolio: str = "Not provided"
    skills: Skills = Field(default_factory=Skills)
    education: List[Education] = Field(default_factory=list)
    work_experience: List[WorkExperience] = Field(default_factory=list)
    projects: List[Project] = Field(default_factory=list)
    certifications: List[str] = Field(default_factory=list)
    languages: List[str] = Field(default_factory=list)

class ExtractionMetadata(BaseModel):
    """Metadata about the extraction process"""
    fileType: str
    textLength: int
    processingTimeSeconds: float
    complexity: str
    modelUsed: str
    timestamp: float

class ParseResponse(BaseModel):
    """Response model for resume parsing"""
    success: bool
    parsed: ResumeData
    extractionMetadata: ExtractionMetadata

class ErrorResponse(BaseModel):
    """Error response model"""
    success: bool = False
    error: str
    detail: Optional[str] = None

class HealthResponse(BaseModel):
    """Health check response model"""
    status: str
    version: str