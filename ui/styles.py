import re
from pathlib import Path

import streamlit as st

from core.constants import DEBUG_MODE

_STATIC_CSS_PATH = Path(__file__).resolve().parent.parent / "static" / "app.css"


@st.cache_resource
def _minified_app_css(_cache_key):
    """The app's CSS lives in static/app.css (plain, readable, easy to diff)
    rather than as a giant Python string. Streamlit's static file server
    forces Content-Type: text/plain on .css/.js files (see
    AppStaticFileHandler.SAFE_APP_STATIC_FILE_EXTENSIONS), so a real
    <link rel="stylesheet"> to it is silently blocked by the browser's
    nosniff check - it has to be read and inlined instead. Stripping
    comments/whitespace here is cached per process (st.cache_resource), so
    the regex work happens once, not on every rerun; inlining the result
    still costs bytes on every rerun, but meaningfully fewer of them.

    _cache_key (the file's own mtime, from inject_css below) exists purely
    so editing static/app.css invalidates this cache -- st.cache_resource
    keys on the wrapped function's OWN source, which never changes just
    because a file it happens to read did, so without this a running
    process kept serving whatever CSS was on disk at first import, and a
    plain browser refresh could never show a CSS-only edit -- only
    restarting the server (or clearing the cache) did.
    """
    try:
        raw = _STATIC_CSS_PATH.read_text(encoding="utf-8")
    except OSError:
        return ""
    without_comments = re.sub(r"/\*.*?\*/", "", raw, flags=re.DOTALL)
    return re.sub(r"\s+", " ", without_comments).strip()


def _debug_visuals():
    if not DEBUG_MODE:
        return "", ""

    condition = str(st.session_state.get("condition", "") or "").strip().lower()
    assigned = bool(st.session_state.get("condition_assigned", False))
    debug_condition = (
        condition if assigned and condition in {"baseline", "adaptive"} else "unassigned"
    )
    # Used to repaint the whole .stApp background blue for "baseline" so a
    # developer could tell conditions apart at a glance -- dropped because
    # it visually competed with (and got mistaken for) the app's own
    # background, which must stay one single color everywhere. The small
    # label below is enough to identify the condition during debugging.
    debug_css = """
        .debug-condition-label {
            position: fixed;
            top: 0.65rem;
            right: 0.75rem;
            z-index: 10000;
            padding: 0.28rem 0.52rem;
            border-radius: 999px;
            background: rgba(18, 34, 54, 0.88);
            color: #FFFFFF;
            border: 1px solid rgba(255, 255, 255, 0.28);
            box-shadow: 0 4px 12px rgba(18, 34, 54, 0.16);
            font-family: var(--font-sans);
            font-size: 0.68rem;
            font-weight: 800;
            letter-spacing: 0.06em;
            line-height: 1;
            pointer-events: none;
        }
    """
    label = f'<div class="debug-condition-label">DEBUG — {debug_condition.upper()}</div>'
    return debug_css, label


def inject_css():
    debug_css, debug_label = _debug_visuals()
    try:
        cache_key = _STATIC_CSS_PATH.stat().st_mtime
    except OSError:
        cache_key = 0
    css = f"<style>{_minified_app_css(cache_key)}{debug_css}</style>"
    if hasattr(st, "html"):
        st.html(css)
        if debug_label:
            st.html(debug_label)
    else:
        st.markdown(css, unsafe_allow_html=True)
        if debug_label:
            st.markdown(debug_label, unsafe_allow_html=True)
