import os
import time
from typing import Dict, List, Any, Optional, Tuple

import requests
import streamlit as st
import streamlit.components.v1 as components

# =========================================================
# Page configuration
# =========================================================
st.set_page_config(
    page_title="IPTV Player - LionHD",
    page_icon="📺",
    layout="wide",
    initial_sidebar_state="expanded",
)

# =========================================================
# Configuration & Secrets
# =========================================================
def _get_secret(section_key: str, key: str, default: Optional[str] = None) -> Optional[str]:
    try:
        if section_key in st.secrets and key in st.secrets[section_key]:
            return st.secrets[section_key][key]
    except Exception:
        pass
    return (st.secrets.get(key, None) if hasattr(st, "secrets") else None) or os.getenv(key.upper(), default)

# Fallback to your provided values if no secrets are present.
XSTREAM_URL = _get_secret("xtream", "url", "http://lionzhd.com:8080")
USERNAME    = _get_secret("xtream", "username", "shadyemad44")
PASSWORD    = _get_secret("xtream", "password", "3398495")

# Short timeouts => no infinite spinners
REQ_TIMEOUT = 6          # seconds
CACHE_TTL   = 300        # seconds

# Simple log collector in session
if "logs" not in st.session_state:
    st.session_state["logs"] = []

def log(msg: str):
    ts = time.strftime("%H:%M:%S")
    st.session_state["logs"].append(f"[{ts}] {msg}")

def show_logs():
    if not st.session_state["logs"]:
        st.write("No logs yet.")
        return
    st.text("\n".join(st.session_state["logs"][-400:]))

def is_https_page() -> bool:
    # On Streamlit Cloud, your app is served over HTTPS.
    return True

def warn_mixed_content(url: str):
    if is_https_page() and url.startswith("http://"):
        st.warning(
            "This page is **HTTPS**, but the stream URL is **HTTP**. "
            "Browsers block mixed content, so playback will be prevented. "
            "Use an **HTTPS** stream or put an **HTTPS reverse proxy** in front of your provider.",
            icon="🔒",
        )

# =========================================================
# Networking helpers (fail-fast, never block UI forever)
# =========================================================
def _request_json(url: str, params: Optional[Dict[str, Any]] = None) -> Tuple[bool, Any, str]:
    """GET JSON with short timeout, returning (ok, data, error)."""
    try:
        r = requests.get(url, params=params, timeout=REQ_TIMEOUT)
        if r.status_code != 200:
            return False, None, f"HTTP {r.status_code}"
        # Might not always be JSON on failure; guard decoding
        try:
            return True, r.json(), ""
        except Exception as e:
            return False, None, f"Invalid JSON: {e}"
    except requests.exceptions.Timeout:
        return False, None, "Timeout"
    except requests.exceptions.ConnectionError as e:
        return False, None, f"Connection error: {e}"
    except Exception as e:
        return False, None, f"Error: {e}"

def api_get(action: str, extra_params: Optional[Dict[str, Any]] = None) -> Tuple[bool, Any, str]:
    params = {"username": USERNAME, "password": PASSWORD, "action": action}
    if extra_params:
        params.update(extra_params)
    url = f"{XSTREAM_URL}/player_api.php"
    ok, data, err = _request_json(url, params)
    return ok, data, err

def build_stream_url(stream_id: str, typ: str = "live", ext: Optional[str] = None) -> str:
    """
    live:  /live/<user>/<pass>/<id>.m3u8
    vod:   /movie/<user>/<pass>/<id>.mp4 (sometimes .m3u8 depending on provider)
    """
    if typ == "live":
        ext = ext or "m3u8"
        path = "live"
    else:
        ext = ext or "mp4"
        path = "movie"
    return f"{XSTREAM_URL}/{path}/{USERNAME}/{PASSWORD}/{stream_id}.{ext}"

def render_hls_player(url: str, height: int = 460, autoplay: bool = False) -> None:
    """HLS-capable HTML5 player using hls.js when needed."""
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
        (function() {{
          const video = document.getElementById("{element_id}");
          const src = "{url}";
          function init() {{
            const isHls = src.endsWith(".m3u8") || src.includes(".m3u8");
            if (isHls && window.Hls && Hls.isSupported()) {{
              const hls = new Hls();
              hls.loadSource(src);
              hls.attachMedia(video);
            }} else if (isHls && video.canPlayType('application/vnd.apple.mpegurl')) {{
              video.src = src; // Safari native HLS
            }} else {{
              video.src = src; // MP4 or other
            }}
          }}
          init();
        }})();
      </script>
    </body>
    </html>
    """
    components.html(html, height=height + 20, scrolling=False)

# =========================================================
# Cached wrappers (return (ok, data, err) tuples)
# =========================================================
@st.cache_data(ttl=CACHE_TTL, show_spinner=False)
def get_auth() -> Tuple[bool, Dict[str, Any], str]:
    url = f"{XSTREAM_URL}/player_api.php"
    params = {"username": USERNAME, "password": PASSWORD}
    ok, data, err = _request_json(url, params=params)
    if not ok:
        return False, {}, err
    if "user_info" not in data:
        return False, {}, "Response missing 'user_info'"
    return True, data, ""

@st.cache_data(ttl=CACHE_TTL, show_spinner=False)
def get_live_categories() -> Tuple[bool, List[Dict[str, Any]], str]:
    ok, data, err = api_get("get_live_categories")
    if not ok:
        return False, [], err
    cats = data if isinstance(data, list) else data.get("categories", [])
    return True, cats or [], ""

@st.cache_data(ttl=CACHE_TTL, show_spinner=False)
def get_vod_categories() -> Tuple[bool, List[Dict[str, Any]], str]:
    ok, data, err = api_get("get_vod_categories")
    if not ok:
        return False, [], err
    cats = data if isinstance(data, list) else data.get("categories", [])
    return True, cats or [], ""

@st.cache_data(ttl=CACHE_TTL, show_spinner=False)
def get_live_streams(category_id: Optional[str] = None) -> Tuple[bool, List[Dict[str, Any]], str]:
    extra = {"category_id": category_id} if category_id else None
    ok, data, err = api_get("get_live_streams", extra)
    if not ok:
        return False, [], err
    return True, data if isinstance(data, list) else [], ""

@st.cache_data(ttl=CACHE_TTL, show_spinner=False)
def get_vod_streams(category_id: Optional[str] = None) -> Tuple[bool, List[Dict[str, Any]], str]:
    extra = {"category_id": category_id} if category_id else None
    ok, data, err = api_get("get_vod_streams", extra)
    if not ok:
        return False, [], err
    return True, data if isinstance(data, list) else [], ""

# =========================================================
# UI helpers
# =========================================================
def sidebar_diagnostics():
    st.sidebar.header("Diagnostics")

    st.sidebar.caption(f"Server: `{XSTREAM_URL}`")
    st.sidebar.caption(f"Username: `{USERNAME}`")
    # (avoid printing password)

    if is_https_page() and XSTREAM_URL.startswith("http://"):
        st.sidebar.warning(
            "App is **HTTPS** but server is **HTTP**. Video playback will be blocked by the browser.",
            icon="⚠️",
        )

    if st.sidebar.button("Run quick diagnostics"):
        # 1) Ping base (HEAD/GET player_api without creds)
        base_ok, _, base_err = _request_json(f"{XSTREAM_URL}/player_api.php")
        log(f"Ping player_api.php → {'OK' if base_ok else 'FAIL'} ({base_err or 'reachable'})")

        # 2) Auth test
        ok, data, err = get_auth()
        if ok:
            user = data.get("user_info", {})
            log(f"Auth → OK (user={user.get('username')}, status={user.get('status','?')})")
        else:
            log(f"Auth → FAIL ({err})")

        # 3) Live cat sample
        ok, cats, err = get_live_categories()
        if ok:
            log(f"Live categories → OK (count={len(cats)})")
        else:
            log(f"Live categories → FAIL ({err})")

        # 4) Live stream sample
        ok, streams, err = get_live_streams()
        if ok:
            log(f"Live streams → OK (count={len(streams)})")
            if streams:
                sample_id = streams[0].get("stream_id")
                test_url = build_stream_url(sample_id, "live", "m3u8")
                log(f"Sample live URL: {test_url}")
        else:
            log(f"Live streams → FAIL ({err})")

        st.sidebar.success("Diagnostics complete. See logs in the bottom panel.")

def live_tab():
    st.subheader("📡 Live TV")

    ok, cats, err = get_live_categories()
    if not ok:
        st.error(f"Failed to load categories: {err}")
        return

    cat_names = ["All"] + [c.get("category_name", f"Cat {i}") for i, c in enumerate(cats)]
    selected_cat = st.selectbox("Category", cat_names, index=0)

    cat_id = None
    if selected_cat != "All":
        for c in cats:
            if c.get("category_name") == selected_cat:
                cat_id = c.get("category_id")
                break

    if st.button("Load Channels", type="secondary"):
        ok, streams, err = get_live_streams(cat_id)
        if not ok:
            st.error(f"Failed to fetch streams: {err}")
        else:
            st.session_state["live_streams"] = streams
            st.success(f"Loaded {len(streams)} channels")

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

    ok, cats, err = get_vod_categories()
    if not ok:
        st.error(f"Failed to load categories: {err}")
        return

    cat_names = ["All"] + [c.get("category_name", f"Cat {i}") for i, c in enumerate(cats)]
    selected_cat = st.selectbox("Movie Category", cat_names, index=0)

    cat_id = None
    if selected_cat != "All":
        for c in cats:
            if c.get("category_name") == selected_cat:
                cat_id = c.get("category_id")
                break

    if st.button("Load Movies", type="secondary"):
        ok, streams, err = get_vod_streams(cat_id)
        if not ok:
            st.error(f"Failed to fetch VOD: {err}")
        else:
            st.session_state["vod_streams"] = streams
            st.success(f"Loaded {len(streams)} movies")

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
    st.info("If your provider exposes series as VOD entries, use **Search** or browse VOD categories.")

def search_tab():
    st.subheader("🔍 Search")
    q = st.text_input("Search channels & movies")
    if not q:
        return
    q_low = q.strip().lower()
    # quick local search across cached datasets
    results: List[Dict[str, Any]] = []

    ok, live_streams, err = get_live_streams()
    if ok:
        for it in live_streams:
            if q_low in (it.get("name") or "").lower():
                results.append({**it, "_kind": "live"})
    ok, vod_streams, err = get_vod_streams()
    if ok:
        for it in vod_streams:
            if q_low in (it.get("name") or "").lower():
                results.append({**it, "_kind": "vod"})

    if not results:
        st.warning("No matches found.")
        return

    st.success(f"Found {len(results)} items.")
    for item in results[:40]:
        cols = st.columns([4, 1, 1])
        name = item.get("name", "Unknown")
        sid = item.get("stream_id")
        kind = item.get("_kind", "live")
        cols[0].write(f"**{name}** · #{sid}")
        cols[1].write("LIVE" if kind == "live" else "VOD")
        if cols[2].button("Play", key=f"play_{kind}_{sid}"):
            if kind == "live":
                st.session_state["current_live_url"] = build_stream_url(sid, "live", "m3u8")
            else:
                st.session_state["current_vod_url"] = build_stream_url(sid, "vod", "mp4")
            st.rerun()

# =========================================================
# App
# =========================================================
def main():
    st.title("📺 LionHD IPTV Player")

    sidebar_diagnostics()

    # Try auth quickly (non-blocking; short timeout)
    ok_auth, auth_data, auth_err = get_auth()
    if not ok_auth:
        st.info(
            "Authentication did not succeed yet. You can still attempt to load categories. "
            "If repeated calls fail, verify server/credentials/reachability."
        )
        st.caption(f"Auth status: {auth_err}")

    else:
        user = auth_data.get("user_info", {})
        server = auth_data.get("server_info", {})
        st.sidebar.success(f"✅ Logged in: **{user.get('username', 'Unknown')}**")
        st.sidebar.info(f"📊 Active: {user.get('active_cons', 0)}/{user.get('max_connections', 0)}")
        st.sidebar.caption(f"⏱️ Expires: {user.get('exp_date', 'N/A')}")
        st.sidebar.caption(f"🌐 Server: {server.get('url', XSTREAM_URL)}")

    tab1, tab2, tab3, tab4 = st.tabs(["🏠 Live TV", "🎥 Movies", "📺 Series", "🔍 Search"])
    with tab1:
        live_tab()
    with tab2:
        movies_tab()
    with tab3:
        series_tab()
    with tab4:
        search_tab()

    st.divider()
    with st.expander("🧾 Logs (last run)"):
        show_logs()

if __name__ == "__main__":
    main()
