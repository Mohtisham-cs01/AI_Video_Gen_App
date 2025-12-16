import google.generativeai as genai
import os
from dotenv import load_dotenv

load_dotenv()

# Configure API key
genai.configure(api_key=os.getenv("GEMINI_API_KEY"))

print("Available models:")
print("=" * 60)

for model in genai.list_models():
    print(f"\nModel: {model.name}")
    print(f"  Display Name: {model.display_name}")
    print(f"  Supported Methods: {model.supported_generation_methods}")
    if hasattr(model, 'supported_modalities'):
        print(f"  Supported Modalities: {model.supported_modalities}")
