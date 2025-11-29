import os
import time
import asyncio
import json
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from playwright.async_api import async_playwright
from dotenv import load_dotenv

load_dotenv()

STUDENT_EMAIL = os.getenv("STUDENT_EMAIL")
STUDENT_SECRET = os.getenv("STUDENT_SECRET")

app = FastAPI(title="Async Quiz Solver API")

# ------------------------
# Request model
# ------------------------
class QuizRequest(BaseModel):
    email: str
    secret: str
    url: str

# ------------------------
# Async quiz-solving logic
# ------------------------
async def solve_quiz_logic(page):
    """
    Fully async quiz-solving logic.
    Replace dummy logic with actual computation from the quiz page.
    """
    await page.wait_for_load_state("networkidle")
    content = await page.content()

    # Extract submit_url if present
    submit_url = None
    try:
        scripts = await page.query_selector_all("script, pre")
        for s in scripts:
            txt = await s.inner_text()
            if '"submit_url"' in txt:
                data = json.loads(txt)
                submit_url = data.get("submit_url")
                break
    except Exception:
        submit_url = None

    # Dummy answer computation (replace with real logic)
    answer = 12345

    # Submit the answer if URL exists
    if submit_url:
        async with page.context.request.post(submit_url, json={
            "email": STUDENT_EMAIL,
            "secret": STUDENT_SECRET,
            "url": page.url,
            "answer": answer
        }) as res:
            try:
                res_json = await res.json()
                print("Submission response:", res_json)
                next_url = res_json.get("url")
            except Exception:
                next_url = None
        return answer, next_url
    else:
        return answer, None

# ------------------------
# Main endpoint
# ------------------------
@app.post("/solve")
async def solve_quiz(payload: QuizRequest):
    # 1️⃣ Secret validation
    if payload.email != STUDENT_EMAIL or payload.secret != STUDENT_SECRET:
        raise HTTPException(status_code=403, detail="Invalid secret")

    # 2️⃣ Visit the quiz page
    try:
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            page = await browser.new_page()
            await page.goto(payload.url, wait_until="networkidle")

            # Solve first quiz
            answer, next_url = await solve_quiz_logic(page)

            # Follow next quizzes until 3-minute deadline
            start_time = time.time()
            while next_url and time.time() - start_time < 180:
                await page.goto(next_url, wait_until="networkidle")
                answer, next_url = await solve_quiz_logic(page)

            await browser.close()

    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Quiz solving failed: {str(e)}")

    # 3️⃣ Success response
    return {
        "email": payload.email,
        "secret": payload.secret,
        "url": payload.url,
        "answer": answer
    }
