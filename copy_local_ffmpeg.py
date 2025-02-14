import os
import shutil
import platform
from pathlib import Path
import subprocess

def copy_local_ffmpeg():
    """Copy FFmpeg to vendor directory"""
    # Create vendor directory
    vendor_dir = Path('vendor/ffmpeg')
    if vendor_dir.exists():
        shutil.rmtree(vendor_dir)
    vendor_dir.mkdir(parents=True, exist_ok=True)
    
    # Source FFmpeg directory
    ffmpeg_dir = Path('FFmpeg-n7.1')
    
    if not ffmpeg_dir.exists():
        print(f"Could not find FFmpeg in {ffmpeg_dir}")
        return
    
    # Find and copy FFmpeg binaries
    print("Looking for FFmpeg binaries...")
    
    # Copy ffmpeg
    ffmpeg_binary = next(ffmpeg_dir.rglob('ffmpeg'), None)
    if ffmpeg_binary:
        print(f"Found ffmpeg at: {ffmpeg_binary}")
        shutil.copy2(ffmpeg_binary, vendor_dir / 'ffmpeg')
        (vendor_dir / 'ffmpeg').chmod(0o755)
        print("Copied ffmpeg")
    
    # Copy ffprobe
    ffprobe_binary = next(ffmpeg_dir.rglob('ffprobe'), None)
    if ffprobe_binary:
        print(f"Found ffprobe at: {ffprobe_binary}")
        shutil.copy2(ffprobe_binary, vendor_dir / 'ffprobe')
        (vendor_dir / 'ffprobe').chmod(0o755)
        print("Copied ffprobe")
    
    # Verify installation
    try:
        result = subprocess.run([str(vendor_dir / 'ffmpeg'), '-version'],
                              capture_output=True,
                              text=True)
        print("\nFFmpeg version info:")
        print(result.stdout.split('\n')[0])
        print("\nCopy complete! FFmpeg is ready to use.")
    except Exception as e:
        print(f"Warning: Could not verify FFmpeg installation: {e}")

if __name__ == '__main__':
    copy_local_ffmpeg() 