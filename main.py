import os
import uuid
import redis
import cloudinary
import cloudinary.uploader
from fastapi import FastAPI, File, UploadFile, Request, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from dotenv import load_dotenv

# --- THIS IS THE FIX ---
# Define the absolute path to the project's root directory
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# --- Configuration ---
load_dotenv()
app = FastAPI()

# Configure Cloudinary using credentials from environment variables
cloudinary.config(
  cloud_name = os.getenv("CLOUDINARY_CLOUD_NAME"),
  api_key = os.getenv("CLOUDINARY_API_KEY"),
  api_secret = os.getenv("CLOUDINARY_API_SECRET"),
  secure = True
)

# Connect to Redis using the URL from environment variables
redis_url = os.getenv("REDIS_URL")
if not redis_url:
    r = redis.Redis(host='localhost', port=6379, db=0, decode_responses=True)
else:
    r = redis.from_url(redis_url, decode_responses=True)

# --- APPLY THE FIX HERE ---
# Mount static files using the absolute path
app.mount(
    "/static",
    StaticFiles(directory=os.path.join(BASE_DIR, "static")),
    name="static"
)
# Point to the templates directory using the absolute path
templates = Jinja2Templates(directory=os.path.join(BASE_DIR, "templates"))


# --- API Endpoints ---
@app.get("/", response_class=HTMLResponse)
async def read_root(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})

@app.post("/upload")
async def upload_file(request: Request, file: UploadFile = File(...)):
    upload_result = cloudinary.uploader.upload(file.file, resource_type="auto")
    file_url = upload_result.get("secure_url")
    link_id = str(uuid.uuid4().hex[:10])
    r.setex(link_id, 900, file_url)
    base_url = str(request.base_url)
    one_time_link = f"{base_url}file/{link_id}"
    return {"download_link": one_time_link}

@app.get("/file/{link_id}")
async def get_file_redirect(link_id: str):
    file_url = r.get(link_id)
    if not file_url:
        raise HTTPException(status_code=404, detail="Link is invalid, has been used, or has expired.")
    r.delete(link_id)
    return RedirectResponse(url=file_url)