import streamlit as st
import yt_dlp
import re
from urllib.parse import urlparse, parse_qs
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

class YouTubeProxy:
    def __init__(self):
        pass
    
    @st.cache_data(ttl=300)
    def search_videos(self, query, max_results=15):
        """Search YouTube videos using yt-dlp"""
        print(f"🔍 Searching for: {query}")  # Debug log
        
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
                for entry in results.get('entries', []):
                    if entry and entry.get('id'):
                        duration = entry.get('duration', 0)
                        duration_str = self.format_duration(duration)
                        
                        videos.append({
                            'id': entry['id'],
                            'title': entry.get('title', 'Unknown')[:120],
                            'channel': entry.get('uploader', 'Unknown'),
                            'duration': duration_str,
                            'thumbnail': f"https://i.ytimg.com/vi/{entry['id']}/mqdefault.jpg"
                        })
                return videos
        except Exception as e:
            print(f"❌ Search error: {str(e)}")
            return []
    
    @st.cache_data(ttl=300)
    def get_video_info(self, video_id):
        """Get detailed video information"""
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
                    'duration': self.format_duration(duration),
                    'views': f"{info.get('view_count', 0):,}",
                    'description': info.get('description', '')[:300] + '...' if len(info.get('description', '')) > 300 else info.get('description', ''),
                    'thumbnail': info.get('thumbnail', f"https://i.ytimg.com/vi/{video_id}/maxresdefault.jpg')
                }
        except Exception as e:
            print(f"❌ Video info error: {str(e)}")
            return {}
    
    def get_stream_url(self, video_id):
        """Get direct stream URL for video"""
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
                url = info.get('url') or info.get('formats', [{}])[0].get('url')
                print(f"✅ Stream URL found: {'Yes' if url else 'No'}")
                return url
        except Exception as e:
            print(f"❌ Stream error: {str(e)}")
            return None
    
    def extract_video_id(self, url):
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
    
    @staticmethod
    def format_duration(seconds):
        if not seconds or seconds == 0:
            return "Live"
        minutes = seconds // 60
        secs = seconds % 60
        return f"{minutes}:{secs:02d}"

# Initialize proxy
proxy = YouTubeProxy()

# Header
st.markdown('<h1 class="main-header">🎥 YouTube Proxy</h1>', unsafe_allow_html=True)
st.markdown("**✅ Works behind corporate firewalls** - No direct YouTube connections!")

# Tabs for Search and URL
tab1, tab2 = st.tabs(["🔍 Search", "🔗 Direct URL"])

with tab1:
    # Search tab
    st.subheader("Search Videos")
    
    col1, col2 = st.columns([4, 1])
    with col1:
        search_query = st.text_input("Enter search term", placeholder="e.g., rick roll, coding tutorial")
    with col2:
        search_pressed = st.button("🔍 Search", type="primary")
    
    if search_pressed and search_query:
        with st.spinner("Searching YouTube..."):
            results = proxy.search_videos(search_query)
        
        if results:
            st.markdown(f'<div class="success-box">✅ Found {len(results)} videos!</div>', unsafe_allow_html=True)
            
            for i, video in enumerate(results):
                col1, col2 = st.columns([3, 1])
                with col1:
                    st.markdown(f"**{video['title']}**")
                    st.caption(f"👤 {video['channel']} • ⏱️ {video['duration']}")
                with col2:
                    if st.button("▶️ Play", key=f"search_play_{i}"):
                        st.session_state.current_video = video
                        st.session_state.video_mode = 'search'
                        st.rerun()
                st.markdown("---")
        else:
            st.markdown('<div class="error-box">❌ No videos found. Try different keywords.</div>', unsafe_allow_html=True)

with tab2:
    # Direct URL tab
    st.subheader("Load YouTube URL")
    url_input = st.text_input("Paste YouTube URL", placeholder="https://www.youtube.com/watch?v=...")
    
    if st.button("▶️ Load Video", type="primary") and url_input:
        video_id = proxy.extract_video_id(url_input)
        if video_id:
            st.session_state.current_video = {
                'id': video_id,
                'title': 'Loading...',
                'channel': 'Loading...',
                'duration': 'Loading...'
            }
            st.session_state.video_mode = 'url'
            st.rerun()
        else:
            st.error("❌ Invalid YouTube URL")

# Video Player Section
if 'current_video' in st.session_state and st.session_state.current_video:
    st.markdown("---")
    st.markdown("## 🎬 Video Player")
    
    video = st.session_state.current_video
    video_id = video['id']
    
    # Load video info
    with st.spinner("Loading video info..."):
        video_info = proxy.get_video_info(video_id)
    
    # Video header
    col1, col2, col3 = st.columns([2, 1, 1])
    with col1:
        st.markdown(f"### 🎥 **{video_info.get('title', 'Loading...')}**")
        st.caption(f"👤 {video_info.get('channel', 'Unknown')} • ⏱️ {video_info.get('duration', 'Unknown')}")
    
    with col2:
        if st.button("🔙 Back", type="secondary"):
            del st.session_state.current_video
            st.rerun()
    
    with col3:
        st.markdown(f"[**YouTube**](https://youtube.com/watch?v={video_id})")
    
    # Video player
    st.markdown('<div class="video-container">', unsafe_allow_html=True)
    
    stream_url = proxy.get_stream_url(video_id)
    
    if stream_url:
        st.video(stream_url)
        st.success("✅ Video loaded successfully!")
        
        # Reload button
        if st.button("🔄 Reload Video"):
            st.rerun()
    else:
        st.error("❌ Could not load video stream")
        st.info("💡 This video might be age-restricted, private, or region-blocked.")
    
    st.markdown('</div>', unsafe_allow_html=True)
    
    # Details
    with st.expander("ℹ️ Details"):
        col1, col2 = st.columns(2)
        with col1:
            st.metric("Views", video_info.get('views', 'N/A'))
        with col2:
            st.markdown(f"**Duration:** {video_info.get('duration', 'N/A')}")
        
        if video_info.get('description'):
            st.markdown(video_info['description'])

# Initialize session state
if 'current_video' not in st.session_state:
    st.session_state.current_video = None

# Debug info (remove in production)
with st.expander("🐛 Debug Info"):
    st.code(f"""
Session state keys: {list(st.session_state.keys())}
yt-dlp version: {yt_dlp.version.__version__}
Current video: {getattr(st.session_state.current_video, 'id', 'None')}
    """)

# Footer
st.markdown("---")
st.caption("🎥 YouTube Proxy | Powered by yt-dlp | Deployed on Streamlit Cloud")
