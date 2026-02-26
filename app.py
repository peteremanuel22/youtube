import os
import time
from typing import Dict, List, Any, Optional

import requests
import streamlit as st
import streamlit.components.v1 as components

# -----------------------------
# Streamlit page configuration
# -----------------------------
st.set_page_config(
    page_title="IPTV Player - LionHD",
    page_icon="📺",
    layout="wide",
    initial_sidebar_state="expanded",
)

# -----------------------------
# Configuration & Secrets
# -----------------------------
# You can put these in .streamlit/secrets.toml on Streamlit Cloud:
# [xtream]
# url = "http://lionzhd.com:8080"
# username = "YOUR_USERNAME"
# password = "YOUR_PASSWORD"

def _get_secret(section_key: str, key: str, default: Optional[str] = None) -> Optional[str]:
    try:
        if section_key in st.secrets and key in st.secrets[section_key]:
            return st.secrets[section_key][key]
    except Exception:
        pass
    # Fallback to flat secrets, then env, then default
    return (
        st.secrets.get(key, None)
        if hasattr(st, "secrets") else None
    ) or os.getenv(key.upper(), default)

# ⚠️ For convenience we fall back to your current hardcoded values.
#    For production, move them to st.secrets and rotate the credentials.
XSTREAM_URL = _get_secret("xtream", "url", "http://lionzhd.com:8080")
USERNAME    = _get_secret("xtream", "username", "shadyemad44")
PASSWORD    = _get_secret("xtream", "password", "3398495")

TIMEOUT = 12
CACHE_TTL_SHORT = 300   # 5 minutes
CACHE_TTL_MED   = 600   # 10 minutes


# -----------------------------
# Small utilities
# -----------------------------
def api_get(action: str, extra_params: Optional[Dict[str, Any]] = None) -> Any:
    """Generic GET to the Xtream Codes API."""
    params = {
        "username": USERNAME,
        "password": PASSWORD,
        "action": action
    }
    if extra_params:
        params.update(extra_params)
    url = f"{XSTREAM_URL}/player_api.php"
    r = requests.get(url, params=params, timeout=TIMEOUT)
    r.raise_for_status()
    return r.json()

def build_stream_url(stream_id: str, typ: str = "live", ext: Optional[str] = None) -> str:
    """
    Construct a direct stream URL:
      - live:  /live/<user>/<pass>/<stream_id>.m3u8
      - movie: /movie/<user>/<pass>/<stream_id>.mp4   (some servers use .m3u8)
    """
    if typ == "live":
        ext = ext or "m3u8"
        path = "live"
    else:
        # 'vod' or 'movie'
        ext = ext or "mp4"
        path = "movie"
    return f"{XSTREAM_URL}/{path}/{USERNAME}/{PASSWORD}/{stream_id}.{ext}"

def render_hls_player(url: str, height: int = 460, autoplay: bool = False) -> None:
    """
    Render a simple HLS-capable HTML5 player using hls.js when needed.
    Works on Streamlit Cloud without extra Python packages.
    """
    # Unique element id so multiple players don't collide
    element_id = f"video_{int(time.time() * 1000)}"
    auto_attr = "autoplay muted" if autoplay else ""
    html = f"""
    <html>
    <head>
      <meta charset="utf-8" />
      <script src="https://cdn.jsdelivr.net/npm/hls.js@latest"></script>
      <style>
        body {{ margin:0; padding:0; background-color: transparent; }}
        video {{ width: 100%; height: {height}px; background: #000; }}
      </style>
    </head>
    <body>
      <video id="{element_id}" controls {auto_attr} playsinline></video>
      <script>
        const video = document.getElementById("{element_id}");
        const src = "{url}";
        function play() {{
          if (window.Hls && Hls.isSupported() && (src.endsWith(".m3u8") || src.includes(".m3u8"))) {{
            const hls = new Hls();
            hls.loadSource(src);
            hls.attachMedia(video);
          }} else if (video.canPlayType('application/vnd.apple.mpegurl')) {{
            // Safari (native HLS)
            video.src = src;
          }} else {{
            // MP4 or direct URL fallback
            video.src = src;
          }}
        }}
        play();
      </script>
    </body>
    </html>
    """
    components.html(html, height=height + 20, scrolling=False)


# -----------------------------
# Cached API wrappers
# -----------------------------
@st.cache_data(ttl=CACHE_TTL_SHORT)
def get_auth() -> Optional[Dict[str, Any]]:
    """Authenticate and return user/server info."""
    try:
        url = f"{XSTREAM_URL}/player_api.php"
        params = {"username": USERNAME, "password": PASSWORD}
        r = requests.get(url, params=params, timeout=TIMEOUT)
        if r.status_code != 200:
            return None
        data = r.json()
        if not data or "user_info" not in data:
            return None
        return {
            "user_info": data.get("user_info", {}),
            "server_info": data.get("server_info", {})
        }
    except Exception:
        return None

@st.cache_data(ttl=CACHE_TTL_MED)
def get_live_categories() -> List[Dict[str, Any]]:
    """Get live categories (Xtream returns a list)."""
    try:
        data = api_get("get_live_categories")
        # Many servers return a list, not {"categories": [...]}
        return data if isinstance(data, list) else data.get("categories", [])
    except Exception:
        return []

@st.cache_data(ttl=CACHE_TTL_MED)
def get_vod_categories() -> List[Dict[str, Any]]:
    try:
        data = api_get("get_vod_categories")
        return data if isinstance(data, list) else data.get("categories", [])
    except Exception:
        return []

@st.cache_data(ttl=CACHE_TTL_MED)
def get_live_streams(category_id: Optional[str] = None) -> List[Dict[str, Any]]:
    try:
        extra = {}
        if category_id:
            extra["category_id"] = category_id
        data = api_get("get_live_streams", extra)
        return data if isinstance(data, list) else []
    except Exception:
        return []

@st.cache_data(ttl=CACHE_TTL_MED)
def get_vod_streams(category_id: Optional[str] = None) -> List[Dict[str, Any]]:
    try:
        extra = {}
        if category_id:
            extra["category_id"] = category_id
        data = api_get("get_vod_streams", extra)
        return data if isinstance(data, list) else []
    except Exception:
        return []

@st.cache_data(ttl=CACHE_TTL_MED)
def search_everywhere(q: str) -> List[Dict[str, Any]]:
    """Simple client-side search across live and VOD by name."""
    q_low = q.strip().lower()
    live = get_live_streams()
    vod  = get_vod_streams()
    out: List[Dict[str, Any]] = []
    for item in (live or []):
        if q_low in (item.get("name") or "").lower():
            out.append({**item, "_kind": "live"})
    for item in (vod or []):
        if q_low in (item.get("name") or "").lower():
            out.append({**item, "_kind": "vod"})
    return out


# -----------------------------
# UI
# -----------------------------
def sidebar_info(auth: Dict[str, Any]) -> None:
    st.sidebar.header("Connection")
    user = auth.get("user_info", {})
    server = auth.get("server_info", {})

    st.sidebar.success(f"✅ Logged in as **{user.get('username', 'Unknown')}**")
    st.sidebar.info(
        f"📊 Active: {user.get('active_cons', 0)}/{user.get('max_connections', 0)}"
    )
    exp = user.get("exp_date")
    st.sidebar.caption(f"⏱️ Expires: {exp if exp else 'N/A'}")

    st.sidebar.subheader("Server")
    st.sidebar.caption(f"🌐 {server.get('url', XSTREAM_URL)}")

    with st.sidebar.expander("Settings", expanded=False):
        st.caption(f"Server URL: `{XSTREAM_URL}`")
        st.caption(f"Username: `{USERNAME}`")
        # do not print password


def live_tab():
    st.header("📡 Live TV")

    cats = get_live_categories()
    cat_names = ["All"] + [c.get("category_name", f"Cat {i}") for i, c in enumerate(cats)]
    selected_cat_name = st.selectbox("Category", cat_names, index=0)

    # Resolve category_id
    cat_id = None
    if selected_cat_name != "All":
        for c in cats:
            if c.get("category_name") == selected_cat_name:
                cat_id = c.get("category_id")
                break

    streams = get_live_streams(cat_id)
    if not streams:
        st.warning("No live streams available.")
        return

    colL, colR = st.columns([2, 3], gap="medium")

    with colL:
        names = [f"{s.get('name', 'Unknown')}  ·  #{s.get('stream_id')}" for s in streams]
        idx = st.selectbox("Channel", options=range(len(names)), format_func=lambda i: names[i])
        stream = streams[idx]
        ext_choice = st.radio("Format", ["Auto (.m3u8)"], horizontal=True, key="live_fmt")

        if st.button("▶ Play", type="primary"):
            url = build_stream_url(stream.get("stream_id"), typ="live", ext="m3u8")
            st.session_state["current_live_url"] = url

    with colR:
        url = st.session_state.get("current_live_url")
        if url:
            render_hls_player(url, height=480, autoplay=False)
        else:
            st.info("Select a channel and press **Play**.")

def movies_tab():
    st.header("🎬 Movies (VOD)")
    cats = get_vod_categories()
    cat_names = ["All"] + [c.get("category_name", f"Cat {i}") for i, c in enumerate(cats)]
    selected_cat_name = st.selectbox("Movie Category", cat_names, index=0)

    cat_id = None
    if selected_cat_name != "All":
        for c in cats:
            if c.get("category_name") == selected_cat_name:
                cat_id = c.get("category_id")
                break

    streams = get_vod_streams(cat_id)
    if not streams:
        st.warning("No movies available in this category.")
        return

    colL, colR = st.columns([2, 3], gap="medium")

    with colL:
        names = [f"{s.get('name', 'Unknown')}  ·  #{s.get('stream_id')}" for s in streams]
        idx = st.selectbox("Title", options=range(min(len(names), 200)), format_func=lambda i: names[i])
        stream = streams[idx]

        fmt = st.radio("Preferred format", ["MP4 (.mp4)", "HLS (.m3u8)"], horizontal=True, key="vod_fmt")
        if st.button("▶ Play Movie", type="primary"):
            ext = "mp4" if fmt.startswith("MP4") else "m3u8"
            url = build_stream_url(stream.get("stream_id"), typ="vod", ext=ext)
            st.session_state["current_vod_url"] = url

    with colR:
        url = st.session_state.get("current_vod_url")
        if url:
            render_hls_player(url, height=480, autoplay=False)
        else:
            st.info("Pick a movie and press **Play Movie**.")

def series_tab():
    st.header("📺 Series")
    st.info("Series often require separate series/episode endpoints depending on your Xtream provider. For now, use **Search** to find series VOD entries if your provider exposes them under VOD.")

def search_tab():
    st.header("🔍 Search")
    q = st.text_input("Search across Live & Movies", placeholder="Type channel or movie name...")
    if not q:
        return
    with st.spinner("Searching..."):
        results = search_everywhere(q)

    if not results:
        st.warning("No matches found.")
        return

    st.success(f"Found {len(results)} items")

    for item in results[:40]:  # limit to 40 for performance
        cols = st.columns([4, 1, 1])
        name = item.get("name", "Unknown")
        sid = item.get("stream_id")
        kind = item.get("_kind", "live")
        cols[0].write(f"**{name}**  ·  #{sid}")
        cols[1].badge("LIVE" if kind == "live" else "VOD", variant=("blue" if kind == "live" else "green"))
        if cols[2].button("Play", key=f"play_{kind}_{sid}"):
            if kind == "live":
                st.session_state["current_live_url"] = build_stream_url(sid, "live", "m3u8")
                st.switch_page("app.py")  # simple way to refresh; optional
            else:
                st.session_state["current_vod_url"] = build_stream_url(sid, "vod", "mp4")
                st.switch_page("app.py")


def main():
    st.title("📺 LionHD IPTV Player")

    with st.spinner("Authenticating..."):
        auth = get_auth()

    if not auth:
        st.error("❌ Authentication failed. Please check credentials or server.")
        st.stop()

    # Sidebar
    sidebar_info(auth)

    # Tabs
    tab1, tab2, tab3, tab4 = st.tabs(["🏠 Live TV", "🎥 Movies", "📺 Series", "🔍 Search"])

    with tab1:
        live_tab()
    with tab2:
        movies_tab()
    with tab3:
        series_tab()
    with tab4:
        search_tab()


if __name__ == "__main__":
    main()
