import os
import time
import requests
from dotenv import load_dotenv

load_dotenv()
STUDENT_EMAIL = os.getenv("STUDENT_EMAIL")
STUDENT_SECRET = os.getenv("STUDENT_SECRET")

SERVER_URL = "http://127.0.0.1:8000/solve"
QUIZ_URL = "https://tds-llm-analysis.s-anand.net/demo"  # Replace with actual quiz URL

payload = {
    "email": STUDENT_EMAIL,
    "secret": STUDENT_SECRET,
    "url": QUIZ_URL
}

print(f"📩 Sending payload to server: {QUIZ_URL}")
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
