import streamlit as st
import requests
import json
from streamlit_player import st_player
import pandas as pd
from typing import Dict, List, Any
import time

# Streamlit page config
st.set_page_config(
    page_title="IPTV Player - LionHD",
    page_icon="📺",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Configuration
XSTREAM_URL = "http://lionzhd.com:8080"
USERNAME = "shadyemad44"
PASSWORD = "3398495"

@st.cache_data(ttl=300)  # Cache for 5 minutes
def get_auth_token():
    """Authenticate with Xstream server"""
    try:
        auth_url = f"{XSTREAM_URL}/player_api.php"
        params = {
            "username": USERNAME,
            "password": PASSWORD
        }
        response = requests.get(auth_url, params=params, timeout=10)
        if response.status_code == 200:
            data = response.json()
            if data.get("user_info"):
                return {
                    "token": data.get("token", ""),
                    "user_info": data.get("user_info", {}),
                    "server_info": data.get("server_info", {})
                }
        return None
    except Exception as e:
        st.error(f"Authentication failed: {str(e)}")
        return None

@st.cache_data(ttl=600)
def get_categories(token: str = None) -> List[Dict]:
    """Get available categories"""
    try:
        url = f"{XSTREAM_URL}/player_api.php?username={USERNAME}&password={PASSWORD}&action=get_live_categories"
        response = requests.get(url, timeout=10)
        if response.status_code == 200:
            data = response.json()
            return data.get("categories", [])
        return []
    except:
        return []

@st.cache_data(ttl=600)
def get_live_streams(category_id: str = None) -> List[Dict]:
    """Get live streams"""
    try:
        params = {"username": USERNAME, "password": PASSWORD}
        if category_id:
            params["category_id"] = category_id
        url = f"{XSTREAM_URL}/player_api.php?action=get_live_streams"
        response = requests.get(url, params=params, timeout=10)
        if response.status_code == 200:
            data = response.json()
            return data
        return []
    except:
        return []

@st.cache_data(ttl=600)
def get_vod_streams(category_id: str = None) -> List[Dict]:
    """Get VOD (Movies/Series)"""
    try:
        params = {"username": USERNAME, "password": PASSWORD}
        if category_id:
            params["category_id"] = category_id
        url = f"{XSTREAM_URL}/player_api.php?action=get_vod_streams"
        response = requests.get(url, params=params, timeout=10)
        if response.status_code == 200:
            data = response.json()
            return data
        return []
    except:
        return []

@st.cache_data(ttl=600)
def search_content(query: str) -> List[Dict]:
    """Search across all content"""
    try:
        params = {"username": USERNAME, "password": PASSWORD, "search": query}
        url_live = f"{XSTREAM_URL}/player_api.php?action=get_live_streams"
        url_vod = f"{XSTREAM_URL}/player_api.php?action=get_vod_streams"
        
        live_results = requests.get(url_live, params=params, timeout=10).json()
        vod_results = requests.get(url_vod, params=params, timeout=10).json()
        
        return live_results + vod_results
    except:
        return []

def get_stream_url(stream_id: str, stream_type: str = "live"):
    """Get direct stream URL"""
    try:
        params = {
            "username": USERNAME,
            "password": PASSWORD,
            "action": "get_live_streams" if stream_type == "live" else "get_vod_streams",
            "stream_id": stream_id
        }
        url = f"{XSTREAM_URL}/player_api.php"
        response = requests.get(url, params=params, timeout=10)
        if response.status_code == 200:
            data = response.json()
            if data:
                return data[0].get("stream_url", "")
        return ""
    except:
        return ""

def main():
    st.title("📺 LionHD IPTV Player")
    
    # Sidebar
    st.sidebar.header("Navigation")
    
    # Authentication check
    with st.spinner("Authenticating..."):
        auth_data = get_auth_token()
    
    if not auth_data:
        st.error("❌ Authentication failed. Please check credentials.")
        st.stop()
    
    user_info = auth_data["user_info"]
    st.sidebar.success(f"✅ Logged in as: **{user_info.get('username', 'Unknown')}**")
    st.sidebar.info(f"📊 Active Connections: {user_info.get('active_cons', 0)}/{user_info.get('max_connections', 0)}")
    st.sidebar.info(f"⏱️ Expires: {user_info.get('exp_date', 'N/A')}")
    
    # Main tabs
    tab1, tab2, tab3, tab4 = st.tabs(["🏠 Live TV", "🎥 Movies", "📺 Series", "🔍 Search"])
    
    with tab1:
        st.header("📡 Live Channels")
        categories = get_categories()
        
        if categories:
            col1, col2 = st.columns([1, 3])
            
            with col1:
                st.subheader("Categories")
                selected_cat = st.selectbox("Select Category", 
                                          ["All"] + [cat["category_name"] for cat in categories],
                                          format_func=lambda x: x if x == "All" else x)
            
            with col2:
                if selected_cat == "All":
                    streams = get_live_streams()
                else:
                    cat_id = next((cat["category_id"] for cat in categories if cat["category_name"] == selected_cat), None)
                    streams = get_live_streams(cat_id)
                
                if streams:
                    for stream in streams[:20]:  # Limit to 20 for performance
                        col_a, col_b = st.columns([3, 1])
                        with col_a:
                            if st.button(f"▶️ {stream.get('name', 'Unknown')}", key=f"live_{stream.get('stream_id')}"):
                                stream_url = get_stream_url(stream["stream_id"], "live")
                                if stream_url:
                                    st_player(stream_url, height=400, config={
                                        "controls": True,
                                        "autoplay": False,
                                        "loop": False
                                    })
                                else:
                                    st.error("Failed to load stream")
                        with col_b:
                            st.info(f"{stream.get('stream_icon', '')}")
                else:
                    st.warning("No live streams available")
    
    with tab2:
        st.header("🎬 Movies")
        categories = get_categories()  # VOD categories often same as live
        
        col1, col2 = st.columns([1, 3])
        with col1:
            selected_cat = st.selectbox("Movie Category", 
                                      ["All"] + [cat["category_name"] for cat in categories[:10]],
                                      format_func=lambda x: x if x == "All" else x)
        
        with col2:
            if selected_cat == "All":
                vod_streams = get_vod_streams()
            else:
                cat_id = next((cat["category_id"] for cat in categories if cat["category_name"] == selected_cat), None)
                vod_streams = get_vod_streams(cat_id)
            
            if vod_streams:
                for stream in vod_streams[:12]:
                    col_a, col_b = st.columns([3, 1])
                    with col_a:
                        if st.button(f"🎥 {stream.get('name', 'Unknown')}", key=f"movie_{stream.get('stream_id')}"):
                            stream_url = get_stream_url(stream["stream_id"], "vod")
                            if stream_url:
                                st_player(stream_url, height=400)
                            else:
                                st.error("Failed to load movie")
                    with col_b:
                        st.caption(stream.get('rating', ''))
    
    with tab3:
        st.header("📺 Series")
        # Series often in VOD with specific categories
        st.info("Series are typically organized by category in Movies tab")
        search_query = st.text_input("Search for Series", placeholder="Enter series name")
        if search_query:
            results = search_content(search_query)
            for item in results[:10]:
                if st.button(f"📺 {item.get('name', 'Unknown')}", key=f"series_{item.get('stream_id')}"):
                    stream_url = get_stream_url(item["stream_id"], "vod")
                    if stream_url:
                        st_player(stream_url, height=400)
    
    with tab4:
        st.header("🔍 Search All Content")
        search_query = st.text_input("Search Live, Movies, Series...", placeholder="Enter search term")
        
        if search_query:
            with st.spinner("Searching..."):
                results = search_content(search_query)
            
            if results:
                st.success(f"Found {len(results)} results")
                for item in results[:15]:
                    col1, col2 = st.columns([4, 1])
                    with col1:
                        stream_type = "📡 Live" if "live" in item.get("stream_type", "").lower() else "🎥 VOD"
                        if st.button(f"{stream_type} {item.get('name', 'Unknown')}", key=f"search_{item.get('stream_id')}"):
                            stream_url = get_stream_url(item["stream_id"])
                            if stream_url:
                                st_player(stream_url, height=400)
                    with col2:
                        st.caption(item.get('category_name', ''))

if __name__ == "__main__":
    main()
