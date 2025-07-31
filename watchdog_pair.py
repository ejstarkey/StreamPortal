# watchdog_pair.py (Upgraded with Advanced Ad Logic)
import os
import json
import time
import logging
import argparse
import subprocess
import re
from datetime import datetime
import requests
from bs4 import BeautifulSoup
from obswebsocket import obsws, requests as obs_requests
import random
import itertools

# ─── PATHS ────────────────────────────────
PORTAL_DIR = "/home/cornerpins/portal"
CONFIG_PATH = os.path.join(PORTAL_DIR, "streams_config.json")
ADS_META_PATH = os.path.join(PORTAL_DIR, "ads/ads_metadata.json")
ADS_DIR = os.path.join(PORTAL_DIR, "ads")
ADS_CONFIG_PATH = os.path.join(PORTAL_DIR, "ads_config.json")
ADS_LOG_PATH = os.path.join(PORTAL_DIR, "logs/ad_playback_log.jsonl")

OBS_HOST = "localhost"
OBS_PORT = 4455
OBS_PASSWORD = "B0wl1ng2025!"
POLL_INTERVAL = 10  # seconds

# ─── UTILS ────────────────────────────────

def load_json(path):
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        logging.error(f"Failed to load JSON from {path}: {e}")
        return {}

def load_ads_config():
    return load_json(ADS_CONFIG_PATH)

def load_ads_metadata():
    ads = load_json(ADS_META_PATH)
    for ad in ads:
        ad.setdefault("priority", 5)
    return ads

def get_media_duration(path):
    try:
        out = subprocess.check_output([
            "ffprobe", "-v", "error",
            "-show_entries", "format=duration",
            "-of", "default=noprint_wrappers=1:nokey=1",
            path
        ])
        return float(out.strip())
    except Exception as e:
        logging.warning("ffprobe failed on %s: %s", path, e)
        return None

def log_ad_playback(ad, stream, duration, trigger):
    entry = {
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "stream": stream,
        "ad_id": ad.get("id"),
        "ad_name": ad.get("name"),
        "duration": duration,
        "trigger": trigger
    }
    try:
        os.makedirs(os.path.dirname(ADS_LOG_PATH), exist_ok=True)
        with open(ADS_LOG_PATH, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry) + "\n")
    except Exception as e:
        logging.warning("Failed to log ad playback: %s", e)

def weighted_shuffle(ads):
    return sorted(ads, key=lambda a: random.random() / a.get("priority", 5))

def pick_ads_to_fill(target_sec, ad_pool, last_ad_id):
    pool = [a for a in ad_pool if a["id"] != last_ad_id]
    combos = []
    for r in range(1, len(pool) + 1):
        for combo in itertools.combinations(pool, r):
            total = 0
            for ad in combo:
                if ad["type"] == "Image":
                    total += ad.get("duration", 5)
                else:
                    total += get_media_duration(os.path.join(ADS_DIR, ad["filename"])) or 5
            if total >= target_sec:
                combos.append((combo, total))
    if not combos:
        return [pool[0]] if pool else []
    best = min(combos, key=lambda x: x[1] - target_sec)
    return list(best[0])

def connect_obs():
    ws = obsws(OBS_HOST, OBS_PORT, OBS_PASSWORD)
    ws.connect()
    return ws

def extract_overlay_info(html):
    soup = BeautifulSoup(html, "html.parser")

    text = soup.get_text()
    game_m = re.search(r"Game\s*(\d+)\s*of\s*(\d+)", text)
    game_num, total_games = (int(game_m.group(1)), int(game_m.group(2))) if game_m else (None, None)

    bowler_tables = soup.select("table.scoreboard")
    bowler_frames = []

    for table in bowler_tables:
        if not table.find("h2"):
            continue
        frames = table.select("td.score")
        completed = sum(1 for td in frames if td.text.strip() not in {"", "-", " "})
        bowler_frames.append(completed)

    return {
        "game": game_num,
        "total_games": total_games,
        "frame_counts": bowler_frames
    }

def play_ads(pair_name, ads, trigger):
    for ad in ads:
        file_path = os.path.join(ADS_DIR, ad["filename"])
        duration = ad.get("duration", 5) if ad["type"] == "Image" else get_media_duration(file_path) or 5
        try:
            ws = connect_obs()
            source_name = f"ad_{pair_name}_{ad['id']}"
            settings = {"local_file": file_path, "looping": False}
            ws.call(obs_requests.CreateInput(source_name, "ffmpeg_source", settings))
            ws.call(obs_requests.AddSceneItem(sceneName=pair_name, sourceName=source_name))
            ws.call(obs_requests.RestartMedia(sourceName=source_name))
            time.sleep(duration)
            ws.call(obs_requests.RemoveInput(sourceName=source_name))
            ws.disconnect()
        except Exception as e:
            logging.warning("Failed to play ad %s: %s", ad.get("name"), e)
        log_ad_playback(ad, pair_name, duration, trigger)

def main(pair_index):
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    )
    cfg = load_json(CONFIG_PATH)
    ads_cfg = load_ads_config()
    ads_meta = load_ads_metadata()
    pair = cfg["lane_pairs"][pair_index]
    pair_name = pair["name"]
    state = {
        "last_game": None,
        "halfway_triggered": False,
        "lane_change_triggered": False,
        "last_ad_id": None
    }

    while True:
        if not pair.get("enabled", False):
            logging.info("%s disabled; sleeping", pair_name)
            time.sleep(POLL_INTERVAL)
            continue

        try:
            htmlA = requests.get(pair["odd_lane_scoring_source"], timeout=5).text
            htmlB = requests.get(pair["even_lane_scoring_source"], timeout=5).text
            infoA = extract_overlay_info(htmlA)
            infoB = extract_overlay_info(htmlB)

            mode = ads_cfg.get("mode", "TEAM").upper()
            ads_for_stream = [a for a in ads_meta if pair_name in a.get("streams", [])]
            ads_for_stream = weighted_shuffle(ads_for_stream)

            if mode == "TEAM":
                team_cfg = ads_cfg.get("team", {})
                halfway_done = (
                    all(f >= 5 for f in infoA["frame_counts"]) and
                    all(f >= 5 for f in infoB["frame_counts"])
                )
                if not state["halfway_triggered"] and halfway_done:
                    ads = pick_ads_to_fill(team_cfg.get("halfway_duration", 30), ads_for_stream, state["last_ad_id"])
                    play_ads(pair_name, ads, "halfway")
                    state["halfway_triggered"] = True
                    if ads: state["last_ad_id"] = ads[-1]["id"]

                lane_change_ready = (
                    all(f >= 10 for f in infoA["frame_counts"]) and
                    all(f >= 10 for f in infoB["frame_counts"])
                )
                if not state["lane_change_triggered"] and lane_change_ready:
                    time.sleep(team_cfg.get("lane_change_delay", 30))
                    ads = pick_ads_to_fill(team_cfg.get("lane_change_duration", 180), ads_for_stream, state["last_ad_id"])
                    play_ads(pair_name, ads, "lane_change")
                    state["lane_change_triggered"] = True
                    if ads: state["last_ad_id"] = ads[-1]["id"]

            elif mode == "CUP":
                cup_cfg = ads_cfg.get("cup", {})
                game = min(infoA["game"] or 0, infoB["game"] or 0)
                total = max(infoA["total_games"] or 0, infoB["total_games"] or 0)

                halfway_done = (
                    all(f >= 5 for f in infoA["frame_counts"]) and
                    all(f >= 5 for f in infoB["frame_counts"])
                )
                if not state["halfway_triggered"] and halfway_done:
                    ads = pick_ads_to_fill(cup_cfg.get("halfway_duration", 30), ads_for_stream, state["last_ad_id"])
                    play_ads(pair_name, ads, "halfway")
                    state["halfway_triggered"] = True
                    if ads: state["last_ad_id"] = ads[-1]["id"]

                if state["last_game"] and game > state["last_game"]:
                    ads = pick_ads_to_fill(cup_cfg.get("game_change_duration", 30), ads_for_stream, state["last_ad_id"])
                    play_ads(pair_name, ads, "game_change")
                    if ads: state["last_ad_id"] = ads[-1]["id"]

                final_game_done = (
                    game == total and
                    all(f >= 10 for f in infoA["frame_counts"]) and
                    all(f >= 10 for f in infoB["frame_counts"])
                )
                if final_game_done and not state["lane_change_triggered"]:
                    time.sleep(cup_cfg.get("final_game_delay", 15))
                    ads = pick_ads_to_fill(cup_cfg.get("final_game_duration", 180), ads_for_stream, state["last_ad_id"])
                    play_ads(pair_name, ads, "lane_change")
                    state["lane_change_triggered"] = True
                    if ads: state["last_ad_id"] = ads[-1]["id"]

                state["last_game"] = game

        except Exception as e:
            logging.warning("Watchdog loop error for %s: %s", pair_name, e)

        time.sleep(POLL_INTERVAL)

if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--pair", type=int, required=True)
    args = p.parse_args()
    main(args.pair)
