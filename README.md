# PNG Sequence to Video Converter

A web-based application that converts PNG image sequences to MP4 or MOV (ProRes) video formats with high color accuracy.

## Features

- Drag and drop interface for uploading PNG sequences
- Support for MP4 and MOV (ProRes) output formats
- Adjustable FPS settings
- Real-time file preview
- Color-accurate conversion
- Modern and responsive UI

## Requirements

- Python 3.8+
- FFmpeg installed on your system
- OpenCV
- Flask

## Installation

1. First, make sure you have FFmpeg installed on your system:

   - **macOS** (using Homebrew):
     ```bash
     brew install ffmpeg
     ```
   - **Linux**:
     ```bash
     sudo apt-get update
     sudo apt-get install ffmpeg
     ```

2. Clone this repository:
   ```bash
   git clone <repository-url>
   cd <repository-directory>
   ```

3. Create a virtual environment (optional but recommended):
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

4. Install the required Python packages:
   ```bash
   pip install -r requirements.txt
   ```

## Usage

1. Start the Flask application:
   ```bash
   python app.py
   ```

2. Open your web browser and navigate to:
   ```
   http://localhost:5000
   ```

3. Use the web interface to:
   - Drag and drop PNG files or click "Browse Files" to select them
   - Choose the desired output format (MP4 or MOV)
   - Set the desired FPS (frames per second)
   - Click "Convert to Video" to process the files

4. The converted video will automatically download once processing is complete

## Notes

- The PNG files should be named in sequential order for proper frame ordering
- For MOV output, the application uses ProRes codec for high-quality output
- The maximum file size limit is set to 16MB per file
- The application maintains color accuracy by using PIL for image reading and proper color space conversion

## Error Handling

The application includes error handling for:
- Invalid file types
- Missing files
- Conversion failures
- Server errors

## License

MIT License 