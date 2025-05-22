from typing import Dict, List, Optional, Any, Union
from pydantic import BaseModel, Field
from datetime import datetime

class FileUploadRequest(BaseModel):
    """Request model for file upload"""
    fileName: str
    fileData: str  # Base64 encoded file data

class PersonalInfo(BaseModel):
    """Personal information model"""
    fullName: str = "Not provided"
    jobTitle: str = "Not provided"
    email: str = "Not provided"
    phone: str = "Not provided"
    location: str = "Not provided"
    summary: str = "Not provided"
    profilePicture: Optional[str] = None

class ExperienceItem(BaseModel):
    """Experience item model"""
    jobTitle: str = ""
    company: str = ""
    location: str = ""
    startDate: Optional[str] = None
    endDate: Optional[str] = None
    currentPosition: bool = False
    description: List[str] = Field(default_factory=list)

class ProjectItem(BaseModel):
    """Project item model"""
    projectName: str = ""
    projectUrl: str = ""
    startDate: Optional[str] = None
    endDate: Optional[str] = None
    ongoingProject: bool = False
    description: List[str] = Field(default_factory=list)
    technologies: List[str] = Field(default_factory=list)

class EducationItem(BaseModel):
    """Education item model"""
    degree: str = ""
    institution: str = ""
    location: str = ""
    startDate: Optional[str] = None
    endDate: Optional[str] = None
    current: bool = False
    gpa: str = ""
    description: List[str] = Field(default_factory=list)

class SkillsState(BaseModel):
    """Skills section state"""
    categoryOrder: List[str] = Field(default_factory=list)
    viewMode: str = "categorized"

class Section(BaseModel):
    """Generic section model"""
    id: str
    type: str
    title: str
    order: int
    hidden: bool = False
    format: Optional[str] = None
    items: List[Union[ExperienceItem, ProjectItem, EducationItem, Dict[str, Any]]] = Field(default_factory=list)
    groups: List[Dict[str, Any]] = Field(default_factory=list)
    state: Dict[str, Any] = Field(default_factory=dict)

class ResumeData(BaseModel):
    """Resume data model"""
    id: Optional[str] = None
    targetJobTitle: str = "Not provided"
    targetJobDescription: str = "Not provided"
    personalInfo: PersonalInfo = Field(default_factory=PersonalInfo)
    sections: List[Section] = Field(default_factory=list)

class StyleSettings(BaseModel):
    """Template style settings"""
    fontFamily: str = "'IBM Plex Serif', serif"
    fontSize: str = "12pt"
    lineHeight: str = "1.5"
    headingColor: str = "#333"
    textColor: str = "#333"
    accentColor: str = "#444"
    linkColor: str = "#007bff"

class Template(BaseModel):
    """Template model"""
    id: str = "ibm-plex"
    styleSettings: StyleSettings = Field(default_factory=StyleSettings)

class CompleteResumeResponse(BaseModel):
    """Complete resume response model"""
    resumeData: ResumeData
    lastEdited: str = Field(default_factory=lambda: datetime.utcnow().isoformat() + "Z")

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
    data: CompleteResumeResponse
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