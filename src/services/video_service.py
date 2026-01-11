import os
from moviepy import (
    ColorClip, VideoFileClip, ImageClip, AudioFileClip,
    concatenate_videoclips, CompositeVideoClip, TextClip
)
import moviepy.video.fx as vfx
import requests
import mimetypes
from src.config import Config
import platform

class VideoService:
    def __init__(self):
        self.temp_clips = []
    
    def download_media(self, url, output_dir, scene_id):
        """
        Download media file from URL and determine correct extension.
        Returns the full path to the saved file.
        Explicitly rejects SVG files as they are often problematic.
        """
        try:
            print(f"Downloading: {url}")
            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
            }

            response = requests.get(url, headers=headers, stream=True, timeout=30)
            response.raise_for_status()

            # Determine extension from Content-Type or URL
            content_type = response.headers.get('content-type', '')
            ext = mimetypes.guess_extension(content_type)
            
            # Check for SVG content type
            if 'svg' in content_type or (ext and '.svg' in ext):
                raise Exception(f"Skipping SVG file (unsupported format): {url}")

            if not ext:
                # Fallback to URL parsing
                if '.jpg' in url.lower() or '.jpeg' in url.lower():
                    ext = '.jpg'
                elif '.png' in url.lower():
                    ext = '.png'
                elif '.mp4' in url.lower():
                    ext = '.mp4'
                elif '.svg' in url.lower(): # catch url based svg
                    raise Exception(f"Skipping SVG file (unsupported format): {url}")
                else:
                    ext = '.mp4' # Default fallback, potentially risky
            
            # Additional safety: check if resolved extension is svg
            if ext == '.svg':
                raise Exception(f"Skipping SVG file (unsupported format): {url}")

            # Normalize extension
            if ext == '.jpe': ext = '.jpg'
            
            filename = f"scene_{scene_id}_media{ext}"
            output_path = os.path.join(output_dir, filename)
            
            with open(output_path, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    f.write(chunk)
            
            print(f"✓ Downloaded to {output_path}")
            return output_path
        except Exception as e:
            print(f"✗ Failed to download {url}: {e}")
            raise # Re-raise to stop process
    
    def smart_fit(self, clip, target_size=(1920, 1080)):
        """
        Smart fit clip to target size without cropping.
        Compatible with MoviePy 2.2.1.
        """
        try:
            w, h = clip.w, clip.h
            target_w, target_h = target_size
            
            # Safety check
            if w is None or h is None or w == 0 or h == 0:
                print("Warning: Clip has invalid dimensions in smart_fit. Skipping resize.")
                return clip

            # Calculate aspect ratios
            clip_ratio = w / h
            target_ratio = target_w / target_h
            
            # Check if aspect ratios are similar (within 5% tolerance)
            ratio_match = abs(clip_ratio - target_ratio) / target_ratio < 0.05
            
            if ratio_match:
                new_w, new_h = target_w, target_h
            else:
                scale_x = target_w / w
                scale_y = target_h / h
                scale = min(scale_x, scale_y)
                new_w = int(w * scale)
                new_h = int(h * scale)
            
            # MoviePy 2.2.1: resized method
            return clip.resized(new_size=(new_w, new_h))
        except Exception as e:
            print(f"Error in smart_fit: {e}")
            return clip # Return original if resize fails

    def trim_or_loop_video(self, video_path, target_duration, resolution=(1920, 1080)):
        """
        Trim or loop video to match target duration and resolution.
        """
        try:
            video = VideoFileClip(video_path)
            
            # Smart fit first
            video = self.smart_fit(video, target_size=resolution)
            
            video_duration = video.duration
            
            if video_duration > target_duration:
                print(f"  Trimming video from {video_duration:.2f}s to {target_duration:.2f}s")
                return video.subclipped(0, target_duration).with_position("center")
            elif video_duration < target_duration:
                print(f"  Looping video to reach {target_duration:.2f}s")
                return video.with_effects([vfx.Loop(duration=target_duration)]).with_position("center")
            else:
                return video.with_position("center")
                
        except Exception as e:
            print(f"Error processing video {video_path}: {e}")
            raise
    
    def apply_image_animation(self, clip, resolution=(1920, 1080)):
        """
        Apply a professional Ken Burns / Slide effect to an image clip.
        Slides from upward with a subtle zoom.
        """
        try:
            w, h = resolution
            duration = clip.duration
            
            # 1. Scale up base clip slightly to have 'bleed' for movement
            # We resize to 1.3 to have plenty of room for zoom and slide
            clip = clip.resized(height=int(h * 1.3))
            
            # 2. Dynamic Zoom Calculation (Linear zoom from 100% to 115%)
            def zoom_func(t):
                return 1.0 + 0.15 * (t / duration)
            
            # Apply Zoom effect using resized with lambda (MoviePy 2.x supports this)
            # Actually, MoviePy ImageClip resized with lambda can be tricky.
            # A more robust way is to use a custom frame transition if needed, 
            # but simple position movement is usually enough for "Professional" look if done right.
            
            # 3. Dynamic Position (Slide from Top to Center)
            def pos_func(t):
                # Start 10% from the top and slide down to center
                # Since we are 1.3h, we have 0.3h extra. 
                # Total pixel range = 0.3 * h
                total_travel = 0.2 * h
                start_offset = -0.2 * h
                
                # Ease out cubic for professional feel: 1 - (1 - x)^3
                progress = t / duration
                eased_progress = 1 - (1 - progress)**2 # Quadratic ease-out is smoother
                
                current_y = start_offset + (total_travel * eased_progress)
                return ('center', int(current_y))

            # Apply position movement
            clip = clip.with_position(pos_func)
            
            return clip
        except Exception as e:
            print(f"Error applying image animation: {e}")
            return clip

    def image_to_clip(self, image_path, duration, resolution=(1920, 1080)):
        """Convert image to video clip with specified resolution."""
        try:
            print(f"  Creating {duration:.2f}s clip from image: {os.path.basename(image_path)}")
            clip = ImageClip(image_path).with_duration(duration)
            clip = self.smart_fit(clip, target_size=resolution)
            
            if Config.IMAGE_ANIMATION_ENABLED:
                print("  Applying image animation...")
                clip = self.apply_image_animation(clip, resolution)
            else:
                clip = clip.with_position("center")
                
            return clip
        except Exception as e:
            print(f"Error converting image to clip: {e}")
            raise
    
    def create_scene_clip(self, scene, output_dir, resolution=(1920, 1080)):
        """
        Create a clip for a scene, automatically handling images vs videos.
        """
        try:
            start_time = float(scene.get('start_time', 0))
            end_time = float(scene.get('end_time', start_time + 3))
            duration = end_time - start_time
            
            print(f"\nProcessing Scene {scene.get('id')}: {duration:.2f}s")
            
            media_path = scene.get('media_path')
            media_url = scene.get('media_url')
            
            # 1. Ensure we have a local file
            if not media_path and media_url:
                # Passing scene_id to let download_media decide filename/extension
                media_path = self.download_media(media_url, output_dir, scene['id'])
            
            if not media_path or not os.path.exists(media_path):
                raise Exception(f"No media available for scene {scene['id']}")
            
            # 2. Determine File Type reliably
            lower_path = media_path.lower()
            is_image = False
            
            if lower_path.endswith(('.jpg', '.jpeg', '.png', '.gif', '.bmp', '.webp')):
                is_image = True
            elif lower_path.endswith(('.mp4', '.mov', '.avi', '.mkv', '.webm')):
                is_image = False
            # Check for SVG again just in case (should be caught by download, but for local files)
            elif lower_path.endswith('.svg'):
                raise Exception("SVG files are not supported.")
            else:
                pass # Ambiguous

            # 3. Create Clip
            try:
                if is_image:
                    clip = self.image_to_clip(media_path, duration, resolution)
                else:
                    # Try as video
                    try:
                        clip = self.trim_or_loop_video(media_path, duration, resolution)
                    except OSError as e:
                        print(f"Warning: Failed to open as video ({e}). Trying as image...")
                        clip = self.image_to_clip(media_path, duration, resolution)
            except Exception as inner_e:
                raise Exception(f"Failed to create clip from {media_path}: {inner_e}")
            
            self.temp_clips.append(clip)
            return clip
            
        except Exception as e:
            print(f"Error creating clip for scene {scene.get('id')}: {e}")
            raise # Propagate error to combine_scenes
    
    def add_subtitles_to_video(self, video_clip, subtitle_segments, resolution=(1920, 1080)):
        """Add subtitle overlays."""
        try:
            print("\nAdding subtitles to video...")
            subtitle_clips = []
            
            # Adjust font size based on resolution width
            base_font_size = 50
            if resolution[0] < 1000: # Mobile/Portrait
                 base_font_size = 40
            
            # Determine font
            font_name = 'Arial'
            if platform.system() == 'Windows':
                 font_name = 'arial.ttf' # Generally safer on Windows with ImageMagick/MoviePy
            
            for segment in subtitle_segments:
                if 'start' not in segment or 'end' not in segment or 'text' not in segment:
                    continue
                
                text = segment['text'].strip()
                start = float(segment['start'])
                end = float(segment['end'])
                duration = end - start
                
                try:
                    # Create text clip
                    txt_clip = TextClip(
                        text=text,
                        font_size=base_font_size,
                        color='white',
                        stroke_color='black',
                        stroke_width=2,
                        method='caption',
                        size=(video_clip.w - 50, None),
                        font=font_name 
                    )
                except Exception as font_err:
                     print(f"Font error ({font_name}), trying default: {font_err}")
                     txt_clip = TextClip(
                        text=text,
                        font_size=base_font_size,
                        color='white',
                        stroke_color='black',
                        stroke_width=2,
                        method='caption',
                        size=(video_clip.w - 50, None)
                    )

                txt_clip = txt_clip.with_position(('center', 'bottom')).with_duration(duration).with_start(start)
                subtitle_clips.append(txt_clip)
            
            if subtitle_clips:
                print(f"✓ Added {len(subtitle_clips)} subtitle clips")
                return CompositeVideoClip([video_clip] + subtitle_clips)
            else:
                return video_clip
        except Exception as e:
            print(f"Error adding subtitles: {e}")
            return video_clip

    def combine_scenes(self, scenes, audio_path, output_path, subtitle_segments=None, resolution=(1920, 1080)):
        """Combine scenes into final video with audio."""
        try:
            print("\n" + "="*60)
            print(f"STARTING VIDEO COMPOSITION ({resolution[0]}x{resolution[1]})")
            print("="*60)
            
            output_dir = os.path.dirname(output_path)
            if not os.path.exists(output_dir):
                os.makedirs(output_dir)
            
            # Audio
            audio = AudioFileClip(audio_path)
            audio_duration = audio.duration
            
            # Background - Use resolution here
            background = ColorClip(
                size=resolution, 
                color=(0, 0, 0),
                duration=audio_duration
            )
            
            # Process Scenes
            scene_clips = []
            for scene in scenes:
                # We do NOT use try/except here so that errors bubble up and stop functionality
                clip = self.create_scene_clip(scene, output_dir, resolution)
                
                start_time = float(scene['start_time'])
                end_time = float(scene['end_time'])
                duration = end_time - start_time
                
                if clip.duration != duration:
                        clip = clip.with_duration(duration)

                clip = clip.with_start(start_time)
                
                # Ensure properly positioned - MOVED responsbility to create_scene_clip/image_to_clip
                # clip = clip.with_position("center") # REMOVED: Overwrites animation

                scene_clips.append(clip)
            
            if not scene_clips:
                raise Exception("No valid scene clips created.")

            print(f"\n✓ Creating composite with {len(scene_clips)} scenes")
            final_video = CompositeVideoClip(
                [background] + scene_clips,
                size=resolution,
                bg_color=(0, 0, 0)
            )
            
            final_video = final_video.with_audio(audio)
            
            if subtitle_segments:
                final_video = self.add_subtitles_to_video(final_video, subtitle_segments, resolution)
            
            print(f"\nExporting final video to {output_path}...")
            final_video.write_videofile(
                output_path,
                codec='libx264',
                audio_codec='aac',
                fps=24,
                threads=8,
                preset='ultrafast' 
            )
            
            print("\nCleaning up...")
            for clip in self.temp_clips:
                clip.close()
            self.temp_clips = []
            
            print("\n" + "="*60)
            print(f"✓ VIDEO GENERATION COMPLETE: {output_path}")
            print("="*60)
            return output_path
            
        except Exception as e:
            print(f"\n✗ Error combining scenes: {e}")
            for clip in self.temp_clips:
                try: clip.close()
                except: pass
            self.temp_clips = []
            # Stop the whole process if a scene fails
            raise Exception(f"Video Generation Failed: {e}")
