#!/usr/bin/env python3
"""
Service Monitor Daemon - Continuously monitors system status
Saves results to /tmp/service_status.json for instant access
"""

import json
import time
import subprocess
import psutil
import os
import signal
import sys
import logging
from datetime import timedelta
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed
import threading

# Configuration
STATUS_FILE = "/tmp/service_status.json"
UPDATE_INTERVAL = 15  # seconds
PING_TIMEOUT = 1.5
MAX_WORKERS = 8

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - ServiceMonitor - %(message)s',
    handlers=[
        logging.FileHandler('/tmp/service_monitor.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

class ServiceMonitor:
    def __init__(self):
        self.running = True
        self.last_update = 0
        
    def quick_ping(self, host, timeout=PING_TIMEOUT):
        """Fast ping with short timeout"""
        try:
            result = subprocess.run(
                ["ping", "-c", "1", "-W", str(int(timeout)), host],
                capture_output=True,
                timeout=timeout + 0.5
            )
            return result.returncode == 0
        except:
            return False
    
    def check_obs_websocket(self):
        """Check OBS WebSocket connection"""
        try:
            from obswebsocket import obsws, requests as obsreq
            ws = obsws("localhost", 4455, "B0wl1ng2025!")
            ws.connect(timeout=2)
            ws.call(obsreq.GetVersion())
            ws.disconnect()
            return True
        except:
            return False
    
    def check_systemctl_service(self, service_name):
        """Check if systemd service is active"""
        try:
            result = subprocess.run(
                ["systemctl", "is-active", service_name],
                capture_output=True,
                text=True,
                timeout=2
            )
            return result.stdout.strip() == "active"
        except:
            return False
    
    def get_system_diagnostics(self):
        """Get system diagnostics (fast, no network calls)"""
        diagnostics = {}
        try:
            # Uptime
            with open("/proc/uptime", "r") as f:
                uptime_sec = float(f.read().split()[0])
                diagnostics["Uptime"] = str(timedelta(seconds=int(uptime_sec)))
            
            # Memory usage
            memory = psutil.virtual_memory()
            diagnostics["Memory Usage"] = f"{memory.percent:.1f}%"
            
            # Disk usage
            disk = psutil.disk_usage('/')
            diagnostics["Disk Usage"] = f"{disk.percent:.1f}%"
            
            # CPU usage (quick sample)
            diagnostics["CPU Usage"] = f"{psutil.cpu_percent(interval=0.1):.1f}%"
            
            # Load average
            load_avg = os.getloadavg()
            diagnostics["Load Average"] = f"{load_avg[0]:.2f}"
            
        except Exception as e:
            logger.error(f"Error getting diagnostics: {e}")
            
        return diagnostics
    
    def get_enabled_lanes(self):
        """Get enabled lane pairs from config"""
        try:
            config_path = "/home/cornerpins/portal/streams_config.json"
            if not os.path.exists(config_path):
                return []
                
            with open(config_path, "r") as f:
                config = json.load(f)
                
            return [
                pair for pair in config.get("lane_pairs", [])
                if pair.get("enabled", False)
            ]
        except Exception as e:
            logger.error(f"Error loading config: {e}")
            return []
    
    def monitor_network_services(self):
        """Monitor network-dependent services in parallel"""
        status = {}
        
        # Define all network checks
        network_checks = [
            ("internet", "1.1.1.1"),
            ("cornerpin", "cornerpins.com.au"),
        ]
        
        # Add camera IPs based on enabled lanes
        enabled_lanes = self.get_enabled_lanes()
        camera_ips = []
        ip_map = {
            0: "192.168.83.1", 1: "192.168.83.3", 2: "192.168.83.5", 
            3: "192.168.83.7", 4: "192.168.83.9", 5: "192.168.83.11",
            6: "192.168.83.13", 7: "192.168.83.15", 8: "192.168.83.17",
            9: "192.168.83.19", 10: "192.168.83.21", 11: "192.168.83.23"
        }
        
        for i, lane in enumerate(enabled_lanes):
            if i in ip_map:
                ip = ip_map[i]
                camera_ips.append(ip)
                network_checks.append((f"cam{i}", ip))
        
        # Run all network checks in parallel
        with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
            future_to_service = {
                executor.submit(self.quick_ping, host): service_id
                for service_id, host in network_checks
            }
            
            # Collect results
            for future in as_completed(future_to_service, timeout=PING_TIMEOUT + 1):
                service_id = future_to_service[future]
                try:
                    status[service_id] = future.result()
                except Exception as e:
                    logger.warning(f"Network check failed for {service_id}: {e}")
                    status[service_id] = False
        
        return status, camera_ips
    
    def monitor_local_services(self):
        """Monitor local services (systemd, OBS, etc.)"""
        status = {}
        
        # OBS WebSocket check
        status["obs"] = self.check_obs_websocket()
        
        # Check livescores services for enabled lanes
        enabled_lanes = self.get_enabled_lanes()
        livescores = []
        
        for i, lane in enumerate(enabled_lanes):
            service_name = f"poll-livescores@{i}.service"
            status[service_name] = self.check_systemctl_service(service_name)
            livescores.append({"id": service_name})
        
        # Check DHCP service
        status["dnsmasq"] = self.check_systemctl_service("dnsmasq")
        
        return status, livescores
    
    def collect_status(self):
        """Collect all status information"""
        logger.info("Collecting service status...")
        
        start_time = time.time()
        
        # Get system diagnostics (fast)
        diagnostics = self.get_system_diagnostics()
        
        # Monitor network and local services in parallel
        with ThreadPoolExecutor(max_workers=2) as executor:
            network_future = executor.submit(self.monitor_network_services)
            local_future = executor.submit(self.monitor_local_services)
            
            # Collect results
            try:
                network_status, camera_ips = network_future.result(timeout=5)
                local_status, livescores = local_future.result(timeout=3)
            except Exception as e:
                logger.error(f"Error collecting status: {e}")
                return None
        
        # Combine all status
        all_status = {**network_status, **local_status}
        
        result = {
            "status": all_status,
            "diagnostics": diagnostics,
            "camera_ips": camera_ips,
            "livescores": livescores,
            "last_updated": time.time(),
            "collection_time": round(time.time() - start_time, 2)
        }
        
        logger.info(f"Status collected in {result['collection_time']}s")
        return result
    
    def save_status(self, status_data):
        """Save status to file atomically"""
        if not status_data:
            return False
            
        try:
            # Write to temp file first, then rename (atomic operation)
            temp_file = STATUS_FILE + ".tmp"
            with open(temp_file, "w") as f:
                json.dump(status_data, f, indent=2)
            
            # Atomic rename
            os.rename(temp_file, STATUS_FILE)
            return True
            
        except Exception as e:
            logger.error(f"Error saving status: {e}")
            return False
    
    def run(self):
        """Main monitoring loop"""
        logger.info("Service Monitor starting...")
        
        while self.running:
            try:
                # Collect and save status
                status_data = self.collect_status()
                if status_data and self.save_status(status_data):
                    self.last_update = time.time()
                    logger.debug(f"Status updated at {time.strftime('%H:%M:%S')}")
                
                # Sleep until next update
                time.sleep(UPDATE_INTERVAL)
                
            except KeyboardInterrupt:
                logger.info("Received interrupt signal")
                break
            except Exception as e:
                logger.error(f"Error in monitoring loop: {e}")
                time.sleep(5)  # Brief pause before retrying
        
        logger.info("Service Monitor stopped")
    
    def stop(self):
        """Stop the monitoring loop"""
        self.running = False

def signal_handler(signum, frame):
    """Handle shutdown signals"""
    logger.info(f"Received signal {signum}")
    monitor.stop()
    sys.exit(0)

if __name__ == "__main__":
    # Set up signal handlers
    signal.signal(signal.SIGTERM, signal_handler)
    signal.signal(signal.SIGINT, signal_handler)
    
    # Create and run monitor
    monitor = ServiceMonitor()
    
    # Create initial status file
    logger.info("Creating initial status file...")
    initial_status = monitor.collect_status()
    if initial_status:
        monitor.save_status(initial_status)
    
    # Start monitoring
    try:
        monitor.run()
    except Exception as e:
        logger.error(f"Fatal error: {e}")
        sys.exit(1)