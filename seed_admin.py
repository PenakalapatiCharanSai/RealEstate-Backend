from app.utils.db import get_db
from app.models import UserModel
from app.utils.password_utils import hash_password

def seed_default_users():
    db = get_db()
    if db is None:
        print("[SEED ERROR] Database connection unavailable.")
        return

    users_to_seed = [
        {
            "name": "Charan Admin",
            "email": "pcharan87746@gmail.com",
            "password": "1234",
            "phone": "9876543210",
            "role": "admin",
            "status": "active"
        }
        
    ]

    for u in users_to_seed:
        hpw = hash_password(u["password"])
        existing = db.users.find_one({"email": u["email"]})
        if not existing:
            doc = UserModel.create_document(
                name=u["name"],
                email=u["email"],
                password=hpw,
                phone=u["phone"],
                role=u["role"],
                status=u["status"]
            )
            result = db.users.insert_one(doc)
            print(f"[SEED SUCCESS] Created default user '{u['email']}' ({u['role']}) with ID {result.inserted_id}")
        else:
            db.users.update_one({"email": u["email"]}, {"$set": {"password": hpw, "role": u["role"], "status": u["status"]}})
            print(f"[SEED SUCCESS] Verified/Reset credentials for user '{u['email']}'.")

if __name__ == "__main__":
    from app import create_app
    app = create_app()
    with app.app_context():
        seed_default_users()
