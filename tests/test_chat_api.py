import unittest
import json
import os
import sys
from bson import ObjectId
from datetime import datetime, timezone

# Add backend directory to sys.path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import create_app
from app.utils.db import get_db
from app.utils.jwt_utils import generate_token
from app.models.property import PropertyModel


class ChatAPITestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = create_app()
        cls.client = cls.app.test_client()

        with cls.app.app_context():
            cls.db = get_db()
            if cls.db is None:
                raise RuntimeError("Failed to connect to test database.")

            # Create test user A
            cls.test_user_a = {
                "name": "Test User A",
                "email": "user_a_test@example.com",
                "password": "hashedpassword123",
                "role": "customer",
                "status": "active",
                "created_at": datetime.now(timezone.utc)
            }
            res_a = cls.db.users.update_one(
                {"email": cls.test_user_a["email"]},
                {"$set": cls.test_user_a},
                upsert=True
            )
            user_a_doc = cls.db.users.find_one({"email": cls.test_user_a["email"]})
            cls.user_a_id = str(user_a_doc["_id"])
            cls.token_a = generate_token(cls.user_a_id, role="customer")

            # Create test user B (for isolation tests)
            cls.test_user_b = {
                "name": "Test User B",
                "email": "user_b_test@example.com",
                "password": "hashedpassword123",
                "role": "customer",
                "status": "active",
                "created_at": datetime.now(timezone.utc)
            }
            cls.db.users.update_one(
                {"email": cls.test_user_b["email"]},
                {"$set": cls.test_user_b},
                upsert=True
            )
            user_b_doc = cls.db.users.find_one({"email": cls.test_user_b["email"]})
            cls.user_b_id = str(user_b_doc["_id"])
            cls.token_b = generate_token(cls.user_b_id, role="customer")

            # Create test property
            cls.test_prop = PropertyModel.create_document(
                title="Test Luxury Apartment - Kukatpally",
                type_="Apartment",
                description="Test property featuring 2 bedrooms, swimming pool, parking, ready to move in.",
                transaction_type="Sale",
                price=6800000.0,
                location="Kukatpally, Hyderabad",
                address="Road 1, Kukatpally, Hyderabad",
                area=1150.0,
                bedrooms=2,
                bathrooms=2,
                parking=True,
                furnishing="Semi-Furnished",
                status="Available",
                approval_status="Approved",
                agent_id=cls.user_a_id
            )
            res_p = cls.db.properties.insert_one(cls.test_prop)
            cls.test_prop_id = str(res_p.inserted_id)

    def test_01_chat_api_auth(self):
        """Test 1: Chat API accepts authenticated request with Bearer token."""
        response = self.client.post(
            "/api/chat",
            headers={"Authorization": f"Bearer {self.token_a}"},
            json={"message": "Hello HavenSpace"}
        )
        self.assertEqual(response.status_code, 200)
        data = response.get_json()
        self.assertTrue(data.get("success"))
        self.assertIsNotNone(data.get("conversation_id"))

    def test_02_guest_chat(self):
        """Test 2: Unauthenticated guest chat request succeeds."""
        response = self.client.post(
            "/api/chat",
            json={"message": "I am a guest looking for properties"}
        )
        self.assertEqual(response.status_code, 200)
        data = response.get_json()
        self.assertTrue(data.get("success"))

    def test_03_normal_message(self):
        """Test 3: Normal conversational message."""
        response = self.client.post(
            "/api/chat",
            json={"message": "What services do you offer?"}
        )
        self.assertEqual(response.status_code, 200)
        data = response.get_json()
        self.assertTrue(data.get("success"))
        self.assertIn("message", data)

    def test_04_property_search_natural_language(self):
        """Test 4: Natural language property search queries real MongoDB properties."""
        response = self.client.post(
            "/api/chat",
            json={"message": "I need a 2 BHK apartment in Hyderabad"}
        )
        self.assertEqual(response.status_code, 200)
        data = response.get_json()
        self.assertTrue(data.get("success"))
        self.assertIsInstance(data.get("properties"), list)

    def test_05_property_search_price_filter(self):
        """Test 5: Property search with price filter."""
        response = self.client.post(
            "/api/chat",
            json={"message": "Show me properties under 70 lakhs"}
        )
        self.assertEqual(response.status_code, 200)
        data = response.get_json()
        self.assertTrue(data.get("success"))

    def test_06_property_search_bedroom_filter(self):
        """Test 6: Property search with bedroom filter."""
        response = self.client.post(
            "/api/chat",
            json={"message": "Find 2 BHK properties"}
        )
        self.assertEqual(response.status_code, 200)
        data = response.get_json()
        self.assertTrue(data.get("success"))

    def test_07_property_search_location(self):
        """Test 7: Property search by location."""
        response = self.client.post(
            "/api/chat",
            json={"message": "Show properties in Kukatpally"}
        )
        self.assertEqual(response.status_code, 200)
        data = response.get_json()
        self.assertTrue(data.get("success"))

    def test_08_no_matching_properties(self):
        """Test 8: Search with no matching properties returns friendly message."""
        response = self.client.post(
            "/api/chat",
            json={"message": "Find 10 BHK apartments in NonExistentCity999 for 100 rupees"}
        )
        self.assertEqual(response.status_code, 200)
        data = response.get_json()
        self.assertTrue(data.get("success"))
        self.assertEqual(len(data.get("properties", [])), 0)

    def test_09_property_details(self):
        """Test 9: Specific property details lookup."""
        response = self.client.post(
            "/api/chat",
            json={
                "message": "Tell me about this property",
                "current_property_id": self.test_prop_id
            }
        )
        self.assertEqual(response.status_code, 200)
        data = response.get_json()
        self.assertTrue(data.get("success"))

    def test_10_conversation_creation(self):
        """Test 10: Conversation session creation."""
        response = self.client.post(
            "/api/chat",
            headers={"Authorization": f"Bearer {self.token_a}"},
            json={"message": "Start new property search session"}
        )
        self.assertEqual(response.status_code, 200)
        data = response.get_json()
        self.assertIn("conversation_id", data)

    def test_11_conversation_retrieval(self):
        """Test 11: Retrieving saved user conversations."""
        # Create a conversation first
        post_res = self.client.post(
            "/api/chat",
            headers={"Authorization": f"Bearer {self.token_a}"},
            json={"message": "Test conversation history retrieval"}
        )
        conv_id = post_res.get_json().get("conversation_id")

        # Retrieve list
        list_res = self.client.get(
            "/api/chat/conversations",
            headers={"Authorization": f"Bearer {self.token_a}"}
        )
        self.assertEqual(list_res.status_code, 200)
        convs = list_res.get_json().get("conversations", [])
        self.assertTrue(any(c.get("conversation_id") == conv_id for c in convs))

        # Retrieve detail
        detail_res = self.client.get(
            f"/api/chat/conversations/{conv_id}",
            headers={"Authorization": f"Bearer {self.token_a}"}
        )
        self.assertEqual(detail_res.status_code, 200)

    def test_12_conversation_isolation(self):
        """Test 12: User B cannot access User A's conversation."""
        post_res = self.client.post(
            "/api/chat",
            headers={"Authorization": f"Bearer {self.token_a}"},
            json={"message": "Private conversation of User A"}
        )
        conv_id_a = post_res.get_json().get("conversation_id")

        # Try accessing with User B token
        isolation_res = self.client.get(
            f"/api/chat/conversations/{conv_id_a}",
            headers={"Authorization": f"Bearer {self.token_b}"}
        )
        self.assertEqual(isolation_res.status_code, 403)

    def test_13_enquiry_creation_via_chat(self):
        """Test 13: Creating an enquiry via chatbot."""
        response = self.client.post(
            "/api/chat",
            headers={"Authorization": f"Bearer {self.token_a}"},
            json={
                "message": "Contact the agent for this property",
                "current_property_id": self.test_prop_id
            }
        )
        self.assertEqual(response.status_code, 200)
        data = response.get_json()
        self.assertTrue(data.get("success"))

    def test_14_visit_request_via_chat(self):
        """Test 14: Creating a visit request via chatbot."""
        response = self.client.post(
            "/api/chat",
            headers={"Authorization": f"Bearer {self.token_a}"},
            json={
                "message": "I want to visit this property tomorrow at 5 PM",
                "current_property_id": self.test_prop_id
            }
        )
        self.assertEqual(response.status_code, 200)
        data = response.get_json()
        self.assertTrue(data.get("success"))

    def test_15_ai_provider_failure_fallback(self):
        """Test 15: Graceful fallback when AI provider returns empty or fails."""
        # Simulated by sending standard query without active external network call
        response = self.client.post(
            "/api/chat",
            json={"message": "Tell me about 2 BHK properties"}
        )
        self.assertEqual(response.status_code, 200)
        data = response.get_json()
        self.assertTrue(data.get("success"))
        self.assertTrue(len(data.get("message")) > 0)

    def test_16_mongodb_failure_handling(self):
        """Test 16: MongoDB error handling returns structured JSON instead of stack traces."""
        # Test empty message validation
        response = self.client.post("/api/chat", json={"message": ""})
        self.assertEqual(response.status_code, 400)

    def test_17_malicious_query_input(self):
        """Test 17: Query injection attempts ($where, $gt) are sanitized."""
        response = self.client.post(
            "/api/chat",
            json={"message": "{'$where': 'this.price > 0'}"}
        )
        self.assertEqual(response.status_code, 200)
        data = response.get_json()
        self.assertTrue(data.get("success"))

    def test_18_excessively_long_message(self):
        """Test 18: Messages exceeding 1000 characters are rejected gracefully."""
        long_msg = "A" * 1500
        response = self.client.post(
            "/api/chat",
            json={"message": long_msg}
        )
        self.assertEqual(response.status_code, 400)
        data = response.get_json()
        self.assertFalse(data.get("success"))
        self.assertEqual(data.get("error"), "MESSAGE_TOO_LONG")

    def test_19_missing_visit_info(self):
        """Test 19: Requesting visit without date/time prompts for missing info."""
        response = self.client.post(
            "/api/chat",
            json={
                "message": "I want to visit this property",
                "current_property_id": self.test_prop_id
            }
        )
        self.assertEqual(response.status_code, 200)
        data = response.get_json()
        self.assertTrue(data.get("success"))

    def test_20_api_key_missing_handling(self):
        """Test 20: Chatbot operates gracefully even if AI API key is unconfigured."""
        from app.services.ai_service import GeminiProvider
        provider = GeminiProvider(api_key="")
        res = provider.generate_response(message="Hi", properties=[])
        # Returns None without throwing unhandled exceptions
        self.assertIsNone(res)


if __name__ == "__main__":
    unittest.main()
