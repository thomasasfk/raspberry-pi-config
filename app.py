import os
from datetime import datetime

from fastapi import FastAPI
from fastapi import HTTPException
from fastapi.responses import FileResponse
from fastapi.responses import HTMLResponse
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from starlette.requests import Request

app = FastAPI()

UPLOAD_DIR = os.path.join("www", "uploads")
os.makedirs(UPLOAD_DIR, exist_ok=True)


@app.post("/api/upload-audio")
async def upload_audio_file(request: Request):
    body = await request.body()
    if not body:
        raise HTTPException(status_code=400, detail="No file uploaded")

    unique_filename = f"{datetime.now().strftime('%Y%m%d_%H%M%S')}.m4a"
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
