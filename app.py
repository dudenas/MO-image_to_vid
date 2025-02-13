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

# Add FFmpeg to PATH
vendor_ffmpeg = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'vendor/ffmpeg')
os.environ['PATH'] = f"{vendor_ffmpeg}:{os.environ['PATH']}"

app = Flask(__name__)
CORS(app)  # Enable CORS for all routes
app.config['MAX_CONTENT_LENGTH'] = 512 * 1024 * 1024  # 512MB max file size
app.config['UPLOAD_FOLDER'] = os.path.join(tempfile.gettempdir(), 'uploads')
app.config['TEMP_FOLDER'] = os.path.join(tempfile.gettempdir(), 'temp')

# Ensure upload and temp directories exist
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
os.makedirs(app.config['TEMP_FOLDER'], exist_ok=True)

ALLOWED_EXTENSIONS = {'png'}

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def create_video(image_files, output_path, fps=30, format='mp4'):
    # Get the first image to determine dimensions
    first_image = Image.open(image_files[0])
    width, height = first_image.size
    
    if format == 'mp4':
        # For MP4, we'll use FFmpeg directly for better compatibility
        temp_dir = os.path.dirname(output_path)
        frames_dir = os.path.join(temp_dir, 'frames')
        os.makedirs(frames_dir, exist_ok=True)
        
        # Save frames with proper naming for FFmpeg
        for i, image_path in enumerate(sorted(image_files)):
            img = Image.open(image_path)
            # Convert to RGB if not already
            if img.mode != 'RGB':
                img = img.convert('RGB')
            # Save as PNG with maximum quality
            frame_path = os.path.join(frames_dir, f'frame_{i:06d}.png')
            img.save(frame_path, 'PNG', optimize=False)
        
        # Use FFmpeg to create MP4 with H.264 codec and proper color handling
        stream = ffmpeg.input(os.path.join(frames_dir, 'frame_%06d.png'), 
                            framerate=fps)
        
        # Instagram-compatible settings with good color reproduction
        stream = ffmpeg.output(stream, output_path,
                             vcodec='libx264',
                             pix_fmt='yuv420p',  # Required for maximum compatibility
                             preset='slow',      # Better quality
                             crf=18,            # High quality (17-18 is visually lossless)
                             profile='high',    # High profile for better quality
                             level='4.0',       # Compatible level
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
        
        ffmpeg.run(stream, overwrite_output=True, capture_stdout=True, capture_stderr=True)
        
        # Cleanup frame directory
        shutil.rmtree(frames_dir)
        
    else:  # MOV
        # For MOV/ProRes, we'll use FFmpeg directly
        temp_dir = os.path.dirname(output_path)
        frames_dir = os.path.join(temp_dir, 'frames')
        os.makedirs(frames_dir, exist_ok=True)
        
        # Save frames with proper naming for FFmpeg
        for i, image_path in enumerate(sorted(image_files)):
            img = Image.open(image_path)
            # Convert to RGB if not already
            if img.mode != 'RGB':
                img = img.convert('RGB')
            # Save as PNG with maximum quality
            frame_path = os.path.join(frames_dir, f'frame_{i:06d}.png')
            img.save(frame_path, 'PNG', optimize=False)
        
        # Use FFmpeg to create ProRes MOV with proper color handling
        stream = ffmpeg.input(os.path.join(frames_dir, 'frame_%06d.png'),
                            framerate=fps)
        stream = ffmpeg.output(stream, output_path,
                             vcodec='prores_ks',
                             pix_fmt='yuv422p10le',  # 10-bit color depth
                             profile=3,              # High quality profile
                             vendor='apl0',          # Apple ProRes
                             qscale=1,              # Highest quality
                             **{
                                 'color_primaries': 'bt709',
                                 'color_trc': 'bt709',
                                 'colorspace': 'bt709'
                             })
        
        ffmpeg.run(stream, overwrite_output=True, capture_stdout=True, capture_stderr=True)
        
        # Cleanup frame directory
        shutil.rmtree(frames_dir)
    
    return output_path

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