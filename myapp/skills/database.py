import pandas as pd
from pathlib import Path
from typing import Set
from django.conf import settings
import re

class SkillsDatabase:
    """Manages skill database from Excel file."""

    def __init__(self):
        self.excel_path = getattr(settings, 'SKILLS_EXCEL_PATH', 'technology-skills.xlsx')
        self._skills_cache = None

    def get_all_skills(self) -> Set[str]:
        """Get all skills from Excel file as a flat set."""
        if self._skills_cache is not None:
            return self._skills_cache

        skills = set()
        try:
            excel_skills = self._load_excel_skills()
            skills.update(excel_skills)
        except Exception as e:
            print(f"Warning: Could not load Excel skills: {e}")

        # Clean and normalize skills with validation
        self._skills_cache = {self._normalize_skill(skill) for skill in skills if self._is_valid_skill(skill)}
        return self._skills_cache

    def _load_excel_skills(self) -> list[str]:
        """Load skills from Excel file."""
        if not Path(self.excel_path).exists():
            print(f"Excel file not found at {self.excel_path}")
            return []

        skills = []
        try:
            excel_file = pd.ExcelFile(self.excel_path)
            for sheet_name in excel_file.sheet_names:
                df = pd.read_excel(self.excel_path, sheet_name=sheet_name)
                for col in ['skill', 'skills', 'name', 'title']:
                    if col in df.columns:
                        skills.extend(df[col].dropna().astype(str).tolist())
                        break
                else:
                    skills.extend(df.iloc[:, 0].dropna().astype(str).tolist())
        except Exception as e:
            print(f"Error reading Excel: {e}")
            # Fallback: read default sheet
            df = pd.read_excel(self.excel_path)
            for col in ['skill', 'skills', 'name', 'title']:
                if col in df.columns:
                    skills.extend(df[col].dropna().astype(str).tolist())
                    break
            else:
                skills.extend(df.iloc[:, 0].dropna().astype(str).tolist())

        return skills

    def _normalize_skill(self, skill: str) -> str:
        """Normalize skill for consistent matching."""
        return skill.strip().title()

    def _is_valid_skill(self, skill: str) -> bool:
        """Validate skill to exclude invalid entries."""
        if not skill or len(skill.strip()) <= 2:
            return False
        if re.match(r'^\d+$', skill) or skill.lower() in ['birth', 'email', 'com', 'github', 'linkedin', 'bullet']:
            return False
        if re.match(r'^[A-Za-z][&+]?[A-Za-z]?$', skill) or skill.lower() in ['a+', 'ethics', 'startup']:
            return False
        if not re.search(r'[A-Za-z]{3,}', skill):
            return False
        return True