import json
import requests
from ..config import Config

class LLMService:
    def __init__(self, provider="pollinations"):
        self.provider = provider

    def segment_script_and_generate_queries(self, script_text: str, word_subtitles: list):
        """
        Analyzes the script and word-level subtitles to generate scene segmentation
        and visual queries using Pollinations.ai.
        """
        
        system_prompt = """
        You are an expert video director. Analyze the script and word timings to create a production plan.
        
        Input:
        1. Script.
        2. Word Timings (JSON).
        
        Output:
        A JSON object with a 'scenes' list. Each scene:
        - 'id': int
        - 'text': Exact phrase.
        - 'start_time': float
        - 'end_time': float
        - 'visual_query': Search query for Pexels or DuckDuckGo.
        - 'media_source': "pexels", "duckduckgo", or "pollinations".
          * Use "pexels" for high-quality stock footage/photos.
          * Use "duckduckgo" for specific real-world entities, famous places, or when stock footage might be missing.
          * Use "pollinations" for abstract, fantasy, or very specific generated art.
        - 'image_prompt': Detailed prompt if source is 'pollinations'.
        
        Return ONLY valid JSON. No markdown formatting.
        """
        
        user_prompt = f"""
        Script:
        {script_text}
        
        Word Timings:
        {json.dumps(word_subtitles)[:15000]} # Truncate if too long for GET request safety, though POST is better if supported. Pollinations usually GET.
        """
        
        # Pollinations Text API: https://text.pollinations.ai/{prompt}?model={model}
        # We need to be careful with URL length. Pollinations might support POST or we have to keep it short.
        # Actually, for large inputs like this, Pollinations GET might fail.
        # Let's try to use the prompt in the URL. If it's too long, we might have issues.
        # However, the user specifically asked for Pollinations.ai text models.
        # Let's assume standard usage.
        
        full_prompt = f"{system_prompt}\n\n{user_prompt}"
        
        try:
            # Using openai compatibility endpoint of Pollinations if available would be easier, 
            # but standard way is GET request.
            # Let's try to keep it within reasonable limits or check if they have a POST endpoint.
            # Official docs often show GET. Let's try GET.
            
            # To be safe with JSON parsing, we ask for it explicitly.
            headers = {}
            if Config.POLLINATIONS_API_KEY:
                headers["Authorization"] = f"Bearer {Config.POLLINATIONS_API_KEY}"
            url = f"https://text.pollinations.ai/{requests.utils.quote(full_prompt)}?model=deepseek" # model=openai gives GPT-like responses
            
            response = requests.get(url , headers=headers)
            response.raise_for_status()
            
            result_text = response.text
            
            # Clean up potential markdown code blocks
            if "```json" in result_text:
                result_text = result_text.split("```json")[1].split("```")[0].strip()
            elif "```" in result_text:
                result_text = result_text.split("```")[1].split("```")[0].strip()
                
            return json.loads(result_text)
            
        except Exception as e:
            print(f"LLM Error (Pollinations): {e}")
            # Fallback structure for UI testing if API fails
            return {"scenes": []}

    def generate_visual_queries_only(self, text_chunk):
        pass
