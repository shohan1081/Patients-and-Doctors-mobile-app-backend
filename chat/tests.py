from django.test import TestCase
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase
from django.contrib.auth import get_user_model
from .models import ChatRoom, ChatMessage
from django.core.files.uploadedfile import SimpleUploadedFile

User = get_user_model()

class MessageRequestAndChatTests(APITestCase):
    def setUp(self):
        # Create Patient
        self.patient = User.objects.create_user(
            email="pat1@example.com", username="pat1@example.com", full_name="Patient One", role=User.PATIENT, is_verified=True
        )
        self.patient.set_password("Password123!")
        self.patient.save()

        # Create Verified Doctor
        self.doctor = User.objects.create_user(
            email="doc1@example.com", username="doc1@example.com", full_name="Dr. Smith", role=User.PROVIDER, is_verified=True
        )
        self.doctor.set_password("Password123!")
        self.doctor.save()

        # Create Unverified Doctor
        self.unverified_doctor = User.objects.create_user(
            email="doc_unverified@example.com", username="doc_unverified@example.com", full_name="Dr. Pending", role=User.PROVIDER, is_verified=False
        )
        self.unverified_doctor.save()

        self.doctors_list_url = "/api/users/doctors/"
        self.rooms_url = "/api/chat/rooms/"

    def test_patient_list_verified_doctors_only(self):
        self.client.force_authenticate(user=self.patient)
        response = self.client.get(self.doctors_list_url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        # Should only return Dr. Smith, not the unverified doctor or patient
        self.assertEqual(len(response.data), 1)
        self.assertEqual(response.data[0]["email"], "doc1@example.com")
        self.assertEqual(response.data[0]["full_name"], "Dr. Smith")

    def test_message_request_flow(self):
        # 1. Patient initiates contact with the doctor
        self.client.force_authenticate(user=self.patient)
        data = {
            "doctor": self.doctor.id,
            "patient": self.patient.id
        }
        response = self.client.post(self.rooms_url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data["status"], "pending")
        
        room_id = response.data["id"]
        
        # 2. Try to accept as patient (should fail)
        response = self.client.post(f"{self.rooms_url}{room_id}/accept/")
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

        # 3. Accept as doctor (should succeed)
        self.client.force_authenticate(user=self.doctor)
        response = self.client.post(f"{self.rooms_url}{room_id}/accept/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["status"], "accepted")

        # 4. Check status in DB
        room = ChatRoom.objects.get(id=room_id)
        self.assertEqual(room.status, "accepted")

    def test_message_request_decline(self):
        # Patient initiates
        self.client.force_authenticate(user=self.patient)
        room = ChatRoom.objects.create(doctor=self.doctor, patient=self.patient, status="pending")

        # Decline as doctor
        self.client.force_authenticate(user=self.doctor)
        response = self.client.post(f"{self.rooms_url}{room.id}/decline/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["status"], "declined")

        room.refresh_from_db()
        self.assertEqual(room.status, "declined")

    def test_list_rooms_filter_by_status(self):
        # Create one pending room and one accepted room
        pending_room = ChatRoom.objects.create(doctor=self.doctor, patient=self.patient, status="pending")
        
        second_patient = User.objects.create_user(
            email="pat2@example.com", username="pat2@example.com", full_name="Patient Two", role=User.PATIENT, is_verified=True
        )
        accepted_room = ChatRoom.objects.create(doctor=self.doctor, patient=second_patient, status="accepted")

        self.client.force_authenticate(user=self.doctor)

        # Filter by status=pending
        response = self.client.get(f"{self.rooms_url}?status=pending")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 1)
        self.assertEqual(response.data[0]["id"], pending_room.id)

        # Filter by status=accepted
        response = self.client.get(f"{self.rooms_url}?status=accepted")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 1)
        self.assertEqual(response.data[0]["id"], accepted_room.id)

    def test_chat_attachment_upload_success(self):
        accepted_room = ChatRoom.objects.create(doctor=self.doctor, patient=self.patient, status="accepted")
        self.client.force_authenticate(user=self.patient)

        # Create dummy PDF file
        pdf_content = b'%PDF-1.4 dummy pdf content'
        pdf_file = SimpleUploadedFile("report.pdf", pdf_content, content_type="application/pdf")

        upload_data = {
            "room": accepted_room.id,
            "file": pdf_file,
            "message_type": "file"
        }
        
        response = self.client.post("/api/chat/messages/upload/", upload_data, format="multipart")
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data["message_type"], "file")
        self.assertIsNotNone(response.data["attachment"])
        self.assertIn("report", response.data["attachment"])

        # Verify chat message count in DB
        self.assertEqual(accepted_room.messages.count(), 1)
        self.assertEqual(accepted_room.messages.first().content, "report.pdf")

    def test_chat_attachment_upload_denied_if_pending(self):
        pending_room = ChatRoom.objects.create(doctor=self.doctor, patient=self.patient, status="pending")
        self.client.force_authenticate(user=self.patient)

        pdf_content = b'%PDF-1.4 dummy pdf content'
        pdf_file = SimpleUploadedFile("report.pdf", pdf_content, content_type="application/pdf")

        upload_data = {
            "room": pending_room.id,
            "file": pdf_file,
            "message_type": "file"
        }

        response = self.client.post("/api/chat/messages/upload/", upload_data, format="multipart")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(pending_room.messages.count(), 0)
