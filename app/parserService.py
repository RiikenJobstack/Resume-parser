import openai
import json
from typing import Dict, Any, Optional
import logging
from app.config import settings

class AIResumeParser:
    def __init__(self, api_key: str, model: str = "gpt-4o-mini"):
        """
        Initialize the AI Resume Parser
        
        Args:
            api_key: OpenAI API key
            model: OpenAI model to use (gpt-4o-mini is cost-effective and good for this task)
        """
        self.client = openai.OpenAI(api_key=settings.OPENAI_API_KEY)
        self.model = model
        
    def parse_resume_with_ai(self, preprocessed_text: str, complexity: str = "medium") -> Dict[str, Any]:
        """
        Parse resume text using OpenAI to extract structured data
        
        Args:
            preprocessed_text: The preprocessed resume text
            complexity: Resume complexity level (affects parsing strategy)
            
        Returns:
            Structured resume data in the required format
        """
        
        # Define the target JSON schema
        target_schema = {
            "id": "null or string",
            "targetJobTitle": "string - inferred from job title or experience",
            "targetJobDescription": "string - empty by default",
            "personalInfo": {
                "fullName": "string",
                "jobTitle": "string - current or desired job title", 
                "email": "string",
                "phone": "string - digits only",
                "location": "string",
                "summary": "string - professional summary/objective",
                "profilePicture": "null"
            },
            "sections": [
                {
                    "id": "experience-1",
                    "type": "experience", 
                    "title": "Work Experience",
                    "order": 0,
                    "hidden": False,
                    "items": [
                        {
                            "jobTitle": "string",
                            "company": "string", 
                            "location": "string",
                            "startDate": "string or null (format: 'May 2024')",
                            "endDate": "string or null (format: 'May 2026' or 'Present')",
                            "currentPosition": "boolean",
                            "description": "string - job responsibilities and achievements"
                        }
                    ],
                    "groups": [],
                    "state": {}
                },
                {
                    "id": "projects-1",
                    "type": "projects",
                    "title": "Projects", 
                    "order": 1,
                    "hidden": False,
                    "items": [
                        {
                            "name": "string - project name",
                            "description": "string - project description",
                            "technologies": ["array of technology strings"],
                            "startDate": "string or null",
                            "endDate": "string or null", 
                            "url": "string - project URL if available"
                        }
                    ],
                    "groups": [],
                    "state": {}
                },
                {
                    "id": "education-1", 
                    "type": "education",
                    "title": "Education",
                    "order": 2,
                    "hidden": False,
                    "items": [
                        {
                            "degree": "string - degree name",
                            "institution": "string - school/university name",
                            "location": "string",
                            "startDate": "string or null",
                            "endDate": "string or null",
                            "gpa": "string - GPA if available",
                            "description": "string - additional details"
                        }
                    ],
                    "groups": [],
                    "state": {}
                },
                {
                    "id": "skills-1",
                    "type": "skills", 
                    "title": "Skills",
                    "order": 3,
                    "format": "grouped",
                    "hidden": False,
                    "items": [
                        {
                            "name": "string - skill name",
                            "category": "string - skill category",
                            "level": "string - proficiency level if mentioned"
                        }
                    ],
                    "groups": [
                        {
                            "name": "string - category name",
                            "skills": ["array of skill names in this category"]
                        }
                    ],
                    "state": {
                        "categoryOrder": [],
                        "viewMode": "categorized"
                    }
                }
            ]
        }
        
        # Create the system prompt
        system_prompt = f"""You are an expert resume parser. Your task is to extract structured information from resume text and return it in a specific JSON format.

IMPORTANT INSTRUCTIONS:
1. Extract ALL information accurately from the provided resume text
2. If information is missing or unclear, use null or empty string as appropriate
3. For dates, use format like "May 2024" or "Present" for current positions
4. Group skills by categories when possible (e.g., "Programming Languages", "Frontend Technologies")
5. Infer targetJobTitle from the person's current job title or most recent experience
6. Extract complete job descriptions and project descriptions
7. Phone numbers should contain only digits
8. Return ONLY valid JSON - no additional text or explanations

TARGET JSON SCHEMA:
{json.dumps(target_schema, indent=2)}

Parse the resume and return the data in exactly this structure."""

        user_prompt = f"""Please parse this resume text and extract structured information:

RESUME TEXT:
{preprocessed_text}

Return the parsed data as JSON in the exact format specified in the system prompt."""

        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                temperature=0.1,  # Low temperature for consistent parsing
                max_tokens=4000,
                response_format={"type": "json_object"}  # Ensures JSON response
            )
            
            # Parse the JSON response
            parsed_data = json.loads(response.choices[0].message.content)
            
            # Validate and clean the parsed data
            validated_data = self._validate_and_clean_data(parsed_data)
            
            return validated_data
            
        except Exception as e:
            logging.error(f"Error parsing resume with AI: {str(e)}")
            # Fallback to basic structure if AI parsing fails
            return self._get_fallback_structure(preprocessed_text)
    
    def _validate_and_clean_data(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Validate and clean the parsed data to ensure it matches expected structure
        """
        # Ensure required fields exist
        if 'personalInfo' not in data:
            data['personalInfo'] = {}
        
        # Set defaults for personalInfo
        personal_defaults = {
            "fullName": "",
            "jobTitle": "",
            "email": "",
            "phone": "",
            "location": "",
            "summary": "",
            "profilePicture": None
        }
        
        for key, default_value in personal_defaults.items():
            if key not in data['personalInfo']:
                data['personalInfo'][key] = default_value
        
        # Ensure sections exist and have proper structure
        if 'sections' not in data:
            data['sections'] = []
        
        # Validate each section
        for section in data['sections']:
            if 'items' not in section:
                section['items'] = []
            if 'groups' not in section:
                section['groups'] = []
            if 'state' not in section:
                section['state'] = {}
        
        # Set defaults for top-level fields
        if 'id' not in data:
            data['id'] = None
        if 'targetJobTitle' not in data:
            data['targetJobTitle'] = data.get('personalInfo', {}).get('jobTitle', '').lower()
        if 'targetJobDescription' not in data:
            data['targetJobDescription'] = ""
        
        return data
    
    def _get_fallback_structure(self, text: str) -> Dict[str, Any]:
        """
        Provide a basic fallback structure if AI parsing fails
        """
        lines = text.split('\n')
        name = ""
        
        # Try to extract name from first line
        for line in lines:
            if line.strip():
                name = line.strip()
                break
        
        return {
            "id": None,
            "targetJobTitle": "",
            "targetJobDescription": "",
            "personalInfo": {
                "fullName": name,
                "jobTitle": "",
                "email": "",
                "phone": "",
                "location": "",
                "summary": "",
                "profilePicture": None
            },
            "sections": [
                {
                    "id": "experience-1",
                    "type": "experience",
                    "title": "Work Experience",
                    "order": 0,
                    "hidden": False,
                    "items": [],
                    "groups": [],
                    "state": {}
                },
                {
                    "id": "projects-1",
                    "type": "projects",
                    "title": "Projects",
                    "order": 1,
                    "hidden": False,
                    "items": [],
                    "groups": [],
                    "state": {}
                },
                {
                    "id": "education-1",
                    "type": "education",
                    "title": "Education",
                    "order": 2,
                    "hidden": False,
                    "items": [],
                    "groups": [],
                    "state": {}
                },
                {
                    "id": "skills-1",
                    "type": "skills",
                    "title": "Skills",
                    "order": 3,
                    "format": "grouped",
                    "hidden": False,
                    "items": [],
                    "groups": [],
                    "state": {
                        "categoryOrder": [],
                        "viewMode": "categorized"
                    }
                }
            ]
        }


# Enhanced service integration
class EnhancedDocumentService:
    def __init__(self, openai_api_key: str):
        self.ai_parser = AIResumeParser(openai_api_key)
    
    async def parse_resume_with_ai(self, preprocessed_text: str, complexity: str) -> Dict[str, Any]:
        """
        Parse resume using AI with error handling and retries
        """
        try:
            # First attempt with the specified model
            result = self.ai_parser.parse_resume_with_ai(preprocessed_text, complexity)
            return result
            
        except Exception as e:
            # Log the error
            logging.error(f"Primary AI parsing failed: {str(e)}")
            
            # Try with a different model or approach
            try:
                # Retry with gpt-3.5-turbo if gpt-4 fails (cheaper fallback)
                fallback_parser = AIResumeParser(
                    self.ai_parser.client.api_key, 
                    model="gpt-3.5-turbo"
                )
                result = fallback_parser.parse_resume_with_ai(preprocessed_text, complexity)
                return result
                
            except Exception as e2:
                logging.error(f"Fallback AI parsing also failed: {str(e2)}")
                # Return basic structure as last resort
                return self.ai_parser._get_fallback_structure(preprocessed_text)


# Updated main function integration
async def process_resume_with_ai(file_buffer, ext, openai_api_key: str):
    """
    Enhanced resume processing with AI parsing
    """
    try:
        # Extract and preprocess text (your existing logic)
        raw_text = DocumentService.extract_text_from_file(file_buffer, ext)
        preprocessed_text = DocumentService.preprocess_text(raw_text)
        complexity = DocumentService.classify_resume_complexity(preprocessed_text)
        
        # Initialize AI service
        ai_service = EnhancedDocumentService(openai_api_key)
        
        # Parse with AI
        try:
            parsed_data = await ai_service.parse_resume_with_ai(preprocessed_text, complexity)
        except ValueError as e:
            raise HTTPException(status_code=500, detail=f"Failed to parse resume: {str(e)}")
        
        return JSONResponse({
            "extracted_text": preprocessed_text,
            "complexity": complexity,
            "resumeData": parsed_data  # This is now the structured AI-parsed data
        })
        
    except Exception as e:
        logging.error(f"Resume processing failed: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Resume processing failed: {str(e)}")


# Usage example with your existing code structure:
"""
# In your main function, replace the parsing logic:

try:
    raw_text = DocumentService.extract_text_from_file(file_buffer, ext)
    preprocessed_text = DocumentService.preprocess_text(raw_text)
    complexity = DocumentService.classify_resume_complexity(preprocessed_text)
    
    # Initialize AI parser
    ai_service = EnhancedDocumentService(openai_api_key="your-openai-api-key")
    
    # Parse with AI
    parsed_data = await ai_service.parse_resume_with_ai(preprocessed_text, complexity)
    
    return JSONResponse({
        "extracted_text": preprocessed_text,
        "complexity": complexity,
        "resumeData": parsed_data
    })
    
except Exception as e:
    raise HTTPException(status_code=500, detail=f"Failed to process resume: {str(e)}")
"""