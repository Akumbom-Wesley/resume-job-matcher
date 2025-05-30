import os
from django.conf import settings
from django.shortcuts import render
from django.http import JsonResponse
from rest_framework.views import APIView
from rest_framework.parsers import MultiPartParser
from pdfminer.high_level import extract_text
import google.generativeai as genai
from .models import Job, Resume, Match
from .skills.extractors import SkillsExtractor

# Configure Gemini API
genai.configure(api_key=settings.API_KEY)
model = genai.GenerativeModel('gemini-2.0-flash')


def extract_text_from_pdf(pdf_file):
    """Extract text from a PDF file."""
    try:
        pdf_file.file.seek(0)
        text = extract_text(pdf_file.file)
        return text if text.strip() else None
    except Exception as e:
        print(f"PDF extraction error: {str(e)}")
        return None


def call_gemini(prompt):
    """Call Gemini with a given prompt."""
    try:
        response = model.generate_content(prompt)
        return response.text
    except Exception as e:
        print(f"Gemini API error: {str(e)}")
        return None


class ResumeAnalyzer(APIView):
    """API endpoint to analyze resumes and match against jobs."""
    parser_classes = [MultiPartParser]

    def post(self, request):
        pdf_file = request.FILES.get('resume')
        if not pdf_file:
            return JsonResponse({"error": "No PDF uploaded"}, status=400)

        resume_text = extract_text_from_pdf(pdf_file)
        if not resume_text:
            return JsonResponse({"error": "Failed to extract text"}, status=400)

        # Save resume
        resume = Resume.objects.create(pdf=pdf_file, text=resume_text)

        # Summarize
        summary_prompt = f"Summarize this resume in 3 sentences:\n\n{resume_text}"
        summary = call_gemini(summary_prompt)
        if not summary:
            return JsonResponse({"error": "Failed to summarize"}, status=500)

        # Extract skills using modular system
        skills_extractor = SkillsExtractor()
        extraction_result = skills_extractor.extract_skills(resume_text)

        skills = extraction_result['skills']
        print(f"Extracted {len(skills)} skills using methods: {extraction_result['methods_used']}")

        # Match against jobs
        matches = []
        for job in Job.objects.all():
            job_skills = set(job.skills) if hasattr(job, 'skills') and job.skills else set()
            resume_skills = set(skills)
            matching_skills = list(job_skills.intersection(resume_skills))
            score = (len(matching_skills) / len(job_skills)) * 100 if job_skills else 0

            match = Match.objects.create(
                resume=resume,
                job=job,
                score=round(score, 2),
                matching_skills=matching_skills
            )
            matches.append({
                "job": job.title,
                "score": match.score,
                "matching_skills": matching_skills
            })

        return JsonResponse({
            "summary": summary,
            "skills": skills,
            "extraction_info": {
                "confidence": extraction_result['confidence'],
                "methods_used": extraction_result['methods_used'],
                "total_found": extraction_result['total_found']
            },
            "matches": matches
        })


def upload_resume(request):
    """View for web-based resume upload and analysis."""
    if request.method == 'POST':
        pdf_file = request.FILES.get('resume')
        if not pdf_file:
            return render(request, 'upload.html', {'error': 'No PDF uploaded'})

        # Extract text
        resume_text = extract_text_from_pdf(pdf_file)
        if not resume_text:
            return render(request, 'upload.html', {'error': 'Failed to extract text. Please try a different PDF.'})

        # Store resume
        resume = Resume.objects.create(pdf=pdf_file, text=resume_text)

        # Summarize resume
        summary = call_gemini(f"Summarize this resume in 3 sentences:\n\n{resume_text}")
        if not summary:
            return render(request, 'upload.html', {'error': 'Failed to summarize'})

        # Extract skills using modular system
        skills_extractor = SkillsExtractor()
        extraction_result = skills_extractor.extract_skills(resume_text)
        skills = extraction_result['skills']

        # Match against jobs
        matches = []
        for job in Job.objects.all():
            job_skills = set(job.skills) if hasattr(job, 'skills') and job.skills else set()
            resume_skills = set(skills)
            matching_skills = list(job_skills.intersection(resume_skills))
            score = (len(matching_skills) / len(job_skills)) * 100 if job_skills else 0

            Match.objects.create(
                resume=resume,
                job=job,
                score=round(score, 2),
                matching_skills=matching_skills
            )
            matches.append({
                'job': job.title,
                'score': round(score, 2),
                'matching_skills': matching_skills
            })

        # Render result
        data = {
            'summary': summary,
            'skills': skills,
            'matches': matches,
            'extraction_info': extraction_result
        }
        return render(request, 'result.html', {'data': data})

    return render(request, 'upload.html')