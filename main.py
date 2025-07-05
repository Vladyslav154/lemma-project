import os
from fastapi import FastAPI, File, UploadFile, Request, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from dotenv import load_dotenv
import redis
import uuid
import cloudinary
import cloudinary.uploader

# --- THIS IS THE FIX ---
# Define the absolute path to the project's root directory
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# --- Configuration ---
load_dotenv()
app = FastAPI()

# Configure Cloudinary
cloudinary.config(
  cloud_name = os.getenv("CLOUDINARY_CLOUD_NAME"),
  api_key = os.getenv("CLOUDINARY_API_KEY"),
  api_secret = os.getenv("CLOUDINARY_API_SECRET"),
  secure = True
)

# Connect to Redis
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


# --- Endpoints (API) ---
# The rest of your code stays the same...

@app.get("/", response_class=HTMLResponse)
async def read_root(request: Request):
    """Serves the main HTML page."""
    return templates.TemplateResponse("index.html", {"request": request})

# ...