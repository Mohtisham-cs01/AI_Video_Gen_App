import requests
import os
import time
import urllib.parse
import json
import base64
from abc import ABC, abstractmethod
import subprocess
from pydub import AudioSegment
from ..config import Config

class TTSService(ABC):
    @abstractmethod
    def generate_audio(self, text: str, output_path: str, voice: str = "openai"):
        pass

class PollinationsTTS(TTSService):
    def generate_audio(self, text: str, output_path: str, voice: str = "alloy"):
        """
        Generates audio using Pollinations.ai API with chunking support for long scripts.
        """
        print(f"Generating audio for script length: {len(text)}")
        
        # 1. Split script into chunks
        # chunks = self._split_script_into_chunks(text)
        chunks = [text]
        if not chunks:
            raise ValueError("Script is empty or could not be split.")
            
        chunk_files = []
        temp_dir = os.path.dirname(output_path)
        base_name = os.path.splitext(os.path.basename(output_path))[0]
        
        try:
            # 2. Generate audio for each chunk
            for i, chunk in enumerate(chunks):
                chunk_id = i + 1
                chunk_filename = os.path.join(temp_dir, f"{base_name}_chunk_{chunk_id:03d}.mp3")
                
                print(f"Processing chunk {chunk_id}/{len(chunks)}...")
                if self._generate_single_chunk(chunk, chunk_filename, voice):
                    chunk_files.append(chunk_filename)
                else:
                    raise Exception(f"Failed to generate audio for chunk {chunk_id}")
                
                # Small delay to be nice to the API
                time.sleep(1)

            # 3. Combine chunks
            if self._combine_audio_files(chunk_files, output_path):
                print(f"Audio successfully generated at {output_path}")
                return output_path
            else:
                raise Exception("Failed to combine audio chunks.")
                
        finally:
            # Cleanup temp files
            for f in chunk_files:
                if os.path.exists(f):
                    try:
                        os.remove(f)
                    except:
                        pass

    def _split_script_into_chunks(self, script, max_chunk_length=300):
        chunks = []
        lines = script.strip().split('\n')
        current_chunk = ""
        
        for line in lines:
            line = line.strip()
            if not line:
                continue
                
            # If direction like [calm tone], start new chunk
            if line.startswith('[') and line.endswith(']'):
                if current_chunk:
                    chunks.append(current_chunk)
                current_chunk = line
            # Check length
            elif len(current_chunk) + len(line) > max_chunk_length and current_chunk:
                chunks.append(current_chunk)
                current_chunk = line
            else:
                if current_chunk:
                    current_chunk += "\n" + line
                else:
                    current_chunk = line
        
        if current_chunk:
            chunks.append(current_chunk)
            
        print(f"Split script into {len(chunks)} chunks")
        for i, chunk in enumerate(chunks):
            print(f"  Chunk {i+1}: {len(chunk)} chars - {chunk[:50]}...")
            
        return chunks

    def _validate_audio_content(self, content):
        """
        Validate that the response content is actually audio data.
        Returns True if valid audio, False otherwise.
        """
        if not content:
            return False
        
        # Check minimum size (audio files should be at least 1KB)
        if len(content) < 1024:
            print("  ⚠ Response too small to be valid audio")
            return False
        
        # Check for common audio file signatures
        audio_signatures = {
            b'ID3': 'mp3',  # MP3 with ID3 tag
            b'\xFF\xFB': 'mp3',  # MP3 without ID3 tag
            b'RIFF': 'wav',  # WAV files
            b'OggS': 'ogg',  # OGG files
            b'fLaC': 'flac', # FLAC files
        }
        
        for signature, file_type in audio_signatures.items():
            if content.startswith(signature):
                print(f"  ✓ Valid {file_type.upper()} audio signature detected")
                return True
        
        # Check for common error patterns in content
        error_indicators = [
            b'<html', b'<!DOCTYPE', b'error', b'Error', 
            b'{"error"', b'not found', b'unauthorized'
        ]
        
        content_start = content[:500].lower()  # Check first 500 bytes
        for indicator in error_indicators:
            if indicator.lower() in content_start:
                print(f"  ✗ Error indicator found: {indicator}")
                return False
        
        # If we get here and it's a reasonable size, assume it's audio
        if len(content) > 5000:  # If larger than 5KB, likely audio
            print("  ✓ Large response, assuming valid audio")
            return True
        
        print("  ⚠ Unable to verify audio format, but saving anyway")
        return True

    def _generate_single_chunk(self, text, output_path, voice, max_retries=3):
        url = "https://gen.pollinations.ai/v1/chat/completions"
        
        headers = {
            "Content-Type": "application/json"
        }
        if Config.POLLINATIONS_API_KEY:
            headers["Authorization"] = f"Bearer {Config.POLLINATIONS_API_KEY}"
            
        payload = {
            "model": "openai-audio",
            "messages": [{"role": "user", "content": text}],
            "modalities": ["text", "audio"],
            "audio": {"voice": voice, "format": "mp3"}
        }
            
        for attempt in range(max_retries):
            try:
                print(f"  Attempt {attempt + 1}/{max_retries}")
                response = requests.post(url, headers=headers, json=payload, timeout=60)
                
                if response.status_code != 200:
                    print(f"  ✗ API Error ({response.status_code}): {response.text[:200]}")
                    if attempt < max_retries - 1:
                        time.sleep(2)
                        continue
                    else:
                        return False
                
                data = response.json()
                
                # Extract audio data
                audio_content = None
                try:
                    audio_content = data['choices'][0]['message']['audio']['data']
                except (KeyError, IndexError) as e:
                    print(f"  ✗ Unexpected response structure: {e}")
                    # Try to see if it's in a different format or just text
                    if 'choices' in data and data['choices']:
                        print(f"  Message content: {data['choices'][0].get('message', {}).get('content')}")
                
                if not audio_content:
                    print(f"  ✗ No audio data found in response")
                    if attempt < max_retries - 1:
                        time.sleep(2)
                        continue
                    else:
                        return False

                # Decode base64
                audio_bytes = base64.b64decode(audio_content)
                
                with open(output_path, 'wb') as f:
                    f.write(audio_bytes)
                    
                print(f"  ✓ Chunk successfully saved: {output_path} ({len(audio_bytes)} bytes)")
                return True
                
            except Exception as e:
                print(f"  ✗ Error generating chunk (attempt {attempt+1}): {e}")
                if attempt < max_retries - 1:
                    time.sleep(2)
                else:
                    return False
        return False

    def _combine_audio_files(self, chunk_files, output_path):
        try:
            combined = AudioSegment.empty()
            valid_count = 0
            for f in chunk_files:
                if os.path.exists(f):
                    try:
                        segment = AudioSegment.from_mp3(f)
                        combined += segment
                        # Add small pause? Reference adds 500ms
                        combined += AudioSegment.silent(duration=500)
                        valid_count += 1
                        print(f"  ✓ Added {os.path.basename(f)} to combined audio")
                    except Exception as e:
                        print(f"  ✗ Skipping invalid audio file {f}: {e}")
                else:
                    print(f"  ✗ Chunk file not found: {f}")
            
            if valid_count == 0:
                print("  ✗ No valid audio files to combine!")
                return False

            combined.export(output_path, format="mp3")
            print(f"  ✓ Combined {valid_count} chunks into {output_path}")
            return True
        except Exception as e:
            print(f"Error combining audio: {e}")
            return False

class AudioExtractor:
    @staticmethod
    def extract_audio(video_path: str, output_path: str):
        """
        Extracts audio from a video file using ffmpeg.
        """
        try:
            command = [
                'ffmpeg', '-y',
                '-i', video_path,
                '-vn', # No video
                '-acodec', 'mp3',
                '-ab', '192k',
                '-ar', '44100',
                output_path
            ]
            subprocess.run(command, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            return output_path
        except subprocess.CalledProcessError as e:
            print(f"Error extracting audio: {e}")
            raise

import wave
from google import genai
from google.genai import types

class GeminiTTS(TTSService):
    def __init__(self, api_key=None, model="gemini-2.5-flash-preview-tts"):
        """
        Initialize Gemini TTS service.
        
        Args:
            api_key: Gemini API key (defaults to Config.GEMINI_API_KEY)
            model: TTS preview model (gemini-2.5-flash-preview-tts or gemini-2.5-pro-preview-tts)
        """
        self.api_key = api_key or Config.GEMINI_API_KEY
        self.model_name = model
        if not self.api_key:
            raise ValueError("Gemini API key is required. Set GEMINI_API_KEY in .env file.")
        
        self.client = genai.Client(api_key=self.api_key)
    
    def _save_wave_file(self, filename, pcm, channels=1, rate=24000, sample_width=2):
        """Helper to save PCM data as WAV file."""
        with wave.open(filename, "wb") as wf:
            wf.setnchannels(channels)
            wf.setsampwidth(sample_width)
            wf.setframerate(rate)
            wf.writeframes(pcm)

    def generate_audio(self, text: str, output_path: str, voice: str = "Puck"):
        """
        Generates audio using Gemini TTS Preview API.
        
        Args:
            text: Text to convert to speech
            output_path: Path to save the generated audio
            voice: Voice name (Puck, Charon, Kore, Fenrir, Aoede)
        """
        try:
            print(f"Generating audio using Gemini TTS Preview ({self.model_name})...")
            print(f"Voice: {voice}")
            
            response = self.client.models.generate_content(
                model=self.model_name,
                contents=text,
                config=types.GenerateContentConfig(
                    response_modalities=["AUDIO"],
                    speech_config=types.SpeechConfig(
                        voice_config=types.VoiceConfig(
                            prebuilt_voice_config=types.PrebuiltVoiceConfig(
                                voice_name=voice,
                            )
                        )
                    ),
                )
            )
            
            # Extract raw PCM data
            # Based on user snippet: response.candidates[0].content.parts[0].inline_data.data
            if not response.candidates:
                 raise Exception("No candidates returned from Gemini API")
            
            candidate = response.candidates[0]
            if not candidate.content or not candidate.content.parts:
                 raise Exception("No content parts returned from Gemini API")

            part = candidate.content.parts[0]
            if not part.inline_data or not part.inline_data.data:
                 raise Exception("No inline data returned from Gemini API")

            pcm_data = part.inline_data.data
            
            # Save as WAV
            self._save_wave_file(output_path, pcm_data)
            print(f"✓ Audio file saved to {output_path}")
            return output_path
            
        except Exception as e:
            print(f"Error generating Gemini TTS audio: {e}")
            import traceback
            traceback.print_exc()
            raise

# Factory or simple usage
def get_tts_service(service_type: str = "pollinations") -> TTSService:
    if service_type == "pollinations":
        return PollinationsTTS()
    elif service_type == "gemini":
        return GeminiTTS()
    raise ValueError(f"Unknown TTS service: {service_type}")
