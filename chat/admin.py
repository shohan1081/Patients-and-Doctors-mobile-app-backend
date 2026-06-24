from django.contrib import admin
from unfold.admin import ModelAdmin, TabularInline
from .models import ChatRoom, ChatMessage

class ChatMessageInline(TabularInline):
    model = ChatMessage
    extra = 0
    readonly_fields = ('sender', 'content', 'message_type', 'attachment', 'is_read', 'created_at')
    can_delete = False

@admin.register(ChatRoom)
class ChatRoomAdmin(ModelAdmin):
    list_display = ('id', 'doctor', 'patient', 'created_at')
    search_fields = ('doctor__email', 'doctor__full_name', 'patient__email', 'patient__full_name')
    ordering = ('-created_at',)
    inlines = [ChatMessageInline]

@admin.register(ChatMessage)
class ChatMessageAdmin(ModelAdmin):
    list_display = ('room', 'sender', 'message_type', 'is_read', 'created_at')
    list_filter = ('message_type', 'is_read', 'created_at')
    search_fields = ('sender__email', 'sender__full_name', 'content')
    ordering = ('-created_at',)
