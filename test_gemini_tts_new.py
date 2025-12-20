import os
import sys
from dotenv import load_dotenv

# Add root to path (optional if running from root, but good for safety)
sys.path.append(os.getcwd())

# Load env vars
load_dotenv()

from src.services.audio_service import GeminiTTS

def test_tts():
    print("Testing Gemini TTS...")
    
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        print("Error: GEMINI_API_KEY not found in environment variables.")
        return

    try:
        tts = GeminiTTS(api_key=api_key)
        output_path = "test_output.wav"
        
        text = "Hello! This is a test of the new Gemini TTS integration."
        print(f"Generating audio for: '{text}'")
        
        result_path = tts.generate_audio(text, output_path)
        
        if os.path.exists(result_path):
            print(f"Success! Audio saved to {result_path}")
            print(f"File size: {os.path.getsize(result_path)} bytes")
        else:
            print("Error: Output file was not created.")
            
    except Exception as e:
        print(f"Test failed with error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_tts()
