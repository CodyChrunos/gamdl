from fastapi import FastAPI, Request, HTTPException, Security
from fastapi.security import APIKeyHeader
from datetime import datetime, date
import os
from collections import defaultdict
import yt_dlp
from pathlib import Path
import urllib.parse
import gc
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI()

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Adjust this to your frontend domains
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# API key setup
api_key_header = APIKeyHeader(name="X-API-Key")
API_KEY = os.getenv("API_KEY")

# Since Vercel is serverless, we need to use /tmp for file operations
global_download_dir = "/tmp"
Path(global_download_dir).mkdir(exist_ok=True)

def verify_api_key(api_key: str = Security(api_key_header)):
    if api_key != API_KEY:
        raise HTTPException(
            status_code=403,
            detail="Invalid API key"
        )
    return api_key

@app.post("/api/audio")
async def download_audio(request: Request, api_key: str = Security(verify_api_key)):
    try:
        data = await request.json()
        video_url = data.get('url')
        
        timestamp = datetime.now().strftime('%Y%m%d%H%M%S')
        output_template = str(Path(global_download_dir) / f'%(title).70s_{timestamp}.%(ext)s')
        
        ydl_opts = {
            'format': 'bestaudio/best',
            'outtmpl': output_template,
            'quiet': True,
            'no_warnings': True,
            'noprogress': True,
            'postprocessors': [{
                'key': 'FFmpegExtractAudio',
                'preferredcodec': 'mp3',
                'preferredquality': '192'
            }]
        }
        
        # Download the audio
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.download([video_url])
        
        downloaded_files = list(Path(global_download_dir).glob(f"*_{timestamp}.*"))
        if not downloaded_files:
            return {"error": "Download failed"}
            
        downloaded_file = downloaded_files[0]
        
        # Read the file content
        file_content = downloaded_file.read_bytes()
        
        # Clean up the file
        downloaded_file.unlink()
        
        # Return the file content directly
        return Response(
            content=file_content,
            media_type="audio/mpeg",
            headers={
                "Content-Disposition": f'attachment; filename="{downloaded_file.name}"'
            }
        )
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        gc.collect()

# For Vercel serverless function
from mangum import Mangum
handler = Mangum(app)
