import json
from channels.generic.websocket import AsyncWebsocketConsumer
from channels.db import database_sync_to_async
from django.contrib.auth import get_user_model
from rest_framework_simplejwt.tokens import AccessToken

User = get_user_model()

@database_sync_to_async
def get_user_from_token(token):
    try:
        access_token = AccessToken(token)
        user_id = access_token['user_id']
        return User.objects.get(id=user_id)
    except Exception:
        return None

class ChatConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        self.room_id = self.scope['url_route']['kwargs']['room_id']
        self.room_group_name = f'chat_{self.room_id}'

        # Get token from query string safely
        from urllib.parse import parse_qs
        query_string = self.scope.get('query_string', b'').decode('utf-8')
        query_params = parse_qs(query_string)
        token = query_params.get('token', [None])[0]

        self.user = None
        if token:
            self.user = await get_user_from_token(token)

        # Authenticate user and verify room membership
        if not self.user or not await self.is_member_of_room(self.room_id, self.user):
            await self.close()
            return

        # Join room group
        await self.channel_layer.group_add(
            self.room_group_name,
            self.channel_name
        )

        await self.accept()

    async def disconnect(self, close_code):
        # Leave room group
        if hasattr(self, 'room_group_name'):
            await self.channel_layer.group_discard(
                self.room_group_name,
                self.channel_name
            )

    async def receive(self, text_data):
        try:
            data = json.loads(text_data)
        except json.JSONDecodeError:
            return

        # Fallback to allow sending either 'message' or 'content'
        content = data.get('message') or data.get('content')
        message_type = data.get('message_type', 'text')

        if not content:
            return

        # Save message to database
        db_message = await self.save_message(self.room_id, self.user, content, message_type)
        if not db_message:
            return

        # Send message to room group
        await self.channel_layer.group_send(
            self.room_group_name,
            {
                'type': 'chat_message',
                'id': db_message.id,
                'sender_id': self.user.id,
                'sender_email': self.user.email,
                'sender_name': self.user.full_name,
                'content': content,
                'message_type': message_type,
                'attachment': db_message.attachment.url if db_message.attachment else None,
                'created_at': db_message.created_at.isoformat()
            }
        )

    async def chat_message(self, event):
        # Send message to WebSocket
        await self.send(text_data=json.dumps({
            'id': event['id'],
            'sender_id': event['sender_id'],
            'sender_email': event['sender_email'],
            'sender_name': event['sender_name'],
            'message': event['content'],
            'content': event['content'],
            'message_type': event['message_type'],
            'attachment': event.get('attachment'),
            'created_at': event['created_at']
        }))

    @database_sync_to_async
    def is_member_of_room(self, room_id, user):
        from .models import ChatRoom
        try:
            room = ChatRoom.objects.get(id=room_id)
            return room.doctor == user or room.patient == user
        except ChatRoom.DoesNotExist:
            return False

    @database_sync_to_async
    def save_message(self, room_id, sender, content, message_type):
        from .models import ChatRoom, ChatMessage
        try:
            room = ChatRoom.objects.get(id=room_id)
            if room.status != 'accepted':
                return None
            return ChatMessage.objects.create(
                room=room,
                sender=sender,
                content=content,
                message_type=message_type
            )
        except Exception:
            return None
