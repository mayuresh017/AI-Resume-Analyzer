import os
import firebase_admin
from firebase_admin import credentials, firestore


import firebase_admin
from firebase_admin import credentials, firestore
import os

def init_firebase():
    try:
        if not firebase_admin._apps:
            cred_path = "serviceAccountKey.json"
            
            if not os.path.exists(cred_path):
                print("⚠ Firebase not configured")
                return None

            cred = credentials.Certificate(cred_path)
            firebase_admin.initialize_app(cred)

        return firestore.client()

    except Exception as e:
        print("Firebase Error:", e)
        return None