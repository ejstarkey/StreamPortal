# reolink_camera_api.py - Custom lightweight Reolink API implementation

import requests
import json
import logging
import base64
from datetime import datetime
from typing import Dict, Optional, Any

class ReolinkCamera:
    """Lightweight Reolink Camera API client using direct HTTP requests"""
    
    def __init__(self, ip: str, username: str, password: str, port: int = 80):
        self.ip = ip
        self.username = username
        self.password = password
        self.port = port
        self.token = None
        self.base_url = f"http://{ip}:{port}/cgi-bin/api.cgi"
        self.session = requests.Session()
        
    def _make_request(self, cmd: str, action: int = 0, param: Dict = None) -> Dict:
        """Make API request to camera"""
        data = [{
            "cmd": cmd,
            "action": action,
            "param": param or {}
        }]
        
        try:
            response = self.session.post(
                self.base_url,
                json=data,
                timeout=10
            )
            response.raise_for_status()
            result = response.json()
            return result[0] if result else {}
        except Exception as e:
            logging.error(f"API request failed for {cmd}: {e}")
            return {"error": str(e)}
    
    def login(self) -> bool:
        """Login to camera and get token"""
        try:
            result = self._make_request("Login", 0, {
                "User": {
                    "userName": self.username,
                    "password": self.password
                }
            })
            
            if result.get("code") == 0:
                self.token = result.get("value", {}).get("Token", {}).get("name")
                return True
            else:
                logging.error(f"Login failed: {result}")
                return False
                
        except Exception as e:
            logging.error(f"Login error: {e}")
            return False
    
    def logout(self) -> bool:
        """Logout from camera"""
        if not self.token:
            return True
            
        result = self._make_request("Logout")
        self.token = None
        return result.get("code") == 0
    
    def _ensure_login(self) -> bool:
        """Ensure we're logged in"""
        if not self.token:
            return self.login()
        return True
    
    # PTZ Controls
    def ptz_control(self, operation: str, speed: int = 32) -> bool:
        """Control PTZ movement"""
        if not self._ensure_login():
            return False
            
        # PTZ operation mapping
        operations = {
            "up": {"channel": 0, "op": "Up", "speed": speed},
            "down": {"channel": 0, "op": "Down", "speed": speed},
            "left": {"channel": 0, "op": "Left", "speed": speed},
            "right": {"channel": 0, "op": "Right", "speed": speed},
            "zoom_in": {"channel": 0, "op": "ZoomInc", "speed": speed},
            "zoom_out": {"channel": 0, "op": "ZoomDec", "speed": speed},
            "stop": {"channel": 0, "op": "Stop", "speed": 0}
        }
        
        if operation not in operations:
            return False
            
        result = self._make_request("PtzCtrl", 0, operations[operation])
        return result.get("code") == 0
    
    def set_preset(self, preset_id: int) -> bool:
        """Set PTZ preset position"""
        if not self._ensure_login():
            return False
            
        result = self._make_request("SetPtzPreset", 0, {
            "channel": 0,
            "enable": 1,
            "id": preset_id
        })
        return result.get("code") == 0
    
    def goto_preset(self, preset_id: int) -> bool:
        """Go to PTZ preset position"""
        if not self._ensure_login():
            return False
            
        result = self._make_request("PtzCtrl", 0, {
            "channel": 0,
            "op": "ToPos",
            "id": preset_id
        })
        return result.get("code") == 0
    
    # Lighting Controls
    def set_spotlight(self, enabled: bool) -> bool:
        """Control camera spotlight"""
        if not self._ensure_login():
            return False
            
        result = self._make_request("SetWhiteLed", 0, {
            "WhiteLed": {
                "channel": 0,
                "mode": 1 if enabled else 0,
                "bright": 100 if enabled else 0
            }
        })
        return result.get("code") == 0
    
    def trigger_siren(self, duration: int = 5) -> bool:
        """Trigger camera siren"""
        if not self._ensure_login():
            return False
            
        result = self._make_request("AudioAlarmPlay", 0, {
            "alarm_mode": "manul",
            "manual_switch": 1,
            "times": duration
        })
        return result.get("code") == 0
    
    # Detection Settings
    def set_motion_detection(self, enabled: bool, sensitivity: int = 50) -> bool:
        """Set motion detection settings"""
        if not self._ensure_login():
            return False
            
        result = self._make_request("SetAlarm", 0, {
            "Alarm": {
                "channel": 0,
                "type": "md",
                "enable": 1 if enabled else 0,
                "sensitivity": sensitivity
            }
        })
        return result.get("code") == 0
    
    def set_ai_detection(self, person: bool = True, vehicle: bool = True, pet: bool = False) -> bool:
        """Set AI detection settings"""
        if not self._ensure_login():
            return False
            
        result = self._make_request("SetAiAlarm", 0, {
            "AiAlarm": {
                "channel": 0,
                "dog_cat": {
                    "alarm_type": "dogCat",
                    "enable": 1 if pet else 0
                },
                "people": {
                    "alarm_type": "people", 
                    "enable": 1 if person else 0
                },
                "vehicle": {
                    "alarm_type": "vehicle",
                    "enable": 1 if vehicle else 0
                }
            }
        })
        return result.get("code") == 0
    
    # Image Capture
    def get_snapshot(self) -> Optional[bytes]:
        """Get snapshot from camera"""
        if not self._ensure_login():
            return None
            
        try:
            # Use direct snapshot URL
            snapshot_url = f"http://{self.ip}:{self.port}/cgi-bin/api.cgi"
            params = {
                "cmd": "Snap",
                "channel": 0,
                "rs": "snapshot",
                "user": self.username,
                "password": self.password
            }
            
            response = self.session.get(snapshot_url, params=params, timeout=10)
            response.raise_for_status()
            
            if response.headers.get('content-type', '').startswith('image/'):
                return response.content
            else:
                logging.error("Invalid snapshot response")
                return None
                
        except Exception as e:
            logging.error(f"Snapshot failed: {e}")
            return None
    
    # Device Info
    def get_device_info(self) -> Dict:
        """Get camera device information"""
        if not self._ensure_login():
            return {}
            
        result = self._make_request("GetDevInfo")
        return result.get("value", {}).get("DevInfo", {})
    
    def get_status(self) -> Dict:
        """Get camera status"""
        if not self._ensure_login():
            return {}
            
        device_info = self.get_device_info()
        return {
            "online": True,
            "model": device_info.get("model", "Unknown"),
            "firmware": device_info.get("firmVer", "Unknown"),
            "hardware": device_info.get("hardVer", "Unknown"),
            "serial": device_info.get("serial", "Unknown")
        }


# Flask integration - updated camera_control.py

from flask import Blueprint, request, jsonify, render_template
import json
import logging
from datetime import datetime
import os

# Use our custom Reolink API
from reolink_camera_api import ReolinkCamera

camera_bp = Blueprint('camera', __name__)

CAMERA_CONFIG_FILE = '/home/cornerpins/portal/camera_config.json'
SNAPSHOTS_DIR = '/home/cornerpins/portal/static/snapshots'

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
    """Render camera control interface"""
    return render_template('camera_control.html', 
                         cameras=camera_manager.camera_configs)

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
            'lane_pair': data.get('lane_pair')
        }
        camera_manager.save_camera_config()
        
        # Clear cached connection
        if camera_id in camera_manager.cameras:
            del camera_manager.cameras[camera_id]
        
        return jsonify({'success': True})
    
    return jsonify(camera_manager.camera_configs)

@camera_bp.route('/api/camera/<camera_id>/ptz', methods=['POST'])
def control_ptz(camera_id):
    """Control camera PTZ movement"""
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
    
    return jsonify({'success': success})

@camera_bp.route('/api/camera/<camera_id>/spotlight', methods=['POST'])
def control_spotlight(camera_id):
    """Control camera spotlight"""
    camera = camera_manager.get_camera(camera_id)
    if not camera:
        return jsonify({'error': 'Camera not found or offline'}), 404
    
    data = request.json
    enabled = data.get('enabled', False)
    
    success = camera.set_spotlight(enabled)
    return jsonify({'success': success, 'spotlight_enabled': enabled})

@camera_bp.route('/api/camera/<camera_id>/siren', methods=['POST'])
def control_siren(camera_id):
    """Trigger camera siren"""
    camera = camera_manager.get_camera(camera_id)
    if not camera:
        return jsonify({'error': 'Camera not found or offline'}), 404
    
    data = request.json
    duration = data.get('duration', 5)
    
    success = camera.trigger_siren(duration)
    return jsonify({'success': success})

@camera_bp.route('/api/camera/<camera_id>/detection', methods=['POST'])
def set_detection(camera_id):
    """Set detection settings"""
    camera = camera_manager.get_camera(camera_id)
    if not camera:
        return jsonify({'error': 'Camera not found or offline'}), 404
    
    data = request.json
    
    # Motion detection
    motion_success = camera.set_motion_detection(
        data.get('motion_enabled', True),
        data.get('sensitivity', 50)
    )
    
    # AI detection
    ai_success = camera.set_ai_detection(
        data.get('person_detection', True),
        data.get('vehicle_detection', True),
        data.get('pet_detection', False)
    )
    
    return jsonify({
        'success': motion_success and ai_success,
        'motion_success': motion_success,
        'ai_success': ai_success
    })

@camera_bp.route('/api/camera/<camera_id>/snapshot', methods=['POST'])
def take_snapshot(camera_id):
    """Take snapshot from camera"""
    camera = camera_manager.get_camera(camera_id)
    if not camera:
        return jsonify({'error': 'Camera not found or offline'}), 404
    
    try:
        image_data = camera.get_snapshot()
        if not image_data:
            return jsonify({'error': 'Failed to capture snapshot'}), 500
        
        # Save snapshot
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        filename = f'snapshot_{camera_id}_{timestamp}.jpg'
        filepath = os.path.join(SNAPSHOTS_DIR, filename)
        
        with open(filepath, 'wb') as f:
            f.write(image_data)
        
        return jsonify({
            'success': True,
            'filename': filename,
            'url': f'/static/snapshots/{filename}',
            'timestamp': timestamp
        })
        
    except Exception as e:
        logging.error(f"Snapshot error: {e}")
        return jsonify({'error': str(e)}), 500

@camera_bp.route('/api/camera/<camera_id>/status')
def camera_status(camera_id):
    """Get camera status"""
    camera = camera_manager.get_camera(camera_id)
    if not camera:
        return jsonify({'error': 'Camera not found or offline'}), 404
    
    status = camera.get_status()
    return jsonify(status)

