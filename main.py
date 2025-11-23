import os
import asyncio
import requests
import feedparser
import google.generativeai as genai
import edge_tts
from moviepy.editor import VideoFileClip, AudioFileClip, TextClip, CompositeVideoClip, concatenate_videoclips
from moviepy.config import change_settings

# --- CONFIGURATION ---
# We will load these from Environment Variables for safety
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
PEXELS_API_KEY = os.getenv("PEXELS_API_KEY")

# Valid RSS Feeds (Tech)
RSS_URL = "https://techcrunch.com/feed/" 

# Configure Gemini
genai.configure(api_key=GEMINI_API_KEY)

# 1. GET NEWS
def get_latest_news():
    print("📡 Scanning news feed...")
    feed = feedparser.parse(RSS_URL)
    if feed.entries:
        return feed.entries[0].title, feed.entries[0].description[:500]
    return None, None

# 2. WRITE SCRIPT (Gemini)
def generate_script_and_keywords(title, summary):
    print("🧠 Writing script with Gemini...")
    model = genai.GenerativeModel('gemini-1.5-flash') # Free, fast model
    
    prompt = f"""
    Act as a Gen-Z Tech Influencer. Write a 30-second YouTube Short script about: 
    Title: {title}
    Summary: {summary}
    
    Rules:
    1. Start with a HOOK (0-3s).
    2. Explain the news simply (3-20s).
    3. End with a Question/Engagement bait (20-30s).
    4. Plain text only. No "Scene 1", no "Camera pans". Just the spoken words.
    5. Also, at the very end, on a new line, give me ONE single word search term for stock video (e.g., "Cyberpunk", "Robot", "Bitcoin").
    
    Format:
    [Script here]
    SEARCH_TERM: [Term]
    """
    
    response = model.generate_content(prompt)
    content = response.text.strip().split("SEARCH_TERM:")
    script = content[0].strip()
    search_term = content[1].strip() if len(content) > 1 else "Technology"
    return script, search_term

# 3. GENERATE VOICE (Edge TTS - Free)
async def generate_audio(text, output_file="voiceover.mp3"):
    print("🗣️ Generating high-quality AI Voice...")
    # 'en-US-ChristopherNeural' is a great deep male voice. 
    # Try 'en-US-AriaNeural' for female.
    communicate = edge_tts.Communicate(text, "en-US-ChristopherNeural")
    await communicate.save(output_file)

# 4. GET VIDEO (Pexels)
def download_video(query, filename="background.mp4"):
    print(f"🎬 Downloading video for: {query}")
    headers = {'Authorization': PEXELS_API_KEY}
    # Orientation portrait for Shorts
    url = f"https://api.pexels.com/videos/search?query={query}&per_page=1&orientation=portrait&size=medium"
    r = requests.get(url, headers=headers)
    data = r.json()
    
    if data['videos']:
        video_url = data['videos'][0]['video_files'][0]['link']
        with open(filename, 'wb') as f:
            f.write(requests.get(video_url).content)
        return True
    return False

# 5. EDIT VIDEO
def make_short(script, audio_path, video_path):
    print("🎞️ Editing video...")
    
    # Load Audio to get duration
    audio = AudioFileClip(audio_path)
    duration = audio.duration
    
    # Load Video & Loop it if it's shorter than audio
    clip = VideoFileClip(video_path)
    if clip.duration < duration:
        clip = clip.loop(duration=duration)
    else:
        clip = clip.subclip(0, duration)
        
    # Resize/Crop to 9:16 (1080x1920)
    # Pexels portrait videos are usually good, but we force resize to be safe
    clip = clip.resize(height=1920)
    # Center crop
    clip = clip.crop(x1=clip.w/2 - 540, y1=0, width=1080, height=1920)
    
    clip = clip.set_audio(audio)
    
    # ADD SUBTITLES (Simple Center Text)
    # Note: Complex word-by-word subtitles require ImageMagick configuration 
    # that is hard on free servers. We will use a static overlay for stability.
    txt_clip = TextClip(
        script, 
        fontsize=50, 
        color='white', 
        font='DejaVuSans-Bold', # Safe Linux Font
        method='caption', 
        size=(800, None), # Wrap text
        stroke_color='black', 
        stroke_width=2
    ).set_pos('center').set_duration(duration)

    final = CompositeVideoClip([clip, txt_clip])
    final.write_videofile("final_short.mp4", fps=24, codec='libx264', audio_codec='aac')

# --- MAIN RUNNER ---
async def main():
    title, summary = get_latest_news()
    if not title:
        print("❌ No news found.")
        return

    print(f"🗞️ Story: {title}")
    
    script, search_term = generate_script_and_keywords(title, summary)
    print(f"🔍 Keyword: {search_term}")
    
    await generate_audio(script, "voiceover.mp3")
    
    if download_video(search_term, "background.mp4"):
        make_short(script, "voiceover.mp3", "background.mp4")
        print("✅ DONE! Check final_short.mp4")
    else:
        print("❌ Could not find video.")

if __name__ == "__main__":
    asyncio.run(main())