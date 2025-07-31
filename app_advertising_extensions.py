# ✳️ app_advertising_extensions.py (UI + Logic for Advanced Ad System)

from flask import Blueprint, request, jsonify, send_file
import os, json, csv
from io import StringIO
from datetime import datetime

ads_bp = Blueprint("ads", __name__)
PORTAL_DIR = "/home/cornerpins/portal"
ADS_CONFIG_PATH = os.path.join(PORTAL_DIR, "ads_config.json")
ADS_META_PATH = os.path.join(PORTAL_DIR, "ads/ads_metadata.json")
ADS_LOG_PATH = os.path.join(PORTAL_DIR, "logs/ad_playback_log.jsonl")

# ─── CONFIG GET/SET ───────────────────────────────────────────────────
@ads_bp.route("/ads_config", methods=["GET"])
def get_ads_config():
    try:
        with open(ADS_CONFIG_PATH, "r", encoding="utf-8") as f:
            return jsonify(json.load(f))
    except Exception:
        return jsonify({}), 404

@ads_bp.route("/ads_config", methods=["POST"])
def save_ads_config():
    try:
        config = request.get_json()
        with open(ADS_CONFIG_PATH, "w", encoding="utf-8") as f:
            json.dump(config, f, indent=2)
        return jsonify({"status": "ok"})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# ─── DOWNLOAD PLAYBACK LOG ────────────────────────────────────────────
@ads_bp.route("/download_ad_log")
def download_ad_log():
    if not os.path.isfile(ADS_LOG_PATH):
        return "No log data", 404
    try:
        output = StringIO()
        writer = csv.writer(output)
        writer.writerow(["Timestamp", "Stream", "Ad ID", "Ad Name", "Duration", "Trigger"])
        with open(ADS_LOG_PATH, "r", encoding="utf-8") as f:
            for line in f:
                try:
                    entry = json.loads(line.strip())
                    writer.writerow([
                        entry.get("timestamp"),
                        entry.get("stream"),
                        entry.get("ad_id"),
                        entry.get("ad_name"),
                        entry.get("duration"),
                        entry.get("trigger")
                    ])
                except Exception:
                    continue
        output.seek(0)
        filename = f"ad_playback_log_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.csv"
        return send_file(output, mimetype='text/csv', download_name=filename, as_attachment=True)
    except Exception as e:
        return f"Error: {e}", 500
