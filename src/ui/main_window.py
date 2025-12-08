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

ctk.set_appearance_mode("Dark")
ctk.set_default_color_theme("blue")

class App(ctk.CTk):
    def __init__(self):
        super().__init__()

        self.title("AI Video Creator")
        self.geometry("1000x700")

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
        self.preview_textbox = ctk.CTkTextbox(self.tab_preview, state="disabled")
        self.preview_textbox.pack(fill="both", expand=True, padx=10, pady=10)

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
        self.status_label.configure(text="Scenes Analyzed. Fetching Media...")
        
        # Step 4: Fetch Media (Parallelize this in a real app, here sequential for simplicity or batch)
        # We will just start a task to fetch all media
        self.task_manager.submit_task(
            self._fetch_all_media,
            self._on_media_fetched
        )

    def _fetch_all_media(self):
        # Iterate scenes and fetch media
        for scene in self.scenes:
            query = scene.get('visual_query')
            source = scene.get('media_source')
            
            if source == 'pexels':
                media_url = self.media_service.search_pexels(query)
                scene['media_url'] = media_url
            elif source == 'duckduckgo':
                media_url = self.media_service.search_ddg_images(query)
                scene['media_url'] = media_url
            elif source == 'pollinations':
                prompt = scene.get('image_prompt', query)
                # Generate and save
                filename = f"scene_{scene['id']}.jpg"
                path = os.path.join(Config.OUTPUT_DIR, filename)
                self.media_service.generate_image_pollinations(prompt, path)
                scene['media_path'] = path
        return self.scenes

    def _on_media_fetched(self, result, error):
        if error:
            self.status_label.configure(text=f"Error (Media): {error}", text_color="red")
        else:
            self.status_label.configure(text="Processing Complete!", text_color="green")
            self._update_preview()
            
            # Show Generate Video button
            if not hasattr(self, 'generate_video_btn'):
                self.generate_video_btn = ctk.CTkButton(
                    self.tab_input,
                    text="Generate Final Video",
                    command=self.start_video_generation,
                    fg_color="purple"
                )
                self.generate_video_btn.pack(pady=10)
            else:
                self.generate_video_btn.pack(pady=10)
        
        self.generate_btn.configure(state="normal")

    def _update_preview(self):
        self.preview_textbox.configure(state="normal")
        self.preview_textbox.delete("1.0", "end")
        
        text = "Generated Scenes:\n\n"
        for scene in self.scenes:
            text += f"Scene {scene.get('id')}:\n"
            text += f"  Text: {scene.get('text')}\n"
            text += f"  Time: {scene.get('start_time')} - {scene.get('end_time')}\n"
            text += f"  Visual: {scene.get('visual_query')} ({scene.get('media_source')})\n"
            text += f"  Media: {scene.get('media_url') or scene.get('media_path')}\n\n"
            
        self.preview_textbox.insert("0.0", text)
        self.preview_textbox.configure(state="disabled")
        self.tab_view.set("Preview")

    def _check_tasks(self):
        self.task_manager.check_results()
        self.after(100, self._check_tasks)

    def start_video_generation(self):
        """Start the final video composition."""
        if not self.scenes or not self.generated_audio_path:
            messagebox.showerror("Error", "Missing scenes or audio. Please generate preview first.")
            return
        
        self.status_label.configure(text="Generating Final Video...", text_color="blue")
        self.generate_video_btn.configure(state="disabled")
        
        output_path = os.path.join(Config.OUTPUT_DIR, "final_video.mp4")
        
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
            self.scenes,
            self.generated_audio_path,
            output_path,
            subtitle_segments
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


    def on_closing(self):
        self.task_manager.stop()
        self.destroy()

if __name__ == "__main__":
    app = App()
    app.protocol("WM_DELETE_WINDOW", app.on_closing)
    app.mainloop()
