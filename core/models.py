from django.db import models

class SiteSettings(models.Model):
    site_name = models.CharField(max_length=255)
    logo = models.ImageField(upload_to='site/')
    support_email = models.EmailField()