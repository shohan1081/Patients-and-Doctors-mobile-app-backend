from django.db import models
from django.conf import settings

class ChatRoom(models.Model):
    doctor = models.ForeignKey(
        settings.AUTH_USER_MODEL, 
        on_delete=models.CASCADE, 
        limit_choices_to={'role': 'provider'}, 
        related_name='doctor_rooms'
    )
    patient = models.ForeignKey(
        settings.AUTH_USER_MODEL, 
        on_delete=models.CASCADE, 
        limit_choices_to={'role': 'patient'}, 
        related_name='patient_rooms'
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('doctor', 'patient')

    def __str__(self):
        return f"Chat between {self.doctor.full_name} and {self.patient.full_name}"

class ChatMessage(models.Model):
    MSG_TYPE = [
        ('text', 'Text'),
        ('image', 'Image'),
        ('file', 'File'),
    ]
    room = models.ForeignKey(ChatRoom, on_delete=models.CASCADE, related_name='messages')
    sender = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='sent_messages')
    content = models.TextField()
    message_type = models.CharField(max_length=10, choices=MSG_TYPE, default='text')
    attachment = models.FileField(upload_to='chat/attachments/', blank=True, null=True)
    is_read = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['created_at']

    def __str__(self):
        return f"Message by {self.sender.email} in Room {self.room_id} at {self.created_at}"
