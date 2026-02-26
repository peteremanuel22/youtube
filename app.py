import streamlit as st
import yt_dlp
import re
import time

# Page config
st.set_page_config(
    page_title="YouTube Proxy",
    page_icon="🎥",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom CSS
st.markdown("""
<style>
    .main-header {font-size: 3rem; font-weight: bold; color: #FF0000;}
    .video-container {background: #000; padding: 20px; border-radius: 10px;}
    .error-box {background: #fee; padding: 15px; border-radius: 8px; border-left: 5px solid #f87171;}
    .success-box {background: #dcfce7; padding: 15px; border-radius: 8px; border-left: 5px solid #10b981;}
</style>
""", unsafe_allow_html=True)

def search_videos(query, max_results=15):
    """Search YouTube videos using yt-dlp (NO CACHE)"""
    print(f"🔍 Searching for: {query}")
    
    ydl_opts = {
        'quiet': True,
        'no_warnings': True,
        'extract_flat': 'in_playlist',
        'playlistend': max_results,
    }
    
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            results = ydl.extract_info(f"ytsearch{max_results}:{query}", download=False)
            print(f"✅ Search returned {len(results.get('entries', []))} results")
            
            videos = []
            for entry in results.get('entries', [])[:max_results]:
                if entry and entry.get('id'):
                    duration = entry.get('duration', 0)
                    duration_str = format_duration(duration)
                    
                    videos.append({
                        'id': entry['id'],
                        'title': (entry.get('title', 'Unknown')[:120] + '...') if len(entry.get('title', '')) > 120 else entry.get('title', 'Unknown'),
                        'channel': entry.get('uploader', 'Unknown'),
                        'duration': duration_str,
                        'thumbnail': f"https://i.ytimg.com/vi/{entry['id']}/mqdefault.jpg"
                    })
            return videos
    except Exception as e:
        print(f"❌ Search error: {str(e)}")
        return []

def get_video_info(video_id):
    """Get detailed video information (NO CACHE)"""
    ydl_opts = {
        'quiet': True,
        'no_warnings': True,
    }
    
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(f"https://www.youtube.com/watch?v={video_id}", download=False)
            duration = info.get('duration', 0)
            
            return {
                'title': info.get('title', 'Unknown'),
                'channel': info.get('uploader', 'Unknown'),
                'duration': format_duration(duration),
                'views': f"{info.get('view_count', 0):,}",
                'description': (info.get('description', '')[:300] + '...') if len(info.get('description', '')) > 300 else info.get('description', ''),
                'thumbnail': info.get('thumbnail', f"https://i.ytimg.com/vi/{video_id}/maxresdefault.jpg")
            }
    except Exception as e:
        print(f"❌ Video info error: {str(e)}")
        return {}

def get_stream_url(video_id):
    """Get direct stream URL for video (NO CACHE)"""
    print(f"🎥 Getting stream for: {video_id}")
    
    ydl_opts = {
        'quiet': True,
        'no_warnings': True,
        'format': 'best[height<=720][ext=mp4]/best[ext=mp4]/best[height<=720]/best',
        'noplaylist': True,
    }
    
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(f"https://www.youtube.com/watch?v={video_id}", download=False)
            
            # Get the best available URL
            if info.get('url'):
                return info['url']
            
            # Fallback to first available format URL
            for fmt in info.get('formats', []):
                if fmt.get('url') and fmt.get('vcodec') != 'none' and fmt.get('acodec') != 'none':
                    return fmt['url']
            
            return None
    except Exception as e:
        print(f"❌ Stream error: {str(e)}")
        return None

def extract_video_id(url):
    """Extract video ID from YouTube URL"""
    patterns = [
        r'(?:v=|\/)([0-9A-Za-z_-]{11})',
        r'(?:embed\/)([0-9A-Za-z_-]{11})',
        r'(?:watch\?v=)([0-9A-Za-z_-]{11})',
    ]
    for pattern in patterns:
        match = re.search(pattern, url)
        if match:
            return match.group(1)
    return None

def format_duration(seconds):
    """Format seconds to MM:SS"""
    if not seconds or seconds == 0:
        return "Live"
    minutes = seconds // 60
    secs = seconds % 60
    return f"{minutes}:{secs:02d}"

# Header
st.markdown('<h1 style="font-size:3rem;font-weight:bold;color:#FF0000;">🎥 YouTube Proxy</h1>', unsafe_allow_html=True)
st.markdown("**✅ Works behind corporate firewalls** - No direct YouTube connections from your device!")

# Initialize session state
if 'current_video' not in st.session_state:
    st.session_state.current_video = None

# Tabs
tab1, tab2 = st.tabs(["🔍 Search Videos", "🔗 Direct URL"])

with tab1:
    st.subheader("📺 Search YouTube")
    
    col1, col2 = st.columns([4, 1])
    with col1:
        search_query = st.text_input("", placeholder="rick roll, coding tutorial, music...", label_visibility="collapsed")
    with col2:
        search_pressed = st.button("🔍 Search", type="primary", use_container_width=True)
    
    if search_pressed and search_query.strip():
        with st.spinner(f"🔎 Searching '{search_query}'..."):
            results = search_videos(search_query.strip())
        
        if results:
            st.markdown(f'<div style="background:#dcfce7;padding:15px;border-radius:8px;border-left:5px solid #10b981;">✅ Found {len(results)} videos!</div>', unsafe_allow_html=True)
            
            for i, video in enumerate(results):
                col1, col2 = st.columns([3, 1])
                with col1:
                    st.markdown(f"**{video['title']}**")
                    st.caption(f"👤 {video['channel']}  ⏱️ {video['duration']}")
                with col2:
                    if st.button("▶️ Play", key=f"play_search_{i}", use_container_width=True):
                        st.session_state.current_video = video
                        st.rerun()
                st.markdown("---")
        else:
            st.markdown('<div style="background:#fee;padding:15px;border-radius:8px;border-left:5px solid #f87171;">❌ No videos found. Try different keywords.</div>', unsafe_allow_html=True)

with tab2:
    st.subheader("📎 Load YouTube Link")
    url_input = st.text_input("", placeholder="https://www.youtube.com/watch?v=...", label_visibility="collapsed")
    
    col_url1, col_url2 = st.columns([3, 1])
    with col_url1:
        pass
    with col_url2:
        load_pressed = st.button("▶️ Load Video", type="primary", use_container_width=True)
    
    if load_pressed and url_input.strip():
        video_id = extract_video_id(url_input.strip())
        if video_id:
            st.success(f"✅ Video ID found: `{video_id}`")
            st.session_state.current_video = {
                'id': video_id,
                'title': f"Loading {video_id}...",
                'channel': 'Loading...',
                'duration': 'Loading...'
            }
            st.rerun()
        else:
            st.error("❌ Invalid YouTube URL. Make sure it's a valid video link.")

# VIDEO PLAYER
if st.session_state.current_video:
    st.markdown("---")
    st.markdown("### 🎬 **VIDEO PLAYER**")
    
    video = st.session_state.current_video
    video_id = video['id']
    
    # Show video info
    with st.spinner("Loading video details..."):
        video_info = get_video_info(video_id)
    
    # Header
    col1, col2, col3 = st.columns([2, 1, 1])
    with col1:
        st.markdown(f"### 🎥 **{video_info.get('title', video.get('title', 'Unknown'))}**")
        st.caption(f"👤 {video_info.get('channel', video.get('channel', 'Unknown'))}  ⏱️ {video_info.get('duration', video.get('duration', 'Unknown'))}")
    
    with col2:
        if st.button("🔙 Back to Search", type="secondary", use_container_width=True):
            st.session_state.current_video = None
            st.rerun()
    
    with col3:
        st.markdown(f"[**Open on YT**](https://youtube.com/watch?v={video_id})")
    
    # Player container
    st.markdown('<div style="background:#000;padding:20px;border-radius:10px;margin:10px 0;">', unsafe_allow_html=True)
    
    stream_url = get_stream_url(video_id)
    
    if stream_url:
        st.video(stream_url)
        st.success("✅ Video playing! (Click reload if it stalls)")
        if st.button("🔄 Reload Video", use_container_width=True):
            st.rerun()
    else:
        st.error("❌ Could not load video")
        st.info("💡 Try another video - this one might be private/region-locked")
    
    st.markdown('</div>', unsafe_allow_html=True)
    
    # Video details
    with st.expander("📊 Video Info"):
        col1, col2 = st.columns(2)
        with col1:
            st.metric("Views", video_info.get('views', 'N/A'))
        with col2:
            st.markdown(f"**Length:** {video_info.get('duration', 'N/A')}")
        
        if video_info.get('description'):
            st.markdown("**Description:**")
            st.markdown(video_info['description'])

# Welcome message
if not st.session_state.current_video:
    st.info("""
    🚀 **Quick Start:**
    1. **Search tab** → Type "rick roll" → Click Play
    2. **URL tab** → Paste `https://youtube.com/watch?v=dQw4w9WgXcQ` → Load Video
    
    **Everything works through Streamlit servers** ✅
    """)

st.markdown("---")
st.caption("🎥 YouTube Proxy v2.0 | Powered by yt-dlp")
