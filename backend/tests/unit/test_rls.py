import os
from dotenv import load_dotenv
from supabase import create_client

load_dotenv()

url = os.environ["SUPABASE_URL"]
anon_key = os.environ["SUPABASE_ANON_KEY"]

PATIENT2_EMAIL = os.environ["TEST_PATIENT2_EMAIL"]
PATIENT2_PASSWORD = os.environ["TEST_PATIENT2_PASSWORD"]
client = create_client(url, anon_key)
client.auth.sign_in_with_password({"email": PATIENT2_EMAIL, "password": PATIENT2_PASSWORD})

result = client.table("consultations").select("*").execute()
print("Rows patient2 can see:", result.data)

assert result.data == [], "RLS FAILED — patient2 can see a consultation that isn't theirs"
print("PASS: patient2 cannot see patient1's consultation")


PATIENT1_EMAIL = os.environ["TEST_PATIENT1_EMAIL"]
PATIENT1_PASSWORD = os.environ["TEST_PATIENT1_PASSWORD"]

client2 = create_client(url, anon_key)
client2.auth.sign_in_with_password({"email": PATIENT1_EMAIL, "password": PATIENT1_PASSWORD})

result2 = client2.table("consultations").select("*").execute()
print("Rows patient1 can see:", result2.data)

assert len(result2.data) == 1, "RLS FAILED — patient1 cannot see their own consultation"
print("PASS: patient1 can see their own consultation")
