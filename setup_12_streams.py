import json
import time
import argparse
import configparser
import logging
from obswebsocket import obsws, requests
import os
from pathlib import Path
import subprocess

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

CONFIG_PATH = "streams_config.json"
OBS_HOST = "localhost"
OBS_PORT = 4455
OBS_PASSWORD = "B0wl1ng2025!"

def get_test_pattern_path(scene_name):
    """Generate the test pattern file path based on scene name"""
    import os
    
    # Extract lane numbers from scene name (e.g., "Lane 1&2" -> "1_2")
    try:
        # Handle different possible formats
        if "&" in scene_name:
            lanes = scene_name.replace("Lane ", "").replace(" ", "").split("&")
        else:
            # Fallback parsing
            lanes = scene_name.split()[-1].split("&") if "&" in scene_name else ["1", "2"]
        
        test_pattern_name = f"{lanes[0]}_{lanes[1]}_test_pattern.png"
        test_pattern_path = f"/home/cornerpins/portal/static/images/{test_pattern_name}"
        
        # Verify file exists
        if os.path.exists(test_pattern_path):
            logger.info(f"Found test pattern: {test_pattern_path}")
            return test_pattern_path
        else:
            logger.warning(f"Test pattern not found: {test_pattern_path}")
            return None
            
    except Exception as e:
        logger.error(f"Error determining test pattern path for {scene_name}: {e}")
        return None

def load_config():
    logger.info(f"Loading configuration from {CONFIG_PATH}")
    try:
        with open(CONFIG_PATH) as f:
            return json.load(f)
    except Exception as e:
        logger.error(f"Failed to load config: {e}")
        raise

def connect_obs():
    logger.info(f"Connecting to OBS WebSocket at {OBS_HOST}:{OBS_PORT}")
    ws = obsws(OBS_HOST, OBS_PORT, OBS_PASSWORD)
    try:
        ws.connect()
        logger.info("Connected to OBS WebSocket")
        try:
            ws.call(requests.SetVideoSettings(
                baseWidth=1920,
                baseHeight=1080,
                outputWidth=1920,
                outputHeight=1080,
                fpsNumerator=30,
                fpsDenominator=1
            ))
            resp = ws.call(requests.GetVideoSettings())
            logger.info(f"OBS canvas: {resp.datain}")
        except Exception as ve:
            logger.warning(f"Could not apply canvas resolution: {ve}")
        return ws
    except Exception as e:
        logger.error(f"Failed to connect to OBS WebSocket: {e}")
        raise

def setup_stream(ws, pair, config, start_stream=True):
    scene_name = pair["name"]
    logger.info(f"Setting up stream for scene: {scene_name}")
    scene_item_ids = {}

    # Create scene if not exists
    resp = ws.call(requests.GetSceneList())
    existing_scenes = [s.get("sceneName") or s.get("name") if isinstance(s, dict) else getattr(s, "name", None) for s in resp.getScenes() if s.get("sceneName") or s.get("name") or getattr(s, "name", None)]
    if scene_name not in existing_scenes:
        ws.call(requests.CreateScene(sceneName=scene_name))
        logger.info(f"Created new scene: {scene_name}")
    else:
        logger.info(f"Scene already exists: {scene_name}")

    ws.call(requests.SetCurrentScene(sceneName=scene_name))
    logger.info(f"Switched to scene: {scene_name}")

    # Remove all existing scene items
    resp_items = ws.call(requests.GetSceneItemList(sceneName=scene_name))
    items = resp_items.getSceneItems()
    for item in items:
        ws.call(requests.RemoveSceneItem(sceneName=scene_name, sceneItemId=item["sceneItemId"]))
        logger.info(f"Removed scene item: {item['sceneItemId']} from {scene_name}")

    # Helper to add input and set transform
    def add_input(kind, name, settings, layer_tag, skip_transform=False, custom_transform=None):
        try:
            # Validate RTSP URL for ffmpeg_source
            if kind == "ffmpeg_source" and "input" in settings:
                if not settings["input"].startswith("rtsp://"):
                    logger.error(f"Invalid RTSP URL for {name}: {settings['input']}")
                    return None
            
            # Retry CreateInput up to 3 times
            scene_item_id = None
            for attempt in range(3):
                try:
                    resp = ws.call(requests.CreateInput(
                        sceneName=scene_name,
                        inputName=name,
                        inputKind=kind,
                        inputSettings=settings
                    ))
                    scene_item_id = resp.datain.get("sceneItemId")
                    if scene_item_id:
                        break
                    logger.warning(f"No sceneItemId for {name} on attempt {attempt + 1}")
                    time.sleep(1)
                except Exception as e:
                    logger.warning(f"Attempt {attempt + 1} failed for {name}: {e}")
                    time.sleep(1)
            
            if scene_item_id and not skip_transform:
                if kind in ["ffmpeg_source", "v4l2_input", "browser_source", "image_source"]:
                    time.sleep(1.0)  # Ensure video/browser sources initialize
                
                # Apply custom transform if provided, otherwise use default
                if custom_transform:
                    ws.call(requests.SetSceneItemTransform(
                        sceneName=scene_name,
                        sceneItemId=scene_item_id,
                        sceneItemTransform=custom_transform
                    ))
                else:
                    ws.call(requests.SetSceneItemTransform(
                        sceneName=scene_name,
                        sceneItemId=scene_item_id,
                        sceneItemTransform={
                            "positionX": 0, "positionY": 0,
                            "scaleX": 1.0, "scaleY": 1.0,
                            "rotation": 0.0,
                            "cropTop": 0, "cropBottom": 0,
                            "cropLeft": 0, "cropRight": 0
                        }
                    ))
                    ws.call(requests.SetSceneItemBounds(
                        sceneName=scene_name,
                        sceneItemId=scene_item_id,
                        boundsType="OBS_BOUNDS_STRETCH",
                        boundsAlignment=0,
                        boundsWidth=1920,
                        boundsHeight=1080
                    ))
                
                ws.call(requests.SetSceneItemLocked(
                    sceneName=scene_name,
                    sceneItemId=scene_item_id,
                    sceneItemLocked=True
                ))
            
            if scene_item_id:
                ws.call(requests.SetSceneItemEnabled(
                    sceneName=scene_name,
                    sceneItemId=scene_item_id,
                    sceneItemEnabled=True
                ))
                scene_item_ids[layer_tag] = scene_item_id
                logger.info(f"Added input {name} to {scene_name}")
            else:
                logger.error(f"No sceneItemId for input {name} after 3 attempts")
            return scene_item_id
        except Exception as e:
            logger.error(f"Failed to add input {name} to {scene_name}: {e}")
            return None

    # Add test pattern as bottom layer (ALWAYS)
    test_pattern_path = get_test_pattern_path(scene_name)
    if test_pattern_path:
        scene_item_id = add_input("image_source", scene_name + "_test_pattern", {
            "file": test_pattern_path,
            "unload": False
        }, "test_pattern", skip_transform=True)  # Keep skip for custom

        if scene_item_id:
            try:
                # Get actual dimensions
                transform_info = ws.call(requests.GetSceneItemTransform(
                    sceneName=scene_name,
                    sceneItemId=scene_item_id
                )).datain["sceneItemTransform"]
                image_width = transform_info["sourceWidth"]
                image_height = transform_info["sourceHeight"]
                logger.info(f"Image dimensions: {image_width}x{image_height}")

                # Preserve aspect, fit inside
                scale_x = 1920 / image_width
                scale_y = 1080 / image_height
                scale = min(scale_x, scale_y)

                # Center align
                pos_x = (1920 - image_width * scale) / 2
                pos_y = (1080 - image_height * scale) / 2

                ws.call(requests.SetSceneItemTransform(
                    sceneName=scene_name,
                    sceneItemId=scene_item_id,
                    sceneItemTransform={
                        "positionX": pos_x,
                        "positionY": pos_y,
                        "scaleX": scale,
                        "scaleY": scale,
                        "rotation": 0.0,
                        "cropTop": 0, "cropBottom": 0,
                        "cropLeft": 0, "cropRight": 0
                    }
                ))
                logger.info(f"Applied centered fit transform (scale={scale})")
            except Exception as e:
                logger.error(f"Failed to apply transform: {e}")

    # Add main camera source (lowest layer)
    if pair.get("src_type") == "rtsp" and pair.get("camera_rtsp"):
        add_input("ffmpeg_source", scene_name + "_camera", {
            "input": pair["camera_rtsp"],
            "is_local_file": False,
            "width": 1920,
            "height": 1080,
            "force_hw_dec": True,
            "input_format": "nv12",
            "rescale_output": True
        }, "camera")
    elif pair.get("src_type") == "local" and pair.get("local_src"):
        add_input("v4l2_input", scene_name + "_camera", {
            "device": pair["local_src"],
            "width": 1920,
            "height": 1080,
            "force_resolution": True
        }, "camera")

    # Add pin camera
    pin = pair.get("pin_cam", {})
    if pin.get("enabled"):
        typ = pin.get("type")
        src = pin.get("local") if typ == "local" else pin.get("rtsp")
        kind = "v4l2_input" if typ == "local" else "ffmpeg_source"
        settings = {"device": src, "width": 1920, "height": 1080, "force_resolution": True} if typ == "local" else {
            "input": src, "is_local_file": False, "width": 1920, "height": 1080, "force_hw_dec": True, "input_format": "nv12", "rescale_output": True}
        add_input(kind, scene_name + "_pin_camera", settings, "pin")

    # Add player camera
    player = pair.get("player_cam", {})
    if player.get("enabled"):
        typ = player.get("type")
        src = player.get("local") if typ == "local" else player.get("rtsp")
        kind = "v4l2_input" if typ == "local" else "ffmpeg_source"
        settings = {"device": src, "width": 1920, "height": 1080, "force_resolution": True} if typ == "local" else {
            "input": src, "is_local_file": False, "width": 1920, "height": 1080, "force_hw_dec": True, "input_format": "nv12", "rescale_output": True}
        add_input(kind, scene_name + "_player_camera", settings, "player")

    # Add audio sources
    for idx, audio_dev in enumerate(pair.get('audio_streams', [])):
        device_id = audio_dev.get('pulse_name', audio_dev) if isinstance(audio_dev, dict) else audio_dev
        friendly_name = audio_dev.get('friendly_name', f"{scene_name}_audio_{idx}") if isinstance(audio_dev, dict) else f"{scene_name}_audio_{idx}"
        logger.info(f"Adding audio source {friendly_name} with device_id: {device_id}")
        try:
            scene_item_id = add_input("pulse_input_capture", friendly_name, {
                "device_id": device_id,
                "monitor_type": "monitor_and_output"  # Enable monitoring
            }, f"audio{idx}", skip_transform=True)
            if scene_item_id:
                logger.info(f"Successfully added audio source {friendly_name} with ID {scene_item_id}")
            else:
                logger.error(f"Failed to add audio source {friendly_name}: No sceneItemId returned")
        except Exception as e:
            logger.error(f"Error adding audio source {friendly_name}: {type(e).__name__}: {e}")

    # Apply video/audio delay filters if configured
    delay_ms = pair.get("video_delay_ms", 0)
    if delay_ms > 0:
        logger.info(f"Applying {delay_ms}ms video/audio delay to {scene_name}")

        # Apply Render Delay to camera
        camera_source = scene_name + "_camera"
        try:
            ws.call(requests.AddFilterToSource(
                sourceName=camera_source,
                filterName="Video Delay",
                filterType="render_delay",
                filterSettings={"delay_ms": delay_ms}
            ))
            logger.info(f"Applied Render Delay to {camera_source}")
        except Exception as e:
            logger.warning(f"Failed to apply Render Delay to {camera_source}: {e}")

        # Apply Audio Delay to each audio input
        for idx, audio_dev in enumerate(pair.get("audio_streams", [])):
            audio_source = f"{scene_name}_audio_{idx}"
            try:
                ws.call(requests.AddFilterToSource(
                    sourceName=audio_source,
                    filterName="Audio Delay",
                    filterType="async_delay_filter",
                    filterSettings={"delay_ms": delay_ms}
                ))
                logger.info(f"Applied Audio Delay to {audio_source}")
            except Exception as e:
                logger.warning(f"Failed to apply Audio Delay to {audio_source}: {e}")

    # Add scoring overlays (higher layers)
    try:
        first_lane = int(scene_name.split("&")[0])
        pair_id = (first_lane - 1) // 2
        odd_url = f"http://localhost:1983/overlay/odd/{pair_id}"
        even_url = f"http://localhost:1983/overlay/even/{pair_id}"

        add_input("browser_source", scene_name + "_overlayA", {
            "url": odd_url,
            "width": 1920,
            "height": 1080
        }, "overlayA")

        add_input("browser_source", scene_name + "_overlayB", {
            "url": even_url,
            "width": 1920,
            "height": 1080
        }, "overlayB")
    except Exception as e:
        logger.error(f"Error parsing pair_id or adding overlays for {scene_name}: {e}")

    # Add event banner (highest layer - top left corner)
    banner_url = config.get("event_banner_url")
    logger.info("=== BANNER DEBUG START ===")
    logger.info(f"Config banner_url: {banner_url}")

    if banner_url:
        try:
            # Use fixed app root directory
            app_root = "/home/cornerpins/portal"
            relative_path = banner_url.lstrip("/")
            banner_file_path = os.path.join(app_root, relative_path)
            
            logger.info(f"Testing banner path: {banner_file_path}")
            logger.info(f"  Exists: {os.path.exists(banner_file_path)}")
            
            if not os.path.exists(banner_file_path):
                logger.error(f"❌ BANNER FILE NOT FOUND: {banner_file_path}")
                logger.info("=== BANNER DEBUG END ===")
                # Continue with the function - don't return early
                banner_url = None  # Clear banner_url so rest of function continues
            
            # Banner positioning (300x100px, top-left)
            banner_transform = {
                "positionX": 0,
                "positionY": 0,
                "scaleX": 1.0,
                "scaleY": 1.0,
                "rotation": 0.0,
                "cropTop": 0, "cropBottom": 0,
                "cropLeft": 0, "cropRight": 0
            }
            
            logger.info(f"Adding banner source to OBS: {banner_file_path}")
            
            # Retry adding the input up to 3 times
            scene_item_id = None
            for attempt in range(3):
                try:
                    resp = ws.call(requests.CreateInput(
                        sceneName=scene_name,
                        inputName=scene_name + "_event_banner",
                        inputKind="image_source",
                        inputSettings={
                            "file": banner_file_path,
                            "unload": False
                        }
                    ))
                    scene_item_id = resp.datain.get("sceneItemId")
                    if scene_item_id:
                        logger.info(f"Attempt {attempt + 1}: Successfully created banner source with ID {scene_item_id}")
                        break
                    logger.warning(f"Attempt {attempt + 1}: No sceneItemId returned for banner")
                    time.sleep(1)
                except Exception as e:
                    logger.warning(f"Attempt {attempt + 1}: Failed to create banner source: {e}")
                    time.sleep(1)
            
            if scene_item_id:
                # Apply transform
                ws.call(requests.SetSceneItemTransform(
                    sceneName=scene_name,
                    sceneItemId=scene_item_id,
                    sceneItemTransform=banner_transform
                ))
                # Ensure source is enabled
                ws.call(requests.SetSceneItemEnabled(
                    sceneName=scene_name,
                    sceneItemId=scene_item_id,
                    sceneItemEnabled=True
                ))
                # Lock source
                ws.call(requests.SetSceneItemLocked(
                    sceneName=scene_name,
                    sceneItemId=scene_item_id,
                    sceneItemLocked=True
                ))
                scene_item_ids["banner"] = scene_item_id
                logger.info(f"✅ SUCCESS: Banner added to {scene_name} with ID {scene_item_id}")
            else:
                logger.error(f"❌ FAILED: Could not create banner source for {scene_name} after 3 attempts")
                
        except Exception as e:
            logger.error(f"❌ BANNER EXCEPTION: {e}")
            
    logger.info("=== BANNER DEBUG END ===")

    # Enforce source order (camera lowest, banner on top)
    ordering = ["test_pattern", "camera", "pin", "player", "overlayA", "overlayB", "banner"]
    for index, key in enumerate(ordering):
        if key in scene_item_ids:
            try:
                ws.call(requests.SetSceneItemIndex(
                    sceneName=scene_name,
                    sceneItemId=scene_item_ids[key],
                    sceneItemIndex=index
                ))
                logger.info(f"Set Z-order: {key} → index {index}")
            except Exception as e:
                logger.warning(f"Failed Z-order for {key}: {e}")

def generate_multi_rtmp_config(enabled_pairs, config):
    """Generate Multi-RTMP configuration JSON"""
    rtmp_base_url = config.get("youtube_rtmp_base", "rtmp://a.rtmp.youtube.com/live2")
    
    outputs = []
    for pair in enabled_pairs:
        stream_key = pair.get("stream_key", "")
        pair_name = pair["name"]
        
        if not stream_key:
            logger.warning(f"No stream key for {pair_name}, skipping")
            continue
        
        output_config = {
            "name": f"Pair {pair_name}",
            "enabled": True,
            "server": rtmp_base_url,
            "key": stream_key,
            "use_obs_settings": False,
            "settings": {
                "encoder": "obs_x264",
                "bitrate": "6000",
                "rate_control": "CBR",
                "keyint_sec": 2,
                "preset": "medium",
                "profile": "high",
                "gpu": "0",
                "bf": 2,
                "lookahead": False,
                "psycho_aq": True
            }
        }
        outputs.append(output_config)
        logger.info(f"Added Multi-RTMP config for {pair_name}")
    
    return {"outputs": outputs}

def save_multi_rtmp_config(multi_rtmp_config):
    """Save Multi-RTMP config to OBS profile directory"""
    obs_config_base = Path.home() / ".config" / "obs-studio" / "basic" / "profiles"
    
    if not obs_config_base.exists():
        logger.error(f"OBS config directory not found: {obs_config_base}")
        return False
    
    profile_dirs = [d for d in obs_config_base.iterdir() if d.is_dir()]
    
    if not profile_dirs:
        logger.error("No OBS profiles found")
        return False
    
    profile_dir = next((d for d in profile_dirs if d.name == "Cornerpins"), profile_dirs[0])
    config_file = profile_dir / "obs-multi-rtmp.json"
    
    try:
        with open(config_file, 'w', encoding='utf-8') as f:
            json.dump(multi_rtmp_config, f, indent=2)
        
        logger.info(f"Saved Multi-RTMP config to: {config_file}")
        logger.info(f"Profile: {profile_dir.name}")
        logger.info(f"Configured {len(multi_rtmp_config['outputs'])} outputs")
        return True
        
    except Exception as e:
        logger.error(f"Failed to save Multi-RTMP config: {e}")
        return False

def configure_multi_rtmp_outputs(ws, enabled_pairs, config):
    """Configure Multi-RTMP using WebSocket API - FINAL VERSION"""
    logger.info("🔧 Configuring Multi-RTMP via WebSocket API")
    
    vendor_name = "obs-multi-rtmp"
    rtmp_base_url = config.get("youtube_rtmp_base", "rtmp://a.rtmp.youtube.com/live2")
    
    try:
        # Test plugin availability
        resp = ws.call(requests.CallVendorRequest(
            vendorName=vendor_name,
            requestType="GetOutputs",
            requestData={}
        ))
        logger.info("✅ Multi-RTMP plugin responding")
    except Exception as e:
        logger.error(f"❌ Multi-RTMP plugin not available: {e}")
        return False

    try:
        # Clear existing outputs
        existing_outputs = resp.datain.get("outputs", [])
        logger.info(f"🧹 Clearing {len(existing_outputs)} existing outputs")
        
        for output in existing_outputs:
            try:
                ws.call(requests.CallVendorRequest(
                    vendorName=vendor_name,
                    requestType="RemoveOutput",
                    requestData={"name": output.get("name", "")}
                ))
            except Exception as e:
                logger.warning(f"Failed to remove output: {e}")

        # Add new outputs
        success_count = 0
        
        for pair in enabled_pairs:
            pair_name = pair["name"]
            stream_key = ""
            
            stream_key = pair.get("stream_key", "").strip()  # ALWAYS use stream_key field

            # SIMPLIFIED: Just check if we have a stream key
            if not stream_key:
                logger.warning(f"❌ {pair_name}: No stream key - skipping")
                continue

            logger.info(f"📺 {pair_name}: Using stream key {stream_key[:8]}...")

            # Add and configure output
            output_name = f"Pair {pair_name}"
            
            try:
                # Add output
                ws.call(requests.CallVendorRequest(
                    vendorName=vendor_name,
                    requestType="AddOutput",
                    requestData={
                        "name": output_name,
                        "server": rtmp_base_url,
                        "key": stream_key
                    }
                ))
                
                # Configure settings
                ws.call(requests.CallVendorRequest(
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
                ws.call(requests.CallVendorRequest(
                    vendorName=vendor_name,
                    requestType="EnableOutput",
                    requestData={"name": output_name}
                ))
                
                success_count += 1
                logger.info(f"✅ Configured: {output_name}")
                
            except Exception as e:
                logger.error(f"❌ Failed to configure {output_name}: {e}")

        # Save configuration
        try:
            ws.call(requests.CallVendorRequest(
                vendorName=vendor_name,
                requestType="SaveConfig",
                requestData={}
            ))
            logger.info("💾 Configuration saved")
        except Exception as e:
            logger.warning(f"Save config failed: {e}")

        # Final verification
        try:
            resp = ws.call(requests.CallVendorRequest(
                vendorName=vendor_name,
                requestType="GetOutputs",
                requestData={}
            ))
            
            final_outputs = resp.datain.get("outputs", [])
            enabled_count = sum(1 for output in final_outputs if output.get("enabled", False))
            
            logger.info(f"🔍 Final state: {len(final_outputs)} total, {enabled_count} enabled")
            
            for output in final_outputs:
                name = output.get("name", "Unknown")
                enabled = output.get("enabled", False)
                logger.info(f"  📺 {name}: enabled={enabled}")
                
        except Exception as e:
            logger.warning(f"Verification failed: {e}")

        if success_count > 0:
            logger.info(f"🎉 Multi-RTMP configuration completed: {success_count} outputs")
            return True
        else:
            logger.error("❌ No outputs were configured successfully")
            return False
            
    except Exception as e:
        logger.error(f"❌ Fatal error in Multi-RTMP configuration: {e}")
        return False

def main():
    parser = argparse.ArgumentParser(description="Configure OBS scenes")
    parser.add_argument("--no-stream", action="store_true", help="Configure scenes without starting streaming")
    parser.add_argument("--scenes", help="Comma-separated list of scene names to update")
    args = parser.parse_args()
    logger.info(f"Running setup_12_streams.py with args: no_stream={args.no_stream}, scenes={args.scenes}")

    # Disable browser hardware acceleration
    config_path = Path.home() / ".config" / "obs-studio" / "global.ini"
    config = configparser.ConfigParser(strict=False)
    config.read(config_path)
    if "Browser" not in config.sections():
        config.add_section("Browser")
    config["Browser"]["HardwareAcceleration"] = "false"
    with open(config_path, "w") as f:
        config.write(f)
    logger.info("Disabled browser hardware accel in global.ini")    

    cfg = load_config()
    lane_pairs = cfg.get("lane_pairs", [])
    
    # Filter lane pairs if specific scenes are requested
    if args.scenes:
        scene_names = [name.strip() for name in args.scenes.split(",")]
        enabled_pairs = [p for p in lane_pairs if p.get("enabled") and p.get("name") in scene_names]
        logger.info(f"Selectively updating {len(enabled_pairs)} scenes: {scene_names}")
    else:
        enabled_pairs = [p for p in lane_pairs if p.get("enabled")]
        logger.info(f"Found {len(enabled_pairs)} enabled lane pairs")

    if not enabled_pairs:
        logger.warning("No enabled streams; nothing to do")
        print("No enabled streams; nothing to do.")
        return

    ws = connect_obs()
    time.sleep(2)

    # Configure scenes
    for pair in enabled_pairs:
        setup_stream(ws, pair, cfg, start_stream=not args.no_stream)
        time.sleep(1)

    # Always configure Multi-RTMP outputs, but with the right enabled pairs
    # When selectively updating, we still need all enabled pairs for RTMP config
    if args.scenes:
        # For selective updates, we need to get ALL enabled pairs for RTMP config
        all_enabled_pairs = [p for p in lane_pairs if p.get("enabled")]
        configure_multi_rtmp_outputs(ws, all_enabled_pairs, cfg)
    else:
        # Normal flow - configure with current enabled pairs
        configure_multi_rtmp_outputs(ws, enabled_pairs, cfg)

    # Start relevant livescore watchdogs
    watchdog_script = "/home/cornerpins/portal/enable_livescore_watchdogs.sh"
    try:
        logger.info("Starting livescore watchdog launcher...")
        result = subprocess.run([watchdog_script], check=True, timeout=30, 
                            capture_output=True, text=True)
        logger.info(f"Watchdog script completed: {result.stdout}")
    except subprocess.TimeoutExpired:
        logger.error("Watchdog script timed out after 30 seconds")
    except subprocess.CalledProcessError as e:
        logger.error(f"Watchdog script failed: {e.stderr}")
    except Exception as e:
        logger.error(f"Failed to start watchdogs: {e}")

    ws.disconnect()
    logger.info("Disconnected from OBS WebSocket")

if __name__ == "__main__":
    main()