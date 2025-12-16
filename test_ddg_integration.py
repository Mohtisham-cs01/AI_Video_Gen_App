import os
import sys
from dotenv import load_dotenv

# Add root to path
sys.path.append(os.getcwd())

# Load env vars
load_dotenv()

from src.services.media_service import MediaService

def test_ddg():
    print("Testing DuckDuckGo Image Search Integration...")
    
    ms = MediaService()
    
    query = "beautiful sunset over ocean"
    print(f"Searching for: '{query}'")
    
    try:
        url = ms.search_ddg_images(query)
        
        if url:
            print(f"Success! Found image URL: {url}")
            # Optional: Try to download it to verify it's accessible
            output_path = "test_ddg_image.jpg"
            downloaded = ms.download_file(url, output_path)
            if downloaded and os.path.exists(downloaded):
                 print(f"Successfully downloaded image to {downloaded}")
            else:
                 print("Failed to download image.")
        else:
            print("Error: No results found.")
            
    except Exception as e:
        print(f"Test failed with error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_ddg()
