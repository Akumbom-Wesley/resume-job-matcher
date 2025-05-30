import json
import re
from typing import List, Set, Dict
import google.generativeai as genai
from django.conf import settings
from .database import SkillsDatabase

class AIExtractor:
    """Extracts skills using AI."""

    def __init__(self, api_key: str):
        genai.configure(api_key=api_key)
        self.model = genai.GenerativeModel('gemini-2.0-flash')

    def extract(self, resume_text: str, known_skills: Set[str] = None) -> List[str]:
        """Extract skills using AI with context from known skills."""
        context = ""
        if known_skills:
            sample_skills = list(known_skills)[:30]
            context = f"Here are some example skills to guide you: {', '.join(sample_skills)}"

        prompt = f"""
Extract ALL relevant skills from this resume. Include technical skills, soft skills, 
tools, technologies, certifications, and any other professional capabilities mentioned.

{context}

Resume text:
{resume_text}

Return ONLY a JSON object with this exact format:
{{"skills": ["skill1", "skill2", "skill3"]}}

No additional text or formatting.
"""
        try:
            response = self.model.generate_content(prompt)
            clean_response = self._clean_response(response.text)
            data = json.loads(clean_response)
            return data.get('skills', [])
        except Exception as e:
            print(f"AI extraction failed: {e}")
            return []

    def _clean_response(self, text: str) -> str:
        """Clean AI response to valid JSON."""
        if not text:
            return "{}"
        text = text.strip()
        if text.startswith("```json"):
            text = text[7:]
        elif text.startswith("```"):
            text = text[3:]
        if text.endswith("```"):
            text = text[:-3]
        return text.strip("` \n")

class PatternExtractor:
    """Extracts skills using pattern matching."""

    def __init__(self, known_skills: Set[str]):
        self.known_skills = {skill.lower() for skill in known_skills}

    def extract(self, resume_text: str) -> List[str]:
        """Extract skills using pattern matching against known skills."""
        found_skills = []
        text_lower = resume_text.lower()

        for skill in self.known_skills:
            if self._skill_matches(skill, text_lower):
                original_skill = next((s for s in self.known_skills if s.lower() == skill), skill)
                found_skills.append(skill.title())

        return found_skills

    def _skill_matches(self, skill: str, text: str) -> bool:
        """Check if skill appears in text with various matching strategies."""
        if skill in text:
            return True
        clean_skill = re.sub(r'[^\w\s]', '', skill)
        clean_text = re.sub(r'[^\w\s]', ' ', text)
        if clean_skill in clean_text:
            return True
        if len(skill) <= 4:
            pattern = r'\b' + re.escape(skill) + r'\b'
            if re.search(pattern, text, re.IGNORECASE):
                return True
        return False

class SectionExtractor:
    """Extracts skills from resume sections."""

    def extract(self, resume_text: str) -> List[str]:
        """Extract skills from structured resume sections."""
        skills = []
        skills_section = self._find_skills_section(resume_text)
        if skills_section:
            skills.extend(self._parse_skills_section(skills_section))
        return [skill.title() for skill in skills]  # Ensure consistent casing

    def _find_skills_section(self, text: str) -> str:
        """Find and extract the skills section."""
        patterns = [
            r'(?:technical\s+)?skills[:\s]*(.*?)(?=\n\n|\n[A-Z][a-z]+|\n[A-Z][A-Z\s]+\n|$)',
            r'competencies[:\s]*(.*?)(?=\n\n|\n[A-Z][a-z]+|\n[A-Z][A-Z\s]+\n|$)',
            r'technologies[:\s]*(.*?)(?=\n\n|\n[A-Z][a-z]+|\n[A-Z][A-Z\s]+\n|$)',
        ]
        for pattern in patterns:
            matches = re.findall(pattern, text, re.IGNORECASE | re.DOTALL)
            if matches:
                return matches[0].strip()
        return ""

    def _parse_skills_section(self, section_text: str) -> List[str]:
        """Parse skills from the skills section text."""
        skills = []
        clean_text = re.sub(r'[•\-\*]', '', section_text)
        items = re.split(r'[,\n|;]', clean_text)
        for item in items:
            clean_item = item.strip()
            if len(clean_item) > 1 and not clean_item.isdigit():
                if ':' in clean_item:
                    parts = clean_item.split(':', 1)
                    if len(parts) > 1:
                        sub_skills = re.split(r'[,|;]', parts[1])
                        skills.extend([s.strip() for s in sub_skills if s.strip()])
                else:
                    skills.append(clean_item)
        return skills

class SkillsExtractor:
    """Main skills extraction orchestrator."""

    def __init__(self):
        self.db = SkillsDatabase()
        self.ai_extractor = AIExtractor(settings.API_KEY)

    def extract_skills(self, resume_text: str) -> Dict[str, any]:
        """
        Extract skills using multiple methods.

        Returns:
            {
                'skills': List[str] - final deduplicated skills
                'confidence': str - confidence level
                'methods_used': List[str] - which methods found skills
                'total_found': int - total number of skills found
            }
        """
        all_skills = set()
        methods_used = []
        known_skills = self.db.get_all_skills()

        # Method 1: AI Extraction
        ai_skills = self.ai_extractor.extract(resume_text, known_skills)
        if ai_skills:
            all_skills.update(ai_skills)
            methods_used.append('ai')

        # Method 2: Pattern Matching
        pattern_extractor = PatternExtractor(known_skills)
        pattern_skills = pattern_extractor.extract(resume_text)
        if pattern_skills:
            all_skills.update(pattern_skills)
            methods_used.append('pattern')

        # Method 3: Section Extraction
        section_extractor = SectionExtractor()
        section_skills = section_extractor.extract(resume_text)
        if section_skills:
            validated_skills = [s for s in section_skills if s.lower() in {skill.lower() for skill in known_skills}]
            if validated_skills:
                all_skills.update(validated_skills)
                methods_used.append('section')

        # Determine confidence
        confidence = self._calculate_confidence(len(all_skills), len(methods_used))

        return {
            'skills': sorted(list(all_skills)),
            'confidence': confidence,
            'methods_used': methods_used,
            'total_found': len(all_skills)
        }

    def _calculate_confidence(self, skills_count: int, methods_count: int) -> str:
        """Calculate confidence based on skills found and methods that worked."""
        if skills_count == 0:
            return 'very_low'
        elif skills_count < 3:
            return 'low'
        elif skills_count < 8:
            return 'medium'
        elif methods_count >= 2:
            return 'high'
        else:
            return 'medium'