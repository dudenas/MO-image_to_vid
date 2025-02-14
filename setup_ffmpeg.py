import os
import shutil
import platform
import subprocess
from pathlib import Path
import urllib.request
import tarfile

def setup_ffmpeg():
    """Download and set up FFmpeg for both local and cloud environments"""
    # Create vendor directory
    vendor_dir = Path('vendor/ffmpeg')
    if vendor_dir.exists():
        shutil.rmtree(vendor_dir)
    vendor_dir.mkdir(parents=True, exist_ok=True)
    
    # Download FFmpeg
    print("Downloading FFmpeg...")
    url = "https://johnvansickle.com/ffmpeg/releases/ffmpeg-release-amd64-static.tar.xz"
    archive_path = vendor_dir / "ffmpeg.tar.xz"
    
    urllib.request.urlretrieve(url, archive_path)
    
    # Extract
    print("Extracting FFmpeg...")
    with tarfile.open(archive_path) as tar:
        for member in tar.getmembers():
            if member.name.endswith(('ffmpeg', 'ffprobe')):
                member.name = os.path.basename(member.name)
                tar.extract(member, vendor_dir)
    
    # Make executables
    for binary in ('ffmpeg', 'ffprobe'):
        binary_path = vendor_dir / binary
        if binary_path.exists():
            binary_path.chmod(0o755)
            print(f"Made {binary} executable")
    
    # Clean up
    archive_path.unlink()
    
    # Create symlinks in /usr/local/bin (requires sudo)
    try:
        print("\nCreating system-wide symlinks (requires sudo)...")
        for binary in ('ffmpeg', 'ffprobe'):
            src = vendor_dir / binary
            dst = Path('/usr/local/bin') / binary
            if dst.exists():
                print(f"Removing existing {binary}...")
                subprocess.run(['sudo', 'rm', str(dst)], check=True)
            print(f"Creating symlink for {binary}...")
            subprocess.run(['sudo', 'ln', '-s', str(src.absolute()), str(dst)], check=True)
    except Exception as e:
        print(f"Could not create symlinks: {e}")
        print("You'll need to add vendor/ffmpeg to your PATH manually")
    
    # Verify installation
    try:
        result = subprocess.run(['ffmpeg', '-version'], 
                              capture_output=True, 
                              text=True)
        print("\nFFmpeg version info:")
        print(result.stdout.split('\n')[0])
        print("\nSetup complete! FFmpeg is ready to use.")
    except Exception as e:
        print(f"Warning: Could not verify FFmpeg installation: {e}")

if __name__ == '__main__':
    setup_ffmpeg() 