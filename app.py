from fastapi import FastAPI, File, UploadFile, HTTPException
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
import os
from datetime import datetime
import uuid

from starlette.requests import Request

app = FastAPI()

UPLOAD_DIR = os.path.join("www", "uploads")
os.makedirs(UPLOAD_DIR, exist_ok=True)


@app.post("/api/upload-audio")
async def upload_audio_file(request: Request):
    body = await request.body()
    if not body:
        raise HTTPException(status_code=400, detail="No file uploaded")

    filename = request.headers.get('x-filename', 'audio')
    unique_filename = f"{datetime.now().strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4()}{os.path.splitext(filename)[1] or '.m4a'}"
    file_path = os.path.join(UPLOAD_DIR, unique_filename)

    with open(file_path, "wb") as buffer:
        buffer.write(body)

    return {
        "message": "File uploaded successfully",
        "filename": unique_filename,
        "path": f"/uploads/{unique_filename}"
    }


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
