from rest_framework import viewsets, generics, permissions, status
from rest_framework.response import Response
from rest_framework.decorators import action
from rest_framework.parsers import MultiPartParser, FormParser
from django.shortcuts import get_object_or_404
from django.db.models import Q
from django.contrib.auth import get_user_model

from .models import ChatRoom, ChatMessage
from .serializers import ChatRoomSerializer, ChatMessageSerializer

User = get_user_model()

class ChatRoomViewSet(viewsets.ModelViewSet):
    serializer_class = ChatRoomSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        # Retrieve rooms where user is either the doctor or the patient
        queryset = ChatRoom.objects.filter(Q(doctor=user) | Q(patient=user))
        
        # Allow filtering by status (?status=pending, ?status=accepted, etc.)
        status_param = self.request.query_params.get('status')
        if status_param:
            queryset = queryset.filter(status=status_param)
            
        return queryset

    @action(detail=True, methods=['post'])
    def accept(self, request, pk=None):
        room = self.get_object()
        if request.user != room.doctor:
            return Response(
                {"detail": "Only the doctor assigned to this request can accept it."},
                status=status.HTTP_403_FORBIDDEN
            )
        room.status = 'accepted'
        room.save()
        return Response(self.get_serializer(room).data)

    @action(detail=True, methods=['post'])
    def decline(self, request, pk=None):
        room = self.get_object()
        if request.user != room.doctor:
            return Response(
                {"detail": "Only the doctor assigned to this request can decline it."},
                status=status.HTTP_403_FORBIDDEN
            )
        room.status = 'declined'
        room.save()
        return Response(self.get_serializer(room).data)

    def create(self, request, *args, **kwargs):
        doctor_id = request.data.get('doctor')
        patient_id = request.data.get('patient')

        if not doctor_id or not patient_id:
            return Response(
                {"detail": "Both doctor and patient IDs are required."}, 
                status=status.HTTP_400_BAD_REQUEST
            )

        doctor = get_object_or_404(User, id=doctor_id, role=User.PROVIDER)
        patient = get_object_or_404(User, id=patient_id, role=User.PATIENT)

        # Check permissions: doctor or patient must be the logged-in user
        if request.user != doctor and request.user != patient:
            return Response(
                {"detail": "You can only create rooms involving yourself."},
                status=status.HTTP_403_FORBIDDEN
            )

        # Get or create the room (to prevent duplicate rooms for the same pair)
        room, created = ChatRoom.objects.get_or_create(doctor=doctor, patient=patient)
        serializer = self.get_serializer(room)
        
        return Response(
            serializer.data, 
            status=status.HTTP_201_CREATED if created else status.HTTP_200_OK
        )

class RoomMessagesListView(generics.ListAPIView):
    serializer_class = ChatMessageSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        room_id = self.kwargs['room_id']
        room = get_object_or_404(ChatRoom, id=room_id)
        
        # Access control: user must participate in this chat room
        if room.doctor != self.request.user and room.patient != self.request.user:
            self.permission_denied(
                self.request, 
                message="You are not a participant in this room."
            )
            
        # Automatically mark incoming messages as read when loading history
        room.messages.exclude(sender=self.request.user).update(is_read=True)
        
        return room.messages.all().order_by('created_at')


class ChatAttachmentUploadView(generics.CreateAPIView):
    permission_classes = [permissions.IsAuthenticated]
    parser_classes = [MultiPartParser, FormParser]
    serializer_class = ChatMessageSerializer

    def create(self, request, *args, **kwargs):
        room_id = request.data.get('room') or request.data.get('room_id')
        file_obj = request.FILES.get('file')
        msg_type = request.data.get('message_type', 'file') # 'image' or 'file'

        if not room_id or not file_obj:
            return Response(
                {"detail": "Both room ID and file are required."},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Verify room exists and user is participant
        room = get_object_or_404(ChatRoom, id=room_id)
        if room.doctor != request.user and room.patient != request.user:
            return Response(
                {"detail": "You are not a participant in this room."},
                status=status.HTTP_403_FORBIDDEN
            )

        # Enforce accepted room status
        if room.status != 'accepted':
            return Response(
                {"detail": "Cannot send messages. The chat request has not been accepted by the doctor yet."},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Create ChatMessage record
        db_message = ChatMessage.objects.create(
            room=room,
            sender=request.user,
            content=file_obj.name,
            message_type=msg_type,
            attachment=file_obj
        )

        # Build absolute URI for the serialized file link
        serializer = self.get_serializer(db_message)

        # Broadcast the message in real-time to the WebSocket group!
        from channels.layers import get_channel_layer
        from asgiref.sync import async_to_sync

        channel_layer = get_channel_layer()
        attachment_url = request.build_absolute_uri(db_message.attachment.url) if db_message.attachment else None
        
        async_to_sync(channel_layer.group_send)(
            f'chat_{room.id}',
            {
                'type': 'chat_message',
                'id': db_message.id,
                'sender_id': request.user.id,
                'sender_email': request.user.email,
                'sender_name': request.user.full_name,
                'content': db_message.content,
                'message_type': db_message.message_type,
                'attachment': attachment_url,
                'created_at': db_message.created_at.isoformat()
            }
        )

        return Response(serializer.data, status=status.HTTP_201_CREATED)
