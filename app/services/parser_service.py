import json
import time
import hashlib
import logging
from typing import Dict, Any, Optional
import redis
import re
from openai import OpenAI
from app.config import settings
from app.models import ResumeData

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
    
    async def parse_resume_with_ai(self, text: str, complexity: str = 'simple') -> Dict[str, Any]:
        """
        Parse resume text using OpenAI API with retry mechanism
        
        Args:
            text: Preprocessed resume text
            complexity: 'simple' or 'complex' to determine model
            
        Returns:
            Parsed resume data as dictionary
        """
        # Check cache first if Redis is available
        if self.redis_client:
            cache_key = self.get_cache_key(text)
            cached_result = self.redis_client.get(cache_key)
            if cached_result:
                try:
                    return json.loads(cached_result)
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
        """
        
        # Resume schema to include in the prompt
        resume_schema = {
            "name": "",
            "email": "",
            "phone": "",
            "linkedin": "",
            "github": "",
            "portfolio": "",
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
                    "description": "",
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
                parsed = json.loads(json_str)
                
                # Cache the result if Redis is available
                if self.redis_client:
                    cache_key = self.get_cache_key(text)
                    self.redis_client.setex(
                        cache_key,
                        settings.REDIS_TTL,  # TTL from settings (default 24 hours)
                        json.dumps(parsed)
                    )
                    
                return parsed
                
            except Exception as e:
                logger.error(f"Parsing attempt {attempt + 1} failed: {str(e)}")
                attempt += 1
                if attempt >= max_retries:
                    raise ValueError(f"Failed to parse resume after multiple attempts: {str(e)}")
                # Exponential backoff before retry (1s, 2s, 4s)
                time.sleep(2 ** attempt)
        
        raise ValueError("Failed to parse resume after multiple attempts")