# AI Video Generation App

This application automatically creates videos from a script or an audio file. It uses AI to generate speech, find relevant stock footage, create subtitles, and combine everything into a final video.

## Features

- **Dual Input Modes**: Start with either a text script or an existing audio file.
- **AI-Powered Narration**: Utilizes Text-to-Speech (TTS) services (Pollinations AI, Gemini TTS) to convert your script into spoken audio.
- **Automatic Scene Detection**: Employs a Large Language Model (LLM) to analyze the script and intelligently divide it into distinct scenes.
- **Dynamic Media Sourcing**: For each scene, the app automatically generates search queries and fetches relevant images and videos from various sources:
    - **Pexels**: High-quality stock photos and videos.
    - **DuckDuckGo**: General image search.
    - **Pollinations AI**: AI-generated images based on descriptive prompts.
- **Subtitle Generation**: Automatically transcribes the audio to create word-level subtitles.
- **Video Compilation**: Seamlessly assembles the audio, scene media, and subtitles into a finished `.mp4` video file.
- **User-Friendly Interface**: A simple graphical user interface built with CustomTkinter lets you control the generation process, manage settings, and preview results.
- **Asynchronous Workflow**: Long-running tasks like API calls and video rendering are handled in the background, keeping the UI responsive.

## How It Works

1.  **Input**: You provide a script or upload an audio file.
2.  **Audio Generation**: If you entered a script, the app generates an audio narration using the selected TTS service.
3.  **Subtitle Creation**: The audio is processed to create timed, word-by-word subtitles.
4.  **Scene Analysis**: The script and subtitles are sent to an LLM, which breaks the narrative into scenes and creates corresponding visual queries (e.g., "A programmer writing code on a laptop").
5.  **Media Retrieval**: The app uses the visual queries to search Pexels, DuckDuckGo, or generate new images with Pollinations AI.
6.  **Video Assembly**: Finally, the `moviepy` library is used to combine the generated audio, the downloaded media for each scene, and the subtitles into a single video file.

## Getting Started

### Prerequisites

- Python 3.8+
- Git
- `ffmpeg`: This is a dependency for `moviepy` and `pydub`. Make sure it is installed and accessible in your system's PATH. You can download it from [ffmpeg.org](https://ffmpeg.org/download.html).

### Installation

1.  **Clone the repository:**
    ```bash
    git clone <your-repository-url>
    cd AI_Video_Gen_App
    ```

2.  **Create a virtual environment (recommended):**
    ```bash
    python -m venv venv
    source venv/bin/activate  # On Windows, use `venv\Scripts\activate`
    ```

3.  **Install the required packages:**
    ```bash
    pip install -r requirements.txt
    ```

### Configuration

The application requires API keys for some services. Create a `.env` file in the root directory of the project:

```
PEXELS_API_KEY="your_pexels_api_key"
GEMINI_API_KEY="your_google_gemini_api_key"
```

You can also enter these keys in the "Settings" tab of the application.

## Usage

Run the main application file:

```bash
python main.py
```

The application window will open.
1.  **Choose your input mode**: "Script" or "Audio File".
2.  Enter your script or upload your audio.
3.  Click **"Generate Preview"**. The app will generate audio, subtitles, and analyze scenes. The progress will be shown in the status label.
4.  Once the preview is ready, you can see the scene breakdown in the "Preview" tab.
5.  Click **"Generate Final Video"** to assemble the complete video. The final output will be saved in the `output` directory.

## Key Dependencies

- **GUI**: `customtkinter`
- **Video/Audio**: `moviepy`, `pydub`, `imageio`
- **AI/ML**: `google-generativeai`, `langchain-community`
- **Web**: `requests`, `duckduckgo-search`
- **Environment**: `python-dotenv`
