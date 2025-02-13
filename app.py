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
app.config['UPLOAD_FOLDER'] = os.path.join(tempfile.gettempdir(), 'uploads')
app.config['TEMP_FOLDER'] = os.path.join(tempfile.gettempdir(), 'temp')

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
        first_image.close()  # Close image after getting dimensions
        
        temp_dir = os.path.dirname(output_path)
        frames_dir = os.path.join(temp_dir, 'frames')
        os.makedirs(frames_dir, exist_ok=True)
        
        # Process images in smaller batches
        batch_size = 10
        for i in range(0, len(image_files), batch_size):
            batch = image_files[i:i + batch_size]
            for j, image_path in enumerate(batch):
                frame_index = i + j
                logger.info(f"Processing frame {frame_index + 1}/{len(image_files)}")
                
                with Image.open(image_path) as img:
                    if img.mode != 'RGB':
                        img = img.convert('RGB')
                    frame_path = os.path.join(frames_dir, f'frame_{frame_index:06d}.png')
                    img.save(frame_path, 'PNG', optimize=False)
                
                gc.collect()  # Force garbage collection after each frame
        
        logger.info("Starting FFmpeg encoding")
        
        # FFmpeg encoding with reduced quality for free tier
        stream = ffmpeg.input(os.path.join(frames_dir, 'frame_%06d.png'), framerate=fps)
        
        if format == 'mp4':
            stream = ffmpeg.output(stream, output_path,
                                vcodec='libx264',
                                pix_fmt='yuv420p',
                                preset='ultrafast',  # Faster encoding
                                crf=23,  # Reduced quality
                                movflags='+faststart')
        else:  # mov
            stream = ffmpeg.output(stream, output_path,
                                vcodec='prores_ks',
                                pix_fmt='yuv422p',  # Reduced from yuv422p10le
                                profile=0,  # Proxy profile for smaller size
                                qscale=11)  # Reduced quality
        
        ffmpeg.run(stream, overwrite_output=True, capture_stdout=True, capture_stderr=True)
        
        logger.info("Video creation completed")
        
        # Cleanup
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
    total_files = int(request.form.get('total_files', 0))
    chunk_start = int(request.form.get('chunk_start', 0))
    
    if not files:
        return jsonify({'error': 'No files selected'}), 400
    
    # Create temporary directory for this conversion
    temp_dir = tempfile.mkdtemp(dir=app.config['TEMP_FOLDER'])
    image_files = []
    
    try:
        # Save uploaded files
        for file in files:
            if file and allowed_file(file.filename):
                filename = secure_filename(file.filename)
                filepath = os.path.join(temp_dir, filename)
                file.save(filepath)
                image_files.append(filepath)
        
        if not image_files:
            return jsonify({'error': 'No valid PNG files uploaded'}), 400
        
        # Sort files to ensure proper sequence
        image_files.sort()
        
        # If this is not the last chunk, return success without video
        if chunk_start + len(files) < total_files:
            return jsonify({'status': 'chunk_uploaded'}), 200
        
        # Get all files from temp directory for final processing
        all_files = []
        for root, _, filenames in os.walk(temp_dir):
            for filename in filenames:
                if filename.lower().endswith('.png'):
                    all_files.append(os.path.join(root, filename))
        
        # Sort all files to ensure proper sequence
        all_files.sort()
        
        # Create output filename and path
        output_filename = f'output.{format}'
        output_path = os.path.join(temp_dir, output_filename)
        
        # Convert images to video with fixed 30 FPS
        final_path = create_video(all_files, output_path, fps=30, format=format)
        
        # Verify the file exists and has size
        if not os.path.exists(final_path) or os.path.getsize(final_path) == 0:
            return jsonify({'error': 'Video creation failed'}), 500
        
        # Send the file to user
        return send_file(
            final_path,
            as_attachment=True,
            download_name=output_filename,
            mimetype=f'video/{format}'
        )
    
    except Exception as e:
        return jsonify({'error': str(e)}), 500
    
    finally:
        # Cleanup temporary directory
        shutil.rmtree(temp_dir, ignore_errors=True)

if __name__ == '__main__':
    # Use environment variables for configuration
    port = int(os.environ.get('PORT', 8080))
    debug = os.environ.get('FLASK_ENV') == 'development'
    
    app.run(host='0.0.0.0', port=port, debug=debug) 