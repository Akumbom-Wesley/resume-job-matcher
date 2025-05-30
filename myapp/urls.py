from django.urls import path
from .views import ResumeAnalyzer, upload_resume

urlpatterns = [
    path('analyze-resume/', ResumeAnalyzer.as_view(), name='analyze-resume'),
    path('upload/', upload_resume, name='upload-resume'),
]