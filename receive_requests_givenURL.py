# receive_requests.py - FULL SOLVER
import os
import time
import asyncio
import json
import re
import base64
from io import BytesIO
from datetime import datetime, timedelta
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from playwright.async_api import async_playwright
from dotenv import load_dotenv
import aiohttp
import pandas as pd
import PyPDF2

load_dotenv()

STUDENT_EMAIL = os.getenv("STUDENT_EMAIL")
STUDENT_SECRET = os.getenv("STUDENT_SECRET")
SUBMIT_URL = "https://tds-llm-analysis.s-anand.net/submit"

app = FastAPI(title="Full Quiz Solver")

class QuizRequest(BaseModel):
    email: str
    secret: str
    url: str

async def parse_task_instructions(page):
    """Extract task instructions from quiz page"""
    try:
        # Get all text content
        body_text = await page.evaluate("document.body.innerText")
        
        # Get HTML for more detailed parsing
        html_content = await page.content()
        
        # Look for common instruction patterns
        task_info = {
            "full_text": body_text,
            "html": html_content,
            "links": [],
            "forms": [],
            "tables": [],
            "images": []
        }
        
        # Extract all links
        links = await page.query_selector_all("a[href]")
        for link in links:
            href = await link.get_attribute("href")
            text = await link.inner_text()
            task_info["links"].append({"url": href, "text": text})
        
        # Extract table data
        tables = await page.query_selector_all("table")
        if tables:
            for table in tables:
                table_html = await table.inner_html()
                task_info["tables"].append(table_html)
        
        return task_info
    except Exception as e:
        print(f"Error parsing instructions: {e}")
        return {}

async def solve_csv_task(csv_url, page, instructions):
    """Solve tasks involving CSV files"""
    try:
        print(f"📊 Downloading CSV: {csv_url}")
        async with aiohttp.ClientSession() as session:
            async with session.get(csv_url) as resp:
                csv_content = await resp.text()
        
        df = pd.read_csv(StringIO(csv_content))
        
        # Check what operation is requested
        instructions_lower = instructions.lower()
        
        if "sum" in instructions_lower:
            # Find numeric column and sum
            numeric_cols = df.select_dtypes(include=['number']).columns
            if len(numeric_cols) > 0:
                col = numeric_cols[0]
                answer = df[col].sum()
                return int(answer) if answer == int(answer) else float(answer)
        
        elif "count" in instructions_lower:
            return len(df)
        
        elif "mean" in instructions_lower or "average" in instructions_lower:
            numeric_cols = df.select_dtypes(include=['number']).columns
            if len(numeric_cols) > 0:
                col = numeric_cols[0]
                answer = df[col].mean()
                return float(answer)
        
        elif "max" in instructions_lower:
            numeric_cols = df.select_dtypes(include=['number']).columns
            if len(numeric_cols) > 0:
                col = numeric_cols[0]
                return int(df[col].max())
        
        elif "min" in instructions_lower:
            numeric_cols = df.select_dtypes(include=['number']).columns
            if len(numeric_cols) > 0:
                col = numeric_cols[0]
                return int(df[col].min())
        
        return None
    except Exception as e:
        print(f"CSV solve error: {e}")
        return None

async def solve_pdf_task(pdf_url, page, instructions):
    """Solve tasks involving PDF files"""
    try:
        print(f"📄 Downloading PDF: {pdf_url}")
        async with aiohttp.ClientSession() as session:
            async with session.get(pdf_url) as resp:
                pdf_data = await resp.read()
        
        pdf_reader = PyPDF2.PdfReader(BytesIO(pdf_data))
        text = ""
        for page_obj in pdf_reader.pages:
            text += page_obj.extract_text()
        
        instructions_lower = instructions.lower()
        
        # Look for numbers in PDF
        if "sum" in instructions_lower:
            numbers = [float(n) for n in re.findall(r'\d+\.?\d*', text)]
            if numbers:
                return int(sum(numbers)) if sum(numbers) == int(sum(numbers)) else sum(numbers)
        
        # Look for specific keywords
        if "total" in instructions_lower or "count" in instructions_lower:
            numbers = [int(n) for n in re.findall(r'\d+', text)]
            if numbers:
                return numbers[-1]  # Usually the last number
        
        return None
    except Exception as e:
        print(f"PDF solve error: {e}")
        return None

async def solve_api_task(page, instructions):
    """Solve tasks involving API calls"""
    try:
        # Look for API endpoints and headers in page
        if "api" in instructions.lower() or "endpoint" in instructions.lower():
            # Extract potential API URLs from instructions
            api_urls = re.findall(r'https?://[^\s<>"{}|\\^`\[\]]*', instructions)
            
            for api_url in api_urls:
                if "api" in api_url.lower():
                    print(f"🔗 Calling API: {api_url}")
                    async with aiohttp.ClientSession() as session:
                        async with session.get(api_url) as resp:
                            data = await resp.json()
                            # Try to extract numeric answer
                            if isinstance(data, dict):
                                for key in ['answer', 'result', 'value', 'total']:
                                    if key in data:
                                        return data[key]
                            elif isinstance(data, list) and len(data) > 0:
                                return len(data)
        
        return None
    except Exception as e:
        print(f"API solve error: {e}")
        return None

async def solve_text_task(page, instructions):
    """Solve tasks requiring text parsing"""
    try:
        body_text = await page.evaluate("document.body.innerText")
        
        # Look for explicit answer format
        if "answer" in body_text.lower():
            # Try to extract answer after "answer:" or "answer is"
            match = re.search(r'answer[:\s]+([^\n]+)', body_text, re.IGNORECASE)
            if match:
                answer_text = match.group(1).strip()
                # Try to convert to number if possible
                try:
                    return int(answer_text)
                except:
                    try:
                        return float(answer_text)
                    except:
                        return answer_text
        
        # Look for numbers in specific context
        numbers = re.findall(r'\b\d+\b', body_text)
        if numbers:
            return int(numbers[-1])
        
        return None
    except Exception as e:
        print(f"Text solve error: {e}")
        return None

async def solve_quiz_logic(page, page_url):
    """
    Main quiz-solving logic that handles various task types
    """
    print(f"\n🎯 Solving quiz: {page_url}")
    
    await page.wait_for_load_state("networkidle")
    await asyncio.sleep(2)  # Wait for JS rendering
    
    # Parse task instructions
    task_info = await parse_task_instructions(page)
    instructions = task_info.get("full_text", "")
    
    print(f"📝 Instructions: {instructions[:200]}...")
    
    answer = None
    
    # 1️⃣ Check for CSV files
    csv_links = [l for l in task_info["links"] if ".csv" in l["url"].lower()]
    if csv_links:
        csv_url = csv_links[0]["url"]
        answer = await solve_csv_task(csv_url, page, instructions)
        if answer:
            print(f"✅ CSV answer: {answer}")
    
    # 2️⃣ Check for PDF files
    if not answer:
        pdf_links = [l for l in task_info["links"] if ".pdf" in l["url"].lower()]
        if pdf_links:
            pdf_url = pdf_links[0]["url"]
            answer = await solve_pdf_task(pdf_url, page, instructions)
            if answer:
                print(f"✅ PDF answer: {answer}")
    
    # 3️⃣ Check for API tasks
    if not answer:
        answer = await solve_api_task(page, instructions)
        if answer:
            print(f"✅ API answer: {answer}")
    
    # 4️⃣ Fall back to text parsing
    if not answer:
        answer = await solve_text_task(page, instructions)
        if answer:
            print(f"✅ Text answer: {answer}")
    
    # 5️⃣ If still no answer, try evaluating any form or interactive element
    if not answer:
        try:
            el = await page.query_selector("#answer")
            if el:
                text = await el.inner_text()
                try:
                    answer = int(text.strip())
                except:
                    answer = text.strip()
        except:
            pass
    
    if not answer:
        answer = "0"  # Fallback
        print(f"⚠️ No answer found, using fallback: {answer}")
    
    # Submit answer
    print(f"📤 Submitting answer: {answer}")
    submission_payload = {
        "email": STUDENT_EMAIL,
        "secret": STUDENT_SECRET,
        "url": page_url,
        "answer": answer
    }
    
    async with aiohttp.ClientSession() as session:
        async with session.post(
            SUBMIT_URL,
            json=submission_payload,
            headers={"Content-Type": "application/json"}
        ) as resp:
            try:
                res_json = await resp.json()
                print(f"📥 Server response: {res_json}")
                next_url = res_json.get("url")
                is_correct = res_json.get("correct", False)
                reason = res_json.get("reason", "")
                return is_correct, next_url, answer, reason
            except Exception as e:
                print(f"Error parsing response: {e}")
                return False, None, answer, str(e)

@app.post("/solve")
async def solve_quiz(payload: QuizRequest):
    """Main endpoint to solve quiz chain"""
    
    # Validate credentials
    if payload.email != STUDENT_EMAIL or payload.secret != STUDENT_SECRET:
        raise HTTPException(status_code=403, detail="Invalid credentials")
    
    print(f"\n{'='*60}")
    print(f"🚀 Starting quiz chain from: {payload.url}")
    print(f"{'='*60}")
    
    current_url = payload.url
    start_time = time.time()
    quiz_count = 0
    results = []
    
    try:
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            
            while current_url and (time.time() - start_time) < 180:  # 3 minutes
                quiz_count += 1
                elapsed = time.time() - start_time
                
                print(f"\n⏱️ Elapsed: {elapsed:.1f}s | Quiz #{quiz_count}")
                
                page = await browser.new_page()
                
                try:
                    is_correct, next_url, answer, reason = await solve_quiz_logic(page, current_url)
                    
                    results.append({
                        "quiz": quiz_count,
                        "url": current_url,
                        "answer": answer,
                        "correct": is_correct,
                        "reason": reason
                    })
                    
                    if is_correct:
                        print(f"✅ Correct!")
                        if next_url:
                            print(f"→ Next: {next_url}")
                            current_url = next_url
                        else:
                            print(f"🎉 Quiz chain complete!")
                            current_url = None
                    else:
                        print(f"❌ Incorrect: {reason}")
                        if next_url:
                            print(f"→ Trying next: {next_url}")
                            current_url = next_url
                        else:
                            print(f"No next URL provided")
                            current_url = None
                
                finally:
                    await page.close()
            
            await browser.close()
    
    except Exception as e:
        print(f"❌ Error: {e}")
        raise HTTPException(status_code=400, detail=str(e))
    
    print(f"\n{'='*60}")
    print(f"✅ Completed {quiz_count} quizzes in {time.time() - start_time:.1f}s")
    print(f"{'='*60}\n")
    
    return {
        "email": payload.email,
        "quizzes_solved": quiz_count,
        "results": results,
        "total_time": time.time() - start_time
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8000)
