from flask import Blueprint, render_template, jsonify
import json
import requests
from bs4 import BeautifulSoup
import os

# Blueprint definition; static_folder is served at '/static/'
overlays_bp = Blueprint(
    "overlays",
    __name__,
    template_folder="templates",
    static_folder="static",
    static_url_path="/static"
)

# Path to your live streams config
CONFIG_PATH = "/home/cornerpins/portal/streams_config.json"

def get_overlay_html(pair_id, side):
    import json
    import requests
    from bs4 import BeautifulSoup
    from urllib.parse import urljoin

    CONFIG_PATH = "/home/cornerpins/portal/streams_config.json"

    # Load lane config
    with open(CONFIG_PATH, "r", encoding="utf-8") as f:
        cfg = json.load(f)

    try:
        pair = cfg["lane_pairs"][pair_id]
    except (IndexError, KeyError):
        return "<p>Invalid lane pair.</p>"

    scoring_type = pair.get("scoring_type", "").lower()
    url = pair.get("odd_lane_scoring_source" if side == "a" else "even_lane_scoring_source", "")
    if not url:
        return "<p>No overlay URL configured.</p>"

    try:
        # Always fetch base scoring URL
        r = requests.get(url, timeout=5)
        r.raise_for_status()
        soup = BeautifulSoup(r.text, "html.parser")
    except Exception as e:
        return f"<p>Error fetching overlay: {e}</p>"

    # === Case 1: Livescores format ===
    livescore_block = soup.find("div", id="players-wrap")
    if livescore_block:
        return livescore_block.prettify()

    # === Case 2: DuoHD with iframe ===
    zoom_wrap = soup.find("div", id="zoom-wrap")
    if zoom_wrap:
        iframe = zoom_wrap.find("iframe")
        if iframe and iframe.has_attr("src") and iframe["src"].strip():
            iframe_url = urljoin(url, iframe["src"].strip())
            try:
                iframe_r = requests.get(iframe_url, timeout=5)
                iframe_r.raise_for_status()
                iframe_soup = BeautifulSoup(iframe_r.text, "html.parser")

                zoom = iframe_soup.find("div", id="zoom-wrap")
                if zoom:
                    return zoom.prettify()
                players = iframe_soup.find("div", id="players-wrap")
                if players:
                    return players.prettify()
            except Exception as e:
                return f"<p>Could not load DuoHD iframe content: {e}</p>"
        return "<p>DuoHD iframe found but no src set.</p>"

    # Final fallback — full body if all else fails
    body = soup.find("body")
    if body:
        return body.prettify()

    return "<p>Overlay content not found.</p>"

@overlays_bp.route("/overlay/odd/<int:pair_id>")
def overlay_odd(pair_id):
    content = get_overlay_html(pair_id, "a")
    return render_template("overlay_embed.html", content=content, anchor="left")

@overlays_bp.route("/overlay/even/<int:pair_id>")
def overlay_even(pair_id):
    content = get_overlay_html(pair_id, "b")
    return render_template("overlay_embed.html", content=content, anchor="right")