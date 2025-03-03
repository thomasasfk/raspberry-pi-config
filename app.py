import os
import sqlite3
import requests

from datetime import datetime
from typing import Optional

from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, FileResponse
from fastapi import FastAPI, Request, HTTPException
from starlette.templating import Jinja2Templates
from dotenv import load_dotenv

load_dotenv()

app = FastAPI()

templates = Jinja2Templates(directory="www/templates")
templates.env.filters['format_date'] = lambda date_str: datetime.fromisoformat(date_str.replace('Z', '+00:00')).strftime('%m/%d/%Y at %H:%M:%S')

UPLOAD_DIR = "www/uploads"
os.makedirs(UPLOAD_DIR, exist_ok=True)
DB_PATH = "www/transcriptions.db"
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


def get_all_transcriptions():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM transcriptions ORDER BY created_at DESC")
    transcriptions = [dict(row) for row in cursor.fetchall()]
    conn.close()
    return transcriptions


@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    services = {
        "Home Assistant": {
            "icon": "http://raspberrypi.local:8000/static/icons/favicon.ico",
            "port": 8000,
            "desc": "Home automation platform",
            "host": "raspberrypi.local",
            "path": ""
        },
        # "AppDaemon": {
        #     "icon": "http://raspberrypi.local:8012/aui/favicon.ico",
        #     "port": 8012,
        #     "desc": "AppDaemon service",
        #     "host": "raspberrypi.local",
        #     "path": ""
        # },
        # "OctoPrint": {
        #     "icon": "https://raw.githubusercontent.com/OctoPrint/OctoPrint/master/src/octoprint/static/img/logo.png",
        #     "port": 8001,
        #     "desc": "3D printer management",
        #     "host": "raspberrypi.local",
        #     "path": ""
        # },
        "Pi-hole": {
            "icon": "https://pi-hole.github.io/graphics/Vortex/Vortex.png",
            "port": 8003,
            "desc": "Network-wide ad blocking",
            "host": "raspberrypi.local",
            "path": "/admin/login"
        },
        "ruTorrent": {
            "icon": "http://raspberrypi.local:8005/images/favicon.ico",
            "port": 8005,
            "desc": "Torrent client web interface",
            "host": "raspberrypi.local",
            "path": ""
        },
        "Portainer": {
            "icon": "https://raw.githubusercontent.com/portainer/portainer/develop/app/assets/ico/favicon.ico",
            "port": 8008,
            "desc": "Docker management UI",
            "host": "raspberrypi.local",
            "path": ""
        },
        "Transcriptions": {
            "icon": "https://openai.com/favicon.ico",
            "port": 7999,
            "path": "/transcriptions",
            "desc": "OpenAI Whisper transcriptions",
            "host": "raspberrypi.local"
        },
    }

    return templates.TemplateResponse(
        "index.jinja2",
        {"services": services,
         "request": request}
    )


# Transcription routes
@app.get("/transcriptions", response_class=HTMLResponse)
async def transcriptions_page(
        request: Request, message: Optional[str] = None, success: bool = True, filename: Optional[str] = None
):
    transcriptions = get_all_transcriptions()
    return templates.TemplateResponse(
        "transcriptions.jinja2",
        {"transcriptions": get_all_transcriptions(),
         "selected_transcription": None,
         "message": message,
         "success": success,
         "filename": filename,
         "request": request}
    )

@app.post("/api/upload-audio")
async def upload_audio(request: Request):
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


@app.get("/uploads/{filename}")
async def serve_upload(filename: str):
    file_path = os.path.join(UPLOAD_DIR, filename)
    if os.path.exists(file_path):
        return FileResponse(file_path)
    return HTMLResponse(content="File not found", status_code=404)


app.mount("/static", StaticFiles(directory="www"), name="static")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=7999)
