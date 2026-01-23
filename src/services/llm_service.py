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
            available_sources_prompt += """
        - If media_source is "pexels":
        - visual_query MUST be a short, concrete stock search query
        - No artistic or cinematic language
        """

        if "duckduckgo" in enabled:
            available_sources_prompt += """
        - If media_source is "duckduckgo":
        - visual_query MUST be a factual real-world search query
        - Used for landmarks, people, events, places
        """

        if "pollinations" in enabled:
            available_sources_prompt += """
        - If media_source is "pollinations":
        - visual_query MUST be a detailed AI image generation prompt
        - Describe environment, mood, lighting, camera angle, style
        - Cinematic and context-aware
        """


        # system_prompt = f"""
        #         You are an expert video director.

        #         TASK:
        #         Convert the narration script and word-level timings into a precise video production plan.

        #         INPUT:
        #         1. Script
        #         2. Word Timings (JSON)

        #         OUTPUT:
        #         Return ONLY valid JSON with key "scenes".

        #         Do not create overly long scenes.
        #         Scene duration must be naturally derived from narration flow, not fixed seconds.
                

        #         Each scene MUST include:
        #         - id (int)
        #         - text (exact spoken phrase)
        #         - start_time (float)
        #         - end_time (float)
        #         - media_source (one of {json.dumps(enabled)})
        #         - visual_query (string)

        #         TIMING RULES:
        #         - First scene starts at first word timestamp
        #         - Every next scene starts EXACTLY at previous scene’s end_time
        #         - No gaps, no overlaps
        #         - Timings must come strictly from word timings

        #         MEDIA RULES:
        #         - media_source MUST be chosen ONLY from enabled sources: {json.dumps(enabled)}
        #         - Use source-specific behavior exactly as defined below
        #         - 

        #         SOURCE-SPECIFIC INSTRUCTIONS:
        #         {available_sources_prompt}

        #         OUTPUT RULES:
        #         - JSON ONLY
        #         - No markdown
        #         - No explanations
        #         - No extra text
        #         """

        # Combine instructions and data into a single robust prompt
        combined_prompt = f"""
You are a professional video editor and director. Your goal is to turn a narration script into a perfectly timed video plan.

### INPUT DATA
1. **Script**:
{script_text}

2. **Word-Level Timings** (JSON):
{json.dumps(word_subtitles)[:15000]}

### YOUR TASK
Generate a JSON response containing a list of video scenes.
Each scene must cover a specific segment of the script.

### CRITICAL TIMING RULES (MUST FOLLOW)
1. **NO GAPS**: The `start_time` of Scene N must EXACTLY match the `end_time` of Scene N-1.
2. **FULL COVERAGE**: The first scene starts at the first word's start time. The last scene ends at the last word's end time.
3. **DURATION LIMIT**: 
   - Ideal scene length: **3 to 7 seconds**.
   - Maximum scene length: **10 seconds** (Absolute Limit).
   - If a legitimate sentence/segment is longer than 10 seconds, **YOU MUST SPLIT IT** into two visual scenes.
4. **PACING**: Vary scene lengths. Don't make them all exactly 5 seconds. Use the flow of the speech.

### MEDIA SOURCE RULES
Select `media_source` ONLY from: {json.dumps(enabled)}
{available_sources_prompt}

### OUTPUT FORMAT
Return strictly valid JSON with a single key "scenes".
Example:
{{
  "scenes": [
    {{
      "id": 1,
      "text": "The quick brown fox",
      "start_time": 0.0,
      "end_time": 3.5,
      "media_source": "pexels",
      "visual_query": "red fox running in autumn forest close up"
    }},
    {{
      "id": 2,
      "text": "jumps over the lazy dog.",
      "start_time": 3.5,
      "end_time": 6.2,
      "media_source": "pollinations",
      "visual_query": "lazy sleeping dog in sunlight, cinematic 4k"
    }}
  ]
}}
"""

        try:
            headers = {
                "Content-Type": "application/json"
            }
            if Config.POLLINATIONS_API_KEY:
                headers["Authorization"] = f"Bearer {Config.POLLINATIONS_API_KEY}"
            
            # Use Unified API with OpenAI-compatible Chat Endpoint
            url = "https://gen.pollinations.ai/v1/chat/completions"
            
            payload = {
                "model": "openai-large", # Using 'deepseek' as requested or default reliable model
                "messages": [
                    {"role": "user", "content": combined_prompt}
                ],
                "json": True  # Pollinations specific parameter for JSON mode
            }
            
            print(f"DEBUG: Sending POST request to {url}")
            # print(f"DEBUG: Payload model: {payload['model']}")
            
            response = requests.post(url, headers=headers, json=payload, timeout=120)
            
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
