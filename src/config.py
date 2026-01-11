import os
from dotenv import load_dotenv

load_dotenv()

class Config:
    PEXELS_API_KEY = os.getenv("PEXELS_API_KEY")
    POLLINATIONS_API_KEY = os.getenv("POLLINATIONS_API_KEY")
    GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
    GROQ_API_KEY = os.getenv("GROQ_API_KEY")
    POLLINATIONS_MODEL = "turbo"
    IMAGE_ANIMATION_ENABLED = os.getenv("IMAGE_ANIMATION_ENABLED", "True").lower() == "true"
    WHISPER_MODEL_SIZE = "medium"
    OUTPUT_DIR = os.path.join(os.getcwd(), "output")
    
    # Default enabled sources
    ENABLED_MEDIA_SOURCES = os.getenv("ENABLED_MEDIA_SOURCES", "pexels,pollinations,duckduckgo").split(",")

    @staticmethod
    def validate():
        if not Config.PEXELS_API_KEY:
            print("Warning: PEXELS_API_KEY not found in environment variables.")

    @staticmethod
    def save_key(key, value):
        from dotenv import set_key
        env_file = os.path.join(os.getcwd(), ".env")
        # Update memory
        setattr(Config, key, value)
        # Update file
        set_key(env_file, key, value)
