FROM python:3.10-slim

# Set working directory
WORKDIR /app

# Install build dependencies
RUN apt-get update && apt-get install -y \
    software-properties-common \
    && apt-get update \
    && apt-get install -y \
    wget build-essential yasm cmake nasm \
    pkg-config libtool autoconf automake \
    libx264-dev libx265-dev libvpx-dev \
    libmp3lame-dev libopus-dev libass-dev libfreetype6-dev libvorbis-dev \
    && rm -rf /var/lib/apt/lists/*

# Download and build FFmpeg 7.1
WORKDIR /tmp
RUN wget https://github.com/FFmpeg/FFmpeg/archive/refs/tags/n7.1.tar.gz \
    && tar -xvzf n7.1.tar.gz \
    && cd FFmpeg-n7.1 \
    && ./configure \
        --prefix=/usr/local \
        --enable-gpl \
        --enable-libx264 \
        --enable-libx265 \
        --enable-libvpx \
        --enable-libmp3lame \
        --enable-libopus \
        --enable-libass \
        --enable-libvorbis \
    && make -j$(nproc) \
    && make install \
    && cd .. \
    && rm -rf FFmpeg-n7.1 n7.1.tar.gz

# Verify FFmpeg installation
RUN ffmpeg -version

# Set working directory back to app
WORKDIR /app

# Copy requirements and install
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application files
COPY . .

# Set environment variables
ENV PORT=8080

# Run the application
CMD ["python", "app.py"]
