from rest_framework import viewsets, generics, permissions, status
from rest_framework.response import Response
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
        return ChatRoom.objects.filter(Q(doctor=user) | Q(patient=user))

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
