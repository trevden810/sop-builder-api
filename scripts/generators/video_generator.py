"""
Video generation script for SOP template demos
Creates promotional and instructional videos automatically
"""

import os
import json
import subprocess
from datetime import datetime
import requests
from PIL import Image, ImageDraw, ImageFont
import moviepy.editor as mp
from moviepy.video.tools.drawing import color_gradient
import numpy as np


class VideoGenerator:
    """Generate promotional videos for SOP templates"""
    
    def __init__(self, template_type):
        self.template_type = template_type
        self.assets_dir = "designs/assets"
        self.output_dir = "outputs/videos"
        self.frame_size = (1920, 1080)
        self.fps = 30
        
        # Ensure output directory exists
        os.makedirs(self.output_dir, exist_ok=True)
        
    def create_title_card(self, title, subtitle=None):
        """Create a title card image"""
        img = Image.new('RGB', self.frame_size, color='#2C3E50')
        draw = ImageDraw.Draw(img)
        
        # Try to load custom font, fall back to default
        try:
            title_font = ImageFont.truetype("arial.ttf", 80)
            subtitle_font = ImageFont.truetype("arial.ttf", 40)
        except:
            title_font = ImageFont.load_default()
            subtitle_font = ImageFont.load_default()
        
        # Draw title
        title_bbox = draw.textbbox((0, 0), title, font=title_font)
        title_width = title_bbox[2] - title_bbox[0]
        title_height = title_bbox[3] - title_bbox[1]
        
        title_x = (self.frame_size[0] - title_width) // 2
        title_y = (self.frame_size[1] - title_height) // 2 - 50
        
        draw.text((title_x, title_y), title, fill='white', font=title_font)
        
        # Draw subtitle if provided
        if subtitle:
            subtitle_bbox = draw.textbbox((0, 0), subtitle, font=subtitle_font)
            subtitle_width = subtitle_bbox[2] - subtitle_bbox[0]
            
            subtitle_x = (self.frame_size[0] - subtitle_width) // 2
            subtitle_y = title_y + title_height + 30
            
            draw.text((subtitle_x, subtitle_y), subtitle, fill='#3498DB', font=subtitle_font)
        
        return img
    
    def create_feature_slide(self, feature_title, feature_points):
        """Create a feature highlight slide"""
        img = Image.new('RGB', self.frame_size, color='white')
        draw = ImageDraw.Draw(img)
        
        try:
            title_font = ImageFont.truetype("arial.ttf", 60)
            point_font = ImageFont.truetype("arial.ttf", 36)
        except:
            title_font = ImageFont.load_default()
            point_font = ImageFont.load_default()
        
        # Draw title
        draw.text((100, 100), feature_title, fill='#2C3E50', font=title_font)
        
        # Draw feature points
        y_position = 250
        for point in feature_points:
            draw.text((150, y_position), f"✓ {point}", fill='#34495E', font=point_font)
            y_position += 80
        
        return img
    
    def create_demo_script(self):
        """Create video script based on template type"""
        scripts = {
            'restaurant': {
                'title': 'Restaurant Food Safety SOP Template',
                'subtitle': 'HACCP Compliant • FDA Approved • Health Department Ready',
                'features': [
                    {
                        'title': 'Complete Compliance Coverage',
                        'points': [
                            'FDA Food Code 2022 Updates',
                            'HACCP Principles Built-In',
                            'State-Specific Requirements',
                            'Crisis Response Protocols'
                        ]
                    },
                    {
                        'title': 'Daily Operations Made Simple',
                        'points': [
                            'Temperature Log Templates',
                            'Opening/Closing Checklists',
                            'Employee Health Screening',
                            'Delivery Inspection Forms'
                        ]
                    },
                    {
                        'title': 'Training & Documentation',
                        'points': [
                            'Staff Training Modules',
                            'Certification Tracking',
                            'Audit Trail Features',
                            'Digital Record Keeping'
                        ]
                    }
                ],
                'call_to_action': 'Get Your Restaurant SOP Template Today!'
            },
            'healthcare': {
                'title': 'Healthcare HIPAA Compliance SOP',
                'subtitle': '2025 HIPAA Updates • OCR Audit Ready • BAA Templates',
                'features': [
                    {
                        'title': 'Complete HIPAA Framework',
                        'points': [
                            'Privacy Rule Procedures',
                            'Security Rule Compliance',
                            'Breach Notification Workflows',
                            'Employee Training Records'
                        ]
                    },
                    {
                        'title': 'Risk Management Tools',
                        'points': [
                            'Risk Assessment Templates',
                            'Incident Response Plans',
                            'Vendor Management Forms',
                            'Audit Preparation Guides'
                        ]
                    }
                ],
                'call_to_action': 'Secure Your Healthcare Compliance Today!'
            }
        }
        
        return scripts.get(self.template_type, scripts['restaurant'])
    
    def generate_video_with_moviepy(self):
        """Generate video using MoviePy"""
        script = self.create_demo_script()
        clips = []
        
        # Title card (3 seconds)
        title_img = self.create_title_card(script['title'], script['subtitle'])
        title_img_path = os.path.join(self.output_dir, 'temp_title.png')
        title_img.save(title_img_path)
        
        title_clip = mp.ImageClip(title_img_path).set_duration(3)
        clips.append(title_clip)
        
        # Feature slides (4 seconds each)
        for i, feature in enumerate(script['features']):
            feature_img = self.create_feature_slide(feature['title'], feature['points'])
            feature_img_path = os.path.join(self.output_dir, f'temp_feature_{i}.png')
            feature_img.save(feature_img_path)
            
            feature_clip = mp.ImageClip(feature_img_path).set_duration(4)
            
            # Add fade in/out
            if i == 0:
                feature_clip = feature_clip.crossfadein(0.5)
            else:
                feature_clip = feature_clip.crossfadein(0.5).crossfadeout(0.5)
            
            clips.append(feature_clip)
        
        # CTA card (3 seconds)
        cta_img = self.create_title_card(script['call_to_action'], 'Visit nextlevelsbs.com/sop-templates')
        cta_img_path = os.path.join(self.output_dir, 'temp_cta.png')
        cta_img.save(cta_img_path)
        
        cta_clip = mp.ImageClip(cta_img_path).set_duration(3).crossfadein(0.5)
        clips.append(cta_clip)
        
        # Concatenate all clips
        final_video = mp.concatenate_videoclips(clips, method="compose")
        
        # Add background music if available
        music_path = os.path.join(self.assets_dir, 'background_music.mp3')
        if os.path.exists(music_path):
            audio = mp.AudioFileClip(music_path).volumex(0.3)
            audio = audio.subclip(0, final_video.duration)
            final_video = final_video.set_audio(audio)
        
        # Export video
        output_path = os.path.join(self.output_dir, f'{self.template_type}_promo.mp4')
        final_video.write_videofile(
            output_path,
            fps=self.fps,
            codec='libx264',
            audio_codec='aac'
        )
        
        # Clean up temporary files
        for temp_file in os.listdir(self.output_dir):
            if temp_file.startswith('temp_'):
                os.remove(os.path.join(self.output_dir, temp_file))
        
        return output_path
    
    def create_obs_scene_collection(self):
        """Create OBS scene collection for manual recording"""
        scenes = {
            "scenes": [
                {
                    "name": "Title",
                    "sources": [
                        {
                            "name": "Background",
                            "type": "color_source",
                            "settings": {
                                "color": 0xFF2C3E50,
                                "width": 1920,
                                "height": 1080
                            }
                        },
                        {
                            "name": "Title Text",
                            "type": "text_gdiplus",
                            "settings": {
                                "text": f"{self.template_type.title()} SOP Template",
                                "font": {
                                    "face": "Arial",
                                    "size": 72,
                                    "style": "Bold"
                                },
                                "color": 0xFFFFFFFF
                            }
                        }
                    ]
                },
                {
                    "name": "Demo",
                    "sources": [
                        {
                            "name": "Screen Capture",
                            "type": "monitor_capture",
                            "settings": {
                                "monitor": 0
                            }
                        },
                        {
                            "name": "Highlight Box",
                            "type": "color_source",
                            "settings": {
                                "color": 0xFF3498DB,
                                "width": 4,
                                "height": 400
                            }
                        }
                    ]
                },
                {
                    "name": "CTA",
                    "sources": [
                        {
                            "name": "CTA Background",
                            "type": "image_source",
                            "settings": {
                                "file": os.path.join(self.assets_dir, "cta_background.png")
                            }
                        },
                        {
                            "name": "CTA Text",
                            "type": "text_gdiplus",
                            "settings": {
                                "text": "Get Your Template Today!\\nnextlevelsbs.com/sop-templates",
                                "font": {
                                    "face": "Arial",
                                    "size": 48
                                },
                                "align": "center"
                            }
                        }
                    ]
                }
            ],
            "scene_order": ["Title", "Demo", "CTA"],
            "transitions": {
                "default": "Fade",
                "duration": 500
            }
        }
        
        # Save OBS scene collection
        obs_config_path = os.path.join(self.output_dir, f'{self.template_type}_obs_scenes.json')
        with open(obs_config_path, 'w') as f:
            json.dump(scenes, f, indent=2)
        
        return obs_config_path
    
    def generate_ai_voiceover_script(self):
        """Generate script for AI voiceover"""
        scripts = {
            'restaurant': """
            Is your restaurant ready for its next health inspection?
            
            Our comprehensive Restaurant Food Safety SOP Template includes everything you need:
            FDA Food Code 2022 compliance, HACCP principles built-in, and state-specific requirements.
            
            With daily checklists, temperature logs, and crisis response protocols,
            you'll never worry about compliance again.
            
            Get your Restaurant SOP Template today at nextlevelsbs.com/sop-templates
            """,
            'healthcare': """
            Protect your healthcare organization with our HIPAA Compliance SOP Template.
            
            Updated for 2025 regulations, it includes complete Privacy and Security Rule procedures,
            breach notification workflows, and audit preparation guides.
            
            Don't risk HIPAA violations. Get your Healthcare SOP Template today
            at nextlevelsbs.com/sop-templates
            """
        }
        
        script = scripts.get(self.template_type, scripts['restaurant'])
        
        # Save script for AI voiceover services
        script_path = os.path.join(self.output_dir, f'{self.template_type}_voiceover_script.txt')
        with open(script_path, 'w') as f:
            f.write(script)
        
        return script_path


def main():
    """Generate promotional video for SOP template"""
    import argparse
    
    parser = argparse.ArgumentParser(description='Generate SOP template video')
    parser.add_argument('--type', required=True, 
                       choices=['restaurant', 'healthcare', 'it-onboarding', 'customer-service'],
                       help='Type of SOP template')
    parser.add_argument('--method', choices=['auto', 'obs'], default='auto',
                       help='Video generation method')
    
    args = parser.parse_args()
    
    generator = VideoGenerator(args.type)
    
    if args.method == 'auto':
        # Generate video automatically with MoviePy
        video_path = generator.generate_video_with_moviepy()
        print(f"✅ Video generated: {video_path}")
    else:
        # Generate OBS scene collection for manual recording
        obs_config = generator.create_obs_scene_collection()
        print(f"✅ OBS scene collection created: {obs_config}")
    
    # Always generate voiceover script
    script_path = generator.generate_ai_voiceover_script()
    print(f"✅ Voiceover script created: {script_path}")


if __name__ == "__main__":
    main()
