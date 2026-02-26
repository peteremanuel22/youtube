import streamlit as st
import yt_dlp
import re
import time
import random

st.set_page_config(page_title="YouTube Proxy", page_icon="🎥", layout="wide")

st.markdown("""
<style>
    .main-header {font-size: 3rem; font-weight: bold; color: #FF0000;}
    .video-container {background: #000; padding: 20px; border-radius: 10px;}
    .error-box {background: #fee; padding: 15px; border-radius: 8px; border-left: 5px solid #f87171;}
    .success-box {background: #dcfce7; padding: 15px; border-radius: 8px; border-left: 5px solid #10b981;}
</style>
""", unsafe_allow_html=True)

@st.cache_data(ttl=300)  # Cache user agent only
def get_random_user_agent():
    agents = [
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
    ]
    return random.choice(agents)

def search_videos(query, max_results=10):
    """Fixed search with retries"""
    print(f"🔍 SEARCH: {query}")
    
    for attempt in range(3):
        try:
            ydl_opts = {
                'quiet': True,
                'no_warnings': True,
                'extract_flat': True,
                'playlistend': max_results,
                'user_agent': get_random_user_agent(),
                'extractor_retries': 2,
            }
            
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(f"ytsearch{max_results}:{query}", download=False)
                entries = info.get('entries', [])
                
                videos = []
                for entry in entries:
                    if entry and entry.get('id'):
                        videos.append({
                            'id': entry['id'],
                            'title': entry.get('title', 'Unknown')[:100],
                            'channel': entry.get('uploader', 'Unknown'),
                            'duration': 'N/A',
                            'thumbnail': f"https://i.ytimg.com/vi/{entry['id']}/mqdefault.jpg"
                        })
                
                print(f"✅ SEARCH SUCCESS: {len(videos)} videos")
                return videos[:max_results]
                
        except Exception as e:
            print(f"❌ Search attempt {attempt+1} failed: {str(e)}")
            if attempt < 2:
                time.sleep(2 ** attempt)  # Exponential backoff
            continue
    
    print("❌ ALL SEARCH ATTEMPTS FAILED")
    return []

def get_video_info(video_id):
    """Get video metadata"""
    ydl_opts = {
        'quiet': True,
        'no_warnings': True,
        'user_agent': get_random_user_agent(),
    }
    
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(f"https://youtube.com/watch?v={video_id}", download=False)
            duration = info.get('duration', 0)
            return {
                'title': info.get('title', 'Unknown'),
                'channel': info.get('uploader', 'Unknown'),
                'duration': format_duration(duration),
                'views': f"{info.get('view_count', 0):,}" if info.get('view_count') else 'N/A'
            }
    except:
        return {'title': 'Unknown', 'channel': 'Unknown', 'duration': 'N/A', 'views': 'N/A'}

def get_stream_url(video_id):
    """Get working stream URL with multiple format attempts"""
    print(f"🎥 STREAM: {video_id}")
    
    formats_to_try = [
        'best[height<=720][ext=mp4]',
        'best[height<=480][ext=mp4]', 
        'worst[ext=mp4]',
        'best[height<=720]',
        'best'
    ]
    
    for fmt in formats_to_try:
        try:
            ydl_opts = {
                'quiet': True,
                'no_warnings': True,
                'format': fmt,
                'noplaylist': True,
                'user_agent': get_random_user_agent(),
                'extractor_retries': 3,
            }
            
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(f"https://youtube.com/watch?v={video_id}", download=False)
                
                # Try direct URL first
                if info.get('url') and 'manifest' not in info.get('url', '').lower():
                    print(f"✅ STREAM FOUND: {fmt}")
                    return info['url']
                
                # Try formats
                for f in info.get('formats', []):
                    if f.get('url') and f.get('vcodec') != 'none':
                        print(f"✅ FORMAT STREAM: {f.get('format_id', 'unknown')}")
                        return f['url']
                        
        except Exception as e:
            print(f"❌ Format {fmt} failed: {str(e)}")
            continue
    
    print("❌ NO STREAM URL FOUND")
    return None

def extract_video_id(url):
    patterns = [
        r'(?:v=|\/)([0-9A-Za-z_-]{11})',
        r'(?:embed\/|shorts\/)([0-9A-Za-z_-]{11})',
        r'(?:watch\?v=)([0-9A-Za-z_-]{11})',
    ]
    for pattern in patterns:
        match = re.search(pattern, url, re.IGNORECASE)
        if match:
            return match.group(1)
    return None

def format_duration(seconds):
    if seconds == 0:
        return "Live"
    m, s = divmod(seconds, 60)
    return f"{m}:{s:02d}"

# MAIN APP
st.markdown('<h1 class="main-header">🎥 YouTube Proxy</h1>', unsafe_allow_html=True)

if 'current_video' not in st.session_state:
    st.session_state.current_video = None

tab1, tab2 = st.tabs(["🔍 Search", "🔗 Direct URL"])

with tab1:
    col1, col2 = st.columns([3, 1])
    with col1:
        search_query = st.text_input("Search videos...", placeholder="Try 'cats' or 'coding tutorial'")
    with col2:
        search_btn = st.button("🔍 Search", use_container_width=True)
    
    if search_btn and search_query.strip():
        with st.spinner("🔎 Searching..."):
            videos = search_videos(search_query.strip())
        
        if videos:
            for i, video in enumerate(videos):
                col1, col2 = st.columns([3, 1])
                with col1:
                    st.markdown(f"**{video['title']}**")
                    st.caption(video['channel'])
                with col2:
                    if st.button("▶️ Play", key=f"play_{i}", use_container_width=True):
                        st.session_state.current_video = video
                        st.rerun()
        else:
            st.error("❌ No videos found. Try different keywords!")

with tab2:
    url = st.text_input("YouTube URL", placeholder="https://youtube.com/watch?v=dQw4w9WgXcQ")
    if st.button("▶️ Load Video", use_container_width=True) and url.strip():
        video_id = extract_video_id(url)
        if video_id:
            st.session_state.current_video = {'id': video_id, 'title': 'Loading...', 'channel': 'Loading...'}
            st.rerun()
        else:
            st.error("❌ Invalid YouTube URL")

# VIDEO PLAYER
if st.session_state.current_video:
    st.markdown("---")
    video_id = st.session_state.current_video['id']
    
    with st.spinner("Loading video..."):
        info = get_video_info(video_id)
    
    st.markdown(f"### 🎥 **{info['title']}**")
    st.caption(f"👤 {info['channel']} ⏱️ {info['duration']}")
    
    col1, col2 = st.columns([1, 1])
    with col1:
        if st.button("🔙 Back", use_container_width=True):
            st.session_state.current_video = None
            st.rerun()
    with col2:
        st.markdown(f"[**YouTube**](https://youtube.com/watch?v={video_id})")
    
    with st.spinner("Getting stream..."):
        stream_url = get_stream_url(video_id)
    
    if stream_url:
        st.video(stream_url)
        st.success("✅ Playing! Refresh if needed.")
    else:
        st.error("❌ Could not load this video. Try another one!")

if __name__ == "__main__":
    st.info("**Test URLs:**\nhttps://youtube.com/watch?v=dQw4w9WgXcQ\nhttps://youtube.com/watch?v=XqZsoesa55w")
