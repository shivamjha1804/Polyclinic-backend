import os
from dotenv import load_dotenv
from supabase import create_client

load_dotenv()

url = os.environ["SUPABASE_URL"]
anon_key = os.environ["SUPABASE_ANON_KEY"]

PATIENT2_EMAIL = os.environ["TEST_PATIENT2_EMAIL"]
PATIENT2_PASSWORD = os.environ["TEST_PATIENT2_PASSWORD"]
client = create_client(url, anon_key)
session = client.auth.sign_in_with_password({"email": PATIENT2_EMAIL, "password": PATIENT2_PASSWORD})
patient2_id = session.user.id

result = client.table("consultations").select("*").execute()
print("Rows patient2 can see:", result.data)

assert all(row["patient_id"] == patient2_id for row in result.data), "RLS FAILED — patient2 can see a consultation that isn't theirs"
print("PASS: patient2 can only see their own consultations")


PATIENT1_EMAIL = os.environ["TEST_PATIENT1_EMAIL"]
PATIENT1_PASSWORD = os.environ["TEST_PATIENT1_PASSWORD"]

client2 = create_client(url, anon_key)
session2 = client2.auth.sign_in_with_password({"email": PATIENT1_EMAIL, "password": PATIENT1_PASSWORD})
patient1_id = session2.user.id

result2 = client2.table("consultations").select("*").execute()
print("Rows patient1 can see:", result2.data)

assert len(result2.data) >= 1, "RLS FAILED — patient1 cannot see their own consultation"
assert all(row["patient_id"] == patient1_id for row in result2.data), "RLS FAILED — patient1 can see someone else's consultation"
print("PASS: patient1 can see their own consultation(s), nothing else")
