import os
import sqlite3
import requests
from datetime import datetime

from fastapi import FastAPI
from fastapi import HTTPException
from fastapi.responses import FileResponse
from fastapi.responses import HTMLResponse
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from starlette.requests import Request

from dotenv import load_dotenv

load_dotenv()

app = FastAPI()

UPLOAD_DIR = os.path.join("www", "uploads")
os.makedirs(UPLOAD_DIR, exist_ok=True)
DB_PATH = os.path.join("www", "transcriptions.db")
WHISPER_API_KEY = os.environ.get("WHISPER_API_KEY")


def init_db():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute(
        '''
    CREATE TABLE IF NOT EXISTS transcriptions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        filename TEXT UNIQUE,
        transcription TEXT,
        created_at TIMESTAMP
    )
    '''
    )
    conn.commit()
    conn.close()


init_db()


def transcribe_audio(file_path):
    if not WHISPER_API_KEY:
        raise HTTPException(status_code=500, detail="WHISPER_API_KEY not configured")

    with open(file_path, "rb") as audio_file:
        response = requests.post(
            "https://api.openai.com/v1/audio/transcriptions",
            headers={"Authorization": f"Bearer {WHISPER_API_KEY}"},
            files={"file": audio_file},
            data={"model": "whisper-1"}
        )

    if response.status_code != 200:
        raise HTTPException(status_code=response.status_code, detail=f"Whisper API error: {response.text}")

    return response.json().get("text", "")


def save_transcription(filename, transcription):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO transcriptions (filename, transcription, created_at) VALUES (?, ?, ?)",
        (filename, transcription, datetime.now().isoformat())
    )
    conn.commit()
    conn.close()


@app.post("/api/upload-audio")
async def upload_audio_file(request: Request):
    body = await request.body()
    if not body:
        raise HTTPException(status_code=400, detail="No file uploaded")

    unique_filename = f"{datetime.now().strftime('%Y%m%d_%H%M%S')}.m4a"
    file_path = os.path.join(UPLOAD_DIR, unique_filename)
    with open(file_path, "wb") as buffer:
        buffer.write(body)

    try:
        transcription = transcribe_audio(file_path)
        save_transcription(unique_filename, transcription)
    except Exception as e:
        return {
            "message": f"File uploaded but transcription failed: {str(e)}",
            "filename": unique_filename,
            "path": f"/uploads/{unique_filename}"
        }

    return {
        "message": "File uploaded and transcribed successfully",
        "filename": unique_filename,
        "path": f"/uploads/{unique_filename}",
        "transcription": transcription
    }


@app.get("/api/transcriptions")
async def get_transcriptions():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM transcriptions ORDER BY created_at DESC")
    transcriptions = [dict(row) for row in cursor.fetchall()]
    conn.close()
    return transcriptions


@app.get("/api/transcriptions/{filename}")
async def get_transcription(filename: str):
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM transcriptions WHERE filename = ?", (filename,))
    transcription = cursor.fetchone()
    conn.close()

    if not transcription:
        raise HTTPException(status_code=404, detail="Transcription not found")

    return dict(transcription)


@app.get("/transcriptions", response_class=HTMLResponse)
async def transcriptions_page():
    transcriptions_path = os.path.join("www", "transcriptions.html")
    if os.path.exists(transcriptions_path):
        return FileResponse(transcriptions_path)
    return HTMLResponse(content="Not Found", status_code=404)


@app.get("/api/{path:path}", response_class=JSONResponse)
async def custom_api_routes(path: str):
    return {"message": f"API route for {path} not found"}


app.mount("/", StaticFiles(directory="www", html=True), name="static")


@app.get("/{full_path:path}")
async def serve_spa_index(full_path: str):
    index_path = os.path.join("www", "index.html")
    if os.path.exists(index_path):
        return FileResponse(index_path)
    return HTMLResponse(content="Not Found", status_code=404)
