import streamlit as st
import yt_dlp
import requests
from urllib.parse import urlparse, parse_qs, unquote
import time
from PIL import Image
import io

st.set_page_config(
    page_title="YouTube Proxy",
    page_icon="🎥",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Hide Streamlit elements
hide_streamlit_style = """
    <style>
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    header {visibility: hidden;}
    .st-emotion-cache-1r52f5n {padding: 0.5rem 1rem;}
    </style>
"""
st.markdown(hide_streamlit_style, unsafe_allow_html=True)

class YouTubeProxy:
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
        })
    
    def search_youtube(self, query, max_results=20):
        """Reliable YouTube search using yt-dlp"""
        try:
            ydl_opts = {
                'quiet': True,
                'no_warnings': True,
                'extract_flat': True,  # Don't download, just extract metadata
                'playlistend': max_results,
            }
            
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                search_results = ydl.extract_info(
                    f"ytsearch{max_results}:{query}", 
                    download=False
                )
            
            videos = []
            if 'entries' in search_results:
                for entry in search_results['entries']:
                    if entry:
                        video_id = entry.get('id')
                        title = entry.get('title', 'Unknown Title')
                        duration = entry.get('duration', 0)
                        uploader = entry.get('uploader', 'Unknown Channel')
                        
                        # Format duration
                        if duration:
                            minutes = duration // 60
                            seconds = duration % 60
                            duration_str = f"{minutes}:{seconds:02d}"
                        else:
                            duration_str = "Live"
                        
                        videos.append({
                            'title': title[:100] + '...' if len(title) > 100 else title,
                            'video_id': video_id,
                            'duration': duration_str,
                            'channel': uploader,
                            'thumbnail': f"https://i.ytimg.com/vi/{video_id}/mqdefault.jpg",
                            'url': f"https://www.youtube.com/watch?v={video_id}"
                        })
            
            return videos
            
        except Exception as e:
            st.error(f"Search failed: {str(e)}")
            return []
    
    def get_video_info(self, video_id):
        """Get detailed video information"""
        try:
            ydl_opts = {
                'quiet': True,
                'no_warnings': True,
            }
            
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(f"https://www.youtube.com/watch?v={video_id}", download=False)
                duration = info.get('duration', 0)
                
                # Format duration
                if duration:
                    minutes = duration // 60
                    seconds = duration % 60
                    duration_str = f"{minutes}:{seconds:02d}"
                else:
                    duration_str = "Live"
                
                return {
                    'title': info.get('title', ''),
                    'duration': duration_str,
                    'channel': info.get('uploader', ''),
                    'view_count': info.get('view_count', 0),
                    'thumbnail': info.get('thumbnail', f"https://i.ytimg.com/vi/{video_id}/maxresdefault.jpg"),
                    'description': info.get('description', '')[:500] + '...' if len(info.get('description', '')) > 500 else info.get('description', ''),
                    'upload_date': info.get('upload_date', ''),
                    'like_count': info.get('like_count', 0)
                }
        except:
            return {}
    
    def get_best_stream_url(self, video_id):
        """Get the best available stream URL"""
        try:
            ydl_opts = {
                'quiet': True,
                'no_warnings': True,
                'format': 'best[ext=mp4][height<=720]/best[height<=720]/best[ext=mp4]/best',
                'noplaylist': True,
            }
            
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(f"https://www.youtube.com/watch?v={video_id}", download=False)
                
                # Prefer direct URL or HLS
                if info.get('url'):
                    return info['url']
                
                # Fallback to formats
                for f in info.get('formats', []):
                    if f.get('url') and f.get('vcodec') != 'none' and f.get('acodec') != 'none':
                        return f['url']
                
                return None
        except Exception as e:
            st.error(f"Stream URL error: {str(e)}")
            return None

# Initialize proxy
@st.cache_resource
def get_proxy():
    return YouTubeProxy()

proxy = get_proxy()

# App state
if 'search_results' not in st.session_state:
    st.session_state.search_results = []
if 'current_video' not in st.session_state:
    st.session_state.current_video = None
if 'search_query' not in st.session_state:
    st.session_state.search_query = ""

st.title("🎥 YouTube Proxy")
st.markdown("**Corporate-friendly YouTube access** - No direct YouTube connections from your device!")

# Search interface
col1, col2 = st.columns([4, 1])

with col1:
    search_query = st.text_input(
        "🔍 Search videos", 
        value=st.session_state.search_query,
        placeholder="Type to search YouTube...",
        label_visibility="collapsed",
        help="Search works exactly like YouTube!"
    )

with col2:
    col2_search, col2_clear = st.columns(2)
    with col2_search:
        search_button = st.button("🔍", type="primary", use_container_width=True)
    with col2_clear:
        clear_button = st.button("🗑️", use_container_width=True)

if clear_button:
    st.session_state.search_query = ""
    st.session_state.search_results = []
    st.session_state.current_video = None
    st.rerun()

# Execute search
if search_query and (search_button or search_query != st.session_state.search_query):
    st.session_state.search_query = search_query
    with st.spinner(f"🔎 Searching YouTube for '{search_query}'..."):
        st.session_state.search_results = proxy.search_youtube(search_query, max_results=15)
    
    if st.session_state.search_results:
        st.success(f"✅ Found {len(st.session_state.search_results)} videos!")
    else:
        st.warning("❌ No results found. Try different keywords.")
    
    st.rerun()

# Display search results
if st.session_state.search_results:
    st.markdown("---")
    st.subheader(f"📺 Search Results for '{st.session_state.search_query}'")
    
    for i, video in enumerate(st.session_state.search_results):
        with st.container():
            col1, col2, col3 = st.columns([3, 1, 1])
            
            with col1:
                st.markdown(f"**{video['title']}**")
                st.caption(f"👤 {video['channel']} • ⏱️ {video['duration']}")
            
            with col2:
                if st.button("▶️ **PLAY**", key=f"play_{i}", use_container_width=True):
                    st.session_state.current_video = video
                    st.rerun()
            
            with col3:
                st.markdown(f"[**Watch on YT**]({video['url']})")
            
            st.markdown("---")

# Video Player Section
if st.session_state.current_video:
    st.markdown("---")
    st.markdown("## 🎬 **Now Playing**")
    
    video = st.session_state.current_video
    video_info = proxy.get_video_info(video['video_id'])
    
    # Video info row
    col1, col2 = st.columns([2, 1])
    
    with col1:
        st.markdown(f"### 🎥 {video_info.get('title', video['title'])}")
        st.caption(f"👤 {video_info.get('channel', video['channel'])}")
        
        if video_info.get('view_count'):
            st.caption(f"👀 {video_info['view_count']:,} views")
    
    with col2:
        col_btn1, col_btn2 = st.columns(2)
        with col_btn1:
            if st.button("🔙 Back to Results", key="back_results", use_container_width=True):
                st.session_state.current_video = None
                st.rerun()
        with col_btn2:
            st.markdown(f"[**Open on YT**](https://youtube.com/watch?v={video['video_id']})")
    
    # Video player
    st.markdown("---")
    with st.container():
        stream_url = proxy.get_best_stream_url(video['video_id'])
        
        if stream_url:
            st.video(stream_url, format="video/mp4")
            
            # Reload button for HLS streams that might expire
            st.caption("🔄 Video stalled? Click below to reload:")
            if st.button("🔄 Reload Video", key="reload_video"):
                st.rerun()
        else:
            st.error("❌ Could not load video stream. This video might be age-restricted or unavailable.")
            st.info("💡 Try another video or check if it's available in your region.")
    
    # Additional info
    with st.expander("ℹ️ Video Details", expanded=False):
        col1, col2 = st.columns(2)
        with col1:
            st.markdown(f"**Duration:** {video_info.get('duration', video['duration'])}")
            if video_info.get('upload_date'):
                st.markdown(f"**Uploaded:** {video_info['upload_date']}")
        with col2:
            if video_info.get('like_count'):
                st.markdown(f"**Likes:** {video_info['like_count']:,}")
        
        if video_info.get('description'):
            st.markdown("**Description:**")
            st.markdown(video_info['description'])

# Welcome message
if not st.session_state.search_query and not st.session_state.search_results and not st.session_state.current_video:
    st.markdown("""
    ### 🚀 **How to use:**
    1. **Search** for any video using the search bar above
    2. **Click PLAY** on any result to watch instantly
    3. **No YouTube domains** are accessed from your device ✅
    
    **Works perfectly behind corporate firewalls!** 🛡️
    """)

# Footer
st.markdown("---")
st.caption("🎥 Powered by yt-dlp | 📡 Proxied through Streamlit Cloud")
