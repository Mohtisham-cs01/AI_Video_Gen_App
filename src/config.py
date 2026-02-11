import os
from dotenv import load_dotenv

load_dotenv()

class Config:
    PEXELS_API_KEY = os.getenv("PEXELS_API_KEY")
    POLLINATIONS_API_KEY = os.getenv("POLLINATIONS_API_KEY")
    GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
    GROQ_API_KEY = os.getenv("GROQ_API_KEY")
    # POLLINATIONS_MODEL = "zimage"
    POLLINATIONS_MODEL = os.getenv("POLLINATIONS_MODEL", "zimage")
    IMAGE_ANIMATION_ENABLED = os.getenv("IMAGE_ANIMATION_ENABLED", "True").lower() == "true"
    WHISPER_MODEL_SIZE = "medium"
    OUTPUT_DIR = os.path.join(os.getcwd(), "output")
    POLLINATIONS_MODELS_FILE = os.path.join(os.getcwd(), "pollinations_models.json")
    
    # Default enabled sources
    ENABLED_MEDIA_SOURCES = os.getenv("ENABLED_MEDIA_SOURCES", "pexels,pollinations,duckduckgo").split(",")

    # User Settings File
    USER_SETTINGS_FILE = os.path.join(os.getcwd(), "user_settings.json")

    @staticmethod
    def load_user_settings():
        """Load user settings from JSON file. Returns default dict if file missing."""
        import json
        default_settings = {
            "aspect_ratio": "16:9",
            "input_mode": "script",
            "tts_service": "Pollinations AI",
            "pollinations_model": Config.POLLINATIONS_MODEL,
            "image_animation_enabled": Config.IMAGE_ANIMATION_ENABLED,
            "enabled_media_sources": Config.ENABLED_MEDIA_SOURCES
        }
        
        if os.path.exists(Config.USER_SETTINGS_FILE):
            try:
                with open(Config.USER_SETTINGS_FILE, 'r') as f:
                    saved_settings = json.load(f)
                    # Update defaults with saved values (preserves new keys if defaults expand)
                    default_settings.update(saved_settings)
                    
                    # Update Config static property if present
                    if "enabled_media_sources" in saved_settings:
                         Config.ENABLED_MEDIA_SOURCES = saved_settings["enabled_media_sources"]
                         
            except Exception as e:
                print(f"Error loading user settings: {e}")
                
        return default_settings

    @staticmethod
    def save_user_settings(settings):
        """Save user settings dict to JSON file."""
        import json
        try:
            with open(Config.USER_SETTINGS_FILE, 'w') as f:
                json.dump(settings, f, indent=4)
        except Exception as e:
            print(f"Error saving user settings: {e}")

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
