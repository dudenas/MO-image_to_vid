import os
import cv2
import numpy as np
from flask import Flask, request, render_template, send_file, jsonify
from flask_cors import CORS
from werkzeug.utils import secure_filename
import ffmpeg
from PIL import Image
import tempfile
import shutil
import logging
import gc
from threading import Lock
import json
import re
import platform
import subprocess
import sys
from pathlib import Path
import threading
from time import sleep

# Version number
APP_VERSION = "1.2.7"

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)
CORS(app)
app.config['MAX_CONTENT_LENGTH'] = 512 * 1024 * 1024  # 512MB max file size
app.config['UPLOAD_FOLDER'] = os.path.join(tempfile.gettempdir(), 'uploads')
app.config['TEMP_FOLDER'] = os.path.join(tempfile.gettempdir(), 'temp')

# Ensure directories exist
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
os.makedirs(app.config['TEMP_FOLDER'], exist_ok=True)

ALLOWED_EXTENSIONS = {'png'}

# Global progress tracking
conversion_progress = 0
progress_lock = Lock()

# Set FFmpeg path - ensure it's absolute
base_dir = os.path.abspath(os.path.dirname(__file__))
ffmpeg_dir = os.path.join(base_dir, 'vendor', 'ffmpeg')

# Add FFmpeg to PATH at the beginning to ensure it's found first
os.environ['PATH'] = f"{ffmpeg_dir}{os.pathsep}{os.environ['PATH']}"

# Log FFmpeg path for debugging
logger.info(f"FFmpeg directory: {ffmpeg_dir}")
if os.path.exists(os.path.join(ffmpeg_dir, 'ffmpeg')):
    logger.info("Found FFmpeg binary in vendor directory")
else:
    logger.warning("FFmpeg binary not found in vendor directory")

def update_progress(percent, message=""):
    """Update progress and log it"""
    global conversion_progress
    with progress_lock:
        conversion_progress = percent
    logger.info(f"Progress: {percent}% - {message}")

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def get_ffmpeg_path():
    """Get path to FFmpeg binary"""
    vendor_ffmpeg = Path(__file__).parent / 'vendor' / 'ffmpeg' / 'ffmpeg'
    if vendor_ffmpeg.exists():
        return str(vendor_ffmpeg)
    return 'ffmpeg'  # Fall back to system FFmpeg

def get_ffmpeg_version():
    """Get FFmpeg version and verify it's the correct one"""
    try:
        result = subprocess.run([get_ffmpeg_path(), '-version'], 
                              capture_output=True, 
                              text=True)
        version = result.stdout.split('\n')[0]
        logger.info(f"Using FFmpeg: {version}")
        return version
    except Exception as e:
        logger.error(f"Error checking FFmpeg version: {e}")
        return None

def create_video(image_files, output_path, fps=30, format='mp4'):
    try:
        # Reset progress at start
        update_progress(0, "Starting video creation")
        
        # Get dimensions
        first_image = Image.open(image_files[0])
        width, height = first_image.size
        first_image.close()
        
        temp_dir = os.path.dirname(output_path)
        frames_dir = os.path.join(temp_dir, 'frames')
        os.makedirs(frames_dir, exist_ok=True)
        
        # Process frames with progress updates
        total_frames = len(image_files)
        for i, image_path in enumerate(sorted(image_files)):
            # Update progress for frame processing (0-60%)
            progress = (i + 1) / total_frames * 60
            update_progress(progress, f"Processing frame {i + 1}/{total_frames}")
            
            with Image.open(image_path) as img:
                if img.mode != 'RGB':
                    img = img.convert('RGB')
                frame_path = os.path.join(frames_dir, f'frame_{i:06d}.png')
                img.save(frame_path, 'PNG', optimize=False)
        
        # Update progress for FFmpeg start
        update_progress(70, "Starting video encoding")
        
        # FFmpeg settings
        logger.info("=== FFmpeg Settings ===")
        input_path = os.path.join(frames_dir, 'frame_%06d.png')
        logger.info(f"Input pattern: {input_path}")
        stream = ffmpeg.input(input_path, framerate=fps)
        
        if format == 'mp4':
            logger.info("Creating MP4 with H.264...")
            stream = ffmpeg.output(stream, output_path,
                                vcodec='libx264',
                                pix_fmt='yuv420p',
                                preset='slow',
                                crf=18,
                                profile='high',
                                level='4.0',
                                movflags='+faststart',
                                **{
                                    'color_primaries': 'bt709',
                                    'color_trc': 'bt709',
                                    'colorspace': 'bt709',
                                    'x264-params': (
                                        'colorprim=bt709:'
                                        'transfer=bt709:'
                                        'colormatrix=bt709:'
                                        'force-cfr=1:'
                                        'keyint=48:'
                                        'min-keyint=48:'
                                        'no-scenecut=1'
                                    )
                                })
        else:  # MOV
            logger.info("Creating MOV with ProRes...")
            stream = ffmpeg.output(stream, output_path,
                                vcodec='prores_ks',
                                pix_fmt='yuv422p10le',
                                profile=3,
                                vendor='apl0',
                                qscale=1,
                                **{
                                    'color_primaries': 'bt709',
                                    'color_trc': 'bt709',
                                    'colorspace': 'bt709'
                                })
        
        # Log FFmpeg command
        cmd = ffmpeg.compile(stream)
        logger.info("FFmpeg command:")
        logger.info(' '.join(cmd))
        
        # Run FFmpeg with progress monitoring
        try:
            process = subprocess.Popen(
                ffmpeg.compile(stream),
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                universal_newlines=True
            )
            
            # Monitor FFmpeg progress
            while True:
                line = process.stderr.readline()
                if not line:
                    break
                # Update progress based on FFmpeg output (70-95%)
                if "frame=" in line:
                    try:
                        frame = int(line.split("frame=")[1].split()[0])
                        encode_progress = min(95, 70 + (frame / total_frames) * 25)
                        update_progress(encode_progress, "Encoding video")
                    except:
                        pass
            
            process.wait()
            if process.returncode != 0:
                raise Exception("FFmpeg encoding failed")
        
        except Exception as e:
            logger.error(f"FFmpeg error: {str(e)}")
            raise
        
        # Cleanup and finish
        update_progress(98, "Cleaning up")
        shutil.rmtree(frames_dir)
        
        update_progress(100, "Complete")
        return output_path
        
    except Exception as e:
        logger.error(f"Error in create_video: {str(e)}")
        update_progress(0, f"Error: {str(e)}")
        raise

@app.route('/')
def index():
    return render_template('index.html', version=APP_VERSION)

@app.route('/progress')
def get_progress():
    """Get current progress"""
    global conversion_progress
    with progress_lock:
        return jsonify({'progress': conversion_progress})

@app.route('/convert', methods=['POST'])
def convert():
    if 'files[]' not in request.files:
        return jsonify({'error': 'No files provided'}), 400
    
    files = request.files.getlist('files[]')
    format = request.form.get('format', 'mp4')
    
    if not files:
        return jsonify({'error': 'No files selected'}), 400
    
    if len(files) > 1000:
        return jsonify({'error': 'Maximum 1000 files allowed'}), 400
    
    # Create session-specific temp directory
    temp_dir = tempfile.mkdtemp(dir=app.config['TEMP_FOLDER'])
    logger.info(f"Created temp directory: {temp_dir}")
    
    try:
        update_progress(0, "Processing files")
        
        # Collect and sort files
        file_data = []
        for file in files:
            if file and allowed_file(file.filename):
                try:
                    # Extract number from filename
                    number = int(''.join(filter(str.isdigit, file.filename)))
                    file_data.append((number, file))
                except ValueError:
                    logger.warning(f"Could not extract number from filename: {file.filename}")
                    continue
        
        if not file_data:
            return jsonify({'error': 'No valid PNG files found'}), 400
        
        # Sort by frame number
        file_data.sort(key=lambda x: x[0])
        logger.info(f"Sorted {len(file_data)} files")
        
        # Save files in order
        image_files = []
        for i, (_, file) in enumerate(file_data):
            filename = f'frame_{i:06d}.png'
            filepath = os.path.join(temp_dir, filename)
            file.save(filepath)
            image_files.append(filepath)
            logger.info(f"Saved file {i+1}/{len(file_data)}: {filepath}")
        
        # Create output path
        output_filename = f'output.{format}'
        output_path = os.path.join(temp_dir, output_filename)
        logger.info(f"Output will be saved to: {output_path}")
        
        # Create video
        final_path = create_video(image_files, output_path, fps=30, format=format)
        
        return send_file(
            final_path,
            as_attachment=True,
            download_name=output_filename,
            mimetype=f'video/{format}'
        )
    
    except Exception as e:
        logger.error(f"Conversion error: {str(e)}")
        return jsonify({'error': str(e)}), 500
    
    finally:
        try:
            shutil.rmtree(temp_dir, ignore_errors=True)
            gc.collect()
        except Exception as e:
            logger.error(f"Cleanup error: {str(e)}")

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 8080))
    debug = os.environ.get('FLASK_ENV') == 'development'
    
    logger.info(f"=== Starting PNG to Video Converter ===")
    logger.info(f"Version: {APP_VERSION}")
    get_ffmpeg_version()  # Log FFmpeg version at startup
    logger.info("=======================================")
    
    logger.info(f"Environment: {'Development' if debug else 'Production'}")
    logger.info(f"Platform: {platform.system()} {platform.release()}")
    logger.info(f"Python: {platform.python_version()}")
    logger.info(f"Upload directory: {app.config['UPLOAD_FOLDER']}")
    logger.info(f"Temp directory: {app.config['TEMP_FOLDER']}")
    logger.info("=====================================")
    
    app.run(host='0.0.0.0', port=port, debug=debug) 