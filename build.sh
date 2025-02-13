#!/usr/bin/env bash
# exit on error
set -o errexit

# Create directory for FFmpeg
mkdir -p vendor/ffmpeg

# Download and extract static FFmpeg build with retry
max_attempts=3
attempt=1
while [ $attempt -le $max_attempts ]; do
    if wget https://johnvansickle.com/ffmpeg/builds/ffmpeg-git-amd64-static.tar.xz; then
        break
    fi
    attempt=$((attempt + 1))
    echo "Download failed, retrying... (attempt $attempt of $max_attempts)"
    sleep 5
done

if [ $attempt -gt $max_attempts ]; then
    echo "Failed to download FFmpeg after $max_attempts attempts"
    exit 1
fi

tar xf ffmpeg-git-amd64-static.tar.xz
mv ffmpeg-git-*-amd64-static/ffmpeg vendor/ffmpeg/
chmod +x vendor/ffmpeg/ffmpeg
rm -rf ffmpeg-git-*-amd64-static*

# Install Python dependencies
pip install -r requirements.txt 