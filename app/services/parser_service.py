import json
import time
import hashlib
import logging
from typing import Dict, Any, Optional, List
import redis
import re
from openai import OpenAI
from app.config import settings
from app.models import (
    ResumeData, PersonalInfo, Section, ExperienceItem, 
    ProjectItem, EducationItem, CompleteResumeResponse, 
    Template, StyleSettings, SkillsState
)
from datetime import datetime

logger = logging.getLogger(__name__)

class ParserService:
    """Service for parsing resume text using AI"""
    
    def __init__(self, redis_client: Optional[redis.Redis] = None):
        print(settings.OPENAI_API_KEY)
        """
        Initialize the parser service
        
        Args:
            redis_client: Redis client for caching (optional)
        """
        self.redis_client = redis_client
        self.openai_client = OpenAI(api_key=settings.OPENAI_API_KEY)
    
    def get_cache_key(self, text: str) -> str:
        """
        Generate a cache key for the text
        
        Args:
            text: Text to generate cache key for
            
        Returns:
            Cache key as string
        """
        return f"resume_parse_{hashlib.md5(text.encode()).hexdigest()}"
    
    def _format_description_array(self, description_data) -> List[str]:
        """
        Format description data to return clean array of bullet points
        
        Args:
            description_data: Can be string, list of strings, or mixed content
            
        Returns:
            List of clean description strings (without bullet characters)
        """
        if not description_data:
            return []
        
        # If it's already a list, clean each item
        if isinstance(description_data, list):
            formatted_items = []
            for item in description_data:
                if isinstance(item, str) and item.strip():
                    cleaned_item = self._clean_bullet_text(item.strip())
                    if cleaned_item:  # Only add non-empty items
                        formatted_items.append(cleaned_item)
            return formatted_items
        
        # If it's a string, convert to array
        if isinstance(description_data, str):
            return self._string_to_description_array(description_data)
        
        # Fallback
        return []
    
    def _string_to_description_array(self, text: str) -> List[str]:
        """
        Convert a string with bullet points to an array of clean strings
        
        Args:
            text: String that may contain bullet points or line breaks
            
        Returns:
            List of clean description strings
        """
        if not text or text.strip() == "":
            return []
        
        # Split by common bullet point indicators or line breaks
        lines = re.split(r'[\n\r]+|(?=•)|(?=-\s)|(?=\*\s)|(?=◦)', text)
        formatted_lines = []
        
        for line in lines:
            cleaned_line = self._clean_bullet_text(line.strip())
            if cleaned_line:  # Only add non-empty lines
                formatted_lines.append(cleaned_line)
        
        return formatted_lines
    
    def _clean_bullet_text(self, text: str) -> str:
        """
        Remove bullet point characters and clean text
        
        Args:
            text: Text that may have bullet point characters
            
        Returns:
            Clean text without bullet characters
        """
        if not text:
            return ""
        
        # Remove bullet point characters from the beginning
        cleaned = re.sub(r'^[•\-\*◦]\s*', '', text.strip())
        
        # Skip very short lines that might be artifacts
        if len(cleaned) < 3:
            return ""
        
        return cleaned

    def _format_description(self, description_data) -> str:
        """
        Format description data to handle bullet points and multi-line content
        
        Args:
            description_data: Can be string, list of strings, or mixed content
            
        Returns:
            Properly formatted description string
        """
        if not description_data:
            return ""
        
        # If it's already a string, clean it up
        if isinstance(description_data, str):
            return self._clean_description_text(description_data)
        
        # If it's a list, process each item
        if isinstance(description_data, list):
            formatted_items = []
            for item in description_data:
                if isinstance(item, str) and item.strip():
                    cleaned_item = item.strip()
                    # Add bullet point if it doesn't already have one
                    if not cleaned_item.startswith(('•', '-', '*', '◦')):
                        cleaned_item = f"• {cleaned_item}"
                    formatted_items.append(cleaned_item)
            
            return '\n'.join(formatted_items)
        
        # Fallback to string conversion
        return str(description_data)
    
    def _clean_description_text(self, text: str) -> str:
        """
        Clean and format description text
        
        Args:
            text: Raw description text
            
        Returns:
            Cleaned description text
        """
        if not text:
            return ""
        
        # Split by common bullet point indicators or line breaks
        lines = re.split(r'[\n\r]+|(?=•)|(?=-\s)|(?=\*\s)', text)
        formatted_lines = []
        
        for line in lines:
            line = line.strip()
            if not line:
                continue
            
            # Clean up existing bullet points
            line = re.sub(r'^[•\-\*◦]\s*', '', line)
            
            # Skip very short lines that might be artifacts
            if len(line) < 3:
                continue
            
            # Add consistent bullet point
            formatted_lines.append(f"• {line}")
        
        return '\n'.join(formatted_lines)

    def _create_default_sections(self) -> List[Section]:
        """Create default sections structure"""
        return [
            Section(
                id="experience-1",
                type="experience",
                title="Work Experience",
                order=0,
                hidden=False,
                items=[ExperienceItem()],
                groups=[],
                state={}
            ),
            Section(
                id="projects-1",
                type="projects",
                title="Projects",
                order=1,
                hidden=False,
                items=[ProjectItem()],
                groups=[],
                state={}
            ),
            Section(
                id="education-1",
                type="education",
                title="Education",
                order=2,
                hidden=False,
                items=[EducationItem()],
                groups=[],
                state={}
            ),
            Section(
                id="skills-1",
                type="skills",
                title="Skills",
                order=3,
                format="grouped",
                items=[],
                groups=[],
                state=SkillsState().dict(),
                hidden=False
            )
        ]
    
    def _convert_ai_response_to_resume_data(self, ai_response: Dict[str, Any]) -> ResumeData:
        """Convert AI response to new ResumeData format"""
        
        # Extract personal info
        personal_info = PersonalInfo(
            fullName=ai_response.get('name', 'Not provided'),
            jobTitle=ai_response.get('current_job_title', 'Not provided'),  # Try to extract current job title
            email=ai_response.get('email', 'Not provided'),
            phone=ai_response.get('phone', 'Not provided'),
            location=ai_response.get('location', 'Not provided'),  # Extract location if available
            summary=ai_response.get('summary', 'Not provided'),  # Extract summary from AI response
            profilePicture=None
        )
        
        # Create sections
        sections = []
        
        # Experience section
        experience_items = []
        for exp in ai_response.get('work_experience', []):
            # Handle description as array of bullet points
            description_list = exp.get('description', [])
            formatted_description = self._format_description_array(description_list)
            
            experience_items.append(ExperienceItem(
                jobTitle=exp.get('role', ''),
                company=exp.get('company', ''),
                location=exp.get('location', ''),
                startDate=None,  # Would need date parsing from duration
                endDate=None,
                currentPosition=False,
                description=formatted_description
            ))
        
        if not experience_items:
            experience_items = [ExperienceItem()]
            
        sections.append(Section(
            id="experience-1",
            type="experience",
            title="Work Experience",
            order=0,
            hidden=False,
            items=experience_items,
            groups=[],
            state={}
        ))
        
        # Projects section
        project_items = []
        for proj in ai_response.get('projects', []):
            # Handle project description as array
            project_description = proj.get('description', '')
            if isinstance(project_description, str):
                # If it's a string, convert to array by splitting on bullet points
                project_description_array = self._string_to_description_array(project_description)
            elif isinstance(project_description, list):
                project_description_array = self._format_description_array(project_description)
            else:
                project_description_array = []
            
            project_items.append(ProjectItem(
                projectName=proj.get('name', ''),
                projectUrl=proj.get('url', ''),
                startDate=None,
                endDate=None,
                ongoingProject=False,
                description=project_description_array,
                technologies=proj.get('technologies', [])
            ))
        
        if not project_items:
            project_items = [ProjectItem()]
            
        sections.append(Section(
            id="projects-1",
            type="projects",
            title="Projects",
            order=1,
            hidden=False,
            items=project_items,
            groups=[],
            state={}
        ))
        
        # Education section
        education_items = []
        for edu in ai_response.get('education', []):
            # Handle education description as array (for courses, achievements, etc.)
            edu_major = edu.get('major', '')
            edu_description = [edu_major] if edu_major and edu_major != "Not provided" else []
            
            education_items.append(EducationItem(
                degree=edu.get('degree', ''),
                institution=edu.get('institution', ''),
                location='',  # Would need to be extracted
                startDate=None,
                endDate=None,
                current=False,
                gpa=edu.get('score', ''),
                description=edu_description
            ))
        
        if not education_items:
            education_items = [EducationItem()]
            
        sections.append(Section(
            id="education-1",
            type="education",
            title="Education",
            order=2,
            hidden=False,
            items=education_items,
            groups=[],
            state={}
        ))
        
        # Skills section - convert to grouped format
        skills_data = ai_response.get('skills', {})
        skill_groups = []
        category_order = []
        
        if skills_data.get('languages'):
            skill_groups.append({
                'id': 'languages',
                'name': 'Programming Languages',
                'skills': [{'name': skill, 'level': 'intermediate'} for skill in skills_data['languages']]
            })
            category_order.append('languages')
        
        if skills_data.get('frameworks_libraries'):
            skill_groups.append({
                'id': 'frameworks',
                'name': 'Frameworks & Libraries',
                'skills': [{'name': skill, 'level': 'intermediate'} for skill in skills_data['frameworks_libraries']]
            })
            category_order.append('frameworks')
        
        if skills_data.get('cloud_databases_tech_stack'):
            skill_groups.append({
                'id': 'cloud_tech',
                'name': 'Cloud & Databases',
                'skills': [{'name': skill, 'level': 'intermediate'} for skill in skills_data['cloud_databases_tech_stack']]
            })
            category_order.append('cloud_tech')
        
        if skills_data.get('tools'):
            skill_groups.append({
                'id': 'tools',
                'name': 'Tools',
                'skills': [{'name': skill, 'level': 'intermediate'} for skill in skills_data['tools']]
            })
            category_order.append('tools')
        
        sections.append(Section(
            id="skills-1",
            type="skills",
            title="Skills",
            order=3,
            format="grouped",
            items=[],
            groups=skill_groups,
            state={
                'categoryOrder': category_order,
                'viewMode': 'categorized'
            },
            hidden=False
        ))
        
        return ResumeData(
            id=None,
            targetJobTitle='Not provided',
            targetJobDescription='Not provided',
            personalInfo=personal_info,
            sections=sections
        )
    
    async def parse_resume_with_ai(self, text: str, complexity: str = 'simple') -> CompleteResumeResponse:
        """
        Parse resume text using OpenAI API with retry mechanism
        
        Args:
            text: Preprocessed resume text
            complexity: 'simple' or 'complex' to determine model
            
        Returns:
            Complete resume response with new structure
        """
        # Check cache first if Redis is available
        if self.redis_client:
            cache_key = self.get_cache_key(text)
            cached_result = self.redis_client.get(cache_key)
            if cached_result:
                try:
                    cached_data = json.loads(cached_result)
                    return CompleteResumeResponse(**cached_data)
                except json.JSONDecodeError:
                    logger.warning("Invalid JSON in cache, ignoring")
        
        # Select model based on complexity
        model = settings.OPENAI_MODEL_SIMPLE if complexity == 'simple' else settings.OPENAI_MODEL_COMPLEX
        
        # Define system prompt
        system_prompt = """
        You are an expert resume parser AI. Your task is to extract structured information from resumes accurately.
        Follow these guidelines strictly:
        1. Extract all available information that matches the required JSON schema
        2. Look for patterns that indicate section headers like "EXPERIENCE", "EDUCATION", "SKILLS", etc.
        3. For missing information, use "Not provided" for strings and empty arrays for lists
        4. Make reasonable inferences when information is implicit
        5. Return only valid JSON that matches the schema exactly
        6. For summary field, look for sections labeled as "SUMMARY", "PROFESSIONAL SUMMARY", "ABOUT", "ABOUT ME", "PROFILE", "OBJECTIVE", or "CAREER OBJECTIVE"
        7. Try to infer job titles and locations from context
        8. For work experience and project descriptions, preserve bullet points as separate array items
        9. Each bullet point or responsibility should be a separate string in the description array
        10. Remove bullet point characters (•, -, *) from the text but keep each point as separate array item
        """
        
        # Resume schema to include in the prompt (keeping the old format for AI parsing)
        resume_schema = {
            "name": "",
            "email": "",
            "phone": "",
            "location": "",  # Extract from contact info or experience
            "current_job_title": "",  # Current or most recent job title
            "linkedin": "",
            "github": "",
            "portfolio": "",
            "summary": "",  # Professional summary, about, profile, or objective section
            "skills": {
                "languages": [],
                "frameworks_libraries": [],
                "cloud_databases_tech_stack": [],
                "tools": []
            },
            "education": [
                {
                    "institution": "",
                    "degree": "",
                    "major": "",
                    "score": "",
                    "years": ""
                }
            ],
            "work_experience": [
                {
                    "role": "",
                    "company": "",
                    "location": "",
                    "duration": "",
                    "description": []
                }
            ],
            "projects": [
                {
                    "name": "",
                    "description": [],  # Changed to array for bullet points
                    "technologies": [],
                    "url": ""
                }
            ],
            "certifications": [],
            "languages": []
        }
        
        # Define user prompt
        user_prompt = f"""
        Parse the following resume text and return a clean, structured JSON object exactly matching this schema:
        {json.dumps(resume_schema, indent=2)}
        
        Special Instructions:
        - Extract the "About" section content into the "summary" field
        - Look for sections labeled as "About", "Professional Summary", "Summary", "Profile", "Objective"
        - Extract current location from contact information or experience
        - Identify the most recent or current job title for "current_job_title"
        - For project descriptions, if they contain bullet points, return them as an array of strings
        
        Resume Text:
        {text}
        
        Return ONLY the JSON object with no additional text or explanation.
        """
        
        # Maximum of 3 retries
        max_retries = 3
        attempt = 0
        
        while attempt < max_retries:
            try:
                response = self.openai_client.chat.completions.create(
                    model=model,
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_prompt}
                    ],
                    temperature=0.1,  # Lower temperature for more consistent output
                    max_tokens=2000  # Ensure enough tokens for the response
                )
                
                content = response.choices[0].message.content
                if not content:
                    raise ValueError("Empty response from OpenAI API")
                
                # Extract JSON from the response
                json_match = re.search(r'({[\s\S]*})', content)
                json_str = json_match.group(0) if json_match else content
                
                # Parse and validate the JSON
                ai_parsed = json.loads(json_str)
                
                # Convert AI response to new format
                resume_data = self._convert_ai_response_to_resume_data(ai_parsed)
                
                # Create complete response
                complete_response = CompleteResumeResponse(
                    resumeData=resume_data,
                    lastEdited=datetime.utcnow().isoformat() + "Z"
                )
                
                # Cache the result if Redis is available
                if self.redis_client:
                    cache_key = self.get_cache_key(text)
                    self.redis_client.setex(
                        cache_key,
                        settings.REDIS_TTL,  # TTL from settings (default 24 hours)
                        complete_response.json()
                    )
                    
                return complete_response
                
            except Exception as e:
                logger.error(f"Parsing attempt {attempt + 1} failed: {str(e)}")
                attempt += 1
                if attempt >= max_retries:
                    raise ValueError(f"Failed to parse resume after multiple attempts: {str(e)}")
                # Exponential backoff before retry (1s, 2s, 4s)
                time.sleep(2 ** attempt)
        
        raise ValueError("Failed to parse resume after multiple attempts")