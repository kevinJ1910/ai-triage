from django.db import models

class Patient(models.Model):
    GENDER_CHOICES = (
        ('male', 'Male'),
        ('female', 'Female'),
        ('other', 'Other'),
        ('unknown', 'Unknown'),
    )

    document_id = models.CharField(max_length=50, unique=True)
    full_name = models.CharField(max_length=255, blank=True, null=True, db_index=True)
    birth_date = models.DateField(blank=True, null=True)
    gender = models.CharField(max_length=20, choices=GENDER_CHOICES, default='unknown')
    phone = models.CharField(max_length=50, blank=True, null=True)
    insurance = models.CharField(max_length=255, blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['full_name'], name='patient_name_idx'),
            models.Index(fields=['-created_at'], name='patient_created_idx'),
        ]

    def __str__(self):
        return f"{self.full_name or 'Unknown'} ({self.document_id})"
