#!/usr/bin/env python3
import os
import re
import time
import json
import argparse
import subprocess
import requests
from bs4 import BeautifulSoup

CONFIG_PATH = "/home/cornerpins/portal/streams_config.json"
VENV_PYTHON = "/home/cornerpins/portal/venv/bin/python3"
SCRIPT_PATH = "/home/cornerpins/portal/setup_12_streams.py"
POLL_INTERVAL = 20

def load_config():
    with open(CONFIG_PATH, "r", encoding="utf-8") as f:
        return json.load(f)

def save_config(cfg):
    with open(CONFIG_PATH, "w", encoding="utf-8") as f:
        json.dump(cfg, f, indent=2)

def fetch_lanes_html(centre_id):
    url = f"https://livescores.computerscore.com.au/view-lanes.php?centre={centre_id}"
    r = requests.get(url, timeout=10)
    r.raise_for_status()
    return r.text

def parse_lane_series_map(html):
    soup = BeautifulSoup(html, "html.parser")
    lane_map = {}
    rows = soup.select("tr")
    for row in rows:
        cols = row.find_all("td")
        if len(cols) < 2:
            continue
        lane_text = cols[0].get_text(strip=True)
        view_link = cols[-1].find("a", href=True)
        if not lane_text.lower().startswith("lane") or not view_link:
            continue
        match = re.search(r"seriesID=(\d+)", view_link["href"])
        if match:
            lane_num = int(re.search(r"(\d+)", lane_text).group(1))
            series_id = match.group(1)
            lane_map[lane_num] = series_id
    return lane_map

def monitor_pair(pair_index):
    while True:
        try:
            full_config = load_config()
            if pair_index >= len(full_config.get("lane_pairs", [])):
                print(f"[Pair {pair_index}] Invalid index in config.")
                return

            pair = full_config["lane_pairs"][pair_index]
            if not pair.get("enabled"):
                print(f"[Pair {pair_index}] Not enabled. Exiting.")
                return
            if pair.get("scoring_type") != "livescores":
                print(f"[Pair {pair_index}] Not using Computerscore Livescores. Exiting.")
                return
            centre_id = pair.get("centre")
            if not centre_id:
                print(f"[Pair {pair_index}] No centre selected. Exiting.")
                return

            html = fetch_lanes_html(centre_id)
            lane_map = parse_lane_series_map(html)

            name = pair["name"]
            odd_lane = int(name.split("&")[0].strip().replace("Lane", ""))
            even_lane = odd_lane + 1

            old_odd = pair.get("odd_lane_scoring_source", "")
            old_even = pair.get("even_lane_scoring_source", "")

            new_odd = f"https://livescores.computerscore.com.au/view.php?centre={centre_id}&seriesID={lane_map.get(odd_lane)}" if lane_map.get(odd_lane) else ""
            new_even = f"https://livescores.computerscore.com.au/view.php?centre={centre_id}&seriesID={lane_map.get(even_lane)}" if lane_map.get(even_lane) else ""

            changed = False
            if new_odd and new_odd != old_odd:
                pair["odd_lane_scoring_source"] = new_odd
                changed = True
            if new_even and new_even != old_even:
                pair["even_lane_scoring_source"] = new_even
                changed = True

            if changed:
                print(f"[Pair {pair_index}] SeriesIDs updated.")
                full_config["lane_pairs"][pair_index]["odd_lane_scoring_source"] = new_odd
                full_config["lane_pairs"][pair_index]["even_lane_scoring_source"] = new_even
                save_config(full_config)


                #print(f"[Pair {pair_index}] Reapplying OBS scene.")   EJ edited this to ensure OBS scene creation doesnt happen.
                #subprocess.call([VENV_PYTHON, SCRIPT_PATH, "--no-stream"])
            else:
                print(f"[Pair {pair_index}] No change.")

        except Exception as e:
            print(f"[Pair {pair_index}] Error: {e}")

        time.sleep(POLL_INTERVAL)

if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--pair", type=int, required=True, help="Lane pair index (0-11)")
    args = p.parse_args()
    monitor_pair(args.pair)
