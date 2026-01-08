import requests
import os
from ..config import Config

class MediaService:
    def __init__(self):
        self.pexels_api_key = Config.PEXELS_API_KEY
        self.headers = {"Authorization": self.pexels_api_key} if self.pexels_api_key else {}
        self.pollinations_api_key = Config.POLLINATIONS_API_KEY

    def search_pexels(self, query: str, orientation="landscape", size="medium", type="video"):
        """
        Searches Pexels for videos or photos.
        type: 'video' or 'photo'
        orientation: 'landscape', 'portrait', or 'square'
        """
        if not self.pexels_api_key:
            print("Pexels API key missing.")
            return None

        base_url = "https://api.pexels.com/videos/search" if type == "video" else "https://api.pexels.com/v1/search"
        params = {
            "query": query,
            "per_page": 1,
            "orientation": orientation,
            "size": size
        }
        
        try:
            response = requests.get(base_url, headers=self.headers, params=params)
            response.raise_for_status()
            data = response.json()
            
            if type == "video":
                if data.get('videos'):
                    # Get the best quality link, or a specific size
                    video_files = data['videos'][0]['video_files']
                    # Sort by quality/size logic here if needed
                    return video_files[0]['link']
            else:
                if data.get('photos'):
                    return data['photos'][0]['src']['large']
            
            return None
        except Exception as e:
            print(f"Pexels search error: {e}")
            return None

    def generate_image_pollinations(self, prompt: str, output_path: str, width: int = 1920, height: int = 1080):
        """
        Generates an image using Pollinations.ai with specified dimensions.
        """
        try:
            # Pollinations image URL format: https://gen.pollinations.ai/image/{prompt}?width={width}&height={height}&model={model}
            model = Config.POLLINATIONS_MODEL #or "flux"
            url = f"https://gen.pollinations.ai/image/{requests.utils.quote(prompt)}?width={width}&height={height}&model={model}"
            print(f"Generating Pollinations image: {width}x{height} model={model}")
            
            headers = {}
            if self.pollinations_api_key:
                headers["Authorization"] = f"Bearer {self.pollinations_api_key}"
            
            response = requests.get(url, headers=headers)
            response.raise_for_status()
            
            with open(output_path, 'wb') as f:
                f.write(response.content)
            return output_path
        except Exception as e:
            print(f"Pollinations image error: {e}")
            return None

    def search_ddg_images(self, query: str):
        """
        Searches DuckDuckGo for images using LangChain tool.
        Returns the URL of the first result.
        """
        try:
            from langchain_community.tools import DuckDuckGoSearchResults
            import json
            
            print(f"Searching DDG for: {query}")
            search = DuckDuckGoSearchResults(output_format="json", backend="images")
            results_json = search.invoke(query)
            
            results = json.loads(results_json)
            
            if results and len(results) > 0:
                # Return the first image URL (thumbnail or image)
                first_result = results[0]
                image_url = first_result.get("image") or first_result.get("thumbnail")
                
                if image_url:
                    print(f"✓ Found DDG image: {image_url[:50]}...")
                    return image_url
            
            print("No DDG results found.")
            return None
            
        except Exception as e:
            print(f"DDG search error: {e}")
            return None
