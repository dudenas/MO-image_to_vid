#!/usr/bin/env bash
# exit on error
set -o errexit

# Create directory for FFmpeg
mkdir -p vendor/ffmpeg

# Download and extract static FFmpeg build
wget https://johnvansickle.com/ffmpeg/builds/ffmpeg-git-amd64-static.tar.xz
tar xf ffmpeg-git-amd64-static.tar.xz
mv ffmpeg-git-*-amd64-static/ffmpeg vendor/ffmpeg/
rm -rf ffmpeg-git-*-amd64-static*

# Install Python dependencies
pip install -r requirements.txt 