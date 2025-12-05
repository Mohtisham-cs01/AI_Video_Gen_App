import os
from moviepy import (
    VideoFileClip, ImageClip, AudioFileClip,
    concatenate_videoclips, CompositeVideoClip, TextClip
)
import moviepy.video.fx as vfx
import requests
from src.config import Config

class VideoService:
    def __init__(self):
        self.temp_clips = []
    
    def download_media(self, url, output_path):
        """Download media file from URL."""
        try:
            print(f"Downloading: {url}")
            response = requests.get(url, stream=True, timeout=30)
            response.raise_for_status()
            
            with open(output_path, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    f.write(chunk)
            
            print(f"✓ Downloaded to {output_path}")
            return output_path
        except Exception as e:
            print(f"✗ Failed to download {url}: {e}")
            return None
    
    def trim_or_loop_video(self, video_path, target_duration):
        """
        Trim video if longer than target_duration, loop if shorter.
        
        Args:
            video_path: Path to video file
            target_duration: Target duration in seconds
        
        Returns:
            VideoFileClip with correct duration
        """
        try:
            video = VideoFileClip(video_path)
            video_duration = video.duration
            
            if video_duration > target_duration:
                # Trim video
                print(f"  Trimming video from {video_duration:.2f}s to {target_duration:.2f}s")
                # moviepy 2.x: use subclipped instead of subclip
                return video.subclipped(0, target_duration)
            elif video_duration < target_duration:
                # Loop video
                print(f"  Looping video to reach {target_duration:.2f}s")
                # moviepy 2.x: use with_effects with vfx.Loop
                return video.with_effects([vfx.Loop(duration=target_duration)])
            else:
                return video
                
        except Exception as e:
            print(f"Error processing video {video_path}: {e}")
            raise
    
    def image_to_clip(self, image_path, duration):
        """Convert image to video clip with specified duration."""
        try:
            print(f"  Creating {duration:.2f}s clip from image")
            # moviepy 2.x: duration is often set with with_duration
            return ImageClip(image_path).with_duration(duration)
        except Exception as e:
            print(f"Error converting image to clip: {e}")
            raise
    
    def create_scene_clip(self, scene, output_dir):
        """
        Create a video clip for a scene.
        
        Args:
            scene: Scene dictionary with media_url/media_path, start_time, end_time
            output_dir: Directory to save temporary files
        
        Returns:
            VideoFileClip or ImageClip
        """
        try:
            start_time = float(scene.get('start_time', 0))
            end_time = float(scene.get('end_time', start_time + 3))
            duration = end_time - start_time
            
            print(f"\nProcessing Scene {scene.get('id')}: {duration:.2f}s")
            
            # Get media path or URL
            media_path = scene.get('media_path')
            media_url = scene.get('media_url')
            
            if not media_path and media_url:
                # Download media
                filename = f"scene_{scene['id']}_media.mp4"
                if '.jpg' in media_url or '.png' in media_url:
                    filename = f"scene_{scene['id']}_media.jpg"
                
                media_path = os.path.join(output_dir, filename)
                media_path = self.download_media(media_url, media_path)
                
                if not media_path:
                    raise Exception(f"Failed to download media for scene {scene['id']}")
            
            if not media_path or not os.path.exists(media_path):
                raise Exception(f"No media found for scene {scene['id']}")
            
            # Determine if image or video
            if media_path.lower().endswith(('.jpg', '.jpeg', '.png', '.gif')):
                # Image
                clip = self.image_to_clip(media_path, duration)
            else:
                # Video
                clip = self.trim_or_loop_video(media_path, duration)
            
            self.temp_clips.append(clip)
            return clip
            
        except Exception as e:
            print(f"Error creating clip for scene {scene.get('id')}: {e}")
            raise
    
    def add_subtitles_to_video(self, video_clip, subtitle_segments):
        """
        Add subtitle text overlays to video.
        
        Args:
            video_clip: The main video clip
            subtitle_segments: List of subtitle segments with start, end, text
        
        Returns:
            CompositeVideoClip with subtitles
        """
        try:
            print("\nAdding subtitles to video...")
            
            subtitle_clips = []
            for segment in subtitle_segments:
                if 'start' not in segment or 'end' not in segment or 'text' not in segment:
                    continue
                
                text = segment['text'].strip()
                start = float(segment['start'])
                end = float(segment['end'])
                duration = end - start
                
                # Create text clip
                # moviepy 2.x TextClip might have different init signature or font handling
                # Assuming standard usage but with new methods for positioning
                txt_clip = TextClip(
                    text=text,
                    font_size=40,
                    color='white',
                    stroke_color='black',
                    stroke_width=2,
                    method='caption',
                    size=(video_clip.w - 100, None)
                )
                
                # moviepy 2.x: use with_position, with_duration, with_start
                txt_clip = txt_clip.with_position(('center', 'bottom')).with_duration(duration).with_start(start)
                subtitle_clips.append(txt_clip)
            
            if subtitle_clips:
                print(f"✓ Added {len(subtitle_clips)} subtitle clips")
                return CompositeVideoClip([video_clip] + subtitle_clips)
            else:
                return video_clip
                
        except Exception as e:
            print(f"Error adding subtitles: {e}")
            # Return video without subtitles if subtitle fails
            return video_clip
    
    def combine_scenes(self, scenes, audio_path, output_path, subtitle_segments=None):
        """
        Combine all scene clips into final video with audio.
        
        Args:
            scenes: List of scene dictionaries
            audio_path: Path to audio file
            output_path: Path to save final video
            subtitle_segments: Optional subtitle segments
        
        Returns:
            Path to final video
        """
        try:
            print("\n" + "="*60)
            print("STARTING VIDEO COMPOSITION")
            print("="*60)
            
            output_dir = os.path.dirname(output_path)
            if not os.path.exists(output_dir):
                os.makedirs(output_dir)
            
            # Create clips for each scene
            clips = []
            print("\nscenes", scenes)
            for scene in scenes:
                clip = self.create_scene_clip(scene, output_dir)
                clips.append(clip)
            
            if not clips:
                raise Exception("No clips created!")
            
            print(f"\n✓ Created {len(clips)} scene clips")
            
            # Concatenate all clips
            print("\nConcatenating clips...")
            final_video = concatenate_videoclips(clips, method="compose")
            
            # Add audio
            print("\nAdding audio track...")
            audio = AudioFileClip(audio_path)
            # moviepy 2.x: use with_audio
            final_video = final_video.with_audio(audio)
            
            # Add subtitles if provided
            if subtitle_segments:
                final_video = self.add_subtitles_to_video(final_video, subtitle_segments)
            
            # Export
            print(f"\nExporting final video to {output_path}...")
            final_video.write_videofile(
                output_path,
                codec='libx264',
                audio_codec='aac',
                fps=24,
                preset='medium'
            )
            
            # Cleanup
            print("\nCleaning up temporary clips...")
            for clip in self.temp_clips:
                clip.close()
            self.temp_clips = []
            
            print("\n" + "="*60)
            print(f"✓ VIDEO GENERATION COMPLETE: {output_path}")
            print("="*60)
            
            return output_path
            
        except Exception as e:
            print(f"\n✗ Error combining scenes: {e}")
            # Cleanup on error
            for clip in self.temp_clips:
                try:
                    clip.close()
                except:
                    pass
            self.temp_clips = []
            raise
