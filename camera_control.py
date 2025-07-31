# camera_control.py - Flask routes for bowling broadcast camera control

from flask import Blueprint, request, jsonify, render_template
import json
import logging
from datetime import datetime
import os
from typing import Optional, Dict, List

# Import our custom Reolink API
from reolink_camera_api import ReolinkCamera

camera_bp = Blueprint('camera', __name__)

CAMERA_CONFIG_FILE = '/home/cornerpins/portal/camera_config.json'
SNAPSHOTS_DIR = '/home/cornerpins/portal/static/snapshots'
STREAMS_CONFIG_FILE = '/home/cornerpins/portal/streams_config.json'

# Bowling-specific presets
BOWLING_PRESETS = {
    1: "Pin Deck View",
    2: "Approach View", 
    3: "Player Position",
    4: "Wide Lane View",
    5: "Scoring Area",
    6: "Ball Return",
    7: "Settee Area",
    8: "Overview"
}

class CameraManager:
    def __init__(self):
        self.cameras = {}
        self.load_camera_config()
        # Ensure snapshots directory exists
        os.makedirs(SNAPSHOTS_DIR, exist_ok=True)
    
    def load_camera_config(self):
        """Load camera configuration from JSON file"""
        try:
            with open(CAMERA_CONFIG_FILE, 'r') as f:
                config = json.load(f)
                self.camera_configs = config.get('cameras', {})
        except FileNotFoundError:
            self.camera_configs = {}
            self.save_camera_config()
    
    def save_camera_config(self):
        """Save camera configuration to JSON file"""
        config = {'cameras': self.camera_configs}
        with open(CAMERA_CONFIG_FILE, 'w') as f:
            json.dump(config, f, indent=2)
    
    def auto_discover_cameras_from_streams(self):
        """Auto-discover cameras from streams configuration"""
        try:
            with open(STREAMS_CONFIG_FILE, 'r') as f:
                streams_config = json.load(f)
            
            discovered_cameras = {}
            
            for lane_pair in streams_config.get('lane_pairs', []):
                if not lane_pair.get('enabled', False):
                    continue
                
                lane_name = lane_pair.get('name', '')
                
                # Main lane camera
                if lane_pair.get('src_type') == 'rtsp' and lane_pair.get('camera_rtsp'):
                    rtsp_url = lane_pair.get('camera_rtsp')
                    ip = self._extract_ip_from_rtsp(rtsp_url)
                    if ip:
                        camera_id = f"lane_{lane_name.replace('&', '_').replace(' ', '_').lower()}"
                        discovered_cameras[camera_id] = {
                            'ip': ip,
                            'name': f"{lane_name} Main Camera",
                            'type': 'main_lane',
                            'lane_pair': lane_name,
                            'rtsp_url': rtsp_url,
                            'username': 'admin',  # Default - user can modify
                            'password': '',  # User needs to set
                            'port': 80
                        }
                
                # Pin camera
                pin_cam = lane_pair.get('pin_cam', {})
                if pin_cam.get('enabled') and pin_cam.get('type') == 'rtsp' and pin_cam.get('rtsp'):
                    rtsp_url = pin_cam.get('rtsp')
                    ip = self._extract_ip_from_rtsp(rtsp_url)
                    if ip:
                        camera_id = f"pin_{lane_name.replace('&', '_').replace(' ', '_').lower()}"
                        discovered_cameras[camera_id] = {
                            'ip': ip,
                            'name': f"{lane_name} Pin Camera",
                            'type': 'pin_cam',
                            'lane_pair': lane_name,
                            'rtsp_url': rtsp_url,
                            'username': 'admin',
                            'password': '',
                            'port': 80
                        }
                
                # Player camera
                player_cam = lane_pair.get('player_cam', {})
                if player_cam.get('enabled') and player_cam.get('type') == 'rtsp' and player_cam.get('rtsp'):
                    rtsp_url = player_cam.get('rtsp')
                    ip = self._extract_ip_from_rtsp(rtsp_url)
                    if ip:
                        camera_id = f"player_{lane_name.replace('&', '_').replace(' ', '_').lower()}"
                        discovered_cameras[camera_id] = {
                            'ip': ip,
                            'name': f"{lane_name} Player Camera",
                            'type': 'player_cam',
                            'lane_pair': lane_name,
                            'rtsp_url': rtsp_url,
                            'username': 'admin',
                            'password': '',
                            'port': 80
                        }
            
            return discovered_cameras
            
        except Exception as e:
            logging.error(f"Error discovering cameras from streams: {e}")
            return {}
    
    def _extract_ip_from_rtsp(self, rtsp_url: str) -> str:
        """Extract IP address from RTSP URL"""
        try:
            import re
            # Match IP addresses in RTSP URLs like rtsp://192.168.1.100:554/...
            match = re.search(r'rtsp://(?:.*@)?(\d+\.\d+\.\d+\.\d+)', rtsp_url)
            return match.group(1) if match else ""
        except:
            return ""
    
    def get_camera(self, camera_id: str) -> Optional[ReolinkCamera]:
        """Get or create camera connection"""
        if camera_id not in self.cameras:
            if camera_id in self.camera_configs:
                config = self.camera_configs[camera_id]
                try:
                    camera = ReolinkCamera(
                        config['ip'], 
                        config['username'], 
                        config['password'],
                        config.get('port', 80)
                    )
                    if camera.login():
                        self.cameras[camera_id] = camera
                        return camera
                    else:
                        logging.error(f"Failed to login to camera {camera_id}")
                        return None
                except Exception as e:
                    logging.error(f"Failed to connect to camera {camera_id}: {e}")
                    return None
        return self.cameras.get(camera_id)

# Global camera manager
camera_manager = CameraManager()

@camera_bp.route('/camera_control')
def camera_control_page():
    """Render bowling broadcast camera control interface"""
    # Auto-discover cameras from streams config
    discovered_cameras = camera_manager.auto_discover_cameras_from_streams()
    
    return render_template('camera_control.html', 
                         cameras=camera_manager.camera_configs,
                         discovered_cameras=discovered_cameras,
                         bowling_presets=BOWLING_PRESETS)

@camera_bp.route('/api/camera/discover', methods=['POST'])
def discover_cameras():
    """Auto-discover cameras from streams configuration"""
    try:
        discovered = camera_manager.auto_discover_cameras_from_streams()
        return jsonify({
            'success': True,
            'discovered_cameras': discovered,
            'count': len(discovered)
        })
    except Exception as e:
        logging.error(f"Camera discovery error: {e}")
        return jsonify({'error': str(e)}), 500

@camera_bp.route('/api/camera/import_discovered', methods=['POST'])
def import_discovered_cameras():
    """Import discovered cameras with credentials"""
    try:
        data = request.json
        cameras_to_import = data.get('cameras', {})
        
        imported_count = 0
        for camera_id, camera_data in cameras_to_import.items():
            if camera_data.get('import', False):
                # Add to camera config with provided credentials
                camera_manager.camera_configs[camera_id] = {
                    'ip': camera_data['ip'],
                    'username': camera_data.get('username', 'admin'),
                    'password': camera_data.get('password', ''),
                    'port': camera_data.get('port', 80),
                    'name': camera_data['name'],
                    'type': camera_data['type'],
                    'lane_pair': camera_data['lane_pair'],
                    'rtsp_url': camera_data.get('rtsp_url', '')
                }
                imported_count += 1
        
        camera_manager.save_camera_config()
        
        return jsonify({
            'success': True,
            'imported_count': imported_count,
            'message': f'Imported {imported_count} cameras'
        })
        
    except Exception as e:
        logging.error(f"Camera import error: {e}")
        return jsonify({'error': str(e)}), 500

@camera_bp.route('/api/camera/config', methods=['GET', 'POST'])
def camera_config():
    """Get or update camera configuration"""
    if request.method == 'POST':
        data = request.json
        camera_id = data.get('camera_id')
        
        if not camera_id:
            return jsonify({'error': 'Camera ID required'}), 400
        
        camera_manager.camera_configs[camera_id] = {
            'ip': data.get('ip'),
            'username': data.get('username'),
            'password': data.get('password'),
            'port': data.get('port', 80),
            'name': data.get('name', f'Camera {camera_id}'),
            'type': data.get('type', 'manual'),
            'lane_pair': data.get('lane_pair', '')
        }
        camera_manager.save_camera_config()
        
        # Clear cached connection
        if camera_id in camera_manager.cameras:
            del camera_manager.cameras[camera_id]
        
        return jsonify({'success': True})
    
    return jsonify(camera_manager.camera_configs)

@camera_bp.route('/api/camera/<camera_id>/ptz', methods=['POST'])
def control_ptz(camera_id):
    """Control camera PTZ movement with bowling-specific enhancements"""
    camera = camera_manager.get_camera(camera_id)
    if not camera:
        return jsonify({'error': 'Camera not found or offline'}), 404
    
    data = request.json
    operation = data.get('operation')
    speed = data.get('speed', 32)
    
    success = False
    if operation in ['up', 'down', 'left', 'right', 'zoom_in', 'zoom_out', 'stop']:
        success = camera.ptz_control(operation, speed)
    elif operation == 'set_preset':
        preset_id = data.get('preset_id', 1)
        success = camera.set_preset(preset_id)
    elif operation == 'goto_preset':
        preset_id = data.get('preset_id', 1)
        success = camera.goto_preset(preset_id)
    elif operation == 'quick_preset':
        # Quick preset for live broadcast
        preset_name = data.get('preset_name')
        preset_mapping = {
            'pin_deck': 1,
            'approach': 2,
            'player': 3,
            'wide': 4,
            'scoring': 5,
            'ball_return': 6,
            'settee': 7,
            'overview': 8
        }
        preset_id = preset_mapping.get(preset_name, 1)
        success = camera.goto_preset(preset_id)
    
    return jsonify({'success': success})

@camera_bp.route('/api/camera/<camera_id>/broadcast_mode', methods=['POST'])
def set_broadcast_mode(camera_id):
    """Set camera to optimal settings for live broadcast"""
    camera = camera_manager.get_camera(camera_id)
    if not camera:
        return jsonify({'error': 'Camera not found or offline'}), 404
    
    try:
        data = request.json
        mode = data.get('mode', 'standard')  # standard, action, low_light
        
        success = True
        
        if mode == 'action':
            # Fast shutter for ball tracking
            success &= camera.set_image_settings({
                'exposure_mode': 'manual',
                'shutter_speed': 'fast',
                'sensitivity': 'medium'
            })
        elif mode == 'low_light':
            # Better for darker bowling alleys
            success &= camera.set_image_settings({
                'exposure_mode': 'auto',
                'night_vision': 'smart',
                'sensitivity': 'high'
            })
        else:  # standard
            # Balanced settings for general bowling broadcast
            success &= camera.set_image_settings({
                'exposure_mode': 'auto',
                'sensitivity': 'medium'
            })
        
        return jsonify({
            'success': success,
            'mode': mode,
            'message': f'Camera set to {mode} broadcast mode'
        })
        
    except Exception as e:
        logging.error(f"Broadcast mode error: {e}")
        return jsonify({'error': str(e)}), 500

@camera_bp.route('/api/camera/<camera_id>/spotlight', methods=['POST'])
def control_spotlight(camera_id):
    """Control camera spotlight for lane illumination"""
    camera = camera_manager.get_camera(camera_id)
    if not camera:
        return jsonify({'error': 'Camera not found or offline'}), 404
    
    data = request.json
    enabled = data.get('enabled', False)
    
    success = camera.set_spotlight(enabled)
    return jsonify({'success': success, 'spotlight_enabled': enabled})

@camera_bp.route('/api/camera/<camera_id>/detection', methods=['POST'])
def set_detection(camera_id):
    """Set bowling-specific detection settings"""
    camera = camera_manager.get_camera(camera_id)
    if not camera:
        return jsonify({'error': 'Camera not found or offline'}), 404
    
    data = request.json
    
    # Motion detection for scoring events
    motion_success = camera.set_motion_detection(
        data.get('motion_enabled', True),
        data.get('sensitivity', 75)  # Higher sensitivity for ball detection
    )
    
    # Person detection for player tracking (no pets in bowling!)
    ai_success = camera.set_ai_detection(
        data.get('person_detection', True),
        data.get('vehicle_detection', False),  # No vehicles in bowling alleys
        False  # No pet detection needed
    )
    
    return jsonify({
        'success': motion_success and ai_success,
        'motion_success': motion_success,
        'ai_success': ai_success
    })

@camera_bp.route('/api/camera/<camera_id>/snapshot', methods=['POST'])
def take_snapshot(camera_id):
    """Take snapshot for replay analysis"""
    camera = camera_manager.get_camera(camera_id)
    if not camera:
        return jsonify({'error': 'Camera not found or offline'}), 404
    
    try:
        image_data = camera.get_snapshot()
        if not image_data:
            return jsonify({'error': 'Failed to capture snapshot'}), 500
        
        # Save snapshot with bowling-specific naming
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        camera_config = camera_manager.camera_configs.get(camera_id, {})
        camera_type = camera_config.get('type', 'camera')
        lane_pair = camera_config.get('lane_pair', 'unknown')
        
        filename = f'{camera_type}_{lane_pair}_{timestamp}.jpg'
        filename = filename.replace('&', '_').replace(' ', '_')
        filepath = os.path.join(SNAPSHOTS_DIR, filename)
        
        with open(filepath, 'wb') as f:
            f.write(image_data)
        
        return jsonify({
            'success': True,
            'filename': filename,
            'url': f'/static/snapshots/{filename}',
            'timestamp': timestamp,
            'camera_type': camera_type,
            'lane_pair': lane_pair
        })
        
    except Exception as e:
        logging.error(f"Snapshot error: {e}")
        return jsonify({'error': str(e)}), 500

@camera_bp.route('/api/camera/<camera_id>/status')
def camera_status(camera_id):
    """Get camera status with bowling-specific info"""
    camera = camera_manager.get_camera(camera_id)
    if not camera:
        return jsonify({'error': 'Camera not found or offline'}), 404
    
    try:
        status = camera.get_status()
        camera_config = camera_manager.camera_configs.get(camera_id, {})
        
        # Add bowling-specific status info
        status.update({
            'camera_type': camera_config.get('type', 'unknown'),
            'lane_pair': camera_config.get('lane_pair', ''),
            'rtsp_url': camera_config.get('rtsp_url', ''),
            'broadcast_ready': True if status.get('online') else False
        })
        
        return jsonify(status)
        
    except Exception as e:
        logging.error(f"Status check error: {e}")
        return jsonify({'error': str(e)}), 500

@camera_bp.route('/api/cameras/bulk_action', methods=['POST'])
def bulk_camera_action():
    """Perform bulk actions on multiple cameras (useful for live broadcast)"""
    try:
        data = request.json
        camera_ids = data.get('camera_ids', [])
        action = data.get('action')
        params = data.get('params', {})
        
        results = {}
        
        for camera_id in camera_ids:
            camera = camera_manager.get_camera(camera_id)
            if not camera:
                results[camera_id] = {'success': False, 'error': 'Camera offline'}
                continue
            
            try:
                if action == 'goto_preset':
                    preset_id = params.get('preset_id', 1)
                    success = camera.goto_preset(preset_id)
                elif action == 'set_spotlight':
                    enabled = params.get('enabled', False)
                    success = camera.set_spotlight(enabled)
                elif action == 'take_snapshot':
                    # Take snapshot but don't save (just test camera responsiveness)
                    image_data = camera.get_snapshot()
                    success = bool(image_data)
                else:
                    success = False
                
                results[camera_id] = {'success': success}
                
            except Exception as e:
                results[camera_id] = {'success': False, 'error': str(e)}
        
        return jsonify({
            'success': True,
            'results': results,
            'action': action
        })
        
    except Exception as e:
        logging.error(f"Bulk action error: {e}")
        return jsonify({'error': str(e)}), 500