import os
import sys
from datetime import datetime, timezone
from bson import ObjectId

# Ensure app path is in python sys path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app import create_app
from app.utils.db import get_db
from app.utils.password_utils import hash_password
from app.models.property import PropertyModel

AGENT_EMAIL = "charansaipenakalapati@gmail.com"
AGENT_PASSWORD = "123456"
AGENT_NAME = "Charan Sai Penakalapati"
AGENT_PHONE = "+91 98765 43210"

DEMO_PROPERTIES = [
    {
        "title": "Skyline Grand Penthouse - Jubilee Hills",
        "type_": "Apartment",
        "transaction_type": "Sale",
        "price": 28500000, # ₹2.85 Cr
        "location": "Jubilee Hills, Hyderabad",
        "address": "Road No. 36, Jubilee Hills, Hyderabad, Telangana 500033",
        "area": 3800,
        "bedrooms": 4,
        "bathrooms": 4,
        "parking": True,
        "furnishing": "Fully Furnished",
        "description": "Ultra-luxury 4BHK penthouse with private skydeck terrace, panoramic city view, Italian marble flooring, and smart home automation.",
        "images": [
            "https://images.unsplash.com/photo-1545324418-cc1a3fa10c00?auto=format&fit=crop&w=1200&q=80",
            "https://images.unsplash.com/photo-1600596542815-ffad4c1539a9?auto=format&fit=crop&w=1200&q=80",
            "https://images.unsplash.com/photo-1600607687939-ce8a6c25118c?auto=format&fit=crop&w=1200&q=80"
        ],
        "latitude": 17.4319,
        "longitude": 78.4071
    },
    {
        "title": "The Emerald Estate Villa - Gachibowli",
        "type_": "Villa",
        "transaction_type": "Sale",
        "price": 45000000, # ₹4.50 Cr
        "location": "Gachibowli, Hyderabad",
        "address": "Near Financial District, Gachibowli, Hyderabad, Telangana 500032",
        "area": 5200,
        "bedrooms": 5,
        "bathrooms": 5,
        "parking": True,
        "furnishing": "Fully Furnished",
        "description": "Exquisite 5BHK luxury triplex villa in a gated community featuring a private swimming pool, landscaped garden, private elevator, and clubhouse access.",
        "images": [
            "https://images.unsplash.com/photo-1613977257363-707ba9348227?auto=format&fit=crop&w=1200&q=80",
            "https://images.unsplash.com/photo-1600585154340-be6161a56a0c?auto=format&fit=crop&w=1200&q=80",
            "https://images.unsplash.com/photo-1600566753376-12c8ab7fb75b?auto=format&fit=crop&w=1200&q=80"
        ],
        "latitude": 17.4401,
        "longitude": 78.3489
    },
    {
        "title": "Urban Tech Park Suites - HITECH City",
        "type_": "Commercial Property",
        "transaction_type": "Rent",
        "price": 120000, # ₹1.20 Lakh / month
        "location": "HITECH City, Hyderabad",
        "address": "Mindspace IT Park, HITECH City, Hyderabad, Telangana 500081",
        "area": 2400,
        "bedrooms": 0,
        "bathrooms": 2,
        "parking": True,
        "furnishing": "Semi-Furnished",
        "description": "Plug-and-play Grade-A commercial office space with 30 workstations, conference room, fiber internet infrastructure, and 24/7 power backup.",
        "images": [
            "https://images.unsplash.com/photo-1497366216548-37526070297c?auto=format&fit=crop&w=1200&q=80",
            "https://images.unsplash.com/photo-1497215728101-856f4ea42174?auto=format&fit=crop&w=1200&q=80"
        ],
        "latitude": 17.4435,
        "longitude": 78.3772
    },
    {
        "title": "Royal Palm Residency - Indiranagar",
        "type_": "Apartment",
        "transaction_type": "Sale",
        "price": 16500000, # ₹1.65 Cr
        "location": "Indiranagar, Bangalore",
        "address": "100 Feet Road, Indiranagar, Bangalore, Karnataka 560038",
        "area": 2100,
        "bedrooms": 3,
        "bathrooms": 3,
        "parking": True,
        "furnishing": "Semi-Furnished",
        "description": "Spacious 3BHK premium apartment situated in the heart of Indiranagar. Close to fine dining, metro stations, and top international schools.",
        "images": [
            "https://images.unsplash.com/photo-1512917774080-9991f1c4c750?auto=format&fit=crop&w=1200&q=80",
            "https://images.unsplash.com/photo-1600210492486-724fe5c67fb0?auto=format&fit=crop&w=1200&q=80"
        ],
        "latitude": 12.9784,
        "longitude": 77.6408
    },
    {
        "title": "Lakeside Luxury Bungalow - Whitefield",
        "type_": "Independent House",
        "transaction_type": "Sale",
        "price": 32000000, # ₹3.20 Cr
        "location": "Whitefield, Bangalore",
        "address": "Hope Farm Circle, Whitefield, Bangalore, Karnataka 560066",
        "area": 4100,
        "bedrooms": 4,
        "bathrooms": 4,
        "parking": True,
        "furnishing": "Fully Furnished",
        "description": "Modern 4BHK independent bungalow overlooking a serene lake. Features solar power backup, private rooftop lounge, modular kitchen, and double garage.",
        "images": [
            "https://images.unsplash.com/photo-1600585154526-990dced4db0d?auto=format&fit=crop&w=1200&q=80",
            "https://images.unsplash.com/photo-1600607687920-4e2a09cf159d?auto=format&fit=crop&w=1200&q=80"
        ],
        "latitude": 12.9698,
        "longitude": 77.7499
    },
    {
        "title": "Oceanview Heights - Worli",
        "type_": "Apartment",
        "transaction_type": "Sale",
        "price": 65000000, # ₹6.50 Cr
        "location": "Worli, Mumbai",
        "address": "Worli Sea Face, Mumbai, Maharashtra 400018",
        "area": 2400,
        "bedrooms": 3,
        "bathrooms": 3,
        "parking": True,
        "furnishing": "Fully Furnished",
        "description": "Unmatched Arabian Sea view 3BHK high-rise apartment in Worli. Designer interiors, infinity pool, fitness center, and multi-tier security.",
        "images": [
            "https://images.unsplash.com/photo-1502672260266-1c1ef2d93688?auto=format&fit=crop&w=1200&q=80",
            "https://images.unsplash.com/photo-1560448204-e02f11c3d0e2?auto=format&fit=crop&w=1200&q=80"
        ],
        "latitude": 19.0176,
        "longitude": 72.8173
    },
    {
        "title": "Greenfield Gated Community Plots",
        "type_": "Plot",
        "transaction_type": "Sale",
        "price": 9500000, # ₹95 Lakhs
        "location": "Financial District, Hyderabad",
        "address": "Nanakramguda, Financial District, Hyderabad, Telangana 500032",
        "area": 3600,
        "bedrooms": 0,
        "bathrooms": 0,
        "parking": False,
        "furnishing": "Unfurnished",
        "description": "HMDA & RERA approved 400 sq. yard plot in a premium gated residential layout. Underground utilities, wide blacktop roads, and 24/7 security boundary.",
        "images": [
            "https://images.unsplash.com/photo-1500382017468-9049fed747ef?auto=format&fit=crop&w=1200&q=80"
        ],
        "latitude": 17.4116,
        "longitude": 78.3396
    },
    {
        "title": "Verdant Park Residence - Koregaon Park",
        "type_": "Apartment",
        "transaction_type": "Rent",
        "price": 45000, # ₹45,000 / month
        "location": "Koregaon Park, Pune",
        "address": "Lane 7, Koregaon Park, Pune, Maharashtra 411001",
        "area": 1350,
        "bedrooms": 2,
        "bathrooms": 2,
        "parking": True,
        "furnishing": "Fully Furnished",
        "description": "Charming 2BHK fully furnished apartment surrounded by green tree canopies. Equipped with ACs, Smart TV, modular kitchen, and covered parking.",
        "images": [
            "https://images.unsplash.com/photo-1522708323590-d24dbb6b0267?auto=format&fit=crop&w=1200&q=80",
            "https://images.unsplash.com/photo-1502005229762-cf1b2da7c5d6?auto=format&fit=crop&w=1200&q=80"
        ],
        "latitude": 18.5362,
        "longitude": 73.8940
    }
]

def seed_agent_and_properties():
    app = create_app()
    with app.app_context():
        db = get_db()
        if db is None:
            print("[ERROR] Database connection failed.")
            return

        # 1. Seed or Update Agent User
        hashed_pw = hash_password(AGENT_PASSWORD)
        agent_user = db.users.find_one({"email": AGENT_EMAIL})

        if not agent_user:
            agent_doc = {
                "name": AGENT_NAME,
                "email": AGENT_EMAIL,
                "password": hashed_pw,
                "phone": AGENT_PHONE,
                "role": "agent",
                "status": "active",
                "is_approved": True,
                "email_verified": True,
                "created_at": datetime.now(timezone.utc),
                "updated_at": datetime.now(timezone.utc)
            }
            res = db.users.insert_one(agent_doc)
            agent_id = res.inserted_id
            print(f"[SUCCESS] Agent account created: '{AGENT_EMAIL}' with ID {agent_id}")
        else:
            agent_id = agent_user["_id"]
            db.users.update_one(
                {"_id": agent_id},
                {"$set": {
                    "password": hashed_pw,
                    "role": "agent",
                    "status": "active",
                    "is_approved": True,
                    "email_verified": True,
                    "phone": AGENT_PHONE,
                    "name": AGENT_NAME
                }}
            )
            print(f"[SUCCESS] Agent account updated & activated: '{AGENT_EMAIL}' (ID: {agent_id})")

        # 2. Clear old demo properties for this agent to avoid duplicates
        deleted_count = db.properties.delete_many({"agent_id": agent_id}).deleted_count
        print(f"[INFO] Cleared {deleted_count} existing properties for this agent.")

        # 3. Seed Demo Properties
        inserted_count = 0
        for prop in DEMO_PROPERTIES:
            doc = PropertyModel.create_document(
                title=prop["title"],
                type_=prop["type_"],
                description=prop["description"],
                transaction_type=prop["transaction_type"],
                price=prop["price"],
                location=prop["location"],
                address=prop["address"],
                area=prop["area"],
                bedrooms=prop["bedrooms"],
                bathrooms=prop["bathrooms"],
                parking=prop["parking"],
                furnishing=prop["furnishing"],
                images=prop["images"],
                agent_id=agent_id,
                status="Available",
                approval_status="Approved",
                latitude=prop["latitude"],
                longitude=prop["longitude"]
            )
            db.properties.insert_one(doc)
            inserted_count += 1

        print(f"[SUCCESS] Successfully seeded {inserted_count} presentation-grade demo properties under agent '{AGENT_EMAIL}'!")

if __name__ == "__main__":
    seed_agent_and_properties()
