#!/usr/bin/env python3
# -*- coding: utf-8 -*-
#import eventlet
#eventlet.monkey_patch(socket=True, select=True, time=True)
import os
import json
import uuid
import subprocess
import csv
import re
import threading
import time
import netifaces
import logging
from flask import (
    Flask, render_template, request, redirect, url_for,
    session, flash, jsonify
)
from bs4 import BeautifulSoup
import requests
from obswebsocket import obsws, requests as obs_requests
from flask_socketio import SocketIO, emit
from flask_cors import CORS
from flask import make_response, request
from camera_control import camera_bp
import base64
import psutil
import socket
import platform
import shutil
from youtube_api import create_youtube_stream

OBS_HOST = "localhost"
OBS_PORT = 4455
OBS_PASSWORD = "B0wl1ng2025!"

from overlays import overlays_bp

VALID_USERNAME = "cornerpins"
VALID_PASSWORD = "$treamN0de"

PORTAL_DIR = "/home/cornerpins/portal"
ADS_CONFIG_PATH = os.path.join(PORTAL_DIR, "ads_config.json")
CONFIG_PATH = "streams_config.json"
SCRIPT_PATH = os.path.join(PORTAL_DIR, "setup_12_streams.py")
VENV_PYTHON = os.path.join(PORTAL_DIR, "venv/bin/python3")
ADS_DIR = os.path.join(PORTAL_DIR, "ads")
ADS_META_PATH = os.path.join(ADS_DIR, "ads_metadata.json")
STREAMING_STATUS_PATH = os.path.join(PORTAL_DIR, "streaming_status.json")
RTMP_CONFIG_FILE = '/home/cornerpins/portal/rtmp_settings.json'

os.makedirs(ADS_DIR, exist_ok=True)

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

app = Flask(__name__)
app.register_blueprint(overlays_bp)
app.register_blueprint(camera_bp, url_prefix='/camera')
socketio = SocketIO(app, cors_allowed_origins="*")

app.secret_key = "i.am.batman.1983"
app.debug = True
socketio = SocketIO(app, async_mode='threading', cors_allowed_origins="*")
CORS(app, resources={
    r"*": {
        "origins": ["https://cornerpins.com.au", "http://localhost:*", "https://*.ngrok-free.app"],
        "methods": ["GET", "POST", "PUT", "DELETE", "OPTIONS"],
        "allow_headers": ["Content-Type", "Authorization", "ngrok-skip-browser-warning"],
        "supports_credentials": False,
        "max_age": 600
    }
})

@app.before_request
def handle_preflight():
    if request.method == "OPTIONS":
        response = make_response()
        response.headers.add("Access-Control-Allow-Origin", "*")
        response.headers.add('Access-Control-Allow-Headers', "Content-Type,Authorization,ngrok-skip-browser-warning")
        response.headers.add('Access-Control-Allow-Methods', "GET,PUT,POST,DELETE,OPTIONS")
        response.headers.add('Access-Control-Max-Age', "600")
        return response

@app.after_request
def after_request(response):
    # Add ngrok header
    response.headers['ngrok-skip-browser-warning'] = 'true'
    
    # Ensure CORS headers are always present
    origin = request.headers.get('Origin')
    if origin:
        response.headers['Access-Control-Allow-Origin'] = origin
    else:
        response.headers['Access-Control-Allow-Origin'] = '*'
    
    response.headers['Access-Control-Allow-Methods'] = 'GET, POST, PUT, DELETE, OPTIONS'
    response.headers['Access-Control-Allow-Headers'] = 'Content-Type, Authorization, ngrok-skip-browser-warning'
    response.headers['Access-Control-Max-Age'] = '600'
    
    return response

@app.before_request
def log_request():
    print(f"[REQ] From {request.remote_addr}, Path: {request.path}")

@app.route("/get_video_devices")
def get_video_devices():
    logger.info("Hit /get_video_devices")
    return jsonify(get_video_devices_list())

def get_video_devices_list():
    try:
        output = subprocess.check_output(
            ["v4l2-ctl", "--list-devices"],
            stderr=subprocess.STDOUT,
            timeout=5
        ).decode(errors="ignore")

        lines = output.strip().split("\n")
        devices = []
        seen = {}
        current_label = ""

        for line in lines:
            if not line.startswith("\t"):
                current_label = line.strip()
            elif "/dev/video" in line:
                dev_path = line.strip()
                if current_label and dev_path not in seen:
                    seen[dev_path] = True
                    devices.append({"id": dev_path, "label": current_label})
        return devices

    except subprocess.CalledProcessError as e:
        # Partial output fallback
        partial = e.output.decode(errors="ignore") if e.output else ""
        if partial:
            lines = partial.strip().split("\n")
            devices = []
            seen = {}
            current_label = ""
            for line in lines:
                if not line.startswith("\t"):
                    current_label = line.strip()
                elif "/dev/video" in line:
                    dev_path = line.strip()
                    if current_label and dev_path not in seen:
                        seen[dev_path] = True
                        devices.append({"id": dev_path, "label": current_label})
            return devices
        return []
    except Exception as e:
        logger.error(f"Failed to enumerate video devices: {e}")
        return []



def get_audio_devices_list():
    devices = []
    try:
        subprocess.run(["pulseaudio", "--check"], check=True, capture_output=True)
    except subprocess.CalledProcessError:
        logger.warning("PulseAudio not running, attempting to start...")
        try:
            subprocess.run(["pulseaudio", "--start"], check=True, capture_output=True)
            time.sleep(2)
        except subprocess.CalledProcessError as e:
            logger.error(f"Failed to start PulseAudio: {e}")
            return [{
                "id": "default",
                "label": "Default Input Device",
                "pulse_name": "default",
                "type": "pulse_input_capture"
            }]
    try:
        pactl_sources = subprocess.check_output(
            ["pactl", "list", "sources", "short"], stderr=subprocess.DEVNULL
        ).decode(errors='ignore')
        for line in pactl_sources.split("\n"):
            if line.strip():
                parts = line.split(None, 4)
                if len(parts) >= 2 and "monitor" not in parts[1].lower():
                    pulse_name = parts[1]
                    friendly_name = pulse_name
                    try:
                        info_cmd = subprocess.check_output(
                            ["pactl", "list", "sources"], stderr=subprocess.DEVNULL
                        ).decode(errors='ignore')
                        in_target_source = False
                        for info_line in info_cmd.split("\n"):
                            if f"Name: {pulse_name}" in info_line:
                                in_target_source = True
                            elif in_target_source and "Description:" in info_line:
                                friendly_name = info_line.split("Description:")[1].strip()
                                break
                            elif in_target_source and info_line.startswith("Source #"):
                                break
                    except subprocess.CalledProcessError:
                        pass
                    devices.append({
                        "id": pulse_name,
                        "label": friendly_name,
                        "pulse_name": pulse_name,
                        "type": "pulse_input_capture"
                    })
        if not devices:
            logger.warning("No valid PulseAudio input sources found")
            devices.append({
                "id": "default",
                "label": "Default Input Device",
                "pulse_name": "default",
                "type": "pulse_input_capture"
            })
        logger.info(f"Found {len(devices)} audio devices: {devices}")
        return devices
    except Exception as e:
        logger.error(f"Failed to enumerate audio devices: {e}")
        return [{
            "id": "default",
            "label": "Default Input Device",
            "pulse_name": "default",
            "type": "pulse_input_capture"
        }]

def load_config():
    if not os.path.isfile(CONFIG_PATH):
        logger.warning(f"Config file not found at {CONFIG_PATH}, creating default")
        default = {
            "youtube_rtmp_base": "",
            "youtube_backup_url": "",
            "lane_pairs": []
        }
        save_config(default)
        return default
    try:
        with open(CONFIG_PATH, "r", encoding="utf-8") as f:
            cfg = json.load(f)

        # Ensure pin_cam and player_cam exist for every lane_pair if missing
        for p in cfg.get("lane_pairs", []):
            if "pin_cam" not in p:
                p["pin_cam"] = {
                    "enabled": False,
                    "type": "rtsp",
                    "rtsp": "",
                    "local": ""
                }
            if "player_cam" not in p:
                p["player_cam"] = {
                    "enabled": False,
                    "type": "rtsp",
                    "rtsp": "",
                    "local": ""
                }

        return cfg

    except (json.JSONDecodeError, IOError) as e:
        logger.error(f"Failed to load config: {e}")
        default = {
            "youtube_rtmp_base": "",
            "youtube_backup_url": "",
            "lane_pairs": []
        }
        save_config(default)
        return default


def save_config(cfg):
    try:
        with open(CONFIG_PATH, "w", encoding="utf-8") as f:
            json.dump(cfg, f, indent=2, ensure_ascii=False)
        logger.info(f"Configuration saved to {CONFIG_PATH}")
    except Exception as e:
        logger.error(f"Failed to save config: {e}")

def sort_lane_pairs(pairs):
    try:
        return sorted(pairs, key=lambda p: int(p["name"].split("&")[0]))
    except Exception:
        return pairs

def load_ad_metadata():
    if os.path.isfile(ADS_META_PATH):
        try:
            with open(ADS_META_PATH, "r", encoding="utf-8") as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError):
            return []
    return []

def load_ads_config():
    path = os.path.join(PORTAL_DIR, "ads_config.json")
    default = {
        "mode": "TEAM",
        "team": {
            "halfway_duration": 30,
            "lane_change_delay": 30,
            "lane_change_duration": 180
        },
        "cup": {
            "halfway_duration": 30,
            "game_change_duration": 30,
            "final_game_delay": 15,
            "final_game_duration": 180
        }
    }
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except:
        return default


def save_ad_metadata(ad_list):
    try:
        with open(ADS_META_PATH, "w", encoding="utf-8") as f:
            json.dump(ad_list, f, indent=2, ensure_ascii=False)
        logger.info(f"Advert metadata saved to {ADS_META_PATH}")
    except Exception as e:
        logger.error(f"Failed to save ad metadata: {e}")

def load_streaming_status():
    if os.path.isfile(STREAMING_STATUS_PATH):
        try:
            with open(STREAMING_STATUS_PATH, "r", encoding="utf-8") as f:
                return json.load(f).get("streaming", False)
        except (json.JSONDecodeError, IOError):
            logger.error(f"Failed to load streaming status file: {STREAMING_STATUS_PATH}")
            return False
    return False

def save_streaming_status(status):
    try:
        with open(STREAMING_STATUS_PATH, "w", encoding="utf-8") as f:
            json.dump({"streaming": status}, f, indent=2)
        logger.info(f"Streaming status saved: {status}")
    except Exception as e:
        logger.error(f"Failed to save streaming status: {e}")

@app.route("/", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "").strip()
        if username == VALID_USERNAME and password == VALID_PASSWORD:
            session["logged_in"] = True
            logger.info("User logged in successfully")
            return redirect(url_for("dashboard"))
        else:
            flash("Invalid credentials", "danger")
            logger.warning("Invalid login attempt")
            return redirect(url_for("login"))
    return render_template("login.html", logged_in=False)

@app.route("/dashboard", methods=["GET", "POST"])
def dashboard():
    if not session.get("logged_in"):
        logger.warning("Unauthorized access to /dashboard")
        return redirect(url_for("login"))

    cfg = load_config()
    lane_pairs = cfg.get("lane_pairs", [])
    for p in lane_pairs:
        p.setdefault("enabled", False)
        p.setdefault("src_type", "rtsp")
        p.setdefault("camera_rtsp", "")
        p.setdefault("local_src", "")
        p.setdefault("scoring_type", "livescores")
        p.setdefault("state", "")
        p.setdefault("centre", "")
        p.setdefault("odd_lane_scoring_source", "")
        p.setdefault("even_lane_scoring_source", "")
        p.setdefault("stream_key", "")
        p.setdefault("youtube_live_id", "")
        p.setdefault("audio_streams", [])
        p.setdefault("pin_cam", {})
        pc = p["pin_cam"]
        pc.setdefault("enabled", False)
        pc.setdefault("type", "rtsp")
        pc.setdefault("rtsp", "")
        pc.setdefault("local", "")
        p.setdefault("player_cam", {})
        plc = p["player_cam"]
        plc.setdefault("enabled", False)
        plc.setdefault("type", "rtsp")
        plc.setdefault("rtsp", "")
        plc.setdefault("local", "")

    base_url = cfg.get("youtube_rtmp_base", "")
    backup_url = cfg.get("youtube_backup_url", "")

    # Get audio devices with both labels and pulse_names
    audio_devices = get_audio_devices_list()

    if request.method == "POST":

        logger.warning("💥 RAW FORM DATA: %s", dict(request.form))
        logger.info("Processing dashboard form submission")
        cfg["youtube_rtmp_base"] = request.form.get("youtube_rtmp_base", "").strip()
        cfg["youtube_backup_url"] = request.form.get("youtube_backup_url", "").strip()
        # Always load event_name before any stream creation logic
        try:
            with open("event_data.json", "r", encoding="utf-8") as f:
                events = json.load(f)
            current_event = events[-1] if events else {}
            event_name = current_event.get("event_name", "Unnamed Event")
            logger.info(f"[DEBUG] Loaded event name for stream creation: {event_name}")
        except Exception as e:
            logger.error(f"[FATAL] Could not load event_name from event_data.json: {e}")
            event_name = "Unnamed Event"

        # Create a mapping of labels to pulse_names
        device_mappings = {dev["label"]: dev.get("pulse_name", dev["id"]) for dev in audio_devices}

        any_enabled = False
        for i, pair in enumerate(lane_pairs):
            prefix = f"lane{i}"
            pair["enabled"] = request.form.get(f"{prefix}_enabled") == "on"
            
            if pair["enabled"]:
                any_enabled = True
                
                # Process non-stream fields first
                pair["src_type"] = request.form.get(f"{prefix}_src_type", "rtsp")
                pair["camera_rtsp"] = request.form.get(f"{prefix}_camera_rtsp", "").strip()
                pair["local_src"] = request.form.get(f"{prefix}_local_src", "").strip()
                pair["scoring_type"] = request.form.get(f"{prefix}_scoring_type", "").strip()
                
                # Only populate state/centre if livescores is selected
                if pair["scoring_type"] == "livescores":
                    pair["state"] = request.form.get(f"{prefix}_state", "").strip()
                    pair["centre"] = request.form.get(f"{prefix}_centre", "").strip()
                else:
                    pair["state"] = ""
                    pair["centre"] = ""

                pair["odd_lane_scoring_source"] = request.form.get(f"{prefix}_odd_lane_src", "").strip()
                pair["even_lane_scoring_source"] = request.form.get(f"{prefix}_even_lane_src", "").strip()
                
                # Check autocreate BEFORE processing stream fields
                pair["autocreate"] = request.form.get(f"{prefix}_autocreate") == "on"
                
                # ===== YOUTUBE STREAM CREATION LOGIC =====
                if pair["autocreate"]:
                    logger.info(f"[AutoCreate] Creating stream for {pair['name']}")
                    try:
                        stream_result = create_youtube_stream(event_name, pair["name"])
                        logger.info(f"[AutoCreate] Result from YouTube API: {stream_result}")
                        if stream_result:
                            pair["stream_key"] = stream_result.get("stream_key", "")
                            pair["youtube_live_id"] = stream_result.get("youtube_live_id", "")
                            logger.info(f"[AutoCreate] SUCCESS: {pair['name']} got {pair['youtube_live_id']}")
                        else:
                            logger.error(f"[AutoCreate] FAILED: create_youtube_stream returned None for {pair['name']}")
                    except Exception as e:
                        logger.error(f"[AutoCreate] EXCEPTION: {e}")
                else:
                    # Manual mode - use form values
                    form_stream_key = request.form.get(f"{prefix}_stream_key", "").strip()
                    form_youtube_id = request.form.get(f"{prefix}_youtube_live_id", "").strip()
                    
                    # Only update if form values are different from existing (user made changes)
                    current_stream_key = pair.get("stream_key", "")
                    current_youtube_id = pair.get("youtube_live_id", "")
                    
                    if form_stream_key != current_stream_key:
                        pair["stream_key"] = form_stream_key
                        logger.info(f"[Manual] Updated stream_key for {pair['name']}: {form_stream_key}")
                    
                    if form_youtube_id != current_youtube_id:
                        pair["youtube_live_id"] = form_youtube_id
                        logger.info(f"[Manual] Updated youtube_live_id for {pair['name']}: {form_youtube_id}")
                    
                    # If no changes detected, keep existing values (persistence)
                    if form_stream_key == current_stream_key and form_youtube_id == current_youtube_id:
                        logger.info(f"[Manual] Preserving existing values for {pair['name']}")
                
                # Process other fields
                try:
                    delay_val = int(request.form.get(f"{prefix}_video_delay_ms", 0))
                    pair["video_delay_ms"] = max(0, min(delay_val, 60000))
                except ValueError:
                    pair["video_delay_ms"] = 0

                # Pin cam settings
                pair["pin_cam"]["enabled"] = request.form.get(f"{prefix}_enable_pin_cam") == "on"
                pair["pin_cam"]["type"] = request.form.get(f"{prefix}_pin_cam_type", "rtsp")
                pair["pin_cam"]["rtsp"] = request.form.get(f"{prefix}_pin_rtsp", "").strip()
                pair["pin_cam"]["local"] = request.form.get(f"{prefix}_pin_local", "").strip() if pair["pin_cam"]["enabled"] else ""

                # Player cam settings
                pair["player_cam"]["enabled"] = request.form.get(f"{prefix}_enable_player_cam") == "on"
                pair["player_cam"]["type"] = request.form.get(f"{prefix}_player_cam_type", "rtsp")
                pair["player_cam"]["rtsp"] = request.form.get(f"{prefix}_player_rtsp", "").strip()
                pair["player_cam"]["local"] = request.form.get(f"{prefix}_player_local", "").strip() if pair["player_cam"]["enabled"] else ""

                # Process audio streams
                audio_streams = []
                for audio_idx in range(10):
                    key = f"{prefix}_audio_streams_{audio_idx}"
                    name_key = f"{prefix}_audio_names_{audio_idx}"
                    label = request.form.get(key, "").strip()
                    friendly_name = request.form.get(name_key, "").strip()
                    if label:
                        pulse_name = device_mappings.get(label, label)
                        audio_streams.append({"label": label, "pulse_name": pulse_name, "friendly_name": friendly_name})
                pair["audio_streams"] = audio_streams
            else:
                # Disabled pair - clear values
                pair["local_src"] = ""
                pair["pin_cam"]["local"] = ""
                pair["player_cam"]["local"] = ""
                pair["audio_streams"] = []

        # Process livescores after all pairs are processed
        for pair in lane_pairs:
            if pair.get("enabled") and pair.get("scoring_type") == "livescores":
                try:
                    lane_nums = [int(n) for n in pair["name"].split("&")]
                    res = get_series(pair["centre"])
                    if res and isinstance(res, dict):
                        pair["odd_lane_scoring_source"] = res.get("lane1", "")
                        pair["even_lane_scoring_source"] = res.get("lane2", "")
                except Exception as e:
                    logger.error(f"Failed to fetch Livescores series for {pair['name']}: {e}")

        # Save the configuration
        config_to_save = {
            "youtube_rtmp_base": cfg["youtube_rtmp_base"],
            "youtube_backup_url": cfg["youtube_backup_url"],
            "lane_pairs": sort_lane_pairs(lane_pairs)
        }
        if cfg.get("event_banner_url"):
            config_to_save["event_banner_url"] = cfg["event_banner_url"]
        save_config(config_to_save)

# Track changed scenes
        scenes_to_update = []
        scenes_to_remove = []
        
        # Check for scenes that need removal (disabled)
        for pair in lane_pairs:
            pair_name = pair.get("name")
            prefix = f"lane{lane_pairs.index(pair)}"
            new_enabled = request.form.get(f"{prefix}_enabled") == "on"
            
            # If previously enabled but now disabled
            if pair.get("enabled", False) and not new_enabled:
                scenes_to_remove.append(pair_name)
                logger.info(f"Scene {pair_name} will be removed (disabled)")
        
        # Check for scenes that need updating
        for i, pair in enumerate(lane_pairs):
            prefix = f"lane{i}"
            new_enabled = request.form.get(f"{prefix}_enabled") == "on"
            
            # If newly enabled or settings changed
            if new_enabled and (not pair.get("enabled", False) or 
                               pair.get("camera_rtsp") != request.form.get(f"{prefix}_camera_rtsp", "").strip() or
                               pair.get("local_src") != request.form.get(f"{prefix}_local_src", "").strip() or
                               pair.get("scoring_type") != request.form.get(f"{prefix}_scoring_type", "")):
                scenes_to_update.append(pair["name"])
                logger.info(f"Scene {pair['name']} needs update")
        
        # Remove disabled scenes first
        if scenes_to_remove:
            try:
                ws = obsws(OBS_HOST, OBS_PORT, OBS_PASSWORD)
                ws.connect()
                
                for scene_name in scenes_to_remove:
                    try:
                        ws.call(obs_requests.RemoveScene(sceneName=scene_name))
                        logger.info(f"Removed scene: {scene_name}")
                    except Exception as e:
                        logger.error(f"Failed to remove scene {scene_name}: {e}")
                
                ws.disconnect()
            except Exception as e:
                logger.error(f"Failed to connect to OBS for scene removal: {e}")
        
        # Update changed scenes
        try:
            if scenes_to_update:
                scene_list = ",".join(scenes_to_update)
                result = subprocess.check_output(
                    [VENV_PYTHON, SCRIPT_PATH, "--no-stream", "--scenes", scene_list],
                    stderr=subprocess.STDOUT,
                    cwd=PORTAL_DIR,
                    timeout=120
                )
                logger.info(f"Selectively updated scenes: {scenes_to_update}")
                flash(f"Configuration saved. Updated {len(scenes_to_update)} scenes, removed {len(scenes_to_remove)} scenes.", "success")
            else:
                if scenes_to_remove:
                    flash(f"Configuration saved. Removed {len(scenes_to_remove)} scenes.", "success")
                else:
                    flash("Configuration saved. No scene changes detected.", "success")
                logger.info("No scenes to update")
        except subprocess.CalledProcessError as e:
            logger.error(f"OBS setup error: {e.output.decode(errors='ignore')}")
            flash(f"OBS Error: {e.output.decode(errors='ignore')}", "danger")
        except Exception as e:
            logger.error(f"Unexpected error during OBS setup: {e}")
            flash(f"Unexpected error: {e}", "danger")

        return redirect(url_for("dashboard"))

    return render_template(
        "dashboard.html",
        logged_in=True,
        lane_pairs=sort_lane_pairs(lane_pairs),
        youtube_rtmp_base=base_url,
        youtube_backup_url=backup_url,
        audio_devices=audio_devices,
        local_cameras=get_video_devices_list()
    )

@app.route("/services")
def services_embed():
    return render_template("services_embed.html")



@app.route("/advertising", methods=["GET"])
def advertising():
    if not session.get("logged_in"):
        logger.warning("Unauthorized access to /advertising")
        return redirect(url_for("login"))
    cfg = load_config()
    adverts = load_ad_metadata()
    lane_pairs = sort_lane_pairs(cfg.get("lane_pairs", []))
    # Load playback log if exists
    log_path = os.path.join(PORTAL_DIR, "logs/ad_playback_log.jsonl")
    playback_log = []
    if os.path.isfile(log_path):
        with open(log_path, "r", encoding="utf-8") as f:
            for line in f:
                try:
                    playback_log.append(json.loads(line.strip()))
                except:
                    continue

    return render_template(
        "advertising.html",
        logged_in=True,
        adverts=adverts,
        lane_pairs=lane_pairs,
        ads_config=load_ads_config(),
        playback_log=playback_log[-50:]  # last 50 entries
    )


@app.route("/save_ads_config", methods=["POST"])
def save_ads_config():
    if not session.get("logged_in"):
        return redirect(url_for("login"))

    config = {
        "mode": request.form.get("mode", "TEAM"),
        "team": {
            "halfway_enabled": "team_halfway_enabled" in request.form,
            "halfway_duration": int(request.form.get("team_halfway", 30)),
            "lane_change_delay": int(request.form.get("team_delay", 30)),
            "lane_change_duration": int(request.form.get("team_lane_change", 180)),
        },
        "cup": {
            "halfway_enabled": "cup_halfway_enabled" in request.form,
            "halfway_duration": int(request.form.get("cup_halfway", 30)),
            "game_change_duration": int(request.form.get("cup_game_change", 30)),
            "lane_change_delay": int(request.form.get("cup_lane_delay", 15)),
            "lane_change_duration": int(request.form.get("cup_lane_duration", 180)),
        }
    }

    with open(ADS_CONFIG_PATH, "w", encoding="utf-8") as f:
        json.dump(config, f, indent=2)

    flash("Ad playback configuration saved.", "success")
    return redirect(url_for("advertising"))

@app.route("/mixer")
def mixer():
    if not session.get("logged_in"):
        logger.warning("Unauthorized access to /mixer")
        return redirect(url_for("login"))
    cfg = load_config()
    lane_pairs = [p for p in cfg.get("lane_pairs", []) if p.get("enabled", False)]
    logger.info(f"Rendering mixer.html with {len(lane_pairs)} enabled lane pairs")
    return render_template("mixer.html", lane_pairs=lane_pairs, logged_in=True)

@socketio.on('connect')
def handle_connect():
    logger.info('WebSocket client connected')

@socketio.on('disconnect')
def handle_disconnect():
    logger.info('WebSocket client disconnected')

@socketio.on('audioControl')
def handle_audio_control(data):
    stream_id = data['streamId']
    source_id = data['sourceId']
    property = data['property']
    value = data['value']
    try:
        ws = obsws(OBS_HOST, OBS_PORT, OBS_PASSWORD)
        ws.connect()
        if property == 'volume':
            ws.call(obs_requests.SetInputVolume(inputName=source_id, inputVolumeMul=value / 100.0))
        elif property == 'mute':
            ws.call(obs_requests.SetInputMute(inputName=source_id, inputMuted=value))
        ws.disconnect()
        socketio.emit('audioLevels', {'streamId': stream_id, 'sourceId': source_id, 'level': value})
    except Exception as e:
        logger.error(f"Audio control error: {e}")

@socketio.on('streamConfig')
def handle_stream_config(data):
    if data['request'] == 'current_config':
        cfg = load_config()
        lane_pairs = [p for p in cfg.get("lane_pairs", []) if p.get("enabled", False)]
        socketio.emit('configUpdate', {
            'streams': lane_pairs,
            'sharedSources': []
        })

@app.route("/upload_advert", methods=["POST"])
def upload_advert():
    if not session.get("logged_in"):
        logger.warning("Unauthorized access to /upload_advert")
        return redirect(url_for("login"))

    logger.info("Processing advert upload")
    ad_name = request.form.get("ad_name", "").strip()
    ad_file = request.files.get("ad_file")
    ad_duration = request.form.get("ad_duration", "").strip()
    streams_selected = request.form.getlist("streams")

    if not ad_name or not ad_file or not streams_selected:
        flash("All fields are required.", "danger")
        logger.warning("Advert upload failed: missing fields")
        return redirect(url_for("advertising"))

    original = os.path.basename(ad_file.filename)
    uid = uuid.uuid4().hex
    save_fname = f"{uid}_{original}"
    save_path = os.path.join(ADS_DIR, save_fname)
    try:
        ad_file.save(save_path)
        logger.info(f"Advert file saved: {save_path}")
    except Exception as e:
        flash(f"Failed to save file: {e}", "danger")
        logger.error(f"Failed to save advert file: {e}")
        return redirect(url_for("advertising"))

    ext = original.lower().rsplit(".", 1)[-1]
    ad_type = "Image" if ext in {"jpg","jpeg","png","gif","bmp"} else "Video"
    duration_int = int(ad_duration) if ad_type=="Image" and ad_duration.isdigit() else None

    entry = {
        "id": uid,
        "name": ad_name,
        "filename": save_fname,
        "type": ad_type,
        "duration": duration_int,
        "streams": streams_selected,
        "priority": int(request.form.get("ad_priority", 5))
    }
    adverts = load_ad_metadata()
    adverts.append(entry)
    save_ad_metadata(adverts)
    logger.info(f"Advert metadata saved: {entry}")

    flash("Advert uploaded successfully.", "success")
    return redirect(url_for("advertising"))

@app.route("/download_ad_log")
def download_ad_log():
    log_path = os.path.join(PORTAL_DIR, "logs/ad_playback_log.jsonl")
    if not os.path.isfile(log_path):
        return "Log file not found", 404

    def generate():
        yield "timestamp,stream,ad_id,ad_name,duration,trigger\n"
        with open(log_path, "r", encoding="utf-8") as f:
            for line in f:
                try:
                    e = json.loads(line.strip())
                    yield f"{e['timestamp']},{e['stream']},{e['ad_id']},{e['ad_name']},{e['duration']},{e['trigger']}\n"
                except:
                    continue

    return app.response_class(generate(), mimetype="text/csv")

@app.route("/delete_ad/<ad_id>", methods=["POST"])
def delete_ad(ad_id):
    if not session.get("logged_in"):
        logger.warning("Unauthorized access to /delete_ad")
        return redirect(url_for("login"))
    logger.info(f"Deleting advert with id: {ad_id}")
    adverts = load_ad_metadata()
    to_remove = next((a for a in adverts if a["id"] == ad_id), None)
    if to_remove:
        path = os.path.join(ADS_DIR, to_remove["filename"])
        try:
            if os.path.isfile(path):
                os.remove(path)
                logger.info(f"Advert file deleted: {path}")
        except Exception as e:
            logger.error(f"Failed to delete advert file: {e}")
        adverts.remove(to_remove)
        save_ad_metadata(adverts)
        flash("Advert deleted.", "success")
    else:
        flash("Advert not found.", "danger")
        logger.warning(f"Advert not found for deletion: {ad_id}")
    return redirect(url_for("advertising"))

@app.route("/logout")
def logout():
    session.clear()
    logger.info("User logged out")
    return redirect(url_for("login"))

@app.route("/get_centres/<state>", methods=["GET"])
def get_centres(state):
    logger.info(f"Fetching centres for state: {state}")
    try:
        url = f"https://livescores.computerscore.com.au/centres.php?state={state}"
        res = requests.get(url, timeout=5)
        res.raise_for_status()
        soup = BeautifulSoup(res.text, "html.parser")
        centres = {
            opt["value"].strip(): opt.text.strip()
            for opt in soup.select("option")
            if opt.get("value","").strip().isdigit()
        }
        logger.info(f"Centres fetched successfully: {len(centres)} centres")
        return jsonify(centres)
    except Exception as e:
        logger.error(f"Failed to fetch centres for state {state}: {e}")
        return jsonify({"error": str(e)}), 500

@app.route("/get_series/<centre_id>")
def get_series(centre_id):
    lanes = request.args.get("lanes", "")
    req = [l.strip() for l in lanes.split(",") if l.strip().isdigit()]
    logger.info(f"Fetching series for centre: {centre_id}, lanes: {req}")
    if len(req) != 2:
        logger.warning("Invalid lane numbers provided")
        return jsonify({"error": "Two lane numbers required"}), 400
    try:
        url = f"https://livescores.computerscore.com.au/view-lanes.php?centre={centre_id}"
        res = requests.get(url, timeout=5)
        res.raise_for_status()
        soup = BeautifulSoup(res.text, "lxml")
        links = {}
        found_lanes = []
        for row in soup.select("tr"):
            cols = row.find_all("td")
            if len(cols) >= 2:
                num_text = cols[0].get_text(strip=True)
                num_match = re.search(r"(\d+)", num_text)
                num = num_match.group(1) if num_match else None
                a = cols[-1].find("a", href=True)
                if num and a:
                    found_lanes.append(num)
                    href = a['href']
                    if href.startswith('?'):
                        full_url = f"https://livescores.computerscore.com.au/view.php{href}"
                    else:
                        full_url = f"https://livescores.computerscore.com.au/{href.lstrip('/')}"
                    links[f"lane{num}"] = full_url
        resp = {
            "lane1": links.get(f"lane{req[0]}", ""),
            "lane2": links.get(f"lane{req[1]}", "")
        }
        if not resp["lane1"] or not resp["lane2"]:
            missing = [lane for lane in req if not links.get(f"lane{lane}")]
            logger.warning(
                f"get_series for centre {centre_id}, lanes {req}: missing lanes {missing}, found {found_lanes}"
            )
            resp["warning"] = f"Lane(s) {', '.join(missing)} not found"
        else:
            logger.info(f"get_series for centre {centre_id}, lanes {req}: {resp}")
        return jsonify(resp)
    except Exception as e:
        logger.error(f"get_series error for centre {centre_id}: {str(e)}")
        return jsonify({"error": str(e)}), 500

@app.route("/preview_scenes")
def preview_scenes():
    if not session.get("logged_in"):
        logger.warning("Unauthorized access to /preview_scenes")
        return redirect(url_for("login"))

    scenes = []
    try:
        cfg = load_config()
        lane_pairs = cfg.get("lane_pairs", [])
        logger.info(f"Loaded lane pairs from config: {len(lane_pairs)} pairs")

        enabled_lane_pairs = [pair for pair in lane_pairs if pair.get("enabled", False)]
        logger.info(f"Enabled lane pairs: {len(enabled_lane_pairs)} pairs")

        ws = obsws(OBS_HOST, OBS_PORT, OBS_PASSWORD)
        try:
            ws.connect()
            logger.info("Connected to OBS WebSocket")
        except Exception as connect_err:
            logger.error(f"Could not connect to OBS WebSocket: {connect_err}")
            flash(f"Could not connect to OBS WebSocket: {connect_err}", "danger")
            return render_template("preview_scenes.html", scenes=[])

        try:
            scene_list = ws.call(obs_requests.GetSceneList())
            logger.info(f"Received scene list: {len(scene_list.getScenes())} scenes")

            for pair in enabled_lane_pairs:
                scene_name = pair["name"]
                logger.info(f"Processing scene: {scene_name}")

                screenshot = None
                try:
                    logger.info(f"Requesting screenshot for scene: {scene_name}")
                    response = ws.call(obs_requests.GetSourceScreenshot(
                        sourceName=scene_name,
                        imageFormat="png",
                        width=480,
                        height=270
                    ))
                    image_data = response.getImageData()
                    if image_data and image_data.startswith('data:image/png;base64,'):
                        screenshot = image_data.split(',')[1]  # Extract base64 part
                        logger.info(f"Successfully retrieved screenshot for {scene_name}")
                    else:
                        logger.warning(f"Screenshot for {scene_name} is empty or invalid")
                except Exception as e:
                    logger.error(f"Error retrieving screenshot for {scene_name}: {str(e)}")

                scenes.append({
                    "name": scene_name,
                    "image": screenshot
                })
        except Exception as e:
            logger.error(f"OBS scene list error: {e}")
            flash(f"OBS Preview Fatal Error: {e}", "danger")
            return render_template("preview_scenes.html", scenes=[])
        finally:
            try:
                ws.disconnect()
                logger.info("Disconnected from OBS WebSocket")
            except Exception:
                logger.warning("Failed to disconnect OBS WebSocket")
    except Exception as e:
        logger.error(f"OBS Preview Fatal Error: {e}")
        flash(f"OBS Preview Fatal Error: {e}", "danger")

    return render_template("preview_scenes.html", scenes=scenes)

@app.route("/get-overlay-links/<int:pair>")
def get_overlay_links(pair):
    try:
        with open("streams_config.json", "r", encoding="utf-8") as f:
            config = json.load(f)
        lane = config["lane_pairs"][pair]
        return jsonify({
            "odd": lane.get("odd_lane_scoring_source", ""),
            "even": lane.get("even_lane_scoring_source", "")
        })
    except Exception:
        return jsonify({"odd": "", "even": ""})

from flask import make_response

@app.route("/stream_status", methods=["GET"])
def get_stream_status():
    try:
        is_streaming = load_streaming_status()
        logger.info(f"Stream status queried: {is_streaming}")
        response = make_response(jsonify({"streaming": is_streaming}), 200)
        return response
    except Exception as e:
        logger.error(f"Failed to fetch streaming status: {e}")
        return jsonify({"error": f"Failed to fetch streaming status: {e}", "streaming": False}), 500

@app.route("/get_audio_devices")
def get_audio_devices():
    try:
        devices = get_audio_devices_list()
        # Return user-friendly labels for the dashboard
        labels = [dev["label"] for dev in devices]
        # Add saved audio_streams from streams_config.json
        cfg = load_config()
        for pair in cfg.get("lane_pairs", []):
            for audio in pair.get("audio_streams", []):
                if audio and audio not in labels:
                    labels.append(audio)
        logger.info(f"Returning audio device labels: {labels}")
        return jsonify(labels)
    except Exception as e:
        logger.error(f"Failed to enumerate audio devices: {e}")
        return jsonify([]), 500

@app.route("/get_audio_device_mappings")
def get_audio_device_mappings():
    try:
        devices = get_audio_devices_list()
        mappings = {dev["label"]: dev["pulse_name"] for dev in devices}
        return jsonify(mappings)
    except Exception as e:
        logger.error(f"Failed to fetch audio device mappings: {e}")
        return jsonify({}), 500

@app.route("/event_details_data", methods=["GET"])
def get_event_details_data():
    try:
        with open("event_data.json", "r", encoding="utf-8") as f:
            events = json.load(f)
        response = make_response(jsonify(events), 200)
        response.headers['Access-Control-Allow-Origin'] = 'https://cornerpins.com.au'
        response.headers['Access-Control-Allow-Methods'] = 'GET, POST, PUT, DELETE, OPTIONS'
        response.headers['Access-Control-Allow-Headers'] = 'Content-Type, Authorization'
        return response
    except Exception as e:
        logger.error(f"Error fetching event details: {e}")
        return jsonify({"error": "No events available"}), 404

def process_lane_draw_csv(file_path):
    """Process the uploaded CSV file and return lane draw data"""
    lane_draw = []
    try:
        with open(file_path, 'r', encoding='utf-8') as csvfile:
            # Try to detect the delimiter
            sample = csvfile.read(1024)
            csvfile.seek(0)
            sniffer = csv.Sniffer()
            delimiter = sniffer.sniff(sample).delimiter
            
            reader = csv.DictReader(csvfile, delimiter=delimiter)
            for row in reader:
                # Clean up the row data and get required fields
                bowler_name = str(row.get('Bowler Name', '') or row.get('bowler_name', '') or row.get('Name', '')).strip()
                lane = str(row.get('Lane', '') or row.get('lane', '')).strip()
                time_slot = str(row.get('Time', '') or row.get('time', '') or row.get('time_slot', '')).strip()
                
                if bowler_name and lane and time_slot:
                    lane_draw.append({
                        "bowler_name": bowler_name,
                        "lane": lane,
                        "time": time_slot
                    })
                    
        logger.info(f"Processed CSV: {len(lane_draw)} valid entries")
        return lane_draw
        
    except Exception as e:
        logger.error(f"Error processing CSV: {e}")
        raise ValueError(f"Failed to process CSV file: {e}")

@app.route("/event_details", methods=["GET", "POST"])
def event_details():
    if not session.get("logged_in"):
        return redirect(url_for("login"))
    
    # Load current event and events list at the start
    current_event = None
    events = []
    try:
        with open("event_data.json", "r", encoding="utf-8") as f:
            events = json.load(f)
        if events:
            current_event = events[-1]
            logger.info(f"Loaded current active event: {current_event['event_name']}")
    except (FileNotFoundError, json.JSONDecodeError):
        logger.info("No active event found")
        events = []
        current_event = None
        
    if request.method == "POST":
        
        event_name = request.form.get("event_name", "").strip()
        venue = request.form.get("venue", "").strip()
        event_start = request.form.get("event_dates_start", "").strip()
        event_end = request.form.get("event_dates_end", "").strip()
        
        # ONLY CHECK REQUIRED FIELDS - NOT CSV
        if not all([event_name, venue, event_start, event_end]):
            flash("Event Name, Venue, and Dates are required", "danger")
            return redirect(url_for("event_details"))
        
        try:
            os.makedirs("uploads", exist_ok=True)
            os.makedirs("static/event_banners", exist_ok=True)
            
            # Handle logo upload OR use fallback from hidden field
            banner_filename = None
            banner_url = None
            logo_file = request.files.get("logo_upload")
            fallback_url = request.form.get("hidden_banner_url")

            if logo_file and logo_file.filename:
                import uuid
                file_ext = os.path.splitext(logo_file.filename)[1]
                banner_filename = f"{uuid.uuid4().hex}{file_ext}"
                banner_path = os.path.join("static", "event_banners", banner_filename)
                logo_file.save(banner_path)
                banner_url = f"/static/event_banners/{banner_filename}"
                logger.info(f"Event banner saved: {banner_path}")
            elif fallback_url:
                banner_url = fallback_url
                banner_filename = os.path.basename(fallback_url)
                logger.info(f"Using fallback banner URL: {banner_url}")
                        
            # Handle lane draw if provided (OPTIONAL)
            lane_draw = []
            csv_file = request.files.get("lane_draw_csv")
            if csv_file and csv_file.filename:
                file_path = os.path.join("uploads", csv_file.filename)
                csv_file.save(file_path)
                lane_draw = process_lane_draw_csv(file_path)
                logger.info(f"Lane draw processed: {len(lane_draw)} entries")
            
            # Create event data
            event_data = {
                "event_name": event_name,
                "venue": venue,
                "event_dates_start": event_start,
                "event_dates_end": event_end,
                "banner_filename": banner_filename,
                "banner_url": banner_url,
                "has_lane_draw": bool(lane_draw),
                "lane_draw": lane_draw,
                "created_at": time.strftime("%Y-%m-%d %H:%M:%S")
            }
            
            # Remove existing event with same name and add new one
            events = [e for e in events if e.get("event_name") != event_name]
            events.append(event_data)
            
            # Save updated events list
            with open("event_data.json", "w", encoding="utf-8") as f:
                json.dump(events, f, indent=4)
            
            # Update streams config with banner

            try:
                cfg = load_config()
                if banner_url:
                    cfg["event_banner_url"] = banner_url
                    logger.info(f"Adding banner URL to config: {banner_url}")
                else:
                    cfg.pop("event_banner_url", None)
                    logger.info("Removing banner URL from config")
                save_config(cfg)
                logger.info(f"Successfully updated streams config with banner URL: {banner_url}")
            except Exception as e:
                logger.error(f"Failed to update streams config with banner: {e}")
            
            if lane_draw:
                flash(f"Lane draw included with {len(lane_draw)} bowler entries", "success")
            logger.info(f"Event activated: {event_name}, Banner: {bool(banner_url)}, Lane Draw: {bool(lane_draw)}")
            
        except ValueError as e:
            flash(f"CSV Error: {str(e)}", "danger")
        except Exception as e:
            logger.error(f"Error saving event: {e}")
            flash(f"Error saving event: {str(e)}", "danger")
            
        return redirect(url_for("event_details"))
    
    # GET request - return the template with current event
    return render_template("event_details.html", logged_in=True, current_event=current_event)

@app.route("/lookup_bowler", methods=["POST"])
def lookup_bowler():
    bowler_name = request.form.get("bowler_name", "").strip().lower()
    if not bowler_name:
        return jsonify({"error": "Bowler name required"}), 400
    try:
        with open("event_data.json", "r", encoding="utf-8") as f:
            events = json.load(f)
        for event in events:
            for entry in event.get("lane_draw", []):
                if entry["bowler_name"].lower() == bowler_name:
                    response = make_response(jsonify({"lane": entry["lane"], "time": entry["time"]}), 200)
                    response.headers['Access-Control-Allow-Origin'] = 'https://cornerpins.com.au'
                    response.headers['Access-Control-Allow-Methods'] = 'GET, POST, PUT, DELETE, OPTIONS'
                    response.headers['Access-Control-Allow-Headers'] = 'Content-Type, Authorization'
                    return response
        return jsonify({"error": "Bowler not found"}), 404
    except Exception as e:
        logger.error(f"Error in lookup_bowler: {e}")
        return jsonify({"error": "Server error"}), 500

@app.route("/api/streams", methods=["GET", "OPTIONS"])
def get_streams():
    # Handle OPTIONS explicitly
    if request.method == "OPTIONS":
        response = make_response()
        response.headers['Access-Control-Allow-Origin'] = '*'
        response.headers['Access-Control-Allow-Methods'] = 'GET, POST, PUT, DELETE, OPTIONS'
        response.headers['Access-Control-Allow-Headers'] = 'Content-Type, Authorization, ngrok-skip-browser-warning'
        return response

    try:
        cfg = load_config()
        is_streaming = load_streaming_status()
        banner_url = cfg.get("event_banner_url", "")
        streams = []

        for p in cfg.get("lane_pairs", []):
            if not p.get("enabled", False):
                continue

            name = p["name"]
            autocreate = p.get("autocreate", False)
            
            # ===== FIXED AUTOCREATE LOGIC =====
            if autocreate:
                # Use ONLY YouTube API values for AutoCreate streams
                live_id = p.get("youtube_live_id", "")
                stream_key = p.get("stream_key", "")
                
                if live_id:
                    embed_url = f"https://www.youtube.com/embed/{live_id}"
                else:
                    embed_url = ""
                    
                logger.info(f"[API/AutoCreate] {name}: live_id={live_id}, embed_url={embed_url}")
            else:
                # Use manual dashboard values for non-AutoCreate streams
                live_id = p.get("youtube_live_id", "")
                stream_key = p.get("stream_key", "")
                
                if live_id:
                    embed_url = f"https://www.youtube.com/embed/{live_id}"
                elif stream_key:
                    embed_url = f"https://www.youtube.com/embed/live_stream?channel={stream_key}"
                else:
                    embed_url = ""
                    
                logger.info(f"[API/Manual] {name}: live_id={live_id}, embed_url={embed_url}")

            streams.append({
                "name": name,
                "stream_key": stream_key,
                "youtube_live_id": live_id,
                "embed_url": embed_url,
                "streaming": is_streaming,
                "banner_url": banner_url,
                "autocreate": autocreate  # Add this for debugging
            })

        resp = make_response(jsonify({
            "streams": streams,
            "banner_url": banner_url,
            "has_banner": bool(banner_url)
        }), 200)

        # Ensure CORS headers are set
        resp.headers['Access-Control-Allow-Origin'] = '*'
        resp.headers['Access-Control-Allow-Methods'] = 'GET, POST, PUT, DELETE, OPTIONS'
        resp.headers['Access-Control-Allow-Headers'] = 'Content-Type, Authorization, ngrok-skip-browser-warning'
        resp.headers['Cache-Control'] = 'no-store, no-cache, must-revalidate, max-age=0'
        resp.headers['Pragma'] = 'no-cache'
        resp.headers['Expires'] = '0'

        return resp

    except Exception as e:
        logger.error(f"Error fetching streams: {e}")
        error_resp = make_response(jsonify({"streams": [], "banner_url": "", "has_banner": False}), 500)
        error_resp.headers['Access-Control-Allow-Origin'] = '*'
        return error_resp

# 5. TEST ENDPOINT - Add this for debugging:
@app.route("/test-cors", methods=["GET", "OPTIONS"])
def test_cors():
    if request.method == "OPTIONS":
        response = make_response()
        response.headers['Access-Control-Allow-Origin'] = '*'
        response.headers['Access-Control-Allow-Methods'] = 'GET, POST, PUT, DELETE, OPTIONS'
        response.headers['Access-Control-Allow-Headers'] = 'Content-Type, Authorization, ngrok-skip-browser-warning'
        return response
    
    resp = make_response(jsonify({"status": "CORS working!", "timestamp": time.time()}))
    resp.headers['Access-Control-Allow-Origin'] = '*'
    return resp

@app.route("/debug_autocreate", methods=["GET"])
def debug_autocreate():
    if not session.get("logged_in"):
        return jsonify({"error": "Unauthorized"}), 401
    
    try:
        cfg = load_config()
        debug_info = []
        
        for p in cfg.get("lane_pairs", []):
            if p.get("enabled", False):
                debug_info.append({
                    "name": p["name"],
                    "autocreate": p.get("autocreate", False),
                    "youtube_live_id": p.get("youtube_live_id", ""),
                    "stream_key": p.get("stream_key", ""),
                    "stream_key_preview": p.get("stream_key", "")[:8] + "..." if p.get("stream_key") else "",
                })
        
        return jsonify({
            "debug_info": debug_info,
            "config_path": CONFIG_PATH,
            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S")
        })
        
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/regenerate_multi_rtmp", methods=["POST"])
def regenerate_multi_rtmp():
    """Configure Multi-RTMP via WebSocket API - SAFE REPLACEMENT"""
    logger.info("🛠️ Configuring Multi-RTMP via WebSocket API")

    if not session.get("logged_in"):
        return jsonify({"error": "Unauthorized"}), 401

    try:
        cfg = load_config()
        enabled_pairs = [p for p in cfg.get("lane_pairs", []) if p.get("enabled", False)]
        
        if not enabled_pairs:
            return jsonify({"error": "No enabled streams found"}), 400

        # ENHANCED LOGGING - Show what we're working with
        logger.info(f"Found {len(enabled_pairs)} enabled pairs")
        for pair in enabled_pairs:
            logger.info(f"Pair {pair['name']}: autocreate={pair.get('autocreate')}, "
                       f"stream_key={'YES' if pair.get('stream_key') else 'NO'}, "
                       f"youtube_live_id={'YES' if pair.get('youtube_live_id') else 'NO'}")

        # Connect to OBS
        ws = obsws(OBS_HOST, OBS_PORT, OBS_PASSWORD)
        ws.connect()
        
        vendor_name = "obs-multi-rtmp"
        rtmp_base_url = cfg.get("youtube_rtmp_base", "rtmp://a.rtmp.youtube.com/live2")
        
        # Clear existing outputs
        try:
            resp = ws.call(obs_requests.CallVendorRequest(
                vendorName=vendor_name,
                requestType="GetOutputs",
                requestData={}
            ))
            
            existing_outputs = resp.datain.get("outputs", [])
            logger.info(f"🧹 Found {len(existing_outputs)} existing outputs to clear")
            
            for output in existing_outputs:
                try:
                    output_name = output.get("name", "Unknown")
                    ws.call(obs_requests.CallVendorRequest(
                        vendorName=vendor_name,
                        requestType="RemoveOutput",
                        requestData={"name": output_name}
                    ))
                    logger.info(f"  Removed: {output_name}")
                except Exception as e:
                    logger.warning(f"  Failed to remove {output_name}: {e}")
        except Exception as e:
            logger.warning(f"Failed to clear outputs: {e}")

        # Add new outputs
        success_count = 0
        failed_pairs = []
        configured_outputs = []
        
        for pair in enabled_pairs:
            pair_name = pair["name"]
            stream_key = ""
            
            # ENHANCED LOGGING for each pair
            logger.info(f"\n🔍 Processing {pair_name}:")
            logger.info(f"  AutoCreate: {pair.get('autocreate', False)}")
            logger.info(f"  Current stream_key: {pair.get('stream_key', '')[:8]}..." if pair.get('stream_key') else "  No stream_key")
            logger.info(f"  Current youtube_live_id: {pair.get('youtube_live_id', '')}")
            
            # Handle both AutoCreate AND Manual modes
            if pair.get("autocreate"):
                # AutoCreate mode - use YouTube API generated values
                if pair.get("youtube_live_id") and pair.get("stream_key"):
                    stream_key = pair["stream_key"]
                    logger.info(f"  🤖 Using AutoCreate key: {stream_key[:8]}...")
                else:
                    logger.warning(f"  ❌ AutoCreate enabled but missing youtube_live_id or stream_key")
                    failed_pairs.append(f"{pair_name} (AutoCreate: missing data)")
            else:
                # Manual mode - use form values
                stream_key = pair.get("stream_key", "").strip()
                if stream_key:
                    logger.info(f"  ✋ Using Manual key: {stream_key[:8]}...")
                else:
                    logger.warning(f"  ❌ Manual mode but no stream_key provided")
                    failed_pairs.append(f"{pair_name} (Manual: no key)")

            if not stream_key:
                logger.warning(f"  ⏭️ Skipping {pair_name} - no stream key available")
                continue

            # Add output
            output_name = f"Pair {pair_name}"
            
            try:
                # Add the output
                logger.info(f"  📤 Adding output: {output_name}")
                ws.call(obs_requests.CallVendorRequest(
                    vendorName=vendor_name,
                    requestType="AddOutput",
                    requestData={
                        "name": output_name,
                        "server": rtmp_base_url,
                        "key": stream_key
                    }
                ))
                
                # Configure settings
                logger.info(f"  ⚙️ Configuring settings for: {output_name}")
                ws.call(obs_requests.CallVendorRequest(
                    vendorName=vendor_name,
                    requestType="SetOutputSettings",
                    requestData={
                        "name": output_name,
                        "settings": {
                            "encoder": "obs_x264",
                            "bitrate": 6000,
                            "rate_control": "CBR",
                            "keyint_sec": 2,
                            "preset": "medium",
                            "profile": "high"
                        }
                    }
                ))
                
                # Enable output
                logger.info(f"  ✅ Enabling output: {output_name}")
                ws.call(obs_requests.CallVendorRequest(
                    vendorName=vendor_name,
                    requestType="EnableOutput",
                    requestData={"name": output_name}
                ))
                
                success_count += 1
                configured_outputs.append(output_name)
                logger.info(f"  ✅ SUCCESS: Configured {output_name}")
                
            except Exception as e:
                logger.error(f"  ❌ FAILED to configure {output_name}: {e}")
                failed_pairs.append(f"{pair_name} (Error: {str(e)[:50]}...)")

        # Save configuration
        try:
            ws.call(obs_requests.CallVendorRequest(
                vendorName=vendor_name,
                requestType="SaveConfig",
                requestData={}
            ))
            logger.info("💾 Multi-RTMP configuration saved")
        except Exception as e:
            logger.warning(f"Save config failed (non-critical): {e}")

        # Verify final state
        try:
            resp = ws.call(obs_requests.CallVendorRequest(
                vendorName=vendor_name,
                requestType="GetOutputs",
                requestData={}
            ))
            
            final_outputs = resp.datain.get("outputs", [])
            logger.info(f"\n📊 FINAL VERIFICATION:")
            logger.info(f"  Total outputs: {len(final_outputs)}")
            logger.info(f"  Successfully configured: {success_count}")
            
            for output in final_outputs:
                logger.info(f"  ✓ {output.get('name', 'Unknown')}: enabled={output.get('enabled', False)}")
                
        except Exception as e:
            logger.warning(f"Verification failed: {e}")

        ws.disconnect()
        
        # Build response
        response_data = {
            "success": success_count > 0,
            "outputs_configured": success_count,
            "configured_outputs": configured_outputs,
            "total_enabled_pairs": len(enabled_pairs)
        }
        
        if failed_pairs:
            response_data["failed_pairs"] = failed_pairs
            response_data["message"] = f"Configured {success_count} of {len(enabled_pairs)} outputs. Failed: {', '.join(failed_pairs)}"
        else:
            response_data["message"] = f"Successfully configured all {success_count} outputs"
        
        logger.info(f"\n🎯 SUMMARY: {response_data['message']}")
        
        if success_count > 0:
            return jsonify(response_data)
        else:
            return jsonify(response_data), 500

    except Exception as e:
        logger.error(f"❌ FATAL EXCEPTION in regenerate_multi_rtmp: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return jsonify({"error": str(e), "success": False}), 500

@app.route("/stream", methods=["POST"])
def toggle_stream():
    if not session.get("logged_in"):
        logger.warning("Unauthorized access to /stream")
        return jsonify({"error": "Unauthorized", "streaming": False}), 401

    logger.info("Processing /stream request")
    try:
        cfg = load_config()
        enabled_pairs = [p for p in cfg.get("lane_pairs", []) if p.get("enabled", False)]
        logger.info(f"Found {len(enabled_pairs)} enabled lane pairs")
        
        if not enabled_pairs:
            logger.warning("No enabled streams to start")
            return jsonify({"message": "No enabled streams to start.", "streaming": False}), 400

        is_streaming = load_streaming_status()
        logger.info(f"Current streaming status: {is_streaming}")

        ws = obsws(OBS_HOST, OBS_PORT, OBS_PASSWORD)
        ws.connect()
        logger.info("Connected to OBS WebSocket")

        if not is_streaming:
            # ENHANCED: First ensure Multi-RTMP is configured
            try:
                logger.info("Ensuring Multi-RTMP is configured before starting")
                
                # Check if outputs exist, if not configure them
                resp = ws.call(obs_requests.CallVendorRequest(
                    vendorName="obs-multi-rtmp",
                    requestType="GetOutputs",
                    requestData={}
                ))
                
                existing_outputs = resp.datain.get("outputs", [])
                logger.info(f"Found {len(existing_outputs)} existing Multi-RTMP outputs")
                
                # If no outputs or mismatched count, reconfigure
                if len(existing_outputs) != len(enabled_pairs):
                    logger.info("Multi-RTMP outputs don't match enabled pairs, reconfiguring...")
                    
                    # Configure Multi-RTMP via WebSocket API
                    rtmp_base_url = cfg.get("youtube_rtmp_base", "rtmp://a.rtmp.youtube.com/live2")
                    
                    # Clear existing outputs
                    for output in existing_outputs:
                        try:
                            ws.call(obs_requests.CallVendorRequest(
                                vendorName="obs-multi-rtmp",
                                requestType="RemoveOutput",
                                requestData={"name": output.get("name", "")}
                            ))
                        except:
                            pass
                    
                    # Add new outputs
                    for pair in enabled_pairs:
                        stream_key = ""
                        
                        # Handle both AutoCreate and Manual modes
                        if pair.get("autocreate"):
                            if pair.get("youtube_live_id") and pair.get("stream_key"):
                                stream_key = pair["stream_key"]
                        else:
                            stream_key = pair.get("stream_key", "").strip()
                        
                        if stream_key:
                            output_name = f"Pair {pair['name']}"
                            try:
                                # Add output
                                ws.call(obs_requests.CallVendorRequest(
                                    vendorName="obs-multi-rtmp",
                                    requestType="AddOutput",
                                    requestData={
                                        "name": output_name,
                                        "server": rtmp_base_url,
                                        "key": stream_key
                                    }
                                ))
                                
                                # Enable output
                                ws.call(obs_requests.CallVendorRequest(
                                    vendorName="obs-multi-rtmp",
                                    requestType="EnableOutput",
                                    requestData={"name": output_name}
                                ))
                                
                                logger.info(f"Configured Multi-RTMP output: {output_name}")
                            except Exception as e:
                                logger.warning(f"Failed to configure {output_name}: {e}")
                
                # Save configuration
                try:
                    ws.call(obs_requests.CallVendorRequest(
                        vendorName="obs-multi-rtmp",
                        requestType="SaveConfig",
                        requestData={}
                    ))
                except Exception as e:
                    logger.warning(f"SaveConfig failed: {e}")
                    
            except Exception as e:
                logger.warning(f"Multi-RTMP configuration failed: {e}")

            # Start all Multi-RTMP streams
            try:
                logger.info("Starting Multi-RTMP streams")
                ws.call(obs_requests.CallVendorRequest(
                    vendorName="obs-multi-rtmp",
                    requestType="StartStreaming",
                    requestData={}
                ))

                ws.disconnect()
                save_streaming_status(True)
                logger.info("Multi-RTMP streaming started successfully")
                return jsonify({"message": "Streaming started.", "streaming": True})
            except Exception as e:
                ws.disconnect()
                logger.error(f"Failed to start Multi-RTMP streaming: {e}")
                return jsonify({"error": f"Failed to start streaming: {e}", "streaming": False}), 500
        else:
            # Stop all Multi-RTMP streams
            try:
                logger.info("Stopping Multi-RTMP streams")
                ws.call(obs_requests.CallVendorRequest(
                    vendorName="obs-multi-rtmp",
                    requestType="StopStreaming",
                    requestData={}
                ))
                ws.disconnect()
                save_streaming_status(False)
                logger.info("Multi-RTMP streaming stopped successfully")
                return jsonify({"message": "Streaming stopped.", "streaming": False})
            except Exception as e:
                ws.disconnect()
                logger.error(f"Failed to stop Multi-RTMP streaming: {e}")
                # CRITICAL FIX: Always update status even if stop fails
                save_streaming_status(False)
                return jsonify({"message": "Streaming stopped (with errors).", "streaming": False})

    except Exception as e:
        logger.error(f"Unexpected error in toggle_stream: {e}")
        return jsonify({"error": f"Unexpected error: {e}", "streaming": load_streaming_status()}), 500

@app.route("/tweak", methods=["POST"])
def rtmp_tweak():
    if not session.get("logged_in"):
        logger.warning("Unauthorized access to /tweak")
        return redirect(url_for("login"))

    from pathlib import Path
    obs_profile_dir = Path.home() / ".config" / "obs-studio" / "basic" / "profiles"
    profile_dirs = [d for d in obs_profile_dir.iterdir() if d.is_dir()]
    if not profile_dirs:
        flash("OBS profile directory not found.", "danger")
        return redirect(url_for("dashboard"))

    profile_path = Path.home() / ".config" / "obs-studio" / "basic" / "profiles" / "Cornerpins" / "multiple_output.json"

    try:
        cfg = load_config()
        enabled_pairs = [p for p in cfg.get("lane_pairs", []) if p.get("enabled", False)]
        rtmp_base = cfg.get("youtube_rtmp_base", "rtmp://a.rtmp.youtube.com/live2")

        output_config = {
            "encoder": request.form.get("encoder", "obs_x264"),
            "bitrate": int(request.form.get("bitrate", 6000)),
            "rate_control": request.form.get("rate_control", "CBR"),
            "keyint_sec": int(request.form.get("keyint_sec", 2)),
            "preset": request.form.get("preset", "medium"),
            "profile": request.form.get("profile", "high"),
            "gpu": request.form.get("gpu", "0"),
            "bf": int(request.form.get("bf", 2)),
            "lookahead": request.form.get("lookahead", "false") == "true",
            "psycho_aq": request.form.get("psycho_aq", "true") == "true"
        }

        outputs = []
        for pair in enabled_pairs:
            stream_key = pair.get("stream_key", "")
            pair_name = pair.get("name")
            if stream_key:
                outputs.append({
                    "name": f"{pair_name}",
                    "enabled": True,
                    "server": rtmp_base,
                    "key": stream_key,
                    "use_obs_settings": False,
                    "settings": output_config
                })

        with open(profile_path, "w", encoding="utf-8") as f:
            json.dump({"outputs": outputs}, f, indent=2)

        logger.info(f"RTMP Tweak settings saved to {profile_path}")
        flash("RTMP encoding settings updated.", "success")
    except Exception as e:
        logger.error(f"Error saving RTMP settings: {e}")
        flash("Failed to save RTMP settings.", "danger")

    return redirect(url_for("dashboard"))

@app.route("/get_service_status")
def get_service_status():
   """Lightning-fast service status - just reads from file"""
   import time
   import os
   import json
   
   try:
       status_file = "/tmp/service_status.json"
       
       # Check if status file exists and is recent
       if not os.path.exists(status_file):
           return jsonify({
               "error": "Service monitor not running",
               "status": {},
               "diagnostics": {"Error": "Service monitor daemon not active"},
               "camera_ips": [],
               "livescores": []
           }), 503
       
       # Check file age
       file_age = time.time() - os.path.getmtime(status_file)
       if file_age > 60:  # File older than 1 minute
           logger.warning(f"Service status file is {file_age:.1f}s old")
       
       # Read status file
       with open(status_file, "r") as f:
           status_data = json.load(f)
       
       # Add freshness indicator
       last_updated = status_data.get("last_updated", 0)
       age = time.time() - last_updated
       status_data["diagnostics"]["Status Age"] = f"{age:.1f}s ago"
       
       logger.info(f"Served status in <1ms (data age: {age:.1f}s)")
       return jsonify(status_data)
       
   except json.JSONDecodeError as e:
       logger.error(f"Status file corrupted: {e}")
       return jsonify({
           "error": "Status file corrupted",
           "status": {},
           "diagnostics": {"Error": "Status file corrupted"},
           "camera_ips": [],
           "livescores": []
       }), 500
       
   except Exception as e:
       logger.error(f"Error reading service status: {e}")
       return jsonify({
           "error": str(e),
           "status": {},
           "diagnostics": {"Error": str(e)},
           "camera_ips": [],
           "livescores": []
       }), 500

@app.route("/control_service", methods=["POST"])
def control_service():
    if not session.get("logged_in"):
        return jsonify({"error": "Unauthorized"}), 401
        
    try:
        data = request.get_json()
        svc_id = data.get("service")
        action = data.get("action")

        if not svc_id or not action:
            return jsonify({"error": "Invalid request"}), 400

        if action not in ["start", "stop", "restart"]:
            return jsonify({"error": "Invalid action"}), 400

        logger.info(f"Attempting to {action} service: {svc_id}")
        
        # Try the command with a short timeout
        try:
            result = subprocess.run(
                ["sudo", "systemctl", action, svc_id], 
                capture_output=True, 
                text=True, 
                timeout=10
            )
            
            if result.returncode == 0:
                logger.info(f"Successfully {action}ed service: {svc_id}")
                return jsonify({"status": "ok", "service": svc_id, "action": action})
            else:
                error_msg = result.stderr.strip() or result.stdout.strip() or "Unknown error"
                logger.error(f"Service {action} failed for {svc_id}: {error_msg}")
                
                # Check if it's a sudo password issue
                if "password is required" in error_msg or "conversation failed" in error_msg:
                    return jsonify({
                        "error": "Permission denied. Run: sudo visudo and add 'cornerpins ALL=(ALL) NOPASSWD: /bin/systemctl'"
                    }), 500
                
                return jsonify({"error": f"Service command failed: {error_msg}"}), 500
                
        except subprocess.TimeoutExpired:
            logger.error(f"Service {action} timed out for {svc_id}")
            return jsonify({"error": "Service command timed out"}), 500
            
    except Exception as e:
        logger.error(f"Service control error: {e}")
        return jsonify({"error": str(e)}), 500


@app.route("/restart_system", methods=["POST"])
def restart_system():
    if not session.get("logged_in"):
        return jsonify({"error": "Unauthorized"}), 401
    os.system("sudo reboot")
    return jsonify({"status": "Rebooting"})

@app.route("/shutdown_system", methods=["POST"])
def shutdown_system():
    if not session.get("logged_in"):
        return jsonify({"error": "Unauthorized"}), 401
    os.system("sudo shutdown now")
    return jsonify({"status": "Shutting down"})

# --- DHCP Flask Route Snippets ---
import subprocess
from flask import request, jsonify

@app.route("/save_dhcp_config", methods=["POST"])
def save_dhcp_config():
    if not session.get("logged_in"):
        return jsonify({"error": "Unauthorized"}), 401

    try:
        data = request.get_json()
        config_path = "/home/cornerpins/portal/dhcp_config.json"

        # Ensure required fields have defaults
        config = {
            "lan_nic": data.get("lan_nic", "eth1"),
            "wan_nic": data.get("wan_nic", "eth0"),
            "lan_ip": data.get("lan_ip", "192.168.83.83"),
            "subnet": data.get("subnet", "255.255.255.0"),
            "range_start": data.get("range_start", "192.168.83.100"),
            "range_end": data.get("range_end", "192.168.83.200"),
            "reservations": data.get("reservations", {})
        }

        logger.info(f"💾 Saving config to: {config_path}")
        # Save config file
        with open(config_path, "w", encoding="utf-8") as f:
            json.dump(config, f, indent=2)
        logger.info("✅ Config file saved successfully")

        # Regenerate dnsmasq config but DON'T restart automatically
        logger.info("🔄 Regenerating dnsmasq config...")
        regen_success = regenerate_dnsmasq_conf(config)
        
        if not regen_success:
            logger.error("❌ Failed to regenerate dnsmasq config")
            return jsonify({"error": "Failed to regenerate dnsmasq config"}), 500

        # DON'T restart dnsmasq automatically - let user control it with Start/Stop buttons
        logger.info(f"🎉 DHCP config saved successfully. LAN NIC: {config['lan_nic']} | WAN NIC: {config['wan_nic']}")
        return jsonify({
            "success": True, 
            "message": "DHCP config saved successfully. Use Start/Stop DHCP buttons to control the server."
        })
        
    except Exception as e:
        logger.error(f"❌ Error saving DHCP config: {e}")
        import traceback
        logger.error(f"Full traceback: {traceback.format_exc()}")
        return jsonify({"error": str(e)}), 500

def regenerate_dnsmasq_conf(data):
    """Generate a new dnsmasq config file with static reservations."""
    lan_nic = data.get("lan_nic", "eth1").strip() or "eth1"

    lines = [
        f"interface={lan_nic}",
        f"dhcp-range={data['range_start']},{data['range_end']},{data['subnet']},12h"
    ]

    # Fixed camera IPs
    camera_ip_map = {
        "Lane 1&2": "192.168.83.1", "Lane 3&4": "192.168.83.3", "Lane 5&6": "192.168.83.5",
        "Lane 7&8": "192.168.83.7", "Lane 9&10": "192.168.83.9", "Lane 11&12": "192.168.83.11",
        "Lane 13&14": "192.168.83.13", "Lane 15&16": "192.168.83.15", "Lane 17&18": "192.168.83.17",
        "Lane 19&20": "192.168.83.19", "Lane 21&22": "192.168.83.21", "Lane 23&24": "192.168.83.23"
    }

    for label, mac in data.get("reservations", {}).items():
        if mac.strip():  # Only add if MAC address is not empty
            if label in camera_ip_map:
                # Camera - use fixed IP
                ip = camera_ip_map[label]
                lines.append(f"dhcp-host={mac.strip()},{ip}")
            else:
                # Switch - calculate IP based on switch number
                switch_match = re.search(r'Switch (\d+)', label)
                if switch_match:
                    switch_number = int(switch_match.group(1))
                    ip = f"192.168.83.{switch_number * 2}"
                    lines.append(f"dhcp-host={mac.strip()},{ip}")

    # Write to portal directory first (user has permissions here)
    local_path = "/home/cornerpins/portal/streamnode.conf"
    conf_path = "/etc/dnsmasq.d/streamnode.conf"
    
    try:
        # Write to local file first
        with open(local_path, "w") as f:
            f.write("\n".join(lines))
        
        # Copy to system location with sudo
        subprocess.run(["sudo", "cp", local_path, conf_path], check=True, timeout=10)
        subprocess.run(["sudo", "chmod", "644", conf_path], check=True, timeout=5)
        
        logger.info(f"Generated dnsmasq config with {len(lines)} lines using interface {lan_nic}")
        return True
        
    except Exception as e:
        logger.error(f"Failed to write dnsmasq config: {e}")
        return False

@app.route("/get_dhcp_config", methods=["GET"])
def get_dhcp_config():
    """Fetch the current DHCP config from the JSON file"""
    try:
        config_path = "/home/cornerpins/portal/dhcp_config.json"
        
        # Default config if file doesn't exist
        default_config = {
            "lan_nic": "eth1",
            "wan_nic": "eth0", 
            "lan_ip": "192.168.83.83",
            "subnet": "255.255.255.0",
            "range_start": "192.168.83.100",
            "range_end": "192.168.83.200",
            "reservations": {}
        }
        
        if os.path.exists(config_path):
            with open(config_path, "r", encoding="utf-8") as f:
                config = json.load(f)
                # Ensure all required fields exist
                for key, value in default_config.items():
                    if key not in config:
                        config[key] = value
        else:
            config = default_config
            # Create the file with defaults
            with open(config_path, "w", encoding="utf-8") as f:
                json.dump(config, f, indent=2)
                
        return jsonify(config)
    except Exception as e:
        logger.error(f"Error loading DHCP config: {e}")
        return jsonify({"error": str(e)}), 500


def regenerate_dnsmasq_conf(data):
    """Generate a new dnsmasq config file with static reservations."""
    lan_nic = data.get("lan_nic", "eth1").strip() or "eth1"

    lines = [
        f"interface={lan_nic}",
        f"dhcp-range={data['range_start']},{data['range_end']},{data['subnet']},12h"
    ]

    for label, mac in data.get("reservations", {}).items():
        if mac:
            ip = derive_ip_from_label(label)
            lines.append(f"dhcp-host={mac},{ip}")

    conf_path = "/etc/dnsmasq.d/streamnode.conf"
    with open(conf_path, "w") as f:
        f.write("\n".join(lines))

        logger.info(f"Generated dnsmasq config with {len(lines)} lines using interface {lan_nic}")

def derive_ip_from_label(label):
    """Map the label (camera or switch) to the static IP."""
    lane_ip_map = {
        "Lane 1&2": "192.168.83.1", "Lane 3&4": "192.168.83.3", "Lane 5&6": "192.168.83.5",
        "Lane 7&8": "192.168.83.7", "Lane 9&10": "192.168.83.9", "Lane 11&12": "192.168.83.11",
        "Lane 13&14": "192.168.83.13", "Lane 15&16": "192.168.83.15", "Lane 17&18": "192.168.83.17",
        "Lane 19&20": "192.168.83.19", "Lane 21&22": "192.168.83.21", "Lane 23&24": "192.168.83.23",
        "Switch 1": "192.168.83.2", "Switch 2": "192.168.83.4", "Switch 3": "192.168.83.6",
        "Switch 4": "192.168.83.8", "Switch 5": "192.168.83.10", "Switch 6": "192.168.83.12",
        "Switch 7": "192.168.83.14", "Switch 8": "192.168.83.16", "Switch 9": "192.168.83.18",
        "Switch 10": "192.168.83.20", "Switch 11": "192.168.83.22", "Switch 12": "192.168.83.24"
    }
    return lane_ip_map.get(label, "")


@app.route("/get_nics")
def get_nics():
    """Fetch the available network interfaces and the currently configured LAN/WAN NICs."""
    try:
        import netifaces
        all_nics = netifaces.interfaces()
        filtered = [nic for nic in all_nics if nic != "lo"]  # Exclude loopback interface
        config_path = "/home/cornerpins/portal/dhcp_config.json"

        saved_config = {"lan": "", "wan": ""}
        if os.path.isfile(config_path):
            with open(config_path, "r", encoding="utf-8") as f:
                data = json.load(f)
                saved_config["lan"] = data.get("lan_nic", "")
                saved_config["wan"] = data.get("wan_nic", "")

        return jsonify({"nics": filtered, "config": saved_config})
    except Exception as e:
        return jsonify({"error": str(e), "nics": [], "config": {}}), 500

@app.route("/get_nic_statuses")
def get_nic_statuses():
    import netifaces
    import subprocess

    result = {
        "ip_map": {},
        "ping": {}
    }

    try:
        interfaces = netifaces.interfaces()
        for iface in interfaces:
            addrs = netifaces.ifaddresses(iface)
            inet = addrs.get(netifaces.AF_INET)
            if inet:
                ip = inet[0].get("addr")
                if ip:
                    result["ip_map"][iface] = ip
                    # Try ping
                    try:
                        subprocess.check_call(["ping", "-c", "1", ip], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=2)
                        result["ping"][ip] = True
                    except:
                        result["ping"][ip] = False
    except Exception as e:
        result["error"] = str(e)

    return jsonify(result)

TEMPLATES_PATH = "venue_templates.json"

def load_venue_templates():
    try:
        with open(TEMPLATES_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return []

def save_venue_templates(templates):
    try:
        with open(TEMPLATES_PATH, "w", encoding="utf-8") as f:
            json.dump(templates, f, indent=4)
        logger.info(f"Venue templates saved: {len(templates)} templates")
    except Exception as e:
        logger.error(f"Failed to save venue templates: {e}")

@app.route("/save_venue_template", methods=["POST"])
def save_venue_template():
    if not session.get("logged_in"):
        return jsonify({"error": "Unauthorized"}), 401
    
    template_name = request.json.get("template_name")
    event_name = request.json.get("event_name")
    venue = request.json.get("venue")
    has_banner = request.json.get("has_banner", False)
    banner_url = request.json.get("banner_url")
    
    if not all([template_name, event_name, venue]):
        return jsonify({"error": "Missing required fields"}), 400
    
    templates = load_venue_templates()
    
    # Remove existing template with same name
    templates = [t for t in templates if t["name"] != template_name]
    
    # Add new template with banner info
    template_data = {
        "name": template_name,
        "event_name": event_name,
        "venue": venue,
        "has_banner": has_banner,
        "created_at": time.strftime("%Y-%m-%d %H:%M:%S")
    }
    
    # Only add banner_url if it's a real URL (not placeholder)
    if banner_url and banner_url != 'pending_upload':
        template_data["banner_url"] = banner_url
    
    templates.append(template_data)
    
    save_venue_templates(templates)
    logger.info(f"Saved venue template: {template_name} (has_banner: {has_banner})")
    return jsonify({"success": True, "message": "Template saved"})
    
@app.route("/get_venue_templates", methods=["GET"])
def get_venue_templates():
    if not session.get("logged_in"):
        return jsonify({"error": "Unauthorized"}), 401
    
    templates = load_venue_templates()
    return jsonify(templates)

@app.route("/delete_venue_template", methods=["POST"])
def delete_venue_template():
    if not session.get("logged_in"):
        return jsonify({"error": "Unauthorized"}), 401
    
    template_name = request.json.get("template_name")
    if not template_name:
        return jsonify({"error": "Template name required"}), 400
    
    templates = load_venue_templates()
    templates = [t for t in templates if t["name"] != template_name]
    save_venue_templates(templates)
    
    return jsonify({"success": True, "message": "Template deleted"})

@app.route("/upload_banner_temp", methods=["POST"])
def upload_banner_temp():
    """Upload banner immediately when selected, before form submission"""
    if not session.get("logged_in"):
        return jsonify({"error": "Unauthorized"}), 401
    
    try:
        banner_file = request.files.get("banner_file")
        if not banner_file or not banner_file.filename:
            return jsonify({"error": "No banner file provided"}), 400
        
        # Create directories
        os.makedirs("static/event_banners", exist_ok=True)
        
        # Generate unique filename
        import uuid
        file_ext = os.path.splitext(banner_file.filename)[1]
        banner_filename = f"{uuid.uuid4().hex}{file_ext}"
        banner_path = os.path.join("static", "event_banners", banner_filename)
        
        # Save file
        banner_file.save(banner_path)
        
        # Return the URL
        banner_url = f"/static/event_banners/{banner_filename}"
        
        logger.info(f"Temp banner uploaded: {banner_path}")
        return jsonify({
            "success": True, 
            "banner_url": banner_url,
            "banner_filename": banner_filename
        })
        
    except Exception as e:
        logger.error(f"Error uploading temp banner: {e}")
        return jsonify({"error": str(e)}), 500

@app.route('/api/gpu/status')
def get_gpu_status():
    """Get GPU status information from nvidia-smi"""
    try:
        # Run nvidia-smi with CSV output for easier parsing
        result = subprocess.run([
            'nvidia-smi', 
            '--query-gpu=name,utilization.gpu,utilization.memory,memory.used,memory.total,temperature.gpu,power.draw,power.limit,clocks.current.graphics,encoder.stats.sessionCount',
            '--format=csv,noheader,nounits'
        ], capture_output=True, text=True, timeout=10)
        
        if result.returncode != 0:
            return jsonify({'error': 'nvidia-smi command failed', 'details': result.stderr}), 500
        
        gpus = []
        lines = result.stdout.strip().split('\n')
        
        for line in lines:
            if line.strip():
                parts = [part.strip() for part in line.split(',')]
                if len(parts) >= 6:  # Ensure we have minimum required fields
                    gpu_data = {
                        'name': parts[0],
                        'utilization': parts[1].replace('%', '') if parts[1] != '[Not Supported]' else '0',
                        'memory_utilization': parts[2].replace('%', '') if parts[2] != '[Not Supported]' else '0',
                        'memory_used': parts[3] if parts[3] != '[Not Supported]' else '0',
                        'memory_total': parts[4] if parts[4] != '[Not Supported]' else '0',
                        'temperature': parts[5] if parts[5] != '[Not Supported]' else '0',
                        'power_draw': parts[6] if len(parts) > 6 and parts[6] != '[Not Supported]' else 'N/A',
                        'power_limit': parts[7] if len(parts) > 7 and parts[7] != '[Not Supported]' else 'N/A',
                        'clocks_current': parts[8] if len(parts) > 8 and parts[8] != '[Not Supported]' else 'N/A',
                        'encoder_sessions': parts[9] if len(parts) > 9 and parts[9] != '[Not Supported]' else '0'
                    }
                    gpus.append(gpu_data)
        
        return jsonify({
            'success': True,
            'gpus': gpus,
            'timestamp': subprocess.run(['date', '+%Y-%m-%d %H:%M:%S'], 
                                     capture_output=True, text=True).stdout.strip()
        })
        
    except subprocess.TimeoutExpired:
        return jsonify({'error': 'nvidia-smi command timed out'}), 500
    except subprocess.CalledProcessError as e:
        return jsonify({'error': f'nvidia-smi error: {e}'}), 500
    except Exception as e:
        return jsonify({'error': f'Unexpected error: {str(e)}'}), 500


@app.route('/api/rtmp/settings', methods=['GET', 'POST'])
def get_rtmp_settings():
   """Get current RTMP settings"""
   if request.method == 'GET':
       try:
           if os.path.exists(RTMP_CONFIG_FILE):
               with open(RTMP_CONFIG_FILE, 'r') as f:
                   settings = json.load(f)
           else:
               # Default settings that match your existing form
               settings = {
                   'encoder': 'obs_nvenc',
                   'bitrate': 6000,
                   'rate_control': 'CBR',
                   'keyint_sec': 2,
                   'preset': 'p5',
                   'profile': 'high',
                   'gpu': 0,
                   'bf': 2,
                   'lookahead': 'false',
                   'psycho_aq': 'true'
               }
           
           return jsonify(settings)
           
       except Exception as e:
           return jsonify({'error': f'Failed to load settings: {str(e)}'}), 500
   
   elif request.method == 'POST':
       """Save RTMP settings (enhanced version)"""
       try:
           settings = request.get_json()
           
           # Validate settings
           if not settings:
               return jsonify({'error': 'No settings provided'}), 400
           
           # Ensure directory exists
           os.makedirs(os.path.dirname(RTMP_CONFIG_FILE), exist_ok=True)
           
           # Save to file
           with open(RTMP_CONFIG_FILE, 'w') as f:
               json.dump(settings, f, indent=2)
           
           # Apply settings using your existing function (now enhanced)
           try:
               apply_rtmp_settings_to_multi_rtmp(settings)
               logger.info("🔧 Enhanced RTMP settings saved and applied")
           except Exception as e:
               logger.warning(f"Settings saved but failed to apply to Multi-RTMP: {e}")
           
           return jsonify({'success': True, 'message': 'Enhanced RTMP settings saved successfully'})
           
       except Exception as e:
           return jsonify({'error': f'Failed to save enhanced settings: {str(e)}'}), 500

def apply_rtmp_settings_to_multi_rtmp(settings):
    """Apply RTMP settings to Multi-RTMP config (enhanced to handle per-stream)"""
    try:
        from pathlib import Path
        
        obs_profile_dir = Path.home() / ".config" / "obs-studio" / "basic" / "profiles"
        profile_dirs = [d for d in obs_profile_dir.iterdir() if d.is_dir()]
        
        if not profile_dirs:
            logger.error("OBS profile directory not found")
            return
        
        profile_path = Path.home() / ".config" / "obs-studio" / "basic" / "profiles" / "Cornerpins" / "multiple_output.json"
        
        # Get current config and enabled pairs
        cfg = load_config()
        enabled_pairs = [p for p in cfg.get("lane_pairs", []) if p.get("enabled", False)]
        rtmp_base = cfg.get("youtube_rtmp_base", "rtmp://a.rtmp.youtube.com/live2")
        
        outputs = []
        
        for pair in enabled_pairs:
            stream_key = pair.get("stream_key", "")
            pair_name = pair.get("name")
            
            if not stream_key:
                continue
            
            # Determine which settings to use for this stream
            if isinstance(settings, dict) and settings.get("universal", True):
                # Use universal settings (new format)
                stream_settings = settings.get("universal_settings", settings)
            elif isinstance(settings, dict) and "streams" in settings:
                # Use per-stream settings (new format)
                stream_settings = settings.get("streams", {}).get(pair_name, settings.get("universal_settings", settings))
            else:
                # Use global settings (old format - backward compatibility)
                stream_settings = settings
            
            # Build output config with proper data types
            output_config = {
                "name": f"{pair_name}",
                "enabled": True,
                "server": rtmp_base,
                "key": stream_key,
                "use_obs_settings": False,
                "settings": {
                    "encoder": stream_settings.get("encoder", "obs_nvenc"),
                    "bitrate": str(stream_settings.get("bitrate", 6000)),
                    "rate_control": stream_settings.get("rate_control", "CBR"),
                    "keyint_sec": int(stream_settings.get("keyint_sec", 2)),
                    "preset": stream_settings.get("preset", "p5"),
                    "profile": stream_settings.get("profile", "high"),
                    "gpu": str(stream_settings.get("gpu", 0)),
                    "bf": int(stream_settings.get("bf", 2)),
                    "lookahead": stream_settings.get("lookahead", "false") == "true",
                    "psycho_aq": stream_settings.get("psycho_aq", "true") == "true"
                }
            }
            
            outputs.append(output_config)
        
        # Save the Multi-RTMP config
        config_data = {"outputs": outputs}
        
        with open(profile_path, "w", encoding="utf-8") as f:
            json.dump(config_data, f, indent=2)
        
        logger.info(f"Enhanced RTMP settings applied to {len(outputs)} streams")
        
        # Try to reload Multi-RTMP config in OBS
        try:
            ws = obsws(OBS_HOST, OBS_PORT, OBS_PASSWORD)
            ws.connect()
            
            ws.call(obs_requests.CallVendorRequest(
                vendorName="obs-multi-rtmp",
                requestType="ReloadConfig",
                requestData={}
            ))
            
            ws.disconnect()
            logger.info("Multi-RTMP config reloaded in OBS")
            
        except Exception as e:
            logger.warning(f"Could not reload Multi-RTMP config: {e}")
        
    except Exception as e:
        logger.error(f"Error applying enhanced RTMP settings: {e}")

@app.route('/api/multi-rtmp/status', methods=['GET'])
def get_multi_rtmp_status():
    """Get current Multi-RTMP plugin status from OBS"""
    try:
        ws = obsws(OBS_HOST, OBS_PORT, OBS_PASSWORD)
        ws.connect()
        
        try:
            # Try to get Multi-RTMP status
            response = ws.call(obs_requests.CallVendorRequest(
                vendorName="obs-multi-rtmp",
                requestType="GetStatus",
                requestData={}
            ))
            
            status_data = response.getRequestResponse()
            ws.disconnect()
            
            return jsonify({
                "success": True,
                "outputs": status_data.get("outputs", []),
                "streaming": status_data.get("streaming", False)
            })
            
        except Exception as e:
            ws.disconnect()
            # If Multi-RTMP plugin doesn't support GetStatus, return basic info
            logger.warning(f"Multi-RTMP GetStatus not supported: {e}")
            
            # Read the config file instead
            try:
                from pathlib import Path
                obs_config_base = Path.home() / ".config" / "obs-studio" / "basic" / "profiles"
                profile_dirs = [d for d in obs_config_base.iterdir() if d.is_dir()]
                
                if profile_dirs:
                    config_file = profile_dirs[0] / "multiple_output.json"
                    if config_file.exists():
                        with open(config_file, 'r') as f:
                            config = json.load(f)
                        
                        return jsonify({
                            "success": True,
                            "outputs": config.get("outputs", []),
                            "streaming": False,
                            "note": "Status from config file"
                        })
            except Exception:
                pass
            
            return jsonify({
                "success": False,
                "error": "Multi-RTMP status not available",
                "outputs": []
            })
            
    except Exception as e:
        logger.error(f"OBS connection error: {e}")
        return jsonify({
            "success": False,
            "error": "Failed to connect to OBS",
            "outputs": []
        }), 500

@app.route("/logs")
def view_logs():
    if not session.get("logged_in"):
        return redirect(url_for("login"))
    
    import re
    from collections import defaultdict
    
    logs = {
        "youtube": [],
        "obs": [],
        "streaming": [],
        "overlays": [],
        "audio": [],
        "network": [],
        "ads": [],
        "system": [],
        "all": []
    }
    
    # Read main app log (if using file logging)
    try:
        # Try systemd journal first
        result = subprocess.run(
            ["journalctl", "-u", "cornerpins-portal", "-n", "500", "--no-pager", "--output=short-iso"],
            capture_output=True,
            text=True
        )
        if result.returncode == 0:
            all_lines = result.stdout.strip().split('\n')
        else:
            # Fallback to any log file
            all_lines = []
    except:
        all_lines = []
    
    # Read YouTube debug log if it exists
    youtube_log_path = "/home/cornerpins/portal/youtube_debug.log"
    if os.path.exists(youtube_log_path):
        try:
            with open(youtube_log_path, 'r') as f:
                youtube_lines = f.readlines()[-200:]  # Last 200 lines
                logs["youtube"] = youtube_lines
        except:
            pass
    
    # Read ad playback log
    ad_log_path = "/home/cornerpins/portal/logs/ad_playback_log.jsonl"
    if os.path.exists(ad_log_path):
        try:
            with open(ad_log_path, 'r') as f:
                lines = f.readlines()[-100:]  # Last 100 entries
                for line in lines:
                    try:
                        entry = json.loads(line.strip())
                        formatted = f"[{entry['timestamp']}] {entry['stream']} - {entry['ad_name']} ({entry['duration']}s) - Trigger: {entry['trigger']}"
                        logs["ads"].append(formatted)
                    except:
                        pass
        except:
            pass
    
    # Parse and categorize main logs
    for line in all_lines:
        logs["all"].append(line)
        
        # Categorize by content
        line_lower = line.lower()
        
        if any(keyword in line_lower for keyword in ['youtube', 'stream_key', 'broadcast', 'autocreate']):
            logs["youtube"].append(line)
        
        if any(keyword in line_lower for keyword in ['obs', 'scene', 'source', 'websocket']):
            logs["obs"].append(line)
            
        if any(keyword in line_lower for keyword in ['streaming', 'rtmp', 'multi-rtmp']):
            logs["streaming"].append(line)
            
        if any(keyword in line_lower for keyword in ['overlay', 'scoring', 'livescore']):
            logs["overlays"].append(line)
            
        if any(keyword in line_lower for keyword in ['audio', 'pulse', 'device']):
            logs["audio"].append(line)
            
        if any(keyword in line_lower for keyword in ['network', 'rtsp', 'camera', 'ip']):
            logs["network"].append(line)
            
        if any(keyword in line_lower for keyword in ['error', 'failed', 'exception', 'critical']):
            logs["system"].append(line)
    
    # Get last 200 lines for each category
    for key in logs:
        if key != "all":
            logs[key] = logs[key][-200:]
    
    return render_template("logs.html", logs=logs, logged_in=True)

@app.route("/logs/clear/<category>", methods=["POST"])
def clear_logs(category):
    if not session.get("logged_in"):
        return jsonify({"error": "Unauthorized"}), 401
    
    # Clear specific log files based on category
    if category == "youtube":
        try:
            open("/home/cornerpins/portal/youtube_debug.log", 'w').close()
            return jsonify({"success": True})
        except:
            pass
    
    elif category == "ads":
        try:
            open("/home/cornerpins/portal/logs/ad_playback_log.jsonl", 'w').close()
            return jsonify({"success": True})
        except:
            pass
    
    return jsonify({"error": "Cannot clear this log category"}), 400

if __name__ == "__main__":
    socketio.run(app, host="0.0.0.0", port=1983, debug=False, allow_unsafe_werkzeug=True)




