import os
import json
import torch
import requests
import whisperx
from ..config import Config

class SubtitleService:
    def __init__(self, model_size="base", device=None):
        self.model_size = Config.WHISPER_MODEL_SIZE or model_size
        self.device = device if device else ("cuda" if torch.cuda.is_available() else "cpu")
        self.compute_type = "float16" if self.device == "cuda" else "int8"

    def generate_subtitles(self, audio_path: str):
        """
        Generates subtitles using Groq API (if key available) or fallback to WhisperX.
        Returns the segments with word timings.
        """
        # Try Groq API first if key exists
        if Config.GROQ_API_KEY:
            try:
                print("Attempting to use Groq Whisper API...")
                segments = self._generate_groq_subtitles(audio_path)
                if segments:
                    return segments
            except Exception as e:
                print(f"Groq API failed: {e}")
                print("Falling back to local WhisperX...")
        else:
             print("No Groq API key found. Using local WhisperX...")

        print(f"Loading WhisperX model: {self.model_size} on {self.device} ({self.compute_type})...")
        
        try:
            # 1. Load Model
            model = whisperx.load_model(
                self.model_size,
                self.device,
                compute_type=self.compute_type
            )
            
            # 2. Load Audio
            audio = whisperx.load_audio(audio_path)
            
            # 3. Transcribe
            print("Transcribing...")
            result = model.transcribe(audio, batch_size=16)
            
            # 4. Align
            print("Aligning...")
            model_a, metadata = whisperx.load_align_model(
                language_code=result["language"],
                device=self.device
            )
            
            result = whisperx.align(
                result["segments"],
                model_a,
                metadata,
                audio,
                self.device,
                return_char_alignments=False
            )
            
            # Save JSON for debugging/reference
            json_output_path = audio_path + ".json"
            with open(json_output_path, 'w', encoding='utf-8') as f:
                json.dump(result["segments"], f, indent=2)
                
            return result["segments"]

        except Exception as e:
            print(f"WhisperX error: {e}")
            raise

    def _generate_groq_subtitles(self, audio_path: str):
        """
        Generates subtitles using Groq's Whisper API via HTTP request.
        Request both words and segments.
        """
        url = "https://api.groq.com/openai/v1/audio/transcriptions"
        
        headers = {
            "Authorization": f"Bearer {Config.GROQ_API_KEY}"
        }
        
        try:
            with open(audio_path, "rb") as file:
                files = {
                    "file": (os.path.basename(audio_path), file, "audio/mpeg")
                }
                
                # Request parameters for both segments and words
                data = {
                    "model": "whisper-large-v3",
                    "response_format": "verbose_json",
                    "timestamp_granularities[]": ["word", "segment"] # Request both
                }
                
                print(f"Sending request to Groq API ({url})...")
                response = requests.post(url, headers=headers, files=files, data=data)
                
                if response.status_code != 200:
                   raise Exception(f"Groq API Error {response.status_code}: {response.text}")
                
                result = response.json()
                
                # Transform to match WhisperX output where possible
                # Groq/OpenAI verbose_json structure:
                # {
                #   "text": "...",
                #   "segments": [...],
                #   "words": [...]
                # }
                #
                # WhisperX expects a list of segments, where each segment has a 'words' key.
                # However, OpenAI 'words' are usually a flat list at top level (sometimes).
                # Let's check the structure. If 'words' are at top level, we might need to map them to segments 
                # or just return the segments if they already contain words (some implementations do).
                #
                # Standard OpenAI 'verbose_json' with 'segment' granularity returns segments.
                # 'word' granularity returns top-level 'words'.
                # IF requesting BOTH, we should get both keys.
                #
                # We need to ensure the return value is a list of segments, and ideally each segment has 'words'.
                
                segments = result.get("segments", [])
                words = result.get("words", [])
                
                if not segments and not words:
                    print("Groq API returned no segments and no words.")
                    return []

                # If we have segments but they lack 'words', and we have a top-level 'words' list,
                # we can try to distribute words into segments based on timestamps.
                if segments and words and 'words' not in segments[0]:
                    print("Mapping top-level words to segments...")
                    word_idx = 0
                    for seg in segments:
                        seg_start = seg.get("start", 0)
                        seg_end = seg.get("end", 0)
                        seg_words = []
                        
                        # Collect words that fall within this segment
                        # Assuming sorted words
                        while word_idx < len(words):
                            w = words[word_idx]
                            w_start = w.get("start", 0)
                            w_end = w.get("end", 0) # sometimes not present
                            
                            # Simple overlap check: word center is inside segment
                            # or just start time check
                            if w_start >= seg_start and w_start < seg_end:
                                seg_words.append(w)
                                word_idx += 1
                            elif w_start >= seg_end:
                                break
                            else:
                                # Word started before segment? Should not happen if sorted, or overlap.
                                word_idx += 1
                        
                        seg["words"] = seg_words
                
                # Prepare result: clean up keys if necessary to match WhisperX
                # WhisperX segments usually have: start, end, text, words
                
                print(f"Groq transcription complete. {len(segments)} segments.")
                return segments
                
        except Exception as e:
            raise Exception(f"Failed to generate subtitles via Groq: {e}")


        return []

    def load_from_json(self, json_path: str):
        with open(json_path, 'r') as f:
            return json.load(f)
