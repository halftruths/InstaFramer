from fastapi import FastAPI, HTTPException, Request, Response
from fastapi.responses import HTMLResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
import os
from pydantic import BaseModel
from typing import Optional, List
import io

from image_processor import process_image, batch_process
from amazon_integration import get_amazon_photos, clear_amazon_cache

# Clear leftover amazon cache on startup
clear_amazon_cache()

app = FastAPI(title="Instagram Framer")

# Allow CORS for local dev
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount static directory
app.mount("/static", StaticFiles(directory="static"), name="static")

@app.get("/", response_class=HTMLResponse)
async def read_index():
    with open("static/index.html", "r", encoding="utf-8") as f:
        return f.read()

# Models
class FileOrFolderItem(BaseModel):
    name: str
    path: str
    is_dir: bool
    is_image: bool

class BatchRequest(BaseModel):
    input_folder: str
    output_folder: str
    border_inner_width: float = 0.0
    border_inner_color: str = "#ffffff"
    border_outer_width: float = 0.0
    border_outer_color: str = "#000000"
    fit_instagram: bool = True
    aspect_ratio: str = "4:5"
    respect_original_dimensions: bool = False

class AmazonRequest(BaseModel):
    url: str

@app.get("/api/files")
async def list_files(path: str = None):
    """
    List files and directories in the given path.
    Defaults to user home if None.
    """
    if path is None or path.strip() == "":
        path = os.path.expanduser("~")
        
    if not os.path.exists(path):
        raise HTTPException(status_code=404, detail="Path not found")
        
    if not os.path.isdir(path):
        raise HTTPException(status_code=400, detail="Path is not a directory")

    items: List[FileOrFolderItem] = []
    
    # Add parent directory
    parent_dir = os.path.dirname(path)
    if parent_dir and parent_dir != path:
        items.append(FileOrFolderItem(
            name="..",
            path=parent_dir,
            is_dir=True,
            is_image=False
        ))

    try:
        for entry in os.scandir(path):
            is_image = False
            if entry.is_file():
                ext = os.path.splitext(entry.name)[1].lower()
                if ext in ['.jpg', '.jpeg', '.png', '.webp', '.bmp', '.tiff']:
                    is_image = True
                    
            if entry.is_dir() or is_image:
                items.append(FileOrFolderItem(
                    name=entry.name,
                    path=entry.path,
                    is_dir=entry.is_dir(),
                    is_image=is_image
                ))
    except PermissionError:
        raise HTTPException(status_code=403, detail="Permission denied to access this directory")

    # Sort directories first, then alphabetically
    items.sort(key=lambda x: (not x.is_dir, x.name.lower()))
    return {"current_path": path, "items": items}

@app.get("/api/preview")
async def get_preview(
    image_path: str,
    border_inner_width: float = 0.0,
    border_inner_color: str = "#ffffff",
    border_outer_width: float = 0.0,
    border_outer_color: str = "#000000",
    fit_instagram: bool = True,
    aspect_ratio: str = "4:5",
    respect_original_dimensions: bool = False
):
    if not os.path.exists(image_path) or not os.path.isfile(image_path):
        raise HTTPException(status_code=404, detail="Image not found")
        
    try:
        buffer = process_image(
            input_path=image_path,
            border_inner_width=border_inner_width,
            border_inner_color=border_inner_color,
            border_outer_width=border_outer_width,
            border_outer_color=border_outer_color,
            fit_instagram=fit_instagram,
            aspect_ratio=aspect_ratio,
            respect_original_dimensions=respect_original_dimensions,
            preview=True
        )
        
        if buffer is None:
            raise HTTPException(status_code=500, detail="Error generating preview")
            
        return StreamingResponse(buffer, media_type="image/jpeg")
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/batch")
async def run_batch(request: BatchRequest):
    if not os.path.exists(request.input_folder):
        raise HTTPException(status_code=404, detail="Input folder not found")
        
    try:
        processed_files = batch_process(
            input_folder=request.input_folder,
            output_folder=request.output_folder,
            border_inner_width=request.border_inner_width,
            border_inner_color=request.border_inner_color,
            border_outer_width=request.border_outer_width,
            border_outer_color=request.border_outer_color,
            fit_instagram=request.fit_instagram,
            aspect_ratio=request.aspect_ratio,
            respect_original_dimensions=request.respect_original_dimensions
        )
        return {"status": "success", "processed_count": len(processed_files), "output_folder": request.output_folder}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/amazon")
def run_amazon_scrape(request: AmazonRequest):
    """
    Synchronously run playwright script and return the local path
    where the photos were cached. 
    """
    try:
        url = request.url
        if not ("amazon.com/photos" in url or "amazon.ca/photos" in url or "amazon.co.uk/photos" in url):
            raise ValueError("Not a valid Amazon Photos URL.")
            
        cache_dir = get_amazon_photos(url)
        return {"status": "success", "cache_dir": cache_dir}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


