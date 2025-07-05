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

# --- Define the absolute path to the project's root directory ---
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
    # Fallback for local development if REDIS_URL is not set
    r = redis.Redis(host='localhost', port=6379, db=0, decode_responses=True)
else:
    # This will be used on Render
    r = redis.from_url(redis_url, decode_responses=True)

# Mount static files using an absolute path
app.mount(
    "/static",
    StaticFiles(directory=os.path.join(BASE_DIR, "static")),
    name="static"
)

# Point to the templates directory using an absolute path
templates = Jinja2Templates(directory=os.path.join(BASE_DIR, "templates"))


# --- API Endpoints ---

@app.get("/", response_class=HTMLResponse)
async def read_root(request: Request):
    """Serves the main HTML page."""
    return templates.TemplateResponse("index.html", {"request": request})

@app.post("/upload")
async def upload_file(request: Request, file: UploadFile = File(...)):
    """Accepts a file, uploads it to Cloudinary, and creates a one-time link."""
    try:
        # Upload the file directly to Cloudinary
        upload_result = cloudinary.uploader.upload(file.file, resource_type="auto")
        # Get the secure URL of the uploaded file
        file_url = upload_result.get("secure_url")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Could not upload file to Cloudinary: {e}")

    # Generate a unique ID for our one-time link
    link_id = str(uuid.uuid4().hex[:10])

    # Save the Cloudinary URL in Redis for 15 minutes (900 seconds)
    r.setex(link_id, 900, file_url)
    
    # Form the one-time download link for our service
    base_url = str(request.base_url)
    one_time_link = f"{base_url}file/{link_id}"

    return {"download_link": one_time_link}

@app.get("/file/{link_id}")
async def get_file_redirect(link_id: str):
    """
    Retrieves the Cloudinary URL from Redis using the one-time ID,
    deletes the record, and redirects the user to the actual file.
    """
    file_url = r.get(link_id)
    
    if not file_url:
        raise HTTPException(status_code=404, detail="Link is invalid, has been used, or has expired.")

    # Core Logic: Delete the key from Redis immediately to ensure it's one-time use
    r.delete(link_id)

    # Redirect the user to the file's URL on Cloudinary
    return RedirectResponse(url=file_url)