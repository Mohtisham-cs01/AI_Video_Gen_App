import os
import json
import torch
import whisperx
from ..config import Config

class SubtitleService:
    def __init__(self, model_size="base", device=None):
        self.model_size = Config.WHISPER_MODEL_SIZE or model_size
        self.device = device if device else ("cuda" if torch.cuda.is_available() else "cpu")
        self.compute_type = "float16" if self.device == "cuda" else "int8"

    def generate_subtitles(self, audio_path: str):
        """
        Generates subtitles using WhisperX library directly.
        Returns the full WhisperX output structure (segments with word timings).
        """
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


        return []

    def load_from_json(self, json_path: str):
        with open(json_path, 'r') as f:
            return json.load(f)
