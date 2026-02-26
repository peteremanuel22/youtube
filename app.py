import os
import re
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

REQ_TIMEOUT = 6
CACHE_TTL   = 300

# TV-like user agents sometimes bypass panel/WAF filters that block bots
UA_LIST = [
    "VLC/3.0.20 LibVLC/3.0.20",
    "Lavf/58.76.100",                 # ffmpeg
    "Mozilla/5.0 (SmartTV; Tizen 6.0) AppleWebKit/537.36",
    "IPTV-Smarters-Player",
]

DEFAULT_HEADERS = {
    "User-Agent": UA_LIST[0],
    "Accept": "application/json, */*;q=0.1",
    "Accept-Language": "en-US,en;q=0.8",
    "Connection": "close",
}

# Session logs
if "logs" not in st.session_state:
    st.session_state["logs"] = []

def log(msg: str):
    ts = time.strftime("%H:%M:%S")
    st.session_state["logs"].append(f"[{ts}] {msg}")

def show_logs():
    st.text("\n".join(st.session_state["logs"][-500:]) if st.session_state["logs"] else "No logs yet.")

def is_https_page() -> bool:
    return True  # Streamlit Cloud is HTTPS

def warn_mixed_content(url: str):
    if is_https_page() and url.startswith("http://"):
        st.warning(
            "App is **HTTPS**, but the stream URL is **HTTP**. "
            "Browsers block embedding HTTP inside HTTPS. Use **Open externally (HTTP)** to play in a new tab.",
            icon="🔒",
        )

# =========================================================
# Networking helpers
# =========================================================
def _request(url: str, params: Optional[Dict[str, Any]] = None, headers: Optional[Dict[str, str]] = None) -> Tuple[int, bytes, Dict[str, str]]:
    h = dict(DEFAULT_HEADERS)
    if headers:
        h.update(headers)
    r = requests.get(url, params=params, headers=h, timeout=REQ_TIMEOUT)
    return r.status_code, r.content, dict(r.headers)

def _request_json(url: str, params: Optional[Dict[str, Any]] = None, headers: Optional[Dict[str, str]] = None) -> Tuple[bool, Any, str, int]:
    try:
        code, body, _ = _request(url, params=params, headers=headers)
        if code != 200:
            # Try to show a human-readable snippet of the body
            text = body[:500].decode("utf-8", errors="ignore")
            return False, None, f"HTTP {code}: {text.strip() or 'No body'}", code
        try:
            import json
            return True, json.loads(body.decode("utf-8", errors="ignore")), "", 200
        except Exception as e:
            return False, None, f"Invalid JSON: {e}", 200
    except requests.exceptions.Timeout:
        return False, None, "Timeout", 0
    except requests.exceptions.ConnectionError as e:
        return False, None, f"Connection error: {e}", 0
    except Exception as e:
        return False, None, f"Error: {e}", 0

def api_get(action: str, extra_params: Optional[Dict[str, Any]] = None, headers: Optional[Dict[str, str]] = None) -> Tuple[bool, Any, str, int]:
    params = {"username": USERNAME, "password": PASSWORD, "action": action}
    if extra_params:
        params.update(extra_params)
    url = f"{XSTREAM_URL}/player_api.php"
    return _request_json(url, params=params, headers=headers)

def build_stream_url(stream_id: str, typ: str = "live", ext: Optional[str] = None) -> str:
    if typ == "live":
        ext = ext or "m3u8"
        path = "live"
    else:
        ext = ext or "mp4"
        path = "movie"
    return f"{XSTREAM_URL}/{path}/{USERNAME}/{PASSWORD}/{stream_id}.{ext}"

# =========================================================
# M3U fallback: get.php?username=...&password=...&type=m3u_plus&output=m3u8
# =========================================================
M3U_LINE = f"{XSTREAM_URL}/get.php?username={USERNAME}&password={PASSWORD}&type=m3u_plus&output=m3u8"

@st.cache_data(ttl=CACHE_TTL, show_spinner=False)
def fetch_m3u(headers: Optional[Dict[str, str]] = None) -> Tuple[bool, str, str, int]:
    try:
        code, body, _ = _request(M3U_LINE, headers=headers)
        if code != 200:
            text = body[:300].decode("utf-8", errors="ignore")
            return False, "", f"HTTP {code}: {text or 'No body'}", code
        return True, body.decode("utf-8", errors="ignore"), "", 200
    except Exception as e:
        return False, "", str(e), 0

def parse_m3u(m3u_text: str) -> List[Dict[str, Any]]:
    """
    Parse #EXTM3U / #EXTINF entries to [{name, url, tvg_id, group_title, logo}]
    """
    items: List[Dict[str, Any]] = []
    current: Dict[str, Any] = {}
    for line in m3u_text.splitlines():
        if line.startswith("#EXTINF:"):
            # extract attributes
            attrs = {}
            # attributes like tvg-id="x" tvg-logo="..." group-title="..."
            for m in re.finditer(r'(\w+?)="(.*?)"', line):
                attrs[m.group(1)] = m.group(2)
            # title is after the comma
            title = line.split(",", 1)[1].strip() if "," in line else "Unknown"
            current = {
                "name": title,
                "tvg_id": attrs.get("tvg-id") or attrs.get("tvg_id"),
                "logo": attrs.get("tvg-logo") or attrs.get("tvg_logo"),
                "group": attrs.get("group-title") or attrs.get("group_title"),
            }
        elif line and not line.startswith("#"):
            # this is the URL line
            url = line.strip()
            if current:
                current["url"] = url
                items.append(current)
                current = {}
    return items

# =========================================================
# Cached wrappers (API first, M3U fallback)
# =========================================================
@st.cache_data(ttl=CACHE_TTL, show_spinner=False)
def get_auth() -> Tuple[bool, Dict[str, Any], str, int]:
    url = f"{XSTREAM_URL}/player_api.php"
    params = {"username": USERNAME, "password": PASSWORD}
    # Try API with TV-like User-Agent
    ok, data, err, code = _request_json(url, params=params, headers=DEFAULT_HEADERS)
    if ok and "user_info" in data:
        return True, data, "", 200
    if code == 401:
        return False, {}, f"HTTP 401 from API (creds blocked/denied): {err}", 401
    return False, {}, err or "Unknown", code

@st.cache_data(ttl=CACHE_TTL, show_spinner=False)
def get_live_categories() -> Tuple[bool, List[Dict[str, Any]], str]:
    ok, data, err, code = api_get("get_live_categories")
    if ok:
        cats = data if isinstance(data, list) else data.get("categories", [])
        return True, cats or [], ""
    if code == 401:
        # Use M3U groups as categories
        ok2, m3u, err2, _ = fetch_m3u()
        if not ok2:
            return False, [], f"API 401 and M3U failed: {err2}"
        items = parse_m3u(m3u)
        groups = sorted({it.get("group") or "Other" for it in items})
        return True, [{"category_name": g, "category_id": g} for g in groups], ""
    return False, [], err

@st.cache_data(ttl=CACHE_TTL, show_spinner=False)
def get_live_streams(category_id: Optional[str] = None) -> Tuple[bool, List[Dict[str, Any]], str]:
    ok, data, err, code = api_get("get_live_streams", {"category_id": category_id} if category_id else None)
    if ok and isinstance(data, list):
        return True, data, ""
    if code == 401:
        ok2, m3u, err2, _ = fetch_m3u()
        if not ok2:
            return False, [], f"API 401 and M3U failed: {err2}"
        items = parse_m3u(m3u)
        if category_id:
            items = [it for it in items if (it.get("group") or "Other") == category_id]
        # Convert into API-like shape
        streams = [{"name": it["name"], "stream_id": it.get("url"), "stream_icon": it.get("logo")} for it in items if it.get("url")]
        return True, streams, ""
    return False, [], err

@st.cache_data(ttl=CACHE_TTL, show_spinner=False)
def get_vod_categories() -> Tuple[bool, List[Dict[str, Any]], str]:
    ok, data, err, code = api_get("get_vod_categories")
    if ok:
        cats = data if isinstance(data, list) else data.get("categories", [])
        return True, cats or [], ""
    if code == 401:
        # derive VOD groups from M3U too (they’re usually mixed in)
        ok2, m3u, err2, _ = fetch_m3u()
        if not ok2:
            return False, [], f"API 401 and M3U failed: {err2}"
        items = parse_m3u(m3u)
        groups = sorted({it.get("group") or "Other" for it in items})
        return True, [{"category_name": g, "category_id": g} for g in groups], ""
    return False, [], err

@st.cache_data(ttl=CACHE_TTL, show_spinner=False)
def get_vod_streams(category_id: Optional[str] = None) -> Tuple[bool, List[Dict[str, Any]], str]:
    ok, data, err, code = api_get("get_vod_streams", {"category_id": category_id} if category_id else None)
    if ok and isinstance(data, list):
        return True, data, ""
    if code == 401:
        ok2, m3u, err2, _ = fetch_m3u()
        if not ok2:
            return False, [], f"API 401 and M3U failed: {err2}"
        items = parse_m3u(m3u)
        if category_id:
            items = [it for it in items if (it.get("group") or "Other") == category_id]
        streams = [{"name": it["name"], "stream_id": it.get("url"), "stream_icon": it.get("logo")} for it in items if it.get("url")]
        return True, streams, ""
    return False, [], err

# =========================================================
# Player helpers
# =========================================================
def render_hls_player(url: str, height: int = 460, autoplay: bool = False) -> None:
    """We’ll still try to embed; browsers will block HTTP on HTTPS, so we also show 'open externally'."""
    element_id = f"video_{int(time.time() * 1000)}"
    auto_attr = "autoplay muted" if autoplay else ""
    html = f"""
    <html>
    <head>
      <meta charset="utf-8" />
      https://cdn.jsdelivr.net/npm/hls.js@latest</script>
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

def external_open_button(url: str, label: str = "Open externally (HTTP)"):
    st.markdown(f'<a href="{url}" target="_blank" rel="noopener noreferrer" class="st-btn">{label}</a>', unsafe_allow_html=True)

# =========================================================
# UI
# =========================================================
def sidebar_diagnostics():
    st.sidebar.header("Diagnostics")

    st.sidebar.caption(f"Server: `{XSTREAM_URL}`")
    st.sidebar.caption(f"Username: `{USERNAME}`")

    if is_https_page() and XSTREAM_URL.startswith("http://"):
        st.sidebar.warning(
            "This app is **HTTPS**; embedding **HTTP** media will be blocked by browsers. "
            "Use **Open externally (HTTP)** for playback.",
            icon="⚠️",
        )

    if st.sidebar.button("Run quick diagnostics"):
        # 1) Ping (no creds)
        code, body, _ = _request(f"{XSTREAM_URL}/player_api.php")
        btxt = body[:120].decode("utf-8", errors="ignore")
        log(f"Ping player_api.php → HTTP {code} ({btxt or 'no body'})")

        # 2) Auth
        ok_auth, data_auth, err_auth, code_auth = get_auth()
        if ok_auth:
            user = data_auth.get("user_info", {})
            log(f"Auth → OK (user={user.get('username')}, status={user.get('status','?')})")
        else:
            log(f"Auth → FAIL ({err_auth})")

        # 3) M3U fallback test
        ok_m3u, m3u_text, err_m3u, code_m3u = fetch_m3u()
        if ok_m3u:
            # light sanity check
            log(f"M3U → OK (HTTP 200, size={len(m3u_text)} bytes)")
        else:
            log(f"M3U → FAIL ({err_m3u})")

        st.sidebar.success("Diagnostics complete. See logs at bottom.")

def live_tab():
    st.subheader("📡 Live TV")

    ok, cats, err = get_live_categories()
    if not ok:
        st.error(f"Failed to load categories: {err}")
        return

    names = ["All"] + [c.get("category_name", f"Cat {i}") for i, c in enumerate(cats)]
    sel = st.selectbox("Category", names, index=0)
    cat_id = None if sel == "All" else sel  # ID is the same as name for M3U fallback

    if st.button("Load Channels", type="secondary"):
        ok_s, streams, err_s = get_live_streams(cat_id)
        if not ok_s:
            st.error(f"Failed to fetch streams: {err_s}")
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
        # Determine url (API-style id vs M3U full URL)
        selected = streams[idx]
        sid = selected.get("stream_id")
        if isinstance(sid, str) and sid.startswith("http"):
            url = sid
        else:
            url = build_stream_url(str(sid), "live", "m3u8")

        if st.button("▶ Play (embed)", type="primary", key="play_live"):
            st.session_state["current_live_url"] = url

        if st.button("🔗 Show URL", key="show_live_url"):
            st.code(url, language="text")
            warn_mixed_content(url)

        external_open_button(url, "Open externally (HTTP)")

    with colR:
        url = st.session_state.get("current_live_url")
        if url:
            warn_mixed_content(url)
            render_hls_player(url, height=480, autoplay=False)
        else:
            st.info("Pick a channel and press **Play (embed)** or use **Open externally (HTTP)**.")

def movies_tab():
    st.subheader("🎬 Movies (VOD)")

    ok, cats, err = get_vod_categories()
    if not ok:
        st.error(f"Failed to load categories: {err}")
        return

    names = ["All"] + [c.get("category_name", f"Cat {i}") for i, c in enumerate(cats)]
    sel = st.selectbox("Movie Category", names, index=0)
    cat_id = None if sel == "All" else sel

    if st.button("Load Movies", type="secondary"):
        ok_s, streams, err_s = get_vod_streams(cat_id)
        if not ok_s:
            st.error(f"Failed to fetch VOD: {err_s}")
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
        selected = streams[idx]
        sid = selected.get("stream_id")
        # VOD: try mp4, fallback to m3u8
        if isinstance(sid, str) and sid.startswith("http"):
            url_mp4 = sid
            url_hls = sid
        else:
            url_mp4 = build_stream_url(str(sid), "vod", "mp4")
            url_hls = build_stream_url(str(sid), "vod", "m3u8")

        fmt = st.radio("Format", ["MP4 (.mp4)", "HLS (.m3u8)"], horizontal=True, key="vod_fmt")
        final_url = url_mp4 if fmt.startswith("MP4") else url_hls

        if st.button("▶ Play Movie (embed)", type="primary"):
            st.session_state["current_vod_url"] = final_url

        if st.button("🔗 Show URL", key="show_vod_url"):
            st.code(final_url, language="text")
            warn_mixed_content(final_url)

        external_open_button(final_url, "Open externally (HTTP)")

    with colR:
        url = st.session_state.get("current_vod_url")
        if url:
            warn_mixed_content(url)
            render_hls_player(url, height=480, autoplay=False)
        else:
            st.info("Pick a movie and press **Play Movie (embed)** or **Open externally (HTTP)**.")

def series_tab():
    st.subheader("📺 Series")
    st.info("Use **Search** or VOD categories for series (depends on provider).")

def search_tab():
    st.subheader("🔍 Search")
    q = st.text_input("Search channels & movies")
    if not q:
        return
    q_low = q.strip().lower()
    results: List[Dict[str, Any]] = []

    ok_l, live_streams, _ = get_live_streams()
    if ok_l:
        for it in live_streams:
            if q_low in (it.get("name") or "").lower():
                results.append({**it, "_kind": "live"})
    ok_v, vod_streams, _ = get_vod_streams()
    if ok_v:
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
        sid  = item.get("stream_id")
        kind = item.get("_kind", "live")
        # Resolve direct URL if this came from M3U
        if isinstance(sid, str) and sid.startswith("http"):
            url = sid
        else:
            url = build_stream_url(str(sid), "live" if kind=="live" else "vod", "m3u8" if kind=="live" else "mp4")

        cols[0].write(f"**{name}** · #{sid}")
        cols[1].write("LIVE" if kind == "live" else "VOD")
        if cols[2].button("Play (embed)", key=f"play_{kind}_{sid}"):
            if kind == "live":
                st.session_state["current_live_url"] = url
            else:
                st.session_state["current_vod_url"] = url
            st.rerun()
        external_open_button(url, "Open externally (HTTP)")

# =========================================================
# App
# =========================================================
def main():
    st.title("📺 LionHD IPTV Player")
    st.caption("This app uses Xtream **player_api.php** endpoints and falls back to the **M3U** playlist if API returns 401.")

    # No blocking network calls at load; diagnostics/buttons do the work.
    st.sidebar.header("Connection")
    st.sidebar.caption(f"URL: `{XSTREAM_URL}`")
    st.sidebar.caption(f"User: `{USERNAME}`")
    sidebar_diagnostics()

    tab1, tab2, tab3, tab4 = st.tabs(["🏠 Live TV", "🎥 Movies", "📺 Series", "🔍 Searchtab()
    with tab3:
        series_tab()
    with tab4:
        search_tab()

    st.divider()
    with st.expander("🧾 Logs (last run)"):
        show_logs()

if __name__ == "__main__":
    main()
