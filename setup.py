import os
import sys
import shutil
import urllib.request
import zipfile
import tarfile
import platform
from pathlib import Path
import subprocess

FFMPEG_URLS = {
    'darwin': 'https://www.osxexperts.net/ffmpeg/ffmpeg-latest-macos-arm64.zip',  # ARM Mac
    'darwin_intel': 'https://www.osxexperts.net/ffmpeg/ffmpeg-latest-macos-x86_64.zip',  # Intel Mac
    'win32': 'https://github.com/BtbN/FFmpeg-Builds/releases/download/latest/ffmpeg-master-latest-win64-gpl.zip',
    'linux': 'https://johnvansickle.com/ffmpeg/releases/ffmpeg-release-amd64-static.tar.xz'
}

def is_arm_mac():
    """Check if running on ARM Mac"""
    try:
        return platform.system() == 'Darwin' and platform.machine() == 'arm64'
    except:
        return False

def download_ffmpeg():
    """Download FFmpeg for the current platform"""
    vendor_dir = Path('vendor/ffmpeg')
    # Remove old directory if exists
    if vendor_dir.exists():
        shutil.rmtree(vendor_dir)
    # Create fresh directory
    vendor_dir.mkdir(parents=True, exist_ok=True)
    
    system = platform.system().lower()
    if system not in ['darwin', 'win32', 'linux']:
        print(f"Unsupported platform: {system}")
        return
    
    if system == 'darwin':
        # Select correct Mac URL based on architecture
        url = FFMPEG_URLS['darwin'] if is_arm_mac() else FFMPEG_URLS['darwin_intel']
        archive_path = vendor_dir / 'ffmpeg.zip'
        
        print(f"Downloading FFmpeg for Mac ({platform.machine()})...")
        try:
            # Try using curl (more reliable on Mac)
            subprocess.run(['curl', '-L', url, '-o', str(archive_path)], check=True)
        except:
            # Fallback to urllib
            urllib.request.urlretrieve(url, archive_path)
        
        print("Extracting FFmpeg...")
        with zipfile.ZipFile(archive_path, 'r') as zip_ref:
            zip_ref.extractall(vendor_dir)
        
        # Make executables
        for binary in ('ffmpeg', 'ffprobe'):
            binary_path = vendor_dir / binary
            if binary_path.exists():
                binary_path.chmod(0o755)
                print(f"Made {binary} executable")
        
        archive_path.unlink()
        
    elif system == 'win32':
        url = FFMPEG_URLS[system]
        archive_path = vendor_dir / 'ffmpeg.zip'
        
        print(f"Downloading FFmpeg for Windows...")
        urllib.request.urlretrieve(url, archive_path)
        
        print("Extracting FFmpeg...")
        with zipfile.ZipFile(archive_path, 'r') as zip_ref:
            for file in zip_ref.namelist():
                if file.endswith(('ffmpeg.exe', 'ffprobe.exe')):
                    with zip_ref.open(file) as source, \
                         open(vendor_dir / os.path.basename(file), 'wb') as target:
                        shutil.copyfileobj(source, target)
        
        archive_path.unlink()
        
    else:  # linux
        url = FFMPEG_URLS[system]
        archive_path = vendor_dir / 'ffmpeg.tar.xz'
        
        print(f"Downloading FFmpeg for Linux...")
        urllib.request.urlretrieve(url, archive_path)
        
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
        
        archive_path.unlink()
    
    print("FFmpeg setup complete!")
    
    # Verify installation
    try:
        ffmpeg_path = vendor_dir / ('ffmpeg.exe' if system == 'win32' else 'ffmpeg')
        result = subprocess.run([str(ffmpeg_path), '-version'], 
                              capture_output=True, 
                              text=True)
        print("\nFFmpeg version info:")
        print(result.stdout.split('\n')[0])
    except Exception as e:
        print(f"Warning: Could not verify FFmpeg installation: {e}")

if __name__ == '__main__':
    download_ffmpeg() 