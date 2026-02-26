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
# Config & Secrets
# -----------------------------
def _get_secret(section_key: str, key: str, default: Optional[str] = None) -> Optional[str]:
    try:
        if section_key in st.secrets and key in st.secrets[section_key]:
            return st.secrets[section_key][key]
    except Exception:
        pass
    return (st.secrets.get(key, None) if hasattr(st, "secrets") else None) or os.getenv(key.upper(), default)

XSTREAM_URL = _get_secret("xtream", "url", "http://lionzhd.com:8080")
USERNAME    = _get_secret("xtream", "username", "shadyemad44")
PASSWORD    = _get_secret("xtream", "password", "3398495")

REQ_TIMEOUT = 6         # tighter timeout to avoid long spinners
CACHE_TTL   = 300

def is_https_page() -> bool:
    # Heuristic: Streamlit Cloud pages are HTTPS; local dev often HTTP.
    return True  # On Streamlit Cloud this is HTTPS; adjust if needed.

def warn_mixed_content(url: str):
    if is_https_page() and url.startswith("http://"):
        st.warning(
            "This app is served over **HTTPS**, but the stream URL is **HTTP**. "
            "Modern browsers will **block** mixed content. Use an **HTTPS** stream "
            "or place a small HTTPS proxy in front of your provider.",
            icon="🔒",
        )

# -----------------------------
# Networking helpers
# -----------------------------
def api_get(action: str, extra_params: Optional[Dict[str, Any]] = None) -> Any:
    params = {"username": USERNAME, "password": PASSWORD, "action": action}
    if extra_params:
        params.update(extra_params)
    url = f"{XSTREAM_URL}/player_api.php"
    r = requests.get(url, params=params, timeout=REQ_TIMEOUT)
    r.raise_for_status()
    return r.json()

def build_stream_url(stream_id: str, typ: str = "live", ext: Optional[str] = None) -> str:
    if typ == "live":
        ext = ext or "m3u8"
        path = "live"
    else:
        ext = ext or "mp4"
        path = "movie"
    return f"{XSTREAM_URL}/{path}/{USERNAME}/{PASSWORD}/{stream_id}.{ext}"

def render_hls_player(url: str, height: int = 460, autoplay: bool = False) -> None:
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
        function init() {{
          if (window.Hls && Hls.isSupported() && (src.endsWith(".m3u8") || src.includes(".m3u8"))) {{
            const hls = new Hls();
            hls.loadSource(src);
            hls.attachMedia(video);
          }} else if (video.canPlayType('application/vnd.apple.mpegurl')) {{
            video.src = src; // Safari native HLS
          }} else {{
            video.src = src; // MP4 or direct fallback
          }}
        }}
        init();
      </script>
    </body>
    </html>
    """
    components.html(html, height=height + 20, scrolling=False)

# -----------------------------
# Cached wrappers
# -----------------------------
@st.cache_data(ttl=CACHE_TTL)
def get_auth() -> Dict[str, Any]:
    try:
        r = requests.get(
            f"{XSTREAM_URL}/player_api.php",
            params={"username": USERNAME, "password": PASSWORD},
            timeout=REQ_TIMEOUT,
        )
        if r.status_code != 200:
            return {"ok": False, "error": f"HTTP {r.status_code}"}
        data = r.json()
        if "user_info" not in data:
            return {"ok": False, "error": "No user_info in response"}
        return {"ok": True, "user_info": data.get("user_info", {}), "server_info": data.get("server_info", {})}
    except Exception as e:
        return {"ok": False, "error": str(e)}

@st.cache_data(ttl=CACHE_TTL)
def get_live_categories() -> List[Dict[str, Any]]:
    try:
        data = api_get("get_live_categories")
        return data if isinstance(data, list) else data.get("categories", [])
    except Exception:
        return []

@st.cache_data(ttl=CACHE_TTL)
def get_vod_categories() -> List[Dict[str, Any]]:
    try:
        data = api_get("get_vod_categories")
        return data if isinstance(data, list) else data.get("categories", [])
    except Exception:
        return []

@st.cache_data(ttl=CACHE_TTL)
def get_live_streams(category_id: Optional[str] = None) -> List[Dict[str, Any]]:
    try:
        extra = {"category_id": category_id} if category_id else None
        data = api_get("get_live_streams", extra)
        return data if isinstance(data, list) else []
    except Exception:
        return []

@st.cache_data(ttl=CACHE_TTL)
def get_vod_streams(category_id: Optional[str] = None) -> List[Dict[str, Any]]:
    try:
        extra = {"category_id": category_id} if category_id else None
        data = api_get("get_vod_streams", extra)
        return data if isinstance(data, list) else []
    except Exception:
        return []

def search_everywhere(q: str) -> List[Dict[str, Any]]:
    q = q.strip().lower()
    if not q:
        return []
    out: List[Dict[str, Any]] = []
    for item in get_live_streams():
        if q in (item.get("name") or "").lower():
            out.append({**item, "_kind": "live"})
    for item in get_vod_streams():
        if q in (item.get("name") or "").lower():
            out.append({**item, "_kind": "vod"})
    return out

# -----------------------------
# UI sections
# -----------------------------
def sidebar_info(auth: Dict[str, Any]):
    st.sidebar.header("Connection")
    if not auth.get("ok"):
        st.sidebar.error(f"Auth failed: {auth.get('error', 'unknown')}")
    else:
        user = auth.get("user_info", {})
        server = auth.get("server_info", {})
        st.sidebar.success(f"✅ Logged in as **{user.get('username', 'Unknown')}**")
        st.sidebar.info(f"📊 Active: {user.get('active_cons', 0)}/{user.get('max_connections', 0)}")
        st.sidebar.caption(f"⏱️ Expires: {user.get('exp_date', 'N/A')}")
        st.sidebar.caption(f"🌐 Server: {server.get('url', XSTREAM_URL)}")

    with st.sidebar.expander("Settings", expanded=False):
        st.caption(f"Server URL: `{XSTREAM_URL}`")
        st.caption(f"Username: `{USERNAME}`")
        # Avoid printing password

def live_tab():
    st.subheader("📡 Live TV")
    cats = get_live_categories()
    cat_names = ["All"] + [c.get("category_name", f"Cat {i}") for i, c in enumerate(cats)]
    selected_cat = st.selectbox("Category", cat_names, index=0)

    cat_id = None
    if selected_cat != "All":
        for c in cats:
            if c.get("category_name") == selected_cat:
                cat_id = c.get("category_id")
                break

    if st.button("Load Channels", type="secondary"):
        st.session_state["live_streams"] = get_live_streams(cat_id)

    streams = st.session_state.get("live_streams", [])
    if not streams:
        st.info("Click **Load Channels** to fetch live streams.")
        return

    colL, colR = st.columns([2, 3], gap="medium")
    with colL:
        labels = [f"{s.get('name','Unknown')} · #{s.get('stream_id')}" for s in streams]
        idx = st.selectbox("Channel", options=range(len(labels)), format_func=lambda i: labels[i])
        if st.button("▶ Play", type="primary", key="play_live"):
            url = build_stream_url(streams[idx].get("stream_id"), "live", "m3u8")
            st.session_state["current_live_url"] = url

        if st.button("🔗 Show stream URL", key="show_live_url"):
            url = build_stream_url(streams[idx].get("stream_id"), "live", "m3u8")
            st.code(url, language="text")
            warn_mixed_content(url)

    with colR:
        url = st.session_state.get("current_live_url")
        if url:
            warn_mixed_content(url)
            render_hls_player(url, height=480, autoplay=False)
        else:
            st.info("Pick a channel and press **Play**.")

def movies_tab():
    st.subheader("🎬 Movies (VOD)")
    cats = get_vod_categories()
    cat_names = ["All"] + [c.get("category_name", f"Cat {i}") for i, c in enumerate(cats)]
    selected_cat = st.selectbox("Movie Category", cat_names, index=0)

    cat_id = None
    if selected_cat != "All":
        for c in cats:
            if c.get("category_name") == selected_cat:
                cat_id = c.get("category_id")
                break

    if st.button("Load Movies", type="secondary"):
        st.session_state["vod_streams"] = get_vod_streams(cat_id)

    streams = st.session_state.get("vod_streams", [])
    if not streams:
        st.info("Click **Load Movies** to fetch VOD.")
        return

    colL, colR = st.columns([2, 3], gap="medium")
    with colL:
        labels = [f"{s.get('name','Unknown')} · #{s.get('stream_id')}" for s in streams]
        idx = st.selectbox("Title", options=range(min(len(labels), 200)), format_func=lambda i: labels[i])
        fmt = st.radio("Format", ["MP4 (.mp4)", "HLS (.m3u8)"], horizontal=True, key="vod_fmt")
        if st.button("▶ Play Movie", type="primary"):
            ext = "mp4" if fmt.startswith("MP4") else "m3u8"
            url = build_stream_url(streams[idx].get("stream_id"), "vod", ext)
            st.session_state["current_vod_url"] = url

        if st.button("🔗 Show movie URL", key="show_vod_url"):
            ext = "mp4" if fmt.startswith("MP4") else "m3u8"
            url = build_stream_url(streams[idx].get("stream_id"), "vod", ext)
            st.code(url, language="text")
            warn_mixed_content(url)

    with colR:
        url = st.session_state.get("current_vod_url")
        if url:
            warn_mixed_content(url)
            render_hls_player(url, height=480, autoplay=False)
        else:
            st.info("Pick a movie and press **Play Movie**.")

def series_tab():
    st.subheader("📺 Series")
    st.info("If your provider exposes series as VOD entries, use **Search** or VOD categories.")

def search_tab():
    st.subheader("🔍 Search")
    q = st.text_input("Search channels & movies")
    if not q:
        return
    results = search_everywhere(q)
    if not results:
        st.warning("No matches found.")
        return
    st.success(f"Found {len(results)} items.")
    for item in results[:40]:
        cols = st.columns([4,1,1])
        name = item.get("name","Unknown")
        sid = item.get("stream_id")
        kind = item.get("_kind","live")
        cols[0].write(f"**{name}** · #{sid}")
        cols[1].write("LIVE" if kind=="live" else "VOD")
        if cols[2].button("Play", key=f"play_{kind}_{sid}"):
            if kind == "live":
                st.session_state["current_live_url"] = build_stream_url(sid, "live", "m3u8")
            else:
                st.session_state["current_vod_url"] = build_stream_url(sid, "vod", "mp4")
            st.experimental_rerun()

# -----------------------------
# App
# -----------------------------
def main():
    st.title("📺 LionHD IPTV Player")
    # Try auth quickly but don't block UI
    auth = get_auth()
    sidebar_info(auth)

    tab1, tab2, tab3, tab4 = st.tabs(["🏠 Live TV", "🎥 Movies", "📺 Series", "🔍 Search"])
    with tab1:
        live_tab()
    with tab2:
        movies_tab()
    with tab3:
        series_tab()
    with tab4:
        search_tab()

    if not auth.get("ok"):
        st.info(
            "Authentication did not succeed yet. You can still try loading categories; "
            "if that fails, verify server/credentials/reachability."
        )

if __name__ == "__main__":
    main()
