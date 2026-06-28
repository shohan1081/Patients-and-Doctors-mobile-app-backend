from django.test import TestCase
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase
from django.contrib.auth import get_user_model
from appointments.models import DoctorPatientRelation
from django.core.files.uploadedfile import SimpleUploadedFile

User = get_user_model()

class PatientRegistrationAndLoginTests(APITestCase):
    def setUp(self):
        self.patient_signup_url = reverse('register_patient')
        self.provider_signup_url = reverse('register_provider')
        self.login_url = reverse('token_obtain_pair')

    def test_patient_signup_success(self):
        data = {
            "full_name": "Test Patient",
            "email": "testpatient@example.com",
            "phone_number": "1234567890",
            "password": "Password123!",
            "confirm_password": "Password123!"
        }
        response = self.client.post(self.patient_signup_url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data["message"], "Registration successful. You can now log in.")
        
        # Verify database record
        user = User.objects.get(email="testpatient@example.com")
        self.assertEqual(user.full_name, "Test Patient")
        self.assertEqual(user.role, User.PATIENT)
        self.assertTrue(user.is_verified)
        self.assertTrue(user.is_active)

    def test_patient_signup_password_mismatch(self):
        data = {
            "full_name": "Test Patient Mismatch",
            "email": "mismatch@example.com",
            "phone_number": "1234567890",
            "password": "Password123!",
            "confirm_password": "DifferentPassword!"
        }
        response = self.client.post(self.patient_signup_url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("password", response.data)

    def test_unified_login_success(self):
        # Create a patient and a doctor manually
        patient = User.objects.create_user(
            email="patient1@example.com",
            username="patient1@example.com",
            full_name="Patient One",
            role=User.PATIENT,
            is_verified=True,
            is_active=True
        )
        patient.set_password("Password123!")
        patient.save()

        doctor = User.objects.create_user(
            email="doctor1@example.com",
            username="doctor1@example.com",
            full_name="Doctor One",
            role=User.PROVIDER,
            is_verified=True,
            is_active=True
        )
        doctor.set_password("Password123!")
        doctor.save()

        # Login as patient
        patient_login_data = {
            "email": "patient1@example.com",
            "password": "Password123!"
        }
        response = self.client.post(self.login_url, patient_login_data, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("access", response.data)
        self.assertEqual(response.data["user"]["role"], User.PATIENT)

        # Login as doctor
        doctor_login_data = {
            "email": "doctor1@example.com",
            "password": "Password123!"
        }
        response = self.client.post(self.login_url, doctor_login_data, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("access", response.data)
        self.assertEqual(response.data["user"]["role"], User.PROVIDER)

    def test_provider_login_denied_if_not_verified(self):
        doctor = User.objects.create_user(
            email="doctor_unverified@example.com",
            username="doctor_unverified@example.com",
            full_name="Doctor Unverified",
            role=User.PROVIDER,
            is_verified=False,
            is_active=True
        )
        doctor.set_password("Password123!")
        doctor.save()

        login_data = {
            "email": "doctor_unverified@example.com",
            "password": "Password123!"
        }
        response = self.client.post(self.login_url, login_data, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("detail", response.data)
        self.assertEqual(response.data["detail"][0], "Your account is pending verification by an administrator.")


class DoctorPatientRelationTests(APITestCase):
    def setUp(self):
        # Create users
        self.doctor = User.objects.create_user(
            email="doc@example.com", username="doc@example.com", full_name="Dr. House", role=User.PROVIDER, is_verified=True
        )
        self.doctor.set_password("Password123!")
        self.doctor.save()

        self.patient = User.objects.create_user(
            email="pat@example.com", username="pat@example.com", full_name="John Doe", role=User.PATIENT, is_verified=True
        )
        self.patient.set_password("Password123!")
        self.patient.save()

        # Other doctor
        self.other_doctor = User.objects.create_user(
            email="otherdoc@example.com", username="otherdoc@example.com", full_name="Dr. Strange", role=User.PROVIDER, is_verified=True
        )
        self.other_doctor.set_password("Password123!")
        self.other_doctor.save()

        # URLs
        self.relations_url = "/api/appointments/patients/"

    def test_doctor_add_patient_success(self):
        self.client.force_authenticate(user=self.doctor)
        data = {
            "patient": self.patient.id,
            "disease_title": "Chronic Laziness",
            "health_goals": "Walk 10,000 steps daily",
            "current_conditions": "Fatigue",
            "current_medications": "Vitamin D",
            "allergies_intolerances": "Lactose intolerance"
        }
        response = self.client.post(self.relations_url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data["disease_title"], "Chronic Laziness")
        self.assertEqual(response.data["health_goals"], "Walk 10,000 steps daily")
        self.assertEqual(response.data["current_conditions"], "Fatigue")
        self.assertEqual(response.data["current_medications"], "Vitamin D")
        self.assertEqual(response.data["allergies_intolerances"], "Lactose intolerance")
        
        # Verify relation exists in db
        relation = DoctorPatientRelation.objects.get(doctor=self.doctor, patient=self.patient)
        self.assertEqual(relation.health_goals, "Walk 10,000 steps daily")
        self.assertEqual(relation.current_conditions, "Fatigue")
        self.assertEqual(relation.current_medications, "Vitamin D")
        self.assertEqual(relation.allergies_intolerances, "Lactose intolerance")

    def test_patient_cannot_access_relations(self):
        self.client.force_authenticate(user=self.patient)
        response = self.client.get(self.relations_url)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_doctor_list_linked_patients(self):
        # Link patients to both doctor and other_doctor
        DoctorPatientRelation.objects.create(doctor=self.doctor, patient=self.patient, disease_title="Flu")
        
        second_patient = User.objects.create_user(
            email="pat2@example.com", username="pat2@example.com", full_name="Jane Smith", role=User.PATIENT, is_verified=True
        )
        DoctorPatientRelation.objects.create(doctor=self.other_doctor, patient=second_patient, disease_title="Cold")

        # Get doc list
        self.client.force_authenticate(user=self.doctor)
        response = self.client.get(self.relations_url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 1)
        self.assertEqual(response.data[0]["patient_name"], "John Doe")
        self.assertEqual(response.data[0]["patient_id"], self.patient.id)
        self.assertNotIn("doctor", response.data[0])
        self.assertNotIn("doctor_detail", response.data[0])
        self.assertNotIn("patient_detail", response.data[0])
        self.assertEqual(response.data[0]["disease_title"], "Flu")

    def test_doctor_list_linked_patients_with_progress(self):
        from appointments.models import Protocol, ProtocolLog
        from datetime import datetime
        today = datetime.now().date()

        # Link patient
        relation = DoctorPatientRelation.objects.create(doctor=self.doctor, patient=self.patient, disease_title="Flu")

        # Create active protocols for this patient
        p1 = Protocol.objects.create(
            doctor=self.doctor, patient=self.patient, name="Walk 1",
            duration="3 days", start_date=today, end_date=today
        )
        p2 = Protocol.objects.create(
            doctor=self.doctor, patient=self.patient, name="Walk 2",
            duration="3 days", start_date=today, end_date=today
        )

        # Mark p1 as done today
        ProtocolLog.objects.create(protocol=p1, date=today)

        # Retrieve doc list
        self.client.force_authenticate(user=self.doctor)
        response = self.client.get(self.relations_url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 1)
        self.assertEqual(response.data[0]["patient_name"], "John Doe")
        self.assertEqual(response.data[0]["todays_progress_percentage"], 50.0) # 1 of 2 protocols done
        self.assertEqual(response.data[0]["todays_missed_protocols_count"], 1) # 1 protocol missed

    def test_doctor_update_patient_relation(self):
        relation = DoctorPatientRelation.objects.create(doctor=self.doctor, patient=self.patient, disease_title="Flu")
        self.client.force_authenticate(user=self.doctor)
        
        update_data = {
            "disease_title": "Recovered Flu",
            "health_goals": "Run a marathon"
        }
        response = self.client.patch(f"{self.relations_url}{relation.id}/", update_data, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["disease_title"], "Recovered Flu")
        self.assertEqual(response.data["health_goals"], "Run a marathon")


class PatientProfileTests(APITestCase):
    def setUp(self):
        self.patient = User.objects.create_user(
            email="patient_profile@example.com",
            username="patient_profile@example.com",
            full_name="Patient Profile Test",
            role=User.PATIENT,
            is_verified=True,
            is_active=True
        )
        self.patient.set_password("Password123!")
        self.patient.save()
        self.profile_url = "/api/users/profile/patient/"

    def test_get_patient_profile(self):
        self.client.force_authenticate(user=self.patient)
        response = self.client.get(self.profile_url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["email"], "patient_profile@example.com")
        self.assertEqual(response.data["full_name"], "Patient Profile Test")
        self.assertIsNone(response.data["patient_profile"])

    def test_update_patient_profile(self):
        self.client.force_authenticate(user=self.patient)
        
        small_gif = (
            b'\x47\x49\x46\x38\x39\x61\x01\x00\x01\x00\x00\x00\x00\x21\xf9\x04'
            b'\x01\x0a\x00\x01\x00\x2c\x00\x00\x00\x00\x01\x00\x01\x00\x00\x02'
            b'\x02\x4c\x01\x00\x3b'
        )
        photo = SimpleUploadedFile("profile.gif", small_gif, content_type="image/gif")

        data = {
            "full_name": "John Updated Doe",
            "email": "johndoe_updated@example.com",
            "phone_number": "+1234567890",
            "date_of_birth": "1995-10-15",
            "gender": "male",
            "health_goal": "Gain muscle mass and stay fit.",
            "profile_photo": photo
        }
        response = self.client.put(self.profile_url, data, format='multipart')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        self.assertEqual(response.data["full_name"], "John Updated Doe")
        self.assertEqual(response.data["email"], "johndoe_updated@example.com")
        self.assertEqual(response.data["phone_number"], "+1234567890")
        
        patient_profile = response.data["patient_profile"]
        self.assertEqual(patient_profile["date_of_birth"], "1995-10-15")
        self.assertEqual(patient_profile["gender"], "male")
        self.assertEqual(patient_profile["health_goal"], "Gain muscle mass and stay fit.")
        self.assertIsNotNone(patient_profile["profile_photo"])
        self.assertIn("profile", patient_profile["profile_photo"])


class ChangePasswordTests(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            email="changepass@example.com",
            username="changepass@example.com",
            full_name="Password Changer",
            role=User.PATIENT,
            is_verified=True,
            is_active=True
        )
        self.user.set_password("OldPassword123!")
        self.user.save()
        
        self.change_password_url = "/api/users/change-password/"

    def test_change_password_success(self):
        self.client.force_authenticate(user=self.user)
        data = {
            "current_password": "OldPassword123!",
            "new_password": "NewSecurePassword456!",
            "confirm_password": "NewSecurePassword456!"
        }
        response = self.client.put(self.change_password_url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["detail"], "Password updated successfully.")
        
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password("NewSecurePassword456!"))

    def test_change_password_incorrect_current_password(self):
        self.client.force_authenticate(user=self.user)
        data = {
            "current_password": "WrongOldPassword!",
            "new_password": "NewSecurePassword456!",
            "confirm_password": "NewSecurePassword456!"
        }
        response = self.client.put(self.change_password_url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("current_password", response.data)

    def test_change_password_mismatched_new_passwords(self):
        self.client.force_authenticate(user=self.user)
        data = {
            "current_password": "OldPassword123!",
            "new_password": "NewSecurePassword456!",
            "confirm_password": "DifferentPassword!"
        }
        response = self.client.put(self.change_password_url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("confirm_password", response.data)


class PatientListViewTests(APITestCase):
    def setUp(self):
        self.patient_list_url = "/api/users/patients/"
        
        # Create a doctor
        self.doctor = User.objects.create_user(
            email="doctor_test@example.com",
            username="doctor_test@example.com",
            full_name="Dr. Smith",
            role=User.PROVIDER,
            is_verified=True,
            is_active=True
        )
        
        # Create patients
        self.patient1 = User.objects.create_user(
            email="pat1@example.com",
            username="pat1@example.com",
            full_name="Alice Brown",
            role=User.PATIENT,
            is_verified=True,
            is_active=True
        )
        self.patient2 = User.objects.create_user(
            email="pat2@example.com",
            username="pat2@example.com",
            full_name="Charlie Green",
            role=User.PATIENT,
            is_verified=True,
            is_active=True
        )
        
        # Link patient1 to self.doctor
        DoctorPatientRelation.objects.create(doctor=self.doctor, patient=self.patient1, disease_title="Flu")

    def test_list_patients_success_as_doctor(self):
        # Add profile photos to verify photo URLs are returned
        from users.models import PatientProfile
        PatientProfile.objects.create(user=self.patient1, profile_photo="patients/photos/alice.jpg")

        self.client.force_authenticate(user=self.doctor)
        response = self.client.get(self.patient_list_url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        # Should return both patients
        self.assertEqual(len(response.data), 2)
        
        # Verify is_added flag and simplified keys are correct
        pat1_data = next(item for item in response.data if item['id'] == self.patient1.id)
        pat2_data = next(item for item in response.data if item['id'] == self.patient2.id)
        
        self.assertTrue(pat1_data['is_added'])
        self.assertFalse(pat2_data['is_added'])
        
        self.assertEqual(pat1_data['name'], "Alice Brown")
        self.assertEqual(pat1_data['full_name'], "Alice Brown")
        self.assertIn("alice.jpg", pat1_data['photo'])
        self.assertIn("alice.jpg", pat1_data['profile_photo'])
        
        # Check phone numbers
        self.patient1.phone_number = "9876543210"
        self.patient1.save()
        response2 = self.client.get(self.patient_list_url)
        pat1_updated = next(item for item in response2.data if item['id'] == self.patient1.id)
        self.assertEqual(pat1_updated['mobile_number'], "9876543210")
        self.assertEqual(pat1_updated['phone_number'], "9876543210")

    def test_list_patients_search_by_name(self):
        self.client.force_authenticate(user=self.doctor)
        # Test generic search param
        response = self.client.get(self.patient_list_url, {"search": "Alice"})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 1)
        self.assertEqual(response.data[0]['name'], "Alice Brown")

        # Test name specific search param
        response_name = self.client.get(self.patient_list_url, {"name": "Charlie"})
        self.assertEqual(response_name.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response_name.data), 1)
        self.assertEqual(response_name.data[0]['name'], "Charlie Green")

    def test_list_patients_search_by_number(self):
        self.patient1.phone_number = "55512345"
        self.patient1.save()
        self.client.force_authenticate(user=self.doctor)
        
        # Test searching using ?number=
        response = self.client.get(self.patient_list_url, {"number": "12345"})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 1)
        self.assertEqual(response.data[0]['name'], "Alice Brown")

    def test_list_patients_denied_as_patient(self):
        self.client.force_authenticate(user=self.patient1)
        response = self.client.get(self.patient_list_url)
        # Patients should not have access to this list
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)


class ProtocolTests(APITestCase):
    def setUp(self):
        # Create a doctor
        self.doctor = User.objects.create_user(
            email="doctor_p@example.com", username="doctor_p@example.com", full_name="Dr. Smith", role=User.PROVIDER, is_verified=True
        )
        # Create a patient
        self.patient = User.objects.create_user(
            email="patient_p@example.com", username="patient_p@example.com", full_name="Alice Brown", role=User.PATIENT, is_verified=True
        )
        
        # Link patient to doctor
        DoctorPatientRelation.objects.create(doctor=self.doctor, patient=self.patient, disease_title="Flu")

        # Create another doctor & patient to test validation boundaries
        self.other_doctor = User.objects.create_user(
            email="other_doc_p@example.com", username="other_doc_p@example.com", full_name="Dr. Jones", role=User.PROVIDER, is_verified=True
        )
        self.other_patient = User.objects.create_user(
            email="other_pat_p@example.com", username="other_pat_p@example.com", full_name="Charlie Green", role=User.PATIENT, is_verified=True
        )

        self.protocols_url = "/api/appointments/protocols/"

    def test_create_protocol_success_as_doctor(self):
        self.client.force_authenticate(user=self.doctor)
        data = {
            "patient": self.patient.id,
            "name": "Morning Walk Protocol",
            "description": "Walk every morning to improve cardiovascular fitness",
            "instructions": "Walk for 30 minutes at a brisk pace after waking up.",
            "duration": "2 weeks",
            "start_date": "2026-06-26",
            "end_date": "2026-07-10"
        }
        response = self.client.post(self.protocols_url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data["name"], "Morning Walk Protocol")
        self.assertEqual(response.data["duration"], "2 weeks")
        
        # Check database record
        from appointments.models import Protocol
        self.assertTrue(Protocol.objects.filter(name="Morning Walk Protocol", patient=self.patient).exists())

    def test_create_protocol_denied_if_not_under_care(self):
        # Doctor Smith tries to assign protocol to other_patient (who is not under their care)
        self.client.force_authenticate(user=self.doctor)
        data = {
            "patient": self.other_patient.id,
            "name": "Morning Walk Protocol",
            "duration": "2 weeks",
            "start_date": "2026-06-26",
            "end_date": "2026-07-10"
        }
        response = self.client.post(self.protocols_url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("non_field_errors", response.data)
        self.assertEqual(response.data["non_field_errors"][0], "You can only assign protocols to patients under your care.")

    def test_list_protocols_as_doctor(self):
        from appointments.models import Protocol
        # Create protocols
        Protocol.objects.create(
            doctor=self.doctor, patient=self.patient, name="Walk 1",
            duration="3 days", start_date="2026-06-26", end_date="2026-06-29"
        )
        
        self.client.force_authenticate(user=self.doctor)
        # 1. Failure check: missing patient_id query parameter should return 400
        response_fail = self.client.get(self.protocols_url)
        self.assertEqual(response_fail.status_code, status.HTTP_400_BAD_REQUEST)

        # 2. Success check: with patient_id query parameter
        response = self.client.get(self.protocols_url, {"patient_id": self.patient.id})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 1)
        self.assertEqual(response.data[0]["name"], "Walk 1")
        # Ensure serializer does not contain doctor/patient metadata
        self.assertNotIn("doctor_id", response.data[0])
        self.assertNotIn("doctor_name", response.data[0])
        self.assertNotIn("patient_id", response.data[0])
        self.assertNotIn("patient_name", response.data[0])

    def test_list_protocols_as_patient(self):
        from appointments.models import Protocol
        Protocol.objects.create(
            doctor=self.doctor, patient=self.patient, name="Walk 1",
            duration="3 days", start_date="2026-06-26", end_date="2026-06-29"
        )
        
        self.client.force_authenticate(user=self.patient)
        response = self.client.get(self.protocols_url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 1)
        self.assertEqual(response.data[0]["name"], "Walk 1")

    def test_patient_cannot_edit_protocol(self):
        from appointments.models import Protocol
        protocol = Protocol.objects.create(
            doctor=self.doctor, patient=self.patient, name="Walk 1",
            duration="3 days", start_date="2026-06-26", end_date="2026-06-29"
        )
        
        self.client.force_authenticate(user=self.patient)
        response = self.client.patch(f"{self.protocols_url}{protocol.id}/", {"name": "Malicious Edit"}, format='json')
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_mark_done_success(self):
        from appointments.models import Protocol
        from datetime import datetime
        today = datetime.now().date()
        protocol = Protocol.objects.create(
            doctor=self.doctor, patient=self.patient, name="Walk 1",
            duration="3 days", start_date=today, end_date=today
        )
        
        self.client.force_authenticate(user=self.patient)
        response = self.client.post(f"{self.protocols_url}{protocol.id}/mark-done/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["detail"], "Protocol marked as done for today.")
        self.assertEqual(response.data["progress_percentage"], 100.0)
        self.assertTrue(response.data["completed_today"])
        
        # Verify serialize contains new fields
        response_get = self.client.get(f"{self.protocols_url}{protocol.id}/")
        self.assertEqual(response_get.status_code, status.HTTP_200_OK)
        self.assertTrue(response_get.data["completed_today"])
        self.assertTrue(response_get.data["is_active_today"])
        self.assertEqual(response_get.data["progress_percentage"], 100.0)

    def test_mark_done_already_done(self):
        from appointments.models import Protocol
        from datetime import datetime
        today = datetime.now().date()
        protocol = Protocol.objects.create(
            doctor=self.doctor, patient=self.patient, name="Walk 1",
            duration="3 days", start_date=today, end_date=today
        )
        
        self.client.force_authenticate(user=self.patient)
        self.client.post(f"{self.protocols_url}{protocol.id}/mark-done/")
        
        # Try again
        response = self.client.post(f"{self.protocols_url}{protocol.id}/mark-done/")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response.data["detail"], "This protocol is already marked as done for today.")

    def test_mark_done_permission_denied(self):
        from appointments.models import Protocol
        from datetime import datetime
        today = datetime.now().date()
        protocol = Protocol.objects.create(
            doctor=self.doctor, patient=self.patient, name="Walk 1",
            duration="3 days", start_date=today, end_date=today
        )
        
        # Authenticate as doctor (who is not the patient)
        self.client.force_authenticate(user=self.doctor)
        response = self.client.post(f"{self.protocols_url}{protocol.id}/mark-done/")
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertEqual(response.data["detail"], "You do not have permission to perform this action.")


class RecipeTests(APITestCase):
    def setUp(self):
        # Create user accounts
        self.doctor = User.objects.create_user(
            email="doc_r@example.com", username="doc_r@example.com", full_name="Dr. Smith", role=User.PROVIDER, is_verified=True
        )
        self.doctor.set_password("Password123!")
        self.doctor.save()

        self.patient = User.objects.create_user(
            email="pat_r@example.com", username="pat_r@example.com", full_name="John Doe", role=User.PATIENT, is_verified=True
        )
        self.patient.set_password("Password123!")
        self.patient.save()

        # Link patient to doctor
        from appointments.models import DoctorPatientRelation
        DoctorPatientRelation.objects.create(doctor=self.doctor, patient=self.patient, disease_title="Flu")

        self.recipes_url = "/api/appointments/recipes/"

    def test_doctor_create_recipe_success(self):
        self.client.force_authenticate(user=self.doctor)
        data = {
            "name": "Keto Avocado Salad",
            "category": "lanch", # normalizes to lunch
            "ingredients": "Avocado, Tomatoes, Olive Oil",
            "instructions": "Mix them together.",
            "nutrition_notes": "Rich in healthy fats."
        }
        response = self.client.post(self.recipes_url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data["name"], "Keto Avocado Salad")
        self.assertEqual(response.data["category"], "lunch")
        self.assertEqual(response.data["creator_id"], self.doctor.id)

    def test_patient_cannot_create_recipe(self):
        self.client.force_authenticate(user=self.patient)
        data = {
            "name": "Malicious Recipe",
            "category": "dinner",
            "ingredients": "Sugar",
            "instructions": "Eat sugar."
        }
        response = self.client.post(self.recipes_url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_favorite_unfavorite_recipe(self):
        from appointments.models import Recipe
        recipe = Recipe.objects.create(
            name="Smoothie", category="breakfast", ingredients="Milk, Banana", instructions="Blend", creator=self.doctor
        )

        # 1. Favorite
        self.client.force_authenticate(user=self.patient)
        response = self.client.post(f"{self.recipes_url}{recipe.id}/favorite/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        # Verify serialization includes is_favorite
        response_get = self.client.get(f"{self.recipes_url}{recipe.id}/")
        self.assertTrue(response_get.data["is_favorite"])

        # 2. Filter favorites list
        response_list = self.client.get(self.recipes_url, {"is_favorite": "true"})
        self.assertEqual(len(response_list.data), 1)

        # 3. Unfavorite
        response_unfav = self.client.post(f"{self.recipes_url}{recipe.id}/unfavorite/")
        self.assertEqual(response_unfav.status_code, status.HTTP_200_OK)
        
        response_get2 = self.client.get(f"{self.recipes_url}{recipe.id}/")
        self.assertFalse(response_get2.data["is_favorite"])

    def test_recommend_recipe_success(self):
        from appointments.models import Recipe
        recipe = Recipe.objects.create(
            name="Salad", category="lunch", ingredients="Greens", instructions="Toss", creator=self.doctor
        )

        # Doctor recommends
        self.client.force_authenticate(user=self.doctor)
        data = {"patient": self.patient.id}
        response = self.client.post(f"{self.recipes_url}{recipe.id}/recommend/", data, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        # Patient reads
        self.client.force_authenticate(user=self.patient)
        response_get = self.client.get(f"{self.recipes_url}{recipe.id}/")
        self.assertTrue(response_get.data["is_recommended"])

        # Filter recommended list
        response_list = self.client.get(self.recipes_url, {"recommended": "true"})
        self.assertEqual(len(response_list.data), 1)

    def test_doctor_can_delete_recipe(self):
        from appointments.models import Recipe
        recipe = Recipe.objects.create(
            name="Salad", category="lunch", ingredients="Greens", instructions="Toss", creator=self.doctor
        )

        self.client.force_authenticate(user=self.doctor)
        response = self.client.delete(f"{self.recipes_url}{recipe.id}/")
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)

        # Verify deleted
        self.assertFalse(Recipe.objects.filter(id=recipe.id).exists())






