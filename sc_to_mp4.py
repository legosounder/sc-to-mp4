import sys
import os
import subprocess
import json
import glob
import datetime
import argparse

def process_track(url, output_dir="downloads", custom_img=None, mp3_only=False):
    print(f"\n--- Processing track: {url} ---")
    try:
        # Get JSON dump from yt-dlp to find the artist and title for the individual track
        result = subprocess.run(
            ['yt-dlp', '-J', url],
            capture_output=True, text=True, check=True
        )
        info = json.loads(result.stdout)
    except subprocess.CalledProcessError as e:
        print(f"Error fetching metadata for track {url}: {e.stderr}")
        return
        
    # Prefer 'artist', fall back to 'uploader'
    artist_raw = info.get('artist') or info.get('uploader', 'Unknown Artist')
    artist_raw = artist_raw.replace('，', ',').strip()
    title_raw = info.get('title', 'Unknown Title').strip()
    
    # Create a safe base filename removing problematic characters
    safe_artist = "".join(c for c in artist_raw if c.isalnum() or c in (" ", "-", "_", "&", "'", ",")).strip()
    safe_title = "".join(c for c in title_raw if c.isalnum() or c in (" ", "-", "_", "&", "'", ",")).strip()
    
    base_name = f"{safe_artist} - {safe_title}"
    print(f"Song identified as: {base_name}")
    
    # Ensure output directory exists
    os.makedirs(output_dir, exist_ok=True)
    base_path = os.path.join(output_dir, base_name)
    audio_path = f"{base_path}.mp3"
    
    # MP3 only mode
    if mp3_only:
        print("Downloading MP3 audio and embedding artwork/metadata...")
        ytdlp_cmd = [
            'yt-dlp',
            '-x', '--audio-format', 'mp3',
            '--audio-quality', '0',
            '-o', f'{base_path}.%(ext)s',
        ]
        if not custom_img:
            ytdlp_cmd.extend(['--embed-thumbnail', '--embed-metadata'])
        ytdlp_cmd.append(url)
        
        try:
            subprocess.run(ytdlp_cmd, check=True)
        except subprocess.CalledProcessError:
            print("Error downloading the track.")
            return

        # If a custom image was supplied, embed it using ffmpeg
        if custom_img and os.path.exists(audio_path):
            temp_mp3 = f"{base_path}_temp.mp3"
            os.rename(audio_path, temp_mp3)
            ffmpeg_cmd = [
                'ffmpeg', '-y',
                '-i', temp_mp3,
                '-i', custom_img,
                '-map', '0:a', '-map', '1:0',
                '-c', 'copy',
                '-id3v2_version', '3',
                '-metadata:s:v', 'title=Album cover',
                '-metadata:s:v', 'comment=Cover (front)',
                audio_path
            ]
            try:
                subprocess.run(ffmpeg_cmd, check=True, capture_output=True)
                if os.path.exists(temp_mp3):
                    os.remove(temp_mp3)
            except subprocess.CalledProcessError:
                if os.path.exists(temp_mp3):
                    os.rename(temp_mp3, audio_path)

        if os.path.exists(audio_path):
            print(f"✅ Success! Saved MP3 to: {audio_path}")
        else:
            print(f"Error: Expected MP3 file not found at {audio_path}")
        return

    # MP4 video mode
    print("Downloading audio...")
    ytdlp_cmd = [
        'yt-dlp', 
        '-x', '--audio-format', 'mp3', 
        '-o', f'{base_path}.%(ext)s', 
        url
    ]
    if not custom_img:
        print("Downloading album art...")
        ytdlp_cmd.insert(4, '--write-thumbnail')
        
    try:
        subprocess.run(ytdlp_cmd, check=True)
    except subprocess.CalledProcessError:
        print("Error downloading the track.")
        return
        
    thumb_path = custom_img
    if not thumb_path:
        for ext in ['jpg', 'webp', 'png', 'jpeg']:
            candidate = f"{base_path}.{ext}"
            if os.path.exists(candidate):
                thumb_path = candidate
                break
            
    if not os.path.exists(audio_path):
        print(f"Error: Could not find the downloaded audio block ({audio_path}).")
        return
        
    if not thumb_path:
        print(f"Error: Could not find the downloaded thumbnail for {base_name}.")
        print("The script needs an image to create the video.")
        return
        
    out_path = f"{base_path}.mp4"
    print(f"Creating MP4: {out_path}")
    
    duration = None
    try:
        # Determine exact duration using ffprobe
        duration_cmd = [
            'ffprobe', '-v', 'error', 
            '-show_entries', 'format=duration', 
            '-of', 'default=noprint_wrappers=1:nokey=1', 
            audio_path
        ]
        duration_out = subprocess.run(duration_cmd, capture_output=True, text=True, check=True).stdout.strip()
        duration = float(duration_out)
    except Exception as e:
        print(f"Warning: could not get duration from ffprobe ({e}). Falling back to -shortest.")
        
    ffmpeg_cmd = [
        'ffmpeg', '-y', 
        '-loop', '1', 
        '-i', thumb_path,
        '-i', audio_path,
        '-vf', 'scale=-2:1080,pad=1920:1080:(ow-iw)/2:(oh-ih)/2,format=yuv420p',
        '-c:v', 'libx264', '-preset', 'medium', '-tune', 'stillimage',
        '-c:a', 'aac', '-b:a', '320k'
    ]
    
    if duration is not None:
        # Add 0.5s buffer, pad audio with silence, and stop exactly at the target duration
        ffmpeg_cmd.extend(['-af', 'apad', '-t', str(duration + 0.5)])
    else:
        ffmpeg_cmd.append('-shortest')
        
    ffmpeg_cmd.append(out_path)
    
    try:
        subprocess.run(ffmpeg_cmd, check=True, capture_output=True)
    except subprocess.CalledProcessError as e:
        print("Error running ffmpeg to create the MP4.")
        print(e.stderr.decode('utf-8', errors='replace'))
        return
        
    print("Cleaning up temporary files...")
    try:
        os.remove(audio_path)
        if not custom_img and thumb_path and os.path.exists(thumb_path):
            os.remove(thumb_path)
    except OSError as e:
        print(f"Warning: could not remove temp file: {e}")
        
    print(f"✅ Success! Saved to: {out_path}")


def main():
    parser = argparse.ArgumentParser(description="Convert SoundCloud URLs to MP4 videos or MP3 audio")
    parser.add_argument("url", nargs="?", help="SoundCloud track or playlist URL")
    parser.add_argument("--img", help="Path to a custom image to use instead of the SoundCloud thumbnail")
    parser.add_argument("--mp3", action="store_true", help="Download as MP3 audio only (skip MP4 video creation)")
    parser.add_argument("-o", "--output", default="downloads", help="Directory where downloads will be saved (default: 'downloads')")
    args = parser.parse_args()
    
    url = args.url
    interactive = False
    if not url:
        interactive = True
        url = input("Please enter the SoundCloud track or playlist URL: ").strip()
        if not url:
            print("No URL provided. Exiting.")
            sys.exit(1)
            
    if interactive and not args.mp3:
        mode_choice = input("Select format [1: MP4 Video (default), 2: MP3 Audio only]: ").strip()
        if mode_choice == "2":
            args.mp3 = True
            
    if args.img and not os.path.exists(args.img):
        print(f"Error: Custom image file not found at '{args.img}'.")
        sys.exit(1)
    
    output_base = args.output
    os.makedirs(output_base, exist_ok=True)
    
    print("Fetching URL metadata...")
    try:
        result = subprocess.run(
            ['yt-dlp', '-J', '--flat-playlist', url],
            capture_output=True, text=True, check=True
        )
        info = json.loads(result.stdout)
    except subprocess.CalledProcessError as e:
        print(f"Error fetching metadata: {e.stderr}")
        sys.exit(1)
        
    if info.get('_type') == 'playlist':
        playlist_title = info.get('title', 'playlist').strip()
        safe_title = "".join(c for c in playlist_title if c.isalnum() or c in (" ", "-", "_", "&", "'")).strip()
        date_str = datetime.datetime.now().strftime("%Y-%m-%d")
        folder_name = os.path.join(output_base, f"{safe_title} {date_str}")
        
        print(f"Playlist detected: '{playlist_title}'. Output folder: {folder_name}")
        os.makedirs(folder_name, exist_ok=True)
        
        entries = info.get('entries', [])
        print(f"Found {len(entries)} tracks in playlist.")
        for i, entry in enumerate(entries, 1):
            entry_url = entry.get('url')
            if entry_url:
                print(f"\n[{i}/{len(entries)}]", end="")
                process_track(entry_url, folder_name, custom_img=args.img, mp3_only=args.mp3)
            else:
                print(f"\n[{i}/{len(entries)}] Skipping entry with no URL.")
                
        format_type = "MP3 files" if args.mp3 else "MP4 files"
        print(f"\n🎉 Finished processing playlist! All {format_type} saved in '{folder_name}'")
    else:
        # Single track
        date_str = datetime.datetime.now().strftime("%Y-%m-%d")
        folder_name = os.path.join(output_base, date_str)
        os.makedirs(folder_name, exist_ok=True)
        print(f"Single track detected. Output folder: '{folder_name}'")
        process_track(url, folder_name, custom_img=args.img, mp3_only=args.mp3)


if __name__ == "__main__":
    main()
