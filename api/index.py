# app.py
from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
import subprocess
import os
import shutil
import logging
from datetime import datetime
import tempfile
from pathlib import Path
from typing import List
from dotenv import load_dotenv
from urllib.parse import quote

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def env_to_cookies(env_content: str, output_file: str) -> None:
    """Convert environment variable content to cookie file"""
    try:
        # Extract content from env format
        if '="' not in env_content:
            raise ValueError("Invalid env content format")
        content = env_content.split('="', 1)[1].strip('"')
        
        # Replace escaped newlines with actual newlines
        cookie_content = content.replace('\\n', '\n')
        
        # Write to cookie file
        with open(output_file, 'w') as f:
            f.write(cookie_content)
            
        logger.info(f"Successfully created cookie file at {output_file}")
    except Exception as e:
        logger.error(f"Error creating cookie file: {str(e)}")
        raise ValueError(f"Error converting to cookie file: {str(e)}")

def get_cookies() -> str:
    """Get cookies from environment variable"""
    load_dotenv()
    cookie_content = os.getenv('COOKIES')
    if not cookie_content:
        raise ValueError("COOKIES environment variable not set")
    return cookie_content

def env_to_cookies_from_env(output_file: str) -> None:
    """Convert environment variable from .env file to cookie file"""
    try:
        load_dotenv()
        env_content = os.getenv('COOKIES')
        logger.info("Retrieved cookies from environment variable")
        
        if not env_content:
            raise ValueError("COOKIES not found in environment variables")
            
        env_to_cookies(f'COOKIES="{env_content}"', output_file)
    except Exception as e:
        logger.error(f"Error creating cookie file from env: {str(e)}")
        raise ValueError(f"Error converting to cookie file: {str(e)}")

app = FastAPI(
    title="GAMDL API",
    description="API for downloading Google Drive files using gamdl",
    version="1.0.0"
)

# Create downloads directory if it doesn't exist
DOWNLOADS_DIR = "downloads"
os.makedirs(DOWNLOADS_DIR, exist_ok=True)

# Mount the downloads directory
app.mount("/files", StaticFiles(directory=DOWNLOADS_DIR), name="files")




# [Previous cookie handling code remains the same...]




# [Previous cookie handling code remains the same...]

class DownloadRequest(BaseModel):
    url: str
    


# [Previous cookie handling code remains the same...]

class FileInfo(BaseModel):
    filename: str
    download_url: str
    file_type: str

class DownloadResponse(BaseModel):
    success: bool
    message: str
    files: List[FileInfo]

@app.post("/download", response_model=DownloadResponse)
async def download_file(request: DownloadRequest):
    try:
        # Create a unique subdirectory for this download
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        download_subdir = os.path.join(DOWNLOADS_DIR, timestamp)
        os.makedirs(download_subdir, exist_ok=True)
        
        logger.info(f"Current working directory: {os.getcwd()}")
        logger.info(f"Download directory: {download_subdir}")
        
        # Create cookies file from environment variable
        cookie_path = os.path.join(download_subdir, "cookies.txt")
        logger.info(f"Creating cookies file at: {cookie_path}")
        env_to_cookies_from_env(cookie_path)
        
        # Change to download directory
        original_dir = os.getcwd()
        os.chdir(download_subdir)
        
        # Run gamdl command
        cmd = ["gamdl", "--codec-song", "aac-legacy", request.url]
        logger.info(f"Executing command: {' '.join(cmd)}")
        
        process = subprocess.run(
            cmd,
            capture_output=True,
            text=True
        )
        
        logger.info(f"Command stdout: {process.stdout}")
        logger.info(f"Command stderr: {process.stderr}")
        
        process.check_returncode()
        
        # Find all files recursively in the download directory
        all_files = []
        for root, dirs, files in os.walk('.'):
            for file in files:
                if file != "cookies.txt":
                    file_path = os.path.join(root, file)
                    all_files.append(file_path)
        
        logger.info(f"All files found: {all_files}")
        
        if not all_files:
            raise Exception("No files found after download attempt")
        
        # Process all downloaded files
        downloaded_files = []
        space_url = os.getenv("SPACE_URL", "https://tecuts-testing.hf.space")
        
        for file_path in all_files:
            try:
                # Get just the filename from the path
                filename = os.path.basename(file_path)
                
                # Create new path in current directory
                new_path = os.path.join(".", filename)
                
                logger.info(f"Moving file from {file_path} to {new_path}")
                
                # Copy file to current directory
                shutil.copy2(file_path, new_path)
                
                # Get file extension
                file_type = os.path.splitext(filename)[1].lstrip('.')
                
                # Generate download URL
                encoded_filename = quote(filename)
                download_url = f"{space_url}/files/{timestamp}/{encoded_filename}"
                
                downloaded_files.append(FileInfo(
                    filename=filename,
                    download_url=download_url,
                    file_type=file_type
                ))
                
                logger.info(f"Processed file: {filename} -> {download_url}")
                
            except Exception as e:
                logger.error(f"Error processing file {file_path}: {str(e)}")
                continue
        
        # Clean up original files and directories after successful copy
        for root, dirs, files in os.walk('.'):
            for dir_name in dirs:
                if dir_name == "Apple Music":  # Only remove the music directory
                    dir_path = os.path.join(root, dir_name)
                    logger.info(f"Removing directory: {dir_path}")
                    shutil.rmtree(dir_path, ignore_errors=True)
        
        # Move back to original directory
        os.chdir(original_dir)
        
        if not downloaded_files:
            raise Exception("Failed to process any files")
        
        return DownloadResponse(
            success=True,
            message=f"Successfully downloaded {len(downloaded_files)} files",
            files=downloaded_files
        )
            
    except subprocess.CalledProcessError as e:
        logger.error(f"Download process failed: stdout={e.stdout}, stderr={e.stderr}")
        raise HTTPException(
            status_code=400,
            detail=f"Failed to download: {e.stderr or e.stdout or str(e)}"
        )
    except Exception as e:
        logger.error(f"Unexpected error: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Error: {str(e)}"
        )
    finally:
        if 'original_dir' in locals():
            os.chdir(original_dir)
            
@app.get("/")
async def root():
    return {"message": "Welcome to testing API. Visit /docs for API documentation."}

@app.get("/test")
async def test():
    """Test endpoint to verify setup"""
    try:
        # Test cookie creation
        temp_cookie = os.path.join(DOWNLOADS_DIR, "test_cookies.txt")
        env_to_cookies_from_env(temp_cookie)
        
        # Test gamdl installation
        process = subprocess.run(["gamdl", "--version"], capture_output=True, text=True)
        
        return {
            "gamdl_version": process.stdout.strip(),
            "cookies_created": os.path.exists(temp_cookie),
            "cookies_size": os.path.getsize(temp_cookie) if os.path.exists(temp_cookie) else 0,
            "installed": True,
            "error": process.stderr if process.stderr else None
        }
    except Exception as e:
        return {
            "installed": False,
            "error": str(e)
        }
