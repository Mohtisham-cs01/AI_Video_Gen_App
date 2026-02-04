import os
import json
import torch
import requests
import whisperx
from ..config import Config

from ..utils.subtitle_utils import segments_to_srt

class SubtitleService:
    def __init__(self, model_size="base", device=None):
        self.model_size = Config.WHISPER_MODEL_SIZE or model_size
        self.device = device if device else ("cuda" if torch.cuda.is_available() else "cpu")
        self.compute_type = "float16" if self.device == "cuda" else "int8"

    def generate_subtitles(self, audio_path: str):
        """
        Generates subtitles using Groq API (if key available) or fallback to WhisperX.
        Returns the segments with word timings.
        Saves SRT, Segments JSON, and Words JSON to disk.
        """
        segments = []
        
        # Try Groq API first if key exists
        if Config.GROQ_API_KEY:
            try:
                print("Attempting to use Groq Whisper API...")
                segments = self._generate_groq_subtitles(audio_path)
            except Exception as e:
                print(f"Groq API failed: {e}")
                print("Falling back to local WhisperX...")
                segments = None
        else:
             print("No Groq API key found. Using local WhisperX...")

        # Fallback to local
        if not segments:
            segments = self._generate_local_whisperx(audio_path)

        if segments:
            self._save_outputs(audio_path, segments)

        return segments

    def _generate_local_whisperx(self, audio_path: str):
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
            return result["segments"]

        except Exception as e:
            print(f"WhisperX error: {e}")
            raise

    def _save_outputs(self, audio_path: str, segments: list, words_list: list = None):
        """Save SRT, Segments JSON, and Words JSON."""
        base_path = os.path.splitext(audio_path)[0]
        
        # 1. Save Segments JSON
        with open(base_path + "_segments.json", 'w', encoding='utf-8') as f:
            json.dump(segments, f, indent=2, ensure_ascii=False)
            
        # 2. Save Words JSON
        # If explicit words_list is passed, use it. Otherwise extract from segments.
        final_words = []
        if words_list:
             final_words = words_list
        else:
            for seg in segments:
                if "words" in seg:
                    final_words.extend(seg["words"])
        
        with open(base_path + "_words.json", 'w', encoding='utf-8') as f:
            json.dump(final_words, f, indent=2, ensure_ascii=False)
            
        # 3. Save SRT
        srt_content = segments_to_srt(segments)
        with open(base_path + ".srt", 'w', encoding='utf-8') as f:
            f.write(srt_content)
            
        print(f"Saved subtitles to {base_path} [.srt, _segments.json, _words.json]")


    def _generate_groq_subtitles(self, audio_path: str):
        """
        Generates subtitles using Groq's Whisper API.
        Returns segments with embedded words.
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
                    "timestamp_granularities[]": ["word", "segment"] 
                }
                
                print(f"Sending request to Groq API ({url})...")
                response = requests.post(url, headers=headers, files=files, data=data)
                
                if response.status_code != 200:
                   raise Exception(f"Groq API Error {response.status_code}: {response.text}")
                
                result = response.json()
                
                segments = result.get("segments", [])
                words = result.get("words", []) 
                
                if not segments and not words:
                    return []
                
                # Merge words into segments to match expected structure
                # and fix potential missing words in gaps
                self._merge_words_into_segments(segments, words)

                print(f"Groq transcription complete. {len(segments)} segments.")
                return segments
                
        except Exception as e:
            raise Exception(f"Failed to generate subtitles via Groq: {e}")

    def _merge_words_into_segments(self, segments, words):
        """
        Merges a flat list of words into segments based on timing.
        Ensures NO words are lost by including gap words in the subsequent segment.
        """
        if not segments or not words:
            return

        word_idx = 0
        for seg in segments:
            seg_start = seg.get("start", 0)
            seg_end = seg.get("end", 0)
            seg_words = []
            
            # Consume words until we pass the segment end
            while word_idx < len(words):
                w = words[word_idx]
                w_start = w.get("start", 0)
                
                # Include word if it starts before this segment ends.
                # This effectively grabs any words in the "gap" before this segment too.
                if w_start < seg_end:
                    seg_words.append(w)
                    word_idx += 1
                else:
                    break
            
            seg["words"] = seg_words

        # Append any leftovers to the last segment
        if word_idx < len(words) and segments:
            print(f"Appending {len(words) - word_idx} leftover words to last segment.")
            segments[-1]["words"].extend(words[word_idx:])


    def load_from_json(self, json_path: str):
        with open(json_path, 'r') as f:
            return json.load(f)
