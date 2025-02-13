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

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Add FFmpeg to PATH
vendor_ffmpeg = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'vendor/ffmpeg')
os.environ['PATH'] = f"{vendor_ffmpeg}:{os.environ['PATH']}"

app = Flask(__name__)
CORS(app)  # Enable CORS for all routes
app.config['MAX_CONTENT_LENGTH'] = 256 * 1024 * 1024  # Reduce to 256MB max file size
app.config['UPLOAD_FOLDER'] = '/tmp/uploads'
app.config['TEMP_FOLDER'] = '/tmp/temp'

# Ensure upload and temp directories exist
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
os.makedirs(app.config['TEMP_FOLDER'], exist_ok=True)

ALLOWED_EXTENSIONS = {'png'}

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def cleanup_temp_files():
    """Clean up temporary files and force garbage collection"""
    try:
        shutil.rmtree(app.config['UPLOAD_FOLDER'], ignore_errors=True)
        shutil.rmtree(app.config['TEMP_FOLDER'], ignore_errors=True)
        os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
        os.makedirs(app.config['TEMP_FOLDER'], exist_ok=True)
        gc.collect()  # Force garbage collection
    except Exception as e:
        logger.error(f"Error during cleanup: {str(e)}")

@app.before_request
def before_request():
    """Clean up before each request"""
    cleanup_temp_files()

def create_video(image_files, output_path, fps=30, format='mp4'):
    try:
        logger.info(f"Starting video creation with {len(image_files)} files")
        
        # Get the first image to determine dimensions
        first_image = Image.open(image_files[0])
        width, height = first_image.size
        first_image.close()
        
        # Reduce image dimensions if too large
        max_dimension = 1280  # Limit maximum dimension
        if width > max_dimension or height > max_dimension:
            scale = max_dimension / max(width, height)
            width = int(width * scale)
            height = int(height * scale)
            logger.info(f"Resizing images to {width}x{height}")
        
        temp_dir = os.path.dirname(output_path)
        frames_dir = os.path.join(temp_dir, 'frames')
        os.makedirs(frames_dir, exist_ok=True)
        
        # Process images in very small batches
        batch_size = 5  # Reduced batch size
        for i in range(0, len(image_files), batch_size):
            batch = image_files[i:i + batch_size]
            for j, image_path in enumerate(batch):
                frame_index = i + j
                logger.info(f"Processing frame {frame_index + 1}/{len(image_files)}")
                
                with Image.open(image_path) as img:
                    # Resize if needed
                    if img.size != (width, height):
                        img = img.resize((width, height), Image.Resampling.LANCZOS)
                    if img.mode != 'RGB':
                        img = img.convert('RGB')
                    frame_path = os.path.join(frames_dir, f'frame_{frame_index:06d}.png')
                    img.save(frame_path, 'PNG', optimize=True, quality=85)
                
                # Clean up memory
                gc.collect()
        
        logger.info("Starting FFmpeg encoding")
        
        # FFmpeg encoding with more aggressive compression
        stream = ffmpeg.input(os.path.join(frames_dir, 'frame_%06d.png'), framerate=fps)
        
        if format == 'mp4':
            stream = ffmpeg.output(stream, output_path,
                                vcodec='libx264',
                                pix_fmt='yuv420p',
                                preset='veryfast',  # Even faster encoding
                                crf=28,  # More compression
                                movflags='+faststart')
        else:  # mov
            stream = ffmpeg.output(stream, output_path,
                                vcodec='prores_ks',
                                pix_fmt='yuv420p',  # Less color data
                                profile=0,  # Proxy profile
                                qscale=15)  # More compression
        
        ffmpeg.run(stream, overwrite_output=True, capture_stdout=True, capture_stderr=True)
        
        logger.info("Video creation completed")
        shutil.rmtree(frames_dir, ignore_errors=True)
        gc.collect()
        
        return output_path
        
    except Exception as e:
        logger.error(f"Error in create_video: {str(e)}")
        raise

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/convert', methods=['POST'])
def convert():
    if 'files[]' not in request.files:
        return jsonify({'error': 'No files provided'}), 400
    
    files = request.files.getlist('files[]')
    format = request.form.get('format', 'mp4')
    
    if not files:
        return jsonify({'error': 'No files selected'}), 400
    
    # Limit number of files
    max_files = 100  # Set a reasonable limit
    if len(files) > max_files:
        return jsonify({'error': f'Too many files. Maximum allowed is {max_files}'}), 400
    
    # Create temporary directory
    temp_dir = tempfile.mkdtemp(dir=app.config['TEMP_FOLDER'])
    image_files = []
    
    try:
        total_size = 0
        for file in files:
            if file and allowed_file(file.filename):
                # Check individual file size
                file.seek(0, os.SEEK_END)
                size = file.tell()
                file.seek(0)
                total_size += size
                
                if total_size > app.config['MAX_CONTENT_LENGTH']:
                    return jsonify({'error': 'Total file size too large'}), 400
                
                filename = secure_filename(file.filename)
                filepath = os.path.join(temp_dir, filename)
                file.save(filepath)
                image_files.append(filepath)
        
        if not image_files:
            return jsonify({'error': 'No valid PNG files uploaded'}), 400
        
        # Sort files
        image_files.sort()
        
        # Create output path
        output_filename = f'output.{format}'
        output_path = os.path.join(temp_dir, output_filename)
        
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
        # Cleanup
        shutil.rmtree(temp_dir, ignore_errors=True)
        gc.collect()

if __name__ == '__main__':
    # Use environment variables for configuration
    port = int(os.environ.get('PORT', 8080))
    debug = os.environ.get('FLASK_ENV') == 'development'
    
    app.run(host='0.0.0.0', port=port, debug=debug) 