from django.db import models

class Job(models.Model):
    title = models.CharField(max_length=100)
    description = models.TextField()
    skills = models.JSONField()  # Stores skills as a list, e.g., ["Python", "Django"]

    def __str__(self):
        return self.title

class Resume(models.Model):
    pdf = models.FileField(upload_to='resumes/')  # Stores the PDF in media/resumes/
    text = models.TextField()  # Stores the extracted text

    def __str__(self):
        return f"Resume {self.id}"

class Match(models.Model):
    resume = models.ForeignKey(Resume, on_delete=models.CASCADE)
    job = models.ForeignKey(Job, on_delete=models.CASCADE)
    score = models.FloatField()  # Match score as a percentage
    matching_skills = models.JSONField()  # Skills that matched, e.g., ["Python"]

    def __str__(self):
        return f"Match: Resume {self.resume.id} - {self.job.title} ({self.score}%)"