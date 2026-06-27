from rest_framework import serializers
from django.contrib.auth import get_user_model
from .models import ChatRoom, ChatMessage
from users.serializers import UserSerializer

User = get_user_model()

class ChatRoomSerializer(serializers.ModelSerializer):
    doctor_detail = UserSerializer(source='doctor', read_only=True)
    patient_detail = UserSerializer(source='patient', read_only=True)
    last_message = serializers.SerializerMethodField()

    class Meta:
        model = ChatRoom
        fields = ('id', 'doctor', 'patient', 'status', 'doctor_detail', 'patient_detail', 'last_message', 'created_at')
        read_only_fields = ('status', 'created_at')

    def get_last_message(self, obj):
        msg = obj.messages.last()
        if msg:
            return {
                'id': msg.id,
                'content': msg.content,
                'message_type': msg.message_type,
                'sender_id': msg.sender_id,
                'sender_name': msg.sender.full_name,
                'created_at': msg.created_at.isoformat()
            }
        return None

class ChatMessageSerializer(serializers.ModelSerializer):
    sender_name = serializers.CharField(source='sender.full_name', read_only=True)
    sender_email = serializers.CharField(source='sender.email', read_only=True)

    class Meta:
        model = ChatMessage
        fields = ('id', 'room', 'sender', 'sender_name', 'sender_email', 'content', 'message_type', 'attachment', 'is_read', 'created_at')
        read_only_fields = ('sender', 'is_read', 'created_at')
