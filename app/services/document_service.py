import os
import io
import base64
import re
from typing import Dict, List, Tuple
from io import BytesIO

import pdfplumber
import docx2txt
from app.config import settings

class DocumentService:
    """Service for processing document files"""
    
    @staticmethod
    def extract_text_from_file(file_buffer: BytesIO, file_extension: str) -> str:
        """
        Extract text from different file types
        
        Args:
            file_buffer: BytesIO buffer containing the file
            file_extension: File extension (e.g. '.pdf', '.docx')
            
        Returns:
            Extracted text from the file
        """
        if file_extension.lower() == '.pdf':
            return DocumentService.extract_text_from_pdf(file_buffer)
        elif file_extension.lower() == '.docx':
            return DocumentService.extract_text_from_docx(file_buffer)
        elif file_extension.lower() == '.txt':
            return file_buffer.read().decode('utf-8', errors='replace')
        else:
            raise ValueError(f"Unsupported file type: {file_extension}")
    
    @staticmethod
    def extract_text_from_pdf(buffer: BytesIO) -> str:
        """
        Extract text from PDF using pdfplumber with optimized settings
        
        Args:
            buffer: BytesIO buffer containing the PDF file
            
        Returns:
            Extracted text from the PDF
        """
        text = ""
        try:
            with pdfplumber.open(buffer) as pdf:
                for page in pdf.pages:
                    # Extract text with adjusted tolerance for better character grouping
                    page_text = page.extract_text(x_tolerance=3, y_tolerance=3)
                    if page_text:
                        text += page_text + "\n\n"
                    
                    # Extract tables separately for better structure
                    tables = page.extract_tables()
                    for table in tables:
                        if table:
                            text += "\n" + "\n".join([" | ".join([str(cell or "") for cell in row]) for row in table]) + "\n"
            return text
        except Exception as e:
            raise ValueError(f"PDF text extraction error: {str(e)}")
    
    @staticmethod
    def extract_text_from_docx(buffer: BytesIO) -> str:
        """
        Extract text from DOCX using docx2txt
        
        Args:
            buffer: BytesIO buffer containing the DOCX file
            
        Returns:
            Extracted text from the DOCX
        """
        try:
            text = docx2txt.process(buffer)
            return text
        except Exception as e:
            raise ValueError(f"DOCX text extraction error: {str(e)}")
    
    @staticmethod
    def preprocess_text(text: str) -> str:
        """
        Clean and normalize extracted text
        
        Args:
            text: Raw text extracted from document
            
        Returns:
            Preprocessed text
        """
        if not text:
            return ""
        
        # Remove excessive whitespace
        processed = re.sub(r'\s+', ' ', text)
        
        # Normalize line breaks for better section detection
        processed = re.sub(r'([A-Z][A-Z\s]+:?)\s*\n', r'\n\n\1\n', processed)
        
        # Clean up bullet points
        processed = re.sub(r'•\s*', '- ', processed)
        
        # Add newlines before capitalized sections that are likely headers
        processed = re.sub(r'([.!?])\s+([A-Z][A-Z]+)', r'\1\n\n\2', processed)
        
        return processed.strip()
    
    @staticmethod
    def classify_resume_complexity(text: str) -> str:
        """
        Determine if a resume is simple or complex to use the appropriate model
        
        Args:
            text: Preprocessed text from the resume
            
        Returns:
            'simple' or 'complex' based on resume complexity
        """
        # Count tokens (approximation)
        token_count = len(text.split())
        
        # Check for complex formatting patterns
        has_tables = '|' in text and text.count('|') > 10
        
        # Check for technical content
        technical_keywords = [
            'algorithm', 'framework', 'architecture', 'infrastructure', 
            'kubernetes', 'docker', 'aws', 'azure', 'cloud', 'devops',
            'backend', 'frontend', 'fullstack', 'machine learning', 'ai',
            'microservices', 'distributed', 'scalable', 'optimization'
        ]
        technical_count = sum(1 for word in technical_keywords if word.lower() in text.lower())
        
        # Calculate complexity score
        complexity_score = (
            (token_count > 1000) * 1 +
            has_tables * 2 +
            (technical_count > 5) * 2
        )
        
        return 'complex' if complexity_score >= 3 else 'simple'