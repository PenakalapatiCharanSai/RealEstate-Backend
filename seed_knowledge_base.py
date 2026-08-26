import sys
import os
import logging

# Ensure backend root is on Python path
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

from app import create_app
from app.services.knowledge_service import get_knowledge_service
from app.services.rag_service import get_rag_service

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

HAVENSPACE_KNOWLEDGE_DOCUMENTS = [
    {
        "name": "HavenSpace Platform FAQs",
        "category": "faq",
        "text": """
        HavenSpace is a premier real estate marketplace connecting home buyers, tenants, and verified real estate agents.
        Q: How do I schedule a property visit?
        A: Browse any property listing on HavenSpace and click the 'Schedule Visit' button or ask the HavenSpace AI Assistant. Pick your preferred date and time. The assigned property agent will confirm your visit request.
        Q: Are property prices negotiable?
        A: Prices listed on HavenSpace are set directly by authorized real estate agents. You can submit an enquiry or discuss price negotiation directly during a site visit or agent call.
        Q: Is there any registration fee for buyers?
        A: No! Registration and property searches on HavenSpace are 100% free for customers and home seekers.
        Q: How are properties verified?
        A: Every listing uploaded by real estate agents undergoes an administrative approval process before appearing on the HavenSpace marketplace.
        """
    },
    {
        "name": "HavenSpace Site Visit Guidelines & Rules",
        "category": "guidelines",
        "text": """
        HavenSpace Site Visit & Property Inspection Rules:
        1. Site visits can be scheduled online via property listing pages or via HavenSpace AI Assistant.
        2. Customers should arrive on time for confirmed appointments.
        3. Property visits are conducted by licensed HavenSpace agents or verified property owners.
        4. Rescheduling or cancellation can be done up to 2 hours prior to the scheduled time via the 'My Visits' dashboard.
        5. Emergency contact and agent details are provided once a visit request is confirmed.
        """
    },
    {
        "name": "Agent Guidelines & Property Listing Rules",
        "category": "agent_policy",
        "text": """
        HavenSpace Real Estate Agent Policies:
        1. Agents must provide accurate property titles, locations, addresses, price, BHK, area, and genuine images.
        2. Misleading or fake property listings are strictly prohibited and will lead to account suspension.
        3. All agent listings require HavenSpace Admin approval before public visibility.
        4. Agents are expected to respond to customer enquiries within 24 hours.
        """
    },
    {
        "name": "HavenSpace Terms & Cancellation Policies",
        "category": "terms",
        "text": """
        HavenSpace Terms of Service & Cancellation Policy:
        1. HavenSpace provides a transparent platform for real estate discovery, scheduling, and direct communication.
        2. Users can cancel visit requests at any time before completion without any penalty.
        3. HavenSpace protects user privacy and never sells contact details to unauthorized third-party advertisers.
        """
    }
]

def seed_knowledge_base():
    app = create_app()
    with app.app_context():
        logger.info("Initializing HavenSpace Knowledge Base & Vector Indexing...")
        ks = get_knowledge_service()

        for doc in HAVENSPACE_KNOWLEDGE_DOCUMENTS:
            res = ks.ingest_document(
                document_name=doc["name"],
                text=doc["text"],
                category=doc["category"]
            )
            logger.info(f"Ingested '{doc['name']}': {res.get('inserted_chunks')} chunks created.")

        logger.info("Re-indexing existing property listings for RAG vector search...")
        rag_svc = get_rag_service()
        prop_res = rag_svc.reindex_all_properties()
        logger.info(f"Property Re-indexing Complete: {prop_res.get('indexed_count')}/{prop_res.get('total_properties')} properties indexed.")

if __name__ == "__main__":
    seed_knowledge_base()
