import json
import requests
import urllib.parse
from ..config import Config

class LLMService:
    def __init__(self, provider="pollinations"):
        self.provider = provider

    def segment_script_and_generate_queries(self, script_text: str, word_subtitles: list):
        """
        Analyzes the script and word-level subtitles to generate scene segmentation
        and visual queries using Pollinations.ai.
        """
        
        # Dynamic source prompt based on enabled sources
        available_sources_prompt = ""
        enabled = Config.ENABLED_MEDIA_SOURCES
        
        if "pexels" in enabled:
            available_sources_prompt += '\n* "pexels": Use for high-quality stock footage/photos.'
        if "duckduckgo" in enabled:
            available_sources_prompt += '\n* "duckduckgo": Use for specific real-world entities, famous places, or when stock footage might be missing.'
        if "pollinations" in enabled:
            available_sources_prompt += '\n* "pollinations": Use for abstract, fantasy, or very specific generated art.'
            
        system_prompt = f"""You are an expert video director. Analyze the script and word timings to create a production plan.

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
    - 'media_source': Choose from: {json.dumps(enabled)}.
    {available_sources_prompt}
    - 'image_prompt': Detailed prompt if source is 'pollinations'.

    Don't put gap timing between scenes.
    Return ONLY valid JSON. No markdown formatting."""

        user_prompt = f"""Script:
    {script_text}

    Word Timings:
    {json.dumps(word_subtitles)[:15000]}"""

        # Combine system and user prompts are not needed for chat endpoint, but we keep them for logic
        # full_prompt = f"{system_prompt}\n\n{user_prompt}" 
        
        try:
            headers = {
                "Content-Type": "application/json"
            }
            if Config.POLLINATIONS_API_KEY:
                headers["Authorization"] = f"Bearer {Config.POLLINATIONS_API_KEY}"
            
            # Use Unified API with OpenAI-compatible Chat Endpoint for reliability (POST)
            url = "https://gen.pollinations.ai/v1/chat/completions"
            
            payload = {
                "model": "nova-micro", # User preferred model
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                "json": "true"  # Pollinations specific parameter for JSON mode
            }
            
            print(f"DEBUG: Sending POST request to {url}")
            # print(f"DEBUG: Payload model: {payload['model']}")
            
            response = requests.post(url, headers=headers, json=payload, timeout=60)
            
            print(f"DEBUG: Response status: {response.status_code}")
            
            if response.status_code == 200:
                result_text = response.text.strip()
                
                # The response from chat/completions is usually a JSON object with 'choices'
                # But Pollinations sometimes returns just the content or specific structure.
                # Standard OpenAI format: response['choices'][0]['message']['content']
                # However, with json=true, Pollinations might return the raw JSON object directly in content?
                # Let's handle both standard OpenAI format and direct JSON return just in case.
                
                try:
                    resp_json = response.json()
                    content = None
                    
                    if "choices" in resp_json and len(resp_json["choices"]) > 0:
                        content = resp_json["choices"][0]["message"]["content"]
                    else:
                        # Maybe it returned the content directly? (unlikely for strict OpenAI compat but possible for Pollinations)
                        # or response.text was the content?
                        content = result_text

                    # Now parse the content string as JSON usually
                    if isinstance(content, str):
                        # Clean markdown
                        if "```json" in content:
                            content = content.split("```json")[1].split("```")[0].strip()
                        elif "```" in content:
                            content = content.split("```")[1].split("```")[0].strip()
                        
                        parsed_result = json.loads(content)
                    else:
                        parsed_result = content # It might be already a dict if Pollinations magic happened
                        
                except json.JSONDecodeError:
                     # Fallback if response.json() failed (it shouldn't if 200)
                     # or if content parsing failed
                     print(f"DEBUG: Raw response text: {result_text[:200]}...")
                     # Try parsing raw text if it wasn't valid OpenAI json
                     parsed_result = json.loads(result_text)

                
                # Validate structure
                if "scenes" in parsed_result and isinstance(parsed_result["scenes"], list):
                    print(f"DEBUG: Successfully parsed {len(parsed_result['scenes'])} scenes")
                    return parsed_result
                else:
                    print("DEBUG: Invalid JSON structure in response, checking keys...")
                    if isinstance(parsed_result, dict):
                        print(f"DEBUG: Keys found: {list(parsed_result.keys())}")
                    return {"scenes": []}
            else:
                print(f"ERROR: Request failed with status {response.status_code}")
                # print(f"ERROR: Response text: {response.text[:500]}")
                return {"scenes": []}
                    
        except requests.exceptions.Timeout:
            print("ERROR: Request timed out after 60 seconds")
            return {"scenes": []}
        except Exception as e:
            print(f"ERROR: LLM Error (Pollinations POST): {e}")
            return {"scenes": []}

    def generate_visual_queries_only(self, text_chunk):
        pass
