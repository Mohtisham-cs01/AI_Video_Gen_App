import json
import requests
import urllib.parse
from ..config import Config
import random
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
        #add a random seed in prompt for entropy
        random_seed = random.randint(0, 1000000)
        combined_prompt = f"""
        You are a professional video editor and director. Your goal is to turn a narration script into a perfectly timed video plan.
        random_seed: {random_seed}

        ### INPUT DATA
        1. **Script**:
        {script_text}

        2. **Word-Level Timings** (JSON):
        {json.dumps(word_subtitles)}

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
            "media_source": "source_name",
            "visual_query": "red fox running in autumn forest close up"
            }}
            {{
            "id": 2,
            "text": "The quick brown fox",
            "start_time": 3.5,
            "end_time": 7.0,
            "media_source": "source_name",
            "visual_query": "red fox running in autumn forest close up"
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
                "model": "kimi", # Using 'deepseek' as requested or default reliable model
                "messages": [
                    {"role": "user", "content": combined_prompt}
                ],
                "json": True  # Pollinations specific parameter for JSON mode
            }
            
            print(f"DEBUG: Sending POST request to {url}")
            # print(f"DEBUG: Payload model: {payload['model']}")
            
            response = requests.post(url, headers=headers, json=payload)
            
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
                    
                    # Validate and fix scenes
                    validated_scenes = self._validate_and_fix_scenes(parsed_result["scenes"], word_subtitles)
                    print(f"DEBUG: Validated scenes count: {len(validated_scenes)}")
                    
                    return {"scenes": validated_scenes}
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

    def _validate_and_fix_scenes(self, scenes: list, word_subtitles: list) -> list:
        """
        Validates and fixes scenes to ensure:
        1. No scene exceeds 10 seconds (HARD LIMIT)
        2. No scene is shorter than 0.5 seconds (merged with previous)
        3. No gaps between scenes (filled with visual-only scenes)
        4. No overlaps between scenes (adjusted)
        5. Text aligned with word-level subtitles
        
        Args:
            scenes: List of scene dicts from LLM
            word_subtitles: List of [word, start, end] items from subtitle service
        
        Returns:
            List of validated scene dicts
        """
        if not scenes:
            return []
        
        # --- Constants ---
        MAX_DURATION = 10.0
        MIN_DURATION = 0.5
        FILLER_CHUNK_SIZE = 8.0
        
        # Prompt variations for split scenes (to generate different visuals)
        SPLIT_VARIATIONS = [
            "",  # First chunk keeps original
            ", different angle",
            ", close-up shot",
            ", wide establishing shot",
            ", dramatic lighting",
            ", slow motion feel",
            ", dynamic camera movement",
            ", alternative perspective"
        ]
        
        # --- Prepare word data ---
        # Sort words by start time
        sorted_words = sorted(word_subtitles, key=lambda x: x[1])
        
        def get_words_in_range(start_t: float, end_t: float) -> list:
            """Get words that START within [start_t, end_t)."""
            return [w for w in sorted_words if start_t <= w[1] < end_t]
        
        def get_text_for_range(start_t: float, end_t: float) -> str:
            """Get concatenated text for words in range."""
            words = get_words_in_range(start_t, end_t)
            return " ".join(w[0] for w in words)
        
        # --- PASS 1: Split any scene > MAX_DURATION ---
        split_scenes = []
        
        for scene in scenes:
            start = float(scene.get('start_time', 0))
            end = float(scene.get('end_time', 0))
            duration = end - start
            
            if duration <= 0:
                continue  # Invalid scene, skip
            
            if duration <= MAX_DURATION:
                # Scene is OK, add as-is
                split_scenes.append({
                    "start_time": round(start, 2),
                    "end_time": round(end, 2),
                    "text": scene.get('text', ''),
                    "visual_query": scene.get('visual_query', ''),
                    "media_source": scene.get('media_source', 'pollinations')
                })
            else:
                # Scene is too long, MUST split by time
                current_time = start
                part = 1
                while current_time < end:
                    chunk_end = min(current_time + FILLER_CHUNK_SIZE, end)
                    
                    # Avoid tiny last chunk
                    if (end - chunk_end) < MIN_DURATION and (end - chunk_end) > 0:
                        chunk_end = end
                    
                    # Get text for this chunk from word subtitles
                    chunk_text = get_text_for_range(current_time, chunk_end)
                    
                    # Vary the visual query for each split chunk
                    variation = SPLIT_VARIATIONS[part % len(SPLIT_VARIATIONS)]
                    base_query = scene.get('visual_query', '')
                    varied_query = base_query + variation if base_query else f"Atmospheric scene{variation}"
                    
                    split_scenes.append({
                        "start_time": round(current_time, 2),
                        "end_time": round(chunk_end, 2),
                        "text": chunk_text,
                        "visual_query": varied_query,
                        "media_source": scene.get('media_source', 'pollinations')
                    })
                    
                    current_time = chunk_end
                    part += 1
        
        if not split_scenes:
            return []
        
        # Sort by start_time to ensure order
        split_scenes.sort(key=lambda x: x['start_time'])
        
        # --- PASS 2: Fill gaps and fix overlaps ---
        final_scenes = []
        
        for i, scene in enumerate(split_scenes):
            if i == 0:
                final_scenes.append(scene)
                continue
            
            prev = final_scenes[-1]
            curr = scene.copy()
            
            gap = curr['start_time'] - prev['end_time']
            
            if gap > 0.1:  # Significant gap exists
                # Fill the gap with visual-only scenes
                fill_start = prev['end_time']
                fill_end = curr['start_time']
                
                while fill_start < fill_end:
                    chunk_end = min(fill_start + FILLER_CHUNK_SIZE, fill_end)
                    
                    filler = {
                        "start_time": round(fill_start, 2),
                        "end_time": round(chunk_end, 2),
                        "text": "",  # No spoken text in filler
                        "visual_query": prev.get('visual_query', '') + " (Atmospheric)",
                        "media_source": prev.get('media_source', 'pollinations')
                    }
                    final_scenes.append(filler)
                    fill_start = chunk_end
                    
            elif gap < -0.1:  # Overlap exists
                # Adjust current scene start to fix overlap
                curr['start_time'] = prev['end_time']
                if curr['end_time'] <= curr['start_time']:
                    curr['end_time'] = curr['start_time'] + MIN_DURATION
            
            # Merge very short scenes with previous
            curr_duration = curr['end_time'] - curr['start_time']
            if curr_duration < MIN_DURATION:
                # Extend previous scene instead of adding this tiny one
                prev['end_time'] = max(prev['end_time'], curr['end_time'])
                if curr['text']:
                    prev['text'] = (prev.get('text', '') + " " + curr['text']).strip()
            else:
                final_scenes.append(curr)
        
        # --- PASS 3: Final validation - ensure no scene > MAX_DURATION ---
        # This is a safety net in case any scene slipped through
        validated_scenes = []
        
        for scene in final_scenes:
            duration = scene['end_time'] - scene['start_time']
            
            if duration <= MAX_DURATION:
                validated_scenes.append(scene)
            else:
                # Force split by time
                current_time = scene['start_time']
                end = scene['end_time']
                
                part = 0
                while current_time < end:
                    chunk_end = min(current_time + FILLER_CHUNK_SIZE, end)
                    
                    chunk_text = get_text_for_range(current_time, chunk_end)
                    
                    # Vary the visual query
                    variation = SPLIT_VARIATIONS[part % len(SPLIT_VARIATIONS)]
                    base_query = scene.get('visual_query', '')
                    varied_query = base_query + variation if base_query else f"Atmospheric scene{variation}"
                    
                    validated_scenes.append({
                        "start_time": round(current_time, 2),
                        "end_time": round(chunk_end, 2),
                        "text": chunk_text,
                        "visual_query": varied_query,
                        "media_source": scene.get('media_source', 'pollinations')
                    })
                    
                    current_time = chunk_end
                    part += 1
        
        # --- Assign sequential IDs ---
        for i, scene in enumerate(validated_scenes):
            scene['id'] = i + 1
        
        return validated_scenes

    def generate_visual_queries_only(self, text_chunk):
        pass


