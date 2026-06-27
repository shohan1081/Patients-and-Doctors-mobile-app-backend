from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import ChatRoomViewSet, RoomMessagesListView, ChatAttachmentUploadView

router = DefaultRouter()
router.register('rooms', ChatRoomViewSet, basename='chat_room')

urlpatterns = [
    path('rooms/<int:room_id>/messages/', RoomMessagesListView.as_view(), name='room_messages'),
    path('messages/upload/', ChatAttachmentUploadView.as_view(), name='chat_message_upload'),
    path('', include(router.urls)),
]
