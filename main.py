from fastapi import FastAPI
from pydantic import BaseModel
from fastapi.middleware.cors import CORSMiddleware
import requests
import sqlite3
from datetime import datetime

app = FastAPI()

# ✅ IMPORTANT: CORS (Fixes Failed to Fetch)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Use /tmp for Render write access
DB_NAME = "/tmp/pipeline.db"


# ===== INPUT MODEL =====
class PipelineRequest(BaseModel):
    email: str
    source: str


# ===== INIT DATABASE =====
def init_db():
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("""
        CREATE TABLE IF NOT EXISTS results (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            original TEXT,
            analysis TEXT,
            sentiment TEXT,
            timestamp TEXT
        )
    """)
    conn.commit()
    conn.close()

init_db()


# ===== MOCK AI =====
def analyze_text(text):
    try:
        insights = []

        if "error" in text.lower():
            sentiment = "negative"
            insights.append("The comment discusses a potential issue or problem.")
        elif "thank" in text.lower() or "great" in text.lower():
            sentiment = "positive"
            insights.append("The comment expresses appreciation or positive feedback.")
        else:
            sentiment = "neutral"
            insights.append("The comment appears to provide general information.")

        insights.append(f"The comment contains {len(text.split())} words.")
        insights.append("This appears to be user-generated feedback.")

        analysis = " ".join(insights)

        return analysis, sentiment

    except Exception as e:
        return None, f"AI Error: {str(e)}"


# ===== HEALTH CHECK =====
@app.get("/")
def home():
    return {"message": "Pipeline API is running"}


# ===== MAIN PIPELINE =====
@app.post("/pipeline")
def run_pipeline(request: PipelineRequest):

    results = []
    errors = []

    # 1️⃣ Fetch Data
    try:
        response = requests.get(
            "https://jsonplaceholder.typicode.com/comments?postId=1",
            timeout=5
        )
        response.raise_for_status()
        data = response.json()[:3]
    except Exception as e:
        return {"error": f"API fetch failed: {str(e)}"}

    # 2️⃣ Process Each Item
    for item in data:
        try:
            original_text = item.get("body", "")

            analysis, sentiment = analyze_text(original_text)

            if analysis is None:
                errors.append(sentiment)
                continue

            timestamp = datetime.utcnow().isoformat()

            # 3️⃣ Store in DB
            try:
                conn = sqlite3.connect(DB_NAME)
                c = conn.cursor()
                c.execute(
                    "INSERT INTO results (original, analysis, sentiment, timestamp) VALUES (?, ?, ?, ?)",
                    (original_text, analysis, sentiment, timestamp)
                )
                conn.commit()
                conn.close()
                stored = True
            except Exception as db_error:
                stored = False
                errors.append(f"DB Error: {str(db_error)}")

            results.append({
                "original": original_text,
                "analysis": analysis,
                "sentiment": sentiment,
                "stored": stored,
                "timestamp": timestamp
            })

        except Exception as item_error:
            errors.append(f"Item processing error: {str(item_error)}")

    # 4️⃣ Mock Notification
    print(f"Notification sent to: {request.email}")

    return {
        "items": results,
        "notificationSent": True,
        "processedAt": datetime.utcnow().isoformat(),
        "errors": errors
    }
