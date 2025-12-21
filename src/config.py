import os
from dotenv import load_dotenv

load_dotenv()

class Config:
    PEXELS_API_KEY = os.getenv("PEXELS_API_KEY")
    POLLINATIONS_API_KEY = os.getenv("POLLINATIONS_API_KEY")
    GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
    GROQ_API_KEY = os.getenv("GROQ_API_KEY")
    POLLINATIONS_MODEL = "flux" # or other models
    WHISPER_MODEL_SIZE = "medium"
    OUTPUT_DIR = os.path.join(os.getcwd(), "output")

    @staticmethod
    def validate():
        if not Config.PEXELS_API_KEY:
            print("Warning: PEXELS_API_KEY not found in environment variables.")
