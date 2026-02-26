import streamlit as st
import yt_dlp
import requests
from bs4 import BeautifulSoup
import re
import base64
import io
from urllib.parse import urlparse, parse_qs, urlencode, unquote
import time
from PIL import Image
import os

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
        """Proxy YouTube search results"""
        try:
            search_url = f"https://www.youtube.com/results?search_query={unquote(query)}"
            
            response = self.session.get(search_url, timeout=30)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.text, 'html.parser')
            
            videos = []
            # Extract video data from YouTube search page
            for item in soup.find_all('div', {'id': 'dismissible'})[:max_results]:
                try:
                    title_elem = item.find('a', {'id': 'video-title'})
                    if title_elem:
                        title = title_elem.get('title', title_elem.text.strip())
                        video_id = self._extract_video_id(title_elem.get('href', ''))
                        
                        duration_elem = item.find('span', {'class': 'style-scope ytd-thumbnail-overlay-time-status-renderer'})
                        duration = duration_elem.text.strip() if duration_elem else "Live"
                        
                        channel_elem = item.find('a', {'class': 'yt-simple-endpoint style-scope yt-formatted-string'})
                        channel = channel_elem.text.strip() if channel_elem else "Unknown Channel"
                        
                        videos.append({
                            'title': title,
                            'video_id': video_id,
                            'duration': duration,
                            'channel': channel,
                            'thumbnail': f"https://i.ytimg.com/vi/{video_id}/mqdefault.jpg"
                        })
                except:
                    continue
                    
            return videos
        except Exception as e:
            st.error(f"Search error: {str(e)}")
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
                return {
                    'title': info.get('title', ''),
                    'duration': info.get('duration', 0),
                    'channel': info.get('uploader', ''),
                    'view_count': info.get('view_count', 0),
                    'thumbnail': info.get('thumbnail', ''),
                    'description': info.get('description', '')[:500] + '...' if len(info.get('description', '')) > 500 else info.get('description', '')
                }
        except:
            return {}
    
    def get_video_formats(self, video_id):
        """Get available video formats"""
        try:
            ydl_opts = {
                'quiet': True,
                'no_warnings': True,
                'format': 'best[ext=mp4]/best',
            }
            
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(f"https://www.youtube.com/watch?v={video_id}", download=False)
                formats = []
                
                for f in info.get('formats', []):
                    if f.get('vcodec') != 'none' and f.get('acodec') != 'none':
                        formats.append({
                            'format_id': f.get('format_id'),
                            'height': f.get('height'),
                            'fps': f.get('fps'),
                            'filesize': f.get('filesize'),
                            'ext': f.get('ext')
                        })
                return formats[:5]  # Limit to top 5
        except:
            return []
    
    def stream_video(self, video_id, format_id=None):
        """Stream video content"""
        try:
            ydl_opts = {
                'quiet': True,
                'no_warnings': True,
            }
            if format_id:
                ydl_opts['format'] = format_id
                
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(f"https://www.youtube.com/watch?v={video_id}", download=False)
                stream_url = info.get('url')
                
                if stream_url:
                    return stream_url
                return None
        except Exception as e:
            st.error(f"Streaming error: {str(e)}")
            return None
    
    def _extract_video_id(self, url):
        """Extract video ID from YouTube URL"""
        if not url:
            return ''
        match = re.search(r'(?:v=|\/)([0-9A-Za-z_-]{11}).*', url)
        return match.group(1) if match else ''

proxy = YouTubeProxy()

# App state
if 'search_query' not in st.session_state:
    st.session_state.search_query = ""
if 'current_video' not in st.session_state:
    st.session_state.current_video = None
if 'video_formats' not in st.session_state:
    st.session_state.video_formats = []

st.title("🎥 YouTube Proxy")
st.markdown("---")

# Search bar
col1, col2 = st.columns([3, 1])
with col1:
    search_query = st.text_input(
        "🔍 Search YouTube", 
        value=st.session_state.search_query,
        placeholder="Enter search term...",
        label_visibility="collapsed"
    )
with col2:
    search_btn = st.button("Search", type="primary")

if search_btn or search_query != st.session_state.search_query:
    st.session_state.search_query = search_query
    if search_query:
        with st.spinner("Searching YouTube..."):
            videos = proxy.search_youtube(search_query)
        
        if videos:
            st.session_state.videos = videos
        else:
            st.warning("No videos found or search failed. Try different keywords.")

# Display search results or video player
if 'videos' in st.session_state:
    for i, video in enumerate(st.session_state.videos):
        col1, col2, col3 = st.columns([3, 1, 1])
        
        with col1:
            st.markdown(f"**{video['title']}**")
            st.caption(f"📺 {video['channel']} • {video['duration']}")
        
        with col2:
            if st.button(f"▶️ Play #{i+1}", key=f"play_{i}"):
                st.session_state.current_video = video
                st.session_state.video_formats = proxy.get_video_formats(video['video_id'])
                st.rerun()
        
        with col3:
            st.markdown("**[Watch]**")
        
        st.markdown("---")

# Video player section
if st.session_state.current_video:
    st.markdown("## ▶️ Now Playing")
    
    video_info = st.session_state.current_video
    video_info_full = proxy.get_video_info(video_info['video_id'])
    
    col1, col2 = st.columns([2, 1])
    
    with col1:
        # Video player
        stream_url = proxy.stream_video(video_info['video_id'])
        if stream_url:
            st.video(stream_url)
        else:
            st.error("Could not load video stream. Try another video.")
    
    with col2:
        st.markdown(f"### {video_info_full.get('title', video_info['title'])}")
        st.markdown(f"**{video_info_full.get('channel', video_info['channel'])}**")
        
        if video_info_full.get('duration'):
            minutes = video_info_full['duration'] // 60
            seconds = video_info_full['duration'] % 60
            st.caption(f"⏱️ {minutes}:{seconds:02d}")
        
        if video_info_full.get('view_count'):
            st.caption(f"👀 {video_info_full['view_count']:,} views")
        
        st.markdown("---")
        
        # Format selector
        st.subheader("Quality")
        selected_format = st.selectbox(
            "Select quality:",
            options=st.session_state.video_formats,
            format_func=lambda f: f"{f.get('height', 'Unknown')}p" if f.get('height') else "Auto"
        )
        
        if st.button("🔄 Reload Video", key="reload_video"):
            stream_url = proxy.stream_video(video_info['video_id'], selected_format.get('format_id'))
            if stream_url:
                st.video(stream_url)
            st.rerun()
        
        # Back to search
        if st.button("🔙 Back to Search"):
            st.session_state.current_video = None
            st.session_state.video_formats = []
            st.rerun()
    
    # Description
    if video_info_full.get('description'):
        with st.expander("📝 Description"):
            st.markdown(video_info_full['description'])

# Sidebar with recent searches and favorites
st.sidebar.title("📋 Recent")
st.sidebar.markdown("No recent searches yet.")

st.sidebar.markdown("---")
st.sidebar.title("⭐ Favorites")
st.sidebar.markdown("*Add your favorites here*")