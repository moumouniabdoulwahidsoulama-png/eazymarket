from django.db import models
from django.contrib.auth.models import User

class Notification(models.Model):
    """Notification utilisateur, avec la trace de son envoi par SMS."""

    class Sms(models.TextChoices):
        NONE = "none", "Pas de SMS"
        SENT = "sent", "SMS envoyé"
        FAILED = "failed", "SMS en échec"

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='notifications')
    title = models.CharField(max_length=200)
    message = models.TextField()
    link = models.CharField(max_length=200, blank=True)
    is_read = models.BooleanField(default=False)
    is_urgent = models.BooleanField(
        "Urgente", default=False,
        help_text="Les notifications urgentes partent aussi par SMS",
    )
    sms_status = models.CharField(max_length=10, choices=Sms.choices, default=Sms.NONE)
    sms_detail = models.CharField(max_length=250, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.user.username} - {self.title}"
    
    def mark_as_read(self):
        self.is_read = True
        self.save()