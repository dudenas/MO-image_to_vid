FROM python:3.10-slim

# Set working directory
WORKDIR /app

# Install wget and other dependencies
RUN apt-get update && apt-get install -y \
    wget \
    xz-utils \
    && rm -rf /var/lib/apt/lists/*

# Download and install latest FFmpeg
RUN wget https://johnvansickle.com/ffmpeg/releases/ffmpeg-release-amd64-static.tar.xz \
    && tar -xf ffmpeg-release-amd64-static.tar.xz \
    && mv ffmpeg-*-amd64-static/ffmpeg /usr/local/bin/ \
    && mv ffmpeg-*-amd64-static/ffprobe /usr/local/bin/ \
    && chmod +x /usr/local/bin/ffmpeg /usr/local/bin/ffprobe \
    && rm -rf ffmpeg-*-amd64-static.tar.xz ffmpeg-*-amd64-static

# Copy requirements and install
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application files
COPY . .

# Set environment variables
ENV PORT=8080

# Run the application
CMD ["python", "app.py"]
