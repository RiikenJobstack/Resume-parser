import re
from typing import Dict, List, Any, Optional
from datetime import datetime

class ResumeParser:
    def __init__(self):
        self.sections_map = {
            'work experience': 'experience',
            'experience': 'experience',
            'employment': 'experience',
            'professional experience': 'experience',
            'projects': 'projects',
            'education': 'education',
            'academic background': 'education',
            'skills': 'skills',
            'technical skills': 'skills',
            'core competencies': 'skills',
        }
    
    def parse_resume_text(self, preprocessed_text: str) -> Dict[str, Any]:
        """
        Parse preprocessed resume text into structured JSON format
        """
        lines = preprocessed_text.strip().split('\n')
        
        # Extract personal info
        personal_info = self._extract_personal_info(lines)
        
        # Split content into sections
        sections_data = self._split_into_sections(lines)
        
        # Parse each section
        parsed_sections = self._parse_sections(sections_data)
        
        return {
            "id": None,
            "targetJobTitle": personal_info.get('jobTitle', '').lower().replace('engineer', 'developer'),
            "targetJobDescription": "",
            "personalInfo": personal_info,
            "sections": parsed_sections
        }
    
    def _extract_personal_info(self, lines: List[str]) -> Dict[str, Any]:
        """Extract personal information from the top of the resume"""
        personal_info = {
            "fullName": "",
            "jobTitle": "",
            "email": "",
            "phone": "",
            "location": "",
            "summary": "",
            "profilePicture": None
        }
        
        # Find name (usually first non-empty line)
        for line in lines:
            line = line.strip()
            if line and not self._is_section_header(line):
                personal_info["fullName"] = line
                break
        
        # Find contact info and job title
        contact_pattern = r'Phone:\s*(\d+)|Email:\s*([\w\.-]+@[\w\.-]+)|Location:\s*([^—\n]+)'
        
        for i, line in enumerate(lines[:10]):  # Check first 10 lines
            line = line.strip()
            
            # Check if it's a job title (after name, before contact info)
            if (line and not personal_info["jobTitle"] and 
                line != personal_info["fullName"] and 
                not re.search(contact_pattern, line) and
                not self._is_section_header(line) and
                len(line.split()) <= 4):
                personal_info["jobTitle"] = line
            
            # Extract contact information
            matches = re.findall(contact_pattern, line)
            for match in matches:
                if match[0]:  # Phone
                    personal_info["phone"] = match[0]
                if match[1]:  # Email
                    personal_info["email"] = match[1]
                if match[2]:  # Location
                    personal_info["location"] = match[2].strip()
        
        # Extract summary (usually under "Professional Summary" or similar)
        summary_section = self._find_summary_section(lines)
        if summary_section:
            personal_info["summary"] = summary_section
        
        return personal_info
    
    def _find_summary_section(self, lines: List[str]) -> str:
        """Find and extract the professional summary"""
        summary_keywords = ['professional summary', 'summary', 'profile', 'objective']
        
        for i, line in enumerate(lines):
            line_lower = line.strip().lower()
            if any(keyword in line_lower for keyword in summary_keywords):
                # Collect summary text until next section
                summary_lines = []
                for j in range(i + 1, len(lines)):
                    next_line = lines[j].strip()
                    if self._is_section_header(next_line):
                        break
                    if next_line:
                        summary_lines.append(next_line)
                
                return ' '.join(summary_lines)
        
        return ""
    
    def _is_section_header(self, line: str) -> bool:
        """Check if a line is a section header"""
        line_lower = line.strip().lower()
        section_keywords = [
            'work experience', 'experience', 'employment', 'professional experience',
            'projects', 'education', 'academic background', 'skills', 
            'technical skills', 'core competencies', 'professional summary',
            'summary', 'profile', 'objective'
        ]
        
        return any(keyword in line_lower for keyword in section_keywords)
    
    def _split_into_sections(self, lines: List[str]) -> Dict[str, List[str]]:
        """Split the resume into sections based on headers"""
        sections = {}
        current_section = None
        current_content = []
        
        for line in lines:
            line_stripped = line.strip()
            
            if self._is_section_header(line_stripped):
                # Save previous section
                if current_section and current_content:
                    sections[current_section] = current_content
                
                # Start new section
                current_section = line_stripped.lower()
                current_content = []
            elif current_section:
                current_content.append(line)
        
        # Save last section
        if current_section and current_content:
            sections[current_section] = current_content
        
        return sections
    
    def _parse_sections(self, sections_data: Dict[str, List[str]]) -> List[Dict[str, Any]]:
        """Parse each section into structured format"""
        parsed_sections = []
        section_order = 0
        
        # Define section order
        section_priorities = {
            'experience': 0,
            'projects': 1,
            'education': 2,
            'skills': 3
        }
        
        for section_name, content in sections_data.items():
            section_type = self._get_section_type(section_name)
            if section_type:
                parsed_section = self._parse_section_content(section_type, content, section_name)
                parsed_section['order'] = section_priorities.get(section_type, section_order)
                parsed_sections.append(parsed_section)
                section_order += 1
        
        # Sort by order
        parsed_sections.sort(key=lambda x: x['order'])
        
        return parsed_sections
    
    def _get_section_type(self, section_name: str) -> Optional[str]:
        """Map section name to section type"""
        for key, value in self.sections_map.items():
            if key in section_name:
                return value
        return None
    
    def _parse_section_content(self, section_type: str, content: List[str], section_name: str) -> Dict[str, Any]:
        """Parse content based on section type"""
        base_section = {
            "id": f"{section_type}-1",
            "type": section_type,
            "title": section_name.title(),
            "hidden": False,
            "items": [],
            "groups": [],
            "state": {}
        }
        
        if section_type == 'experience':
            base_section['items'] = self._parse_experience_items(content)
        elif section_type == 'projects':
            base_section['items'] = self._parse_project_items(content)
        elif section_type == 'education':
            base_section['items'] = self._parse_education_items(content)
        elif section_type == 'skills':
            base_section['format'] = 'grouped'
            base_section['items'], base_section['groups'] = self._parse_skills_items(content)
            base_section['state'] = {
                "categoryOrder": [],
                "viewMode": "categorized"
            }
        
        return base_section
    
    def _parse_experience_items(self, content: List[str]) -> List[Dict[str, Any]]:
        """Parse work experience items"""
        items = []
        current_item = {
            "jobTitle": "",
            "company": "",
            "location": "",
            "startDate": None,
            "endDate": None,
            "currentPosition": False,
            "description": ""
        }
        
        description_lines = []
        
        for line in content:
            line = line.strip()
            if not line:
                continue
            
            # Check for date pattern
            date_match = re.search(r'(.*?)(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec|\d{4})', line)
            if date_match and ('—' in line or '-' in line or 'present' in line.lower()):
                # This might be a job title with dates
                parts = re.split(r'[—-]', line)
                if len(parts) >= 2:
                    current_item["jobTitle"] = parts[0].strip()
                    # Parse dates
                    dates = self._parse_date_range(line)
                    current_item["startDate"] = dates[0]
                    current_item["endDate"] = dates[1]
                    current_item["currentPosition"] = 'present' in line.lower()
            
            # Check if it might be a company name (short line after job title)
            elif current_item["jobTitle"] and not current_item["company"] and len(line.split()) <= 3:
                current_item["company"] = line
            
            # Check if it might be a location
            elif current_item["company"] and not current_item["location"] and len(line.split()) <= 3:
                current_item["location"] = line
            
            # Everything else is description
            else:
                description_lines.append(line)
        
        current_item["description"] = ' '.join(description_lines)
        if any(current_item.values()):
            items.append(current_item)
        
        return items
    
    def _parse_project_items(self, content: List[str]) -> List[Dict[str, Any]]:
        """Parse project items"""
        items = []
        current_project = {}
        
        for line in content:
            line = line.strip()
            if not line:
                continue
            
            # Check for project with date
            if re.search(r'(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec|\d{4})', line):
                if current_project:
                    items.append(current_project)
                
                current_project = {
                    "name": "",
                    "description": "",
                    "technologies": [],
                    "startDate": None,
                    "endDate": None,
                    "url": ""
                }
                
                # Extract project name and dates
                parts = line.split('[View Project]') if '[View Project]' in line else [line]
                project_info = parts[0].strip()
                
                # Parse dates
                dates = self._parse_date_range(project_info)
                current_project["startDate"] = dates[0]
                current_project["endDate"] = dates[1]
                
                # Extract project name (before date)
                name_match = re.search(r'^(.*?)\s+(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec|\d{4})', project_info)
                if name_match:
                    current_project["name"] = name_match.group(1).strip()
            
            # Check for technologies
            elif line.startswith('Technologies:'):
                tech_list = line.replace('Technologies:', '').strip()
                current_project["technologies"] = [tech.strip() for tech in tech_list.split(',')]
            
            # Everything else is description
            else:
                if current_project:
                    if current_project["description"]:
                        current_project["description"] += " " + line
                    else:
                        current_project["description"] = line
        
        if current_project:
            items.append(current_project)
        
        return items
    
    def _parse_education_items(self, content: List[str]) -> List[Dict[str, Any]]:
        """Parse education items"""
        items = []
        current_item = {
            "degree": "",
            "institution": "",
            "location": "",
            "startDate": None,
            "endDate": None,
            "gpa": "",
            "description": ""
        }
        
        for line in content:
            line = line.strip()
            if not line:
                continue
            
            # Check for date pattern
            if re.search(r'(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec|\d{4})', line):
                dates = self._parse_date_range(line)
                current_item["startDate"] = dates[0]
                current_item["endDate"] = dates[1]
            
            # Check for degree
            elif any(keyword in line.lower() for keyword in ['bachelor', 'master', 'phd', 'degree', 'engineering']):
                current_item["degree"] = line
            
            # Check for GPA
            elif 'gpa' in line.lower():
                gpa_match = re.search(r'gpa:?\s*(\d+\.?\d*)', line.lower())
                if gpa_match:
                    current_item["gpa"] = gpa_match.group(1)
            
            # Institution or location
            else:
                if not current_item["institution"]:
                    current_item["institution"] = line
                elif not current_item["location"]:
                    current_item["location"] = line
        
        if any(current_item.values()):
            items.append(current_item)
        
        return items
    
    def _parse_skills_items(self, content: List[str]) -> tuple:
        """Parse skills into items and groups"""
        items = []
        groups = []
        
        current_category = ""
        
        for line in content:
            line = line.strip()
            if not line:
                continue
            
            # Check if line contains a category (ends with colon)
            if ':' in line:
                parts = line.split(':', 1)
                current_category = parts[0].strip()
                skills_text = parts[1].strip() if len(parts) > 1 else ""
                
                if skills_text:
                    skills_list = [skill.strip() for skill in skills_text.split(',')]
                    
                    # Add to groups
                    groups.append({
                        "name": current_category,
                        "skills": skills_list
                    })
                    
                    # Add individual items
                    for skill in skills_list:
                        items.append({
                            "name": skill,
                            "category": current_category,
                            "level": ""
                        })
        
        return items, groups
    
    def _parse_date_range(self, text: str) -> tuple:
        """Parse date range from text"""
        # Simple date parsing - can be enhanced
        start_date = None
        end_date = None
        
        # Look for patterns like "May 2024 — May 2026" or "May 2024 - Present"
        date_pattern = r'(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\s+(\d{4})'
        dates = re.findall(date_pattern, text)
        
        if dates:
            if len(dates) >= 1:
                start_date = f"{dates[0][0]} {dates[0][1]}"
            if len(dates) >= 2:
                end_date = f"{dates[1][0]} {dates[1][1]}"
            elif 'present' in text.lower():
                end_date = "Present"
        
        return start_date, end_date


# Usage example:
def parse_resume_from_preprocessed_text(preprocessed_text: str) -> Dict[str, Any]:
    """
    Main function to parse preprocessed resume text
    """
    parser = ResumeParser()
    return {
        "resumeData": parser.parse_resume_text(preprocessed_text)
    }


# Example usage:
if __name__ == "__main__":
    sample_text = """Puneet

software engineer

Phone: 4747474747 Email: admin@jobstack.ai — Location: location

Professional Summary

Accomplished software engineer with a passion for developing innovative solutions to complex
problems. Expertise in cloud-native applications and distributed systems. Proven ability to lead
teams and deliver projects on time and within budget.

Work Experience

; May 2024 -— May 2026
experience 1

company

location

Led a cross-functional team of 8 members in developing and implementing a new customer
relationship management system, resulting in a 30% increase in customer satisfaction scores and
25% reduction in response time.

Projects

netflix clone [View Project] May 2024 — Present
Technologies: React, JavaScript, Redux, Next.js

Spearheaded the optimization of internal workflows through process automation, reducing manual
workload by 40% and improving team productivity by implementing data-driven decision-making
protocols.

Education

. . May 2024 — May 2027
Bachelor's of engineering

institute one

location GPA: : 7.8

Skills

Programming Languages: JavaScript, Python, Java, C#, TypeScript, Go, Rust, C++
Backend Technologies: Flask, Spring, Django, Express, Node.js

Databases: SQL S: erver, MySQL: , PostgreSQL

F: rontend Technologies: React, Angular, Vue.js, HTML: 5, CSS: 3, Sass, Redux, Webpack"""

    result = parse_resume_from_preprocessed_text(sample_text)
    import json
    print(json.dumps(result, indent=2))