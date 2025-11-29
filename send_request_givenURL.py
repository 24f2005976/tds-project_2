import requests
import time
import os
from dotenv import load_dotenv

load_dotenv()

STUDENT_EMAIL = os.getenv("STUDENT_EMAIL")
STUDENT_SECRET = os.getenv("STUDENT_SECRET")
SERVER_URL = "http://127.0.0.1:8000/solve"

payload = {
    "email": STUDENT_EMAIL,
    "secret": STUDENT_SECRET,
    "url": "https://tds-llm-analysis.s-anand.net/project2"
}

print(f"📩 Sending payload to server: {payload['url']}")
response = requests.post(SERVER_URL, json=payload)
print("Status Code:", response.status_code)
print("Response JSON:", response.json())

# -----------------------------
# Optional: monitor workflow
# -----------------------------
print("⏱ Monitoring server quiz-solving workflow for 10 seconds...")
for i in range(10):
    print(f"⏳ Waiting... {i+1}s")
    time.sleep(1)
print("✅ Done monitoring.")
