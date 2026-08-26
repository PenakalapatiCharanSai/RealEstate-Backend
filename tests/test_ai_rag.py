import unittest
import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app import create_app
from app.services.gemini_service import get_gemini_service
from app.services.embedding_service import get_embedding_service
from app.services.rag_service import get_rag_service, cosine_similarity, build_searchable_property_text
from app.utils.rate_limiter import AIRateLimiter

class TestAIRAGSystem(unittest.TestCase):
    def setUp(self):
        self.app = create_app()
        self.client = self.app.test_client()

    def test_01_health_endpoint(self):
        """Test GET /api/ai/health returns 200 and status fields."""
        response = self.client.get('/api/ai/health')
        self.assertEqual(response.status_code, 200)
        data = response.get_json()
        self.assertTrue(data.get('success'))
        self.assertIn('gemini', data)
        self.assertIn('embedding', data)
        self.assertIn('mongodb', data)

    def test_02_cosine_similarity(self):
        """Test vector cosine similarity math calculations."""
        vec1 = [1.0, 0.0, 0.0]
        vec2 = [1.0, 0.0, 0.0]
        vec3 = [0.0, 1.0, 0.0]
        self.assertAlmostEqual(cosine_similarity(vec1, vec2), 1.0)
        self.assertAlmostEqual(cosine_similarity(vec1, vec3), 0.0)

    def test_03_searchable_text_builder(self):
        """Test property document searchable text builder."""
        mock_doc = {
            "title": "Luxury Villa",
            "type": "Villa",
            "bedrooms": 4,
            "bathrooms": 4,
            "price": 15000000,
            "location": "Gachibowli, Hyderabad",
            "address": "Financial District",
            "area": 3500,
            "furnishing": "Furnished",
            "parking": True,
            "description": "Spacious luxury villa with private pool."
        }
        text = build_searchable_property_text(mock_doc)
        self.assertIn("Luxury Villa", text)
        self.assertIn("Gachibowli, Hyderabad", text)
        self.assertIn("15,000,000", text)

    def test_04_rate_limiter(self):
        """Test AIRateLimiter enforces daily limits."""
        limiter = AIRateLimiter()
        limiter.daily_limit = 3

        is_limited, rem1 = limiter.is_rate_limited("test_user_1")
        self.assertFalse(is_limited)

        is_limited, rem2 = limiter.is_rate_limited("test_user_1")
        self.assertFalse(is_limited)

        is_limited, rem3 = limiter.is_rate_limited("test_user_1")
        self.assertFalse(is_limited)

        is_limited, rem4 = limiter.is_rate_limited("test_user_1")
        self.assertTrue(is_limited)
        self.assertEqual(rem4, 0)

    def test_05_ai_chat_validation(self):
        """Test POST /api/ai/chat rejects empty payload."""
        response = self.client.post('/api/ai/chat', json={})
        self.assertEqual(response.status_code, 400)
        data = response.get_json()
        self.assertEqual(data.get('error'), 'VALIDATION_ERROR')

    def test_06_ai_property_search(self):
        """Test POST /api/ai/property-search with natural language query."""
        response = self.client.post('/api/ai/property-search', json={
            "query": "Find 3 BHK in Hyderabad"
        })
        self.assertEqual(response.status_code, 200)
        data = response.get_json()
        self.assertTrue(data.get('success'))
        self.assertIsInstance(data.get('properties'), list)

if __name__ == "__main__":
    unittest.main()
