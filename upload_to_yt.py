import os
import sys
import glob

import google_auth_oauthlib.flow
import googleapiclient.discovery
import googleapiclient.errors
from googleapiclient.http import MediaFileUpload

# Scopes needed for uploading videos
SCOPES = ["https://www.googleapis.com/auth/youtube.upload"]
CLIENT_SECRETS_FILE = "client_secrets.json"

def get_authenticated_service():
    """Authenticates with YouTube using client_secrets.json."""
    if not os.path.exists(CLIENT_SECRETS_FILE):
        print(f"Error: Could not find '{CLIENT_SECRETS_FILE}' in the current directory.")
        print("Please follow the setup instructions to download your OAuth 2.0 Client credentials.")
        sys.exit(1)

    print("Authenticating with YouTube...")
    try:
        # This will open a browser window for the user to login and approve the app
        flow = google_auth_oauthlib.flow.InstalledAppFlow.from_client_secrets_file(
            CLIENT_SECRETS_FILE, SCOPES)
        credentials = flow.run_local_server(port=0)
    except Exception as e:
        print(f"Authentication failed: {e}")
        sys.exit(1)
        
    return googleapiclient.discovery.build("youtube", "v3", credentials=credentials)

def upload_video(youtube, file_path):
    """Uploads a single MP4 to YouTube."""
    if not os.path.exists(file_path):
        print(f"Error: File not found: {file_path}")
        return False

    # Try to extract a clean title from the filename
    # E.g. "Artist - Song Title.mp4" -> "Artist - Song Title"
    filename = os.path.basename(file_path)
    title = os.path.splitext(filename)[0]
    
    print(f"\nUploading '{filename}'...")
    print(f"Parsed YouTube Title: {title}")

    # Set up the video's metadata
    # We will set it to 'private' by default so it doesn't accidentally publish to the world
    # before you are ready. You can change this to 'public' if you want.
    request_body = {
        "snippet": {
            "categoryId": "10", # Category 10 is Music
            "title": title,
            "description": f"Uploaded automatically via script.\n\nTrack: {title}"
        },
        "status": {
            "privacyStatus": "private" 
        }
    }

    # Set up the media file
    mediaFile = MediaFileUpload(file_path, chunksize=-1, resumable=True)

    # API Request
    try:
        request = youtube.videos().insert(
            part="snippet,status",
            body=request_body,
            media_body=mediaFile
        )
        
        # Execute the upload
        response = request.execute()
        print(f"✅ Upload Successful! Video ID: {response['id']}")
        print(f"Link: https://youtu.be/{response['id']}")
        return True
        
    except googleapiclient.errors.HttpError as e:
        print(f"❌ An HTTP error {e.resp.status} occurred:\n{e.content.decode('utf-8', errors='replace')}")
        return False
    except Exception as e:
        print(f"❌ Upload failed: {e}")
        return False

def main():
    if len(sys.argv) < 2:
        print("Usage: python upload_to_yt.py <path_to_mp4_or_directory>")
        print("Example 1: python upload_to_yt.py 'folder/track.mp4'")
        print("Example 2: python upload_to_yt.py 'folder'")
        target = input("\nPlease enter the path to the MP4 file or folder: ").strip()
        if not target:
            sys.exit(1)
    else:
        target = sys.argv[1]

    # Decide if it's a file or folder
    if os.path.isfile(target):
        if target.endswith('.mp4'):
            files_to_upload = [target]
        else:
            print(f"Error: '{target}' is not an MP4 file.")
            sys.exit(1)
    elif os.path.isdir(target):
        # Find all MP4s in the directory
        files_to_upload = glob.glob(os.path.join(target, "*.mp4"))
        if not files_to_upload:
            print(f"No MP4 files found in directory: '{target}'")
            sys.exit(0)
    else:
        print(f"Error: Valid path not found for '{target}'")
        sys.exit(1)

    print(f"Found {len(files_to_upload)} video(s) to upload.")
    
    # Authenticate once for all uploads
    youtube = get_authenticated_service()

    success_count = 0
    for file_path in files_to_upload:
        if upload_video(youtube, file_path):
            success_count += 1

    print(f"\n🎉 Finished! Successfully uploaded {success_count}/{len(files_to_upload)} videos.")

if __name__ == "__main__":
    main()
