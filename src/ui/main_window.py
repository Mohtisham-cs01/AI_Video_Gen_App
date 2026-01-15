import customtkinter as ctk
from tkinter import filedialog, messagebox
import os
import threading
from ..services.audio_service import get_tts_service, AudioExtractor
from ..services.subtitle_service import SubtitleService
from ..services.llm_service import LLMService
from ..services.media_service import MediaService
from ..services.video_service import VideoService
from ..utils.async_utils import AsyncTaskManager
from ..utils.subtitle_utils import optimize_subtitles_for_llm
from ..config import Config
import webbrowser

ctk.set_appearance_mode("Dark")
ctk.set_default_color_theme("blue")

class SceneItem(ctk.CTkFrame):
    def __init__(self, master, scene_data, index, on_retry_callback, media_service):
        super().__init__(master)
        self.scene_data = scene_data
        self.index = index
        self.on_retry = on_retry_callback
        self.media_service = media_service
        
        self._setup_ui()
        self.update_status()

    def _setup_ui(self):
        self.grid_columnconfigure(1, weight=1)
        
        # Header: ID + Time
        header_text = f"Scene {self.scene_data.get('id')} ({self.scene_data.get('start_time')} - {self.scene_data.get('end_time')})"
        self.header_label = ctk.CTkLabel(self, text=header_text, font=ctk.CTkFont(weight="bold"))
        self.header_label.grid(row=0, column=0, columnspan=3, sticky="w", padx=10, pady=(10, 5))
        
        # Text
        self.text_label = ctk.CTkLabel(self, text=f"\"{self.scene_data.get('text')}\"", text_color="gray", wraplength=600, justify="left")
        self.text_label.grid(row=1, column=0, columnspan=3, sticky="w", padx=10, pady=5)
        
        # Controls Row
        
        # 1. Query
        ctk.CTkLabel(self, text="Visual Query:").grid(row=2, column=0, sticky="w", padx=10)
        self.query_entry = ctk.CTkEntry(self, width=200)
        self.query_entry.insert(0, self.scene_data.get('visual_query', ''))
        self.query_entry.grid(row=2, column=1, sticky="w", padx=5)
        
        # 2. Source
        ctk.CTkLabel(self, text="Source:").grid(row=2, column=2, sticky="e", padx=5)
        self.source_var = ctk.StringVar(value=self.scene_data.get('media_source', 'pexels'))
        self.source_option = ctk.CTkOptionMenu(
            self, 
            values=["pexels", "pollinations", "duckduckgo"],
            variable=self.source_var,
            width=120
        )
        self.source_option.grid(row=2, column=3, sticky="e", padx=10)
        
        # 3. Status/Media
        self.status_label = ctk.CTkLabel(self, text="Status: Pending", width=300, anchor="w")
        self.status_label.grid(row=3, column=0, columnspan=2, sticky="w", padx=10, pady=10)
        
        # 4. Upload Button
        self.upload_btn = ctk.CTkButton(self, text="📁 Upload", width=80, command=self._on_manual_upload, fg_color="gray")
        self.upload_btn.grid(row=3, column=2, sticky="e", padx=5, pady=10)

        # 5. Retry Button
        self.retry_btn = ctk.CTkButton(self, text="Fetch/Retry", width=100, command=self._on_retry_click)
        self.retry_btn.grid(row=3, column=3, sticky="e", padx=10, pady=10)

    def _on_manual_upload(self):
        """Handle manual file upload for this scene."""
        file_path = filedialog.askopenfilename(
            title=f"Select Media for Scene {self.scene_data.get('id')}",
            filetypes=[
                ("Media files", "*.mp4 *.jpg *.png *.jpeg *.mov *.avi *.mkv"),
                ("Images", "*.jpg *.png *.jpeg"),
                ("Videos", "*.mp4 *.mov *.avi *.mkv")
            ]
        )
        if file_path:
            # Update data
            self.scene_data['media_path'] = file_path
            self.scene_data['media_url'] = None
            self.scene_data['media_source'] = 'manual'
            
            # Update UI
            self.update_status()
            print(f"Manual media set for scene {self.scene_data.get('id')}: {file_path}")

    def _on_retry_click(self):
        new_query = self.query_entry.get()
        new_source = self.source_var.get()
        
        # Update local data
        self.scene_data['visual_query'] = new_query
        self.scene_data['media_source'] = new_source
        
        # Disable button
        self.retry_btn.configure(state="disabled", text="Fetching...")
        
        # Trigger parent callback
        self.on_retry(self.index, self.scene_data, self)

    def update_status(self):
        """Update UI based on scene_data state."""
        media = self.scene_data.get('media_url') or self.scene_data.get('media_path')
        if media:
            if media.startswith("http"):
                display_text = f"Ready: {media[:40]}..."
                self.status_label.configure(text=display_text, text_color="green")
                # Bind click to open URL
                self.status_label.bind("<Button-1>", lambda e: webbrowser.open(media))
                self.status_label.configure(cursor="hand2")
            else:
                display_text = f"Ready: {os.path.basename(media)}"
                self.status_label.configure(text=display_text, text_color="green")
                # Bind click to open file
                self.status_label.bind("<Button-1>", lambda e: os.startfile(media) if os.name == 'nt' else None)
                self.status_label.configure(cursor="hand2")
        else:
            self.status_label.configure(text="Status: No Media / Failed", text_color="red", cursor="")
            self.status_label.unbind("<Button-1>")
        
        self.retry_btn.configure(state="normal", text="Fetch/Retry")


class App(ctk.CTk):
    def __init__(self):
        super().__init__()

        self.title("AI Video Creator")
        self.geometry("1100x800")

        # Managers
        self.task_manager = AsyncTaskManager()


        self.tts_service = get_tts_service("pollinations")  # Use Pollinations (working)
        self.subtitle_service = SubtitleService()
        self.llm_service = LLMService()
        self.media_service = MediaService()
        self.video_service = VideoService()

        # Data
        self.input_mode = "script"  # "script" or "audio"
        self.uploaded_audio_path = None
        self.generated_audio_path = None
        self.word_subtitles = []
        self.scenes = []
        self.scene_widgets = []

        self._init_ui()
        self._check_tasks()

    def _init_ui(self):
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)

        # Sidebar
        self.sidebar_frame = ctk.CTkFrame(self, width=200, corner_radius=0)
        self.sidebar_frame.grid(row=0, column=0, sticky="nsew")
        self.sidebar_frame.grid_rowconfigure(4, weight=1)

        self.logo_label = ctk.CTkLabel(self.sidebar_frame, text="AI Video Gen", font=ctk.CTkFont(size=20, weight="bold"))
        self.logo_label.grid(row=0, column=0, padx=20, pady=(20, 10))

        self.tab_view = ctk.CTkTabview(self, width=800)
        self.tab_view.grid(row=0, column=1, padx=20, pady=20, sticky="nsew")
        
        self.tab_input = self.tab_view.add("Input")
        self.tab_preview = self.tab_view.add("Preview")
        self.tab_settings = self.tab_view.add("Settings")

        self._setup_input_tab()
        self._setup_preview_tab()
        self._setup_settings_tab()

    def _setup_input_tab(self):
        # Input Mode Selection
        mode_frame = ctk.CTkFrame(self.tab_input)
        mode_frame.pack(fill="x", pady=5)
        
        ctk.CTkLabel(mode_frame, text="Input Mode:").pack(side="left", padx=5)
        
        self.mode_var = ctk.StringVar(value="script")
        self.script_mode_radio = ctk.CTkRadioButton(mode_frame, text="Script", variable=self.mode_var, value="script", command=self.toggle_input_mode)
        self.script_mode_radio.pack(side="left", padx=10)
        
        self.audio_mode_radio = ctk.CTkRadioButton(mode_frame, text="Audio File", variable=self.mode_var, value="audio", command=self.toggle_input_mode)
        self.audio_mode_radio.pack(side="left", padx=10)
        
        # Aspect Ratio Section
        ratio_frame = ctk.CTkFrame(self.tab_input)
        ratio_frame.pack(fill="x", pady=5)
        ctk.CTkLabel(ratio_frame, text="Aspect Ratio:").pack(side="left", padx=5)
        self.ratio_var = ctk.StringVar(value="16:9")
        self.ratio_option = ctk.CTkOptionMenu(
            ratio_frame,
            values=["16:9", "9:16", "1:1"],
            variable=self.ratio_var
        )
        self.ratio_option.pack(side="left", padx=10)

        # Script Input
        self.script_label = ctk.CTkLabel(self.tab_input, text="Enter Script:")
        self.script_label.pack(pady=5, anchor="w")
        
        self.script_textbox = ctk.CTkTextbox(self.tab_input, height=200)
        self.script_textbox.pack(fill="x", pady=5)
        self.script_textbox.insert("0.0", "Enter your video script here...")

        # Audio Upload (initially hidden)
        self.audio_upload_frame = ctk.CTkFrame(self.tab_input)
        # Don't pack it yet
        
        ctk.CTkLabel(self.audio_upload_frame, text="Upload Audio File:").pack(pady=5, anchor="w")
        self.upload_audio_btn = ctk.CTkButton(self.audio_upload_frame, text="Select Audio File", command=self.upload_audio_file)
        self.upload_audio_btn.pack(anchor="w")
        self.audio_filename_label = ctk.CTkLabel(self.audio_upload_frame, text="No file selected", text_color="gray")
        self.audio_filename_label.pack(pady=5, anchor="w")

        # Generate Button
        self.generate_btn = ctk.CTkButton(self.tab_input, text="Generate Preview", command=self.start_generation, fg_color="green")
        self.generate_btn.pack(pady=20)

        self.status_label = ctk.CTkLabel(self.tab_input, text="Ready", text_color="gray")
        self.status_label.pack(pady=5)

    def _setup_preview_tab(self):
        # Header for Preview
        header_frame = ctk.CTkFrame(self.tab_preview, fg_color="transparent")
        header_frame.pack(fill="x", padx=5, pady=5)
        
        ctk.CTkLabel(header_frame, text="Scene Editor", font=ctk.CTkFont(size=16, weight="bold")).pack(side="left")
        
        # Action Buttons
        self.generate_video_btn = ctk.CTkButton(
            header_frame,
            text="Generate Final Video",
            command=self.start_video_generation,
            fg_color="purple",
            state="disabled"
        )
        self.generate_video_btn.pack(side="right")

        # Scrollable list for scenes
        self.scenes_frame = ctk.CTkScrollableFrame(self.tab_preview, width=800, height=500)
        self.scenes_frame.pack(fill="both", expand=True, padx=5, pady=5)

    def _setup_settings_tab(self):
        # Pexels API Key
        self.api_key_label = ctk.CTkLabel(self.tab_settings, text="Pexels API Key:")
        self.api_key_label.pack(pady=5, anchor="w")
        self.api_key_entry = ctk.CTkEntry(self.tab_settings, show="*")
        self.api_key_entry.pack(fill="x", pady=5)
        if Config.PEXELS_API_KEY:
            self.api_key_entry.insert(0, Config.PEXELS_API_KEY)

        # Gemini API Key
        self.gemini_key_label = ctk.CTkLabel(self.tab_settings, text="Gemini API Key (Optional):")
        self.gemini_key_label.pack(pady=5, anchor="w")
        self.gemini_key_entry = ctk.CTkEntry(self.tab_settings, show="*")
        self.gemini_key_entry.pack(fill="x", pady=5)
        if Config.GEMINI_API_KEY:
            self.gemini_key_entry.insert(0, Config.GEMINI_API_KEY)

        # Groq API Key
        self.groq_key_label = ctk.CTkLabel(self.tab_settings, text="Groq API Key (Optional, for fast transcription):")
        self.groq_key_label.pack(pady=5, anchor="w")
        self.groq_key_entry = ctk.CTkEntry(self.tab_settings, show="*")
        self.groq_key_entry.pack(fill="x", pady=5)
        if Config.GROQ_API_KEY:
            self.groq_key_entry.insert(0, Config.GROQ_API_KEY)

        # TTS Service Selection
        self.tts_label = ctk.CTkLabel(self.tab_settings, text="TTS Service:")
        self.tts_label.pack(pady=5, anchor="w")
        
        self.tts_option = ctk.CTkOptionMenu(
            self.tab_settings, 
            values=["Pollinations AI", "Gemini TTS"],
            command=self.change_tts_service
        )
        self.tts_option.pack(fill="x", pady=5)
        self.tts_option.set("Pollinations AI")  # Default (Gemini TTS not working)
        
        # Pollinations Model Selection
        self.model_label = ctk.CTkLabel(self.tab_settings, text="Pollinations Image Model:")
        self.model_label.pack(pady=5, anchor="w")
        
        self.model_frame = ctk.CTkFrame(self.tab_settings, fg_color="transparent")
        self.model_frame.pack(fill="x", pady=5)
        
        self.model_var = ctk.StringVar(value=Config.POLLINATIONS_MODEL)
        self.model_option = ctk.CTkOptionMenu(
            self.model_frame,
            variable=self.model_var,
            values=self._get_model_list_safe()
        )
        self.model_option.pack(side="left", padx=(0, 10))
        
        self.refresh_models_btn = ctk.CTkButton(
            self.model_frame,
            text="↻ Refresh",
            width=80,
            command=self.refresh_pollinations_models
        )
        self.refresh_models_btn.pack(side="left")

        # Media Sources Selection
        self.media_sources_label = ctk.CTkLabel(self.tab_settings, text="Enabled Media Sources (for AI):")
        self.media_sources_label.pack(pady=5, anchor="w")
        
        self.source_checkboxes = {}
        sources = [
            ("Stock Media (Pexels)", "pexels"),
            ("AI Image (Pollinations)", "pollinations"),
            ("Search Engine (DuckDuckGo)", "duckduckgo")
        ]
        
        self.sources_frame = ctk.CTkFrame(self.tab_settings)
        self.sources_frame.pack(fill="x", pady=5)
        
        for label, value in sources:
            var = ctk.StringVar(value=value if value in Config.ENABLED_MEDIA_SOURCES else "")
            cb = ctk.CTkCheckBox(
                self.sources_frame, 
                text=label, 
                variable=var, 
                onvalue=value, 
                offvalue=""
            )
            cb.pack(pady=2, anchor="w", padx=10)
            self.source_checkboxes[value] = var

        # Image Animation Toggle
        self.animation_var = ctk.BooleanVar(value=Config.IMAGE_ANIMATION_ENABLED)
        self.animation_cb = ctk.CTkCheckBox(
            self.tab_settings,
            text="Animate Image Scenes (Ken Burns Effect)",
            variable=self.animation_var
        )
        self.animation_cb.pack(pady=10, anchor="w")


    def _get_model_list_safe(self):
        """Helper to get models without blocking UI too long (though file read is fast)."""
        models = self.media_service.get_pollinations_models()
        return models if models else ["gptimage"] # Fallback

    def refresh_pollinations_models(self):
        """Fetch fresh models from API."""
        self.status_label.configure(text="Refreshing models...", text_color="blue")
        self.refresh_models_btn.configure(state="disabled")
        
        def _task():
            return self.media_service.fetch_pollinations_models()
            
        def _done(result, error):
            self.refresh_models_btn.configure(state="normal")
            if error:
                messagebox.showerror("Error", f"Failed to refresh models: {error}")
                self.status_label.configure(text="Model refresh failed", text_color="red")
            else:
                self.model_option.configure(values=result)
                self.status_label.configure(text="Models refreshed!", text_color="green")
                messagebox.showinfo("Success", f"Found {len(result)} models.")
        
        self.task_manager.submit_task(_task, _done)

    def change_tts_service(self, choice):
        if choice == "Pollinations AI":
            self.tts_service = get_tts_service("pollinations")
        elif choice == "Gemini TTS":
            self.tts_service = get_tts_service("gemini")
        print(f"Switched TTS service to: {choice}")

    def toggle_input_mode(self):
        """Toggle between script and audio input modes."""
        mode = self.mode_var.get()
        self.input_mode = mode
        
        if mode == "script":
            # Show script, hide audio upload
            self.script_label.pack(pady=5, anchor="w")
            self.script_textbox.pack(fill="x", pady=5)
            self.audio_upload_frame.pack_forget()
        else:
            # Hide script, show audio upload
            self.script_label.pack_forget()
            self.script_textbox.pack_forget()
            self.audio_upload_frame.pack(fill="x", pady=10)
    
    def upload_audio_file(self):
        """Handle audio file upload."""
        file_path = filedialog.askopenfilename(
            filetypes=[("Audio files", "*.mp3 *.wav *.m4a *.flac *.ogg")]
        )
        if file_path:
            self.uploaded_audio_path = file_path
            filename = os.path.basename(file_path)
            self.audio_filename_label.configure(text=f"Selected: {filename}", text_color="white")
            print(f"Audio file uploaded: {file_path}")

    def start_generation(self):
        # Update Config from UI
        self._update_config_from_ui()

        # Check input mode
        if self.input_mode == "script":
            script = self.script_textbox.get("1.0", "end-1c")
            if not script.strip() or script.strip() == "Enter your video script here...":
                messagebox.showerror("Error", "Please enter a script.")
                return
            
            self.status_label.configure(text="Generating Audio...", text_color="blue")
            self.generate_btn.configure(state="disabled")
            
            # Step 1: Generate Audio from script
            output_path = os.path.join(Config.OUTPUT_DIR, "generated_audio.mp3")
            if not os.path.exists(Config.OUTPUT_DIR):
                os.makedirs(Config.OUTPUT_DIR)
                
            self.task_manager.submit_task(
                self.tts_service.generate_audio,
                self._on_audio_generated,
                script,
                output_path
            )
        else:
            # Audio file mode
            if not self.uploaded_audio_path:
                messagebox.showerror("Error", "Please upload an audio file.")
                return
            
            self.status_label.configure(text="Processing Audio...", text_color="blue")
            self.generate_btn.configure(state="disabled")
            
            # Use uploaded audio directly
            self.generated_audio_path = self.uploaded_audio_path
            self._on_audio_generated(self.uploaded_audio_path, None)

    def _on_audio_generated(self, result, error):
        if error:
            self.status_label.configure(text=f"Error: {error}", text_color="red")
            self.generate_btn.configure(state="normal")
            return
        
        self.generated_audio_path = result
        self.status_label.configure(text="Audio Generated. Generating Subtitles...")
        
        # Show Play Audio Button
        if not hasattr(self, 'play_audio_btn'):
            self.play_audio_btn = ctk.CTkButton(self.tab_input, text="Play Audio Preview", command=self.play_audio, fg_color="blue")
            self.play_audio_btn.pack(pady=5)
        
        # Step 2: Generate Subtitles
        self.task_manager.submit_task(
            self.subtitle_service.generate_subtitles,
            self._on_subtitles_generated,
            self.generated_audio_path
        )

    def play_audio(self):
        if self.generated_audio_path and os.path.exists(self.generated_audio_path):
            try:
                if os.name == 'nt':
                    os.startfile(self.generated_audio_path)
                else:
                    import subprocess
                    subprocess.call(('xdg-open', self.generated_audio_path))
            except Exception as e:
                messagebox.showerror("Error", f"Could not play audio: {e}")

    def _on_subtitles_generated(self, result, error):
        if error:
            self.status_label.configure(text=f"Error (Subtitles): {error}", text_color="red")
            self.generate_btn.configure(state="normal")
            return

        self.word_subtitles = result
        self.status_label.configure(text="Subtitles Generated. Analyzing Scenes...")
        
        # Step 3: LLM Scene Segmentation
        script = self.script_textbox.get("1.0", "end-1c")
        
        # Optimize subtitles for LLM to save tokens
        optimized_subtitles = optimize_subtitles_for_llm(self.word_subtitles)
        
        self.task_manager.submit_task(
            self.llm_service.segment_script_and_generate_queries,
            self._on_scenes_generated,
            script,
            optimized_subtitles
        )

    def _on_scenes_generated(self, result, error):
        if error:
            self.status_label.configure(text=f"Error (LLM): {error}", text_color="red")
            self.generate_btn.configure(state="normal")
            return

        self.scenes = result.get('scenes', [])
        # Initially, media_url/media_path is None
        for scene in self.scenes:
            scene['media_url'] = None
            scene['media_path'] = None
            
        self.status_label.configure(text="Scenes Analyzed. Fetching Media...")
        
        # Immediately render scenes (status will be pending)
        self._render_scenes()
        self.tab_view.set("Preview")
        
        # Step 4: Fetch Media (All)
        self.task_manager.submit_task(
            self._fetch_all_media,
            self._on_all_media_fetched
        )
    
    def _get_aspect_ratio_settings(self):
        """Return (width, height, orientation) based on selection."""
        ratio = self.ratio_var.get()
        if ratio == "16:9":
            return (1920, 1080, "landscape")
        elif ratio == "9:16":
            return (1080, 1920, "portrait")
        elif ratio == "1:1":
            return (1080, 1080, "square")
        return (1920, 1080, "landscape")

    def _fetch_all_media(self):
        # Iterate scenes and fetch media
        for i, scene in enumerate(self.scenes):
            self._fetch_single_scene_media(scene)
            # Optional: callback to update individual row progress if we had granular callbacks
        return self.scenes

    def _fetch_single_scene_media(self, scene):
        """Fetch media for a single scene dict, modifying it in place."""
        query = scene.get('visual_query')
        source = scene.get('media_source')
        
        width, height, orientation = self._get_aspect_ratio_settings()
        
        scene['media_url'] = None # Reset
        scene['media_path'] = None # Reset
        
        try:
            if source == 'pexels':
                # Pass orientation
                media_url = self.media_service.search_pexels(query, orientation=orientation)
                scene['media_url'] = media_url
            elif source == 'duckduckgo':
                media_url = self.media_service.search_ddg_images(query)
                scene['media_url'] = media_url
            elif source == 'pollinations':
                prompt = scene.get('image_prompt', query)
                filename = f"scene_{scene['id']}_{hash(prompt)}.jpg" # unique-ish name
                path = os.path.join(Config.OUTPUT_DIR, filename)
                # Pass dimensions
                self.media_service.generate_image_pollinations(prompt, path, width, height)
                scene['media_path'] = path
        except Exception as e:
            print(f"Error fetching media for scene {scene.get('id')}: {e}")
            
    def _on_all_media_fetched(self, result, error):
        if error:
            self.status_label.configure(text=f"Error (Media): {error}", text_color="red")
        else:
            self.status_label.configure(text="Processing Complete!", text_color="green")
            self.generate_video_btn.configure(state="normal")
            
            # Update all UI rows
            for widget in self.scene_widgets:
                widget.update_status()

        self.generate_btn.configure(state="normal")

    def _render_scenes(self):
        """Clear and rebuild the scene list."""
        for widget in self.scene_widgets:
            widget.destroy()
        self.scene_widgets = []
        
        # Build widgets
        for i, scene in enumerate(self.scenes):
            item = SceneItem(self.scenes_frame, scene, i, self._retry_single_scene, self.media_service)
            item.pack(fill="x", pady=5, padx=5)
            self.scene_widgets.append(item)

    def _retry_single_scene(self, index, scene_data, widget):
        """Callback from SceneItem to retry fetching."""
        print(f"Retrying scene {index}: {scene_data['visual_query']} via {scene_data['media_source']}")
        
        # Submit single task
        self.task_manager.submit_task(
            self._fetch_single_scene_task,
            lambda res, err: self._on_single_retry_complete(res, err, widget),
            scene_data
        )

    def _fetch_single_scene_task(self, scene_data):
        self._fetch_single_scene_media(scene_data)
        return scene_data

    def _on_single_retry_complete(self, result, error, widget):
        if error:
            print(f"Retry failed: {error}")
            messagebox.showerror("Error", f"Failed to fetch media: {error}")
        
        # Result is the modified scene_data (which is same object reference anyway)
        widget.update_status()

    def _check_tasks(self):
        self.task_manager.check_results()
        self.after(100, self._check_tasks)

    def start_video_generation(self):
        """Start the final video composition."""
        if not self.scenes or not self.generated_audio_path:
            messagebox.showerror("Error", "Missing scenes or audio. Please generate preview first.")
            return
        
        # Filter valid scenes
        valid_scenes = []
        for scene in self.scenes:
            if scene.get('media_url') or (scene.get('media_path') and os.path.exists(scene.get('media_path'))):
                valid_scenes.append(scene)
            else:
                print(f"Skipping scene {scene.get('id')} due to missing media.")
        
        if not valid_scenes:
            messagebox.showerror("Error", "No valid scenes with media found. Please fix scenes in Preview tab.")
            return

        self.status_label.configure(text="Generating Final Video...", text_color="blue")
        self.generate_video_btn.configure(state="disabled")
        
        output_path = os.path.join(Config.OUTPUT_DIR, "final_video.mp4")
        
        # Get dimensions
        width, height, _ = self._get_aspect_ratio_settings()
        
        # Get subtitle segments from word_subtitles
        subtitle_segments = []
        if self.word_subtitles:
            # Convert word subtitles to phrase segments
            current_phrase = []
            phrase_start = None
            
            for word in self.word_subtitles:
                if not current_phrase:
                    phrase_start = word.get('start', 0)
                
                current_phrase.append(word.get('word', ''))
                
                # Create phrase every 5-8 words or at punctuation
                if len(current_phrase) >= 6 or word.get('word', '').strip()[-1:] in '.!?,;':
                    subtitle_segments.append({
                        'start': phrase_start,
                        'end': word.get('end', phrase_start + 2),
                        'text': ' '.join(current_phrase)
                    })
                    current_phrase = []
        
        self.task_manager.submit_task(
            self.video_service.combine_scenes,
            self._on_video_generated,
            valid_scenes,
            self.generated_audio_path,
            output_path,
            subtitle_segments,
            resolution=(width, height)
        )
    
    def _on_video_generated(self, result, error):
        """Handle video generation completion."""
        if error:
            self.status_label.configure(text=f"Error (Video): {error}", text_color="red")
            messagebox.showerror("Video Generation Failed", str(error))
        else:
            self.status_label.configure(text="✓ Final Video Generated!", text_color="green")
            messagebox.showinfo("Success", f"Video saved to:\n{result}")
            
            # Option to open video
            if messagebox.askyesno("Open Video?", "Would you like to open the video?"):
                try:
                    if os.name == 'nt':  # Windows
                        os.startfile(result)
                    else:  # Mac/Linux
                        import subprocess
                        subprocess.call(('xdg-open', result))
                except Exception as e:
                    print(f"Error opening video: {e}")
        
        self.generate_video_btn.configure(state="normal")


    def _update_config_from_ui(self):
        """Update Config singleton and .env with values from UI."""
        if hasattr(self, 'api_key_entry'):
            val = self.api_key_entry.get().strip()
            if val: Config.save_key("PEXELS_API_KEY", val)
            
        if hasattr(self, 'gemini_key_entry'):
            val = self.gemini_key_entry.get().strip()
            if val: Config.save_key("GEMINI_API_KEY", val)
            
        if hasattr(self, 'groq_key_entry'):
            val = self.groq_key_entry.get().strip()
            if val: Config.save_key("GROQ_API_KEY", val)

        if hasattr(self, 'source_checkboxes'):
            selected_sources = []
            for val, var in self.source_checkboxes.items():
                if var.get():
                    selected_sources.append(var.get())
            
            # Ensure at least one is selected, or handle empty case (default to all or pexels)
            if not selected_sources:
                 selected_sources = ["pexels", "pollinations", "duckduckgo"]
                 
            Config.ENABLED_MEDIA_SOURCES = selected_sources
            Config.save_key("ENABLED_MEDIA_SOURCES", ",".join(selected_sources))

        if hasattr(self, 'animation_var'):
            Config.IMAGE_ANIMATION_ENABLED = self.animation_var.get()
            Config.save_key("IMAGE_ANIMATION_ENABLED", str(Config.IMAGE_ANIMATION_ENABLED))

        if hasattr(self, 'model_var'):
            Config.POLLINATIONS_MODEL = self.model_var.get()
            Config.save_key("POLLINATIONS_MODEL", Config.POLLINATIONS_MODEL)


    def on_closing(self):
        self.task_manager.stop()
        self.destroy()

if __name__ == "__main__":
    app = App()
    app.protocol("WM_DELETE_WINDOW", app.on_closing)
    app.mainloop()
