#!/usr/bin/env python3
"""
Multi-RTMP Plugin Identification & API Discovery
Since config files don't work, let's identify what plugin you have and how to control it
"""

import json
import time
from obswebsocket import obsws, requests as obs_requests

OBS_HOST = "localhost"
OBS_PORT = 4455
OBS_PASSWORD = "B0wl1ng2025!"

def identify_plugin_type(ws):
    """Identify what Multi-RTMP plugin is actually installed"""
    print("🔍 IDENTIFYING MULTI-RTMP PLUGIN TYPE...")
    
    # Test different vendor names that might be used
    possible_vendor_names = [
        "obs-multi-rtmp",
        "multi-rtmp",
        "obs-multiple-rtmp", 
        "multiple-rtmp",
        "obs-multistream",
        "multistream",
        "rtmp-multi",
        "obs-rtmp-multi"
    ]
    
    working_vendors = []
    
    for vendor_name in possible_vendor_names:
        try:
            resp = ws.call(obs_requests.CallVendorRequest(
                vendorName=vendor_name,
                requestType="GetOutputs",
                requestData={}
            ))
            
            working_vendors.append(vendor_name)
            print(f"  ✅ FOUND: {vendor_name}")
            
            # Get details about this vendor
            outputs = resp.datain.get("outputs", [])
            print(f"    📊 Current outputs: {len(outputs)}")
            
            if outputs:
                sample_output = outputs[0]
                print(f"    📄 Sample output structure: {list(sample_output.keys())}")
            
        except Exception as e:
            print(f"  ❌ {vendor_name}: {e}")
    
    if not working_vendors:
        print("❌ NO MULTI-RTMP VENDORS FOUND!")
        return None
    
    print(f"\n🎯 Working vendors: {working_vendors}")
    return working_vendors[0]  # Use the first working one

def discover_plugin_api(ws, vendor_name):
    """Discover all available API methods for the plugin"""
    print(f"\n🔍 DISCOVERING API METHODS FOR: {vendor_name}")
    
    # Comprehensive list of possible method names
    methods_to_test = [
        # Standard methods
        "GetOutputs", "ListOutputs", "GetStreams",
        "AddOutput", "CreateOutput", "NewOutput",
        "RemoveOutput", "DeleteOutput", "DestroyOutput",
        "UpdateOutput", "ModifyOutput", "EditOutput",
        "SetOutputSettings", "ConfigureOutput", "SetSettings",
        "GetOutputSettings", "GetSettings", "GetConfiguration",
        "EnableOutput", "SetOutputEnabled", "ActivateOutput",
        "DisableOutput", "SetOutputDisabled", "DeactivateOutput",
        "StartOutput", "StartStream", "BeginOutput",
        "StopOutput", "StopStream", "EndOutput",
        "StartAll", "StopAll", "StartStreaming", "StopStreaming",
        
        # Config methods
        "ReloadConfig", "LoadConfig", "RefreshConfig",
        "SaveConfig", "GetConfig", "SetConfig",
        "ImportConfig", "ExportConfig",
        
        # Status methods
        "GetStatus", "GetState", "GetInfo",
        "IsStreaming", "IsActive", "IsEnabled",
        
        # Batch operations
        "BatchStart", "BatchStop", "BulkOperation",
        
        # Settings methods
        "GetGlobalSettings", "SetGlobalSettings",
        "GetDefaultSettings", "ResetSettings"
    ]
    
    working_methods = {}
    
    for method in methods_to_test:
        try:
            # Try with empty request data first
            resp = ws.call(obs_requests.CallVendorRequest(
                vendorName=vendor_name,
                requestType=method,
                requestData={}
            ))
            
            working_methods[method] = {
                "status": "success",
                "response_keys": list(resp.datain.keys()) if hasattr(resp, 'datain') and resp.datain else [],
                "error": None
            }
            
            print(f"  ✅ {method}: Available")
            if hasattr(resp, 'datain') and resp.datain:
                print(f"    📄 Response: {list(resp.datain.keys())}")
            
        except Exception as e:
            error_str = str(e).lower()
            
            if any(phrase in error_str for phrase in ["not found", "unknown", "invalid", "unsupported"]):
                working_methods[method] = {"status": "not_available", "error": str(e)}
                print(f"  ❌ {method}: Not available")
            else:
                working_methods[method] = {"status": "error", "error": str(e)}
                print(f"  ⚠️ {method}: Error - {e}")
    
    # Show summary
    available_methods = [m for m, info in working_methods.items() if info["status"] == "success"]
    print(f"\n📊 AVAILABLE METHODS ({len(available_methods)}):")
    for method in available_methods:
        print(f"  ✅ {method}")
    
    return working_methods

def test_manual_output_creation(ws, vendor_name):
    """Test creating an output manually to understand the required parameters"""
    print(f"\n🧪 TESTING MANUAL OUTPUT CREATION...")
    
    test_configs = [
        # Basic configuration
        {
            "name": "Test Output 1",
            "server": "rtmp://test.example.com/live",
            "key": "test_key_123"
        },
        
        # With additional settings
        {
            "name": "Test Output 2",
            "server": "rtmp://test.example.com/live", 
            "key": "test_key_456",
            "enabled": True,
            "settings": {
                "encoder": "obs_x264",
                "bitrate": 3000
            }
        },
        
        # Minimal configuration
        {
            "name": "Test Output 3",
            "url": "rtmp://test.example.com/live/test_key_789"
        }
    ]
    
    creation_methods = ["AddOutput", "CreateOutput", "NewOutput"]
    
    for method in creation_methods:
        for i, config in enumerate(test_configs):
            try:
                print(f"  🧪 Testing {method} with config {i+1}...")
                
                resp = ws.call(obs_requests.CallVendorRequest(
                    vendorName=vendor_name,
                    requestType=method,
                    requestData=config
                ))
                
                print(f"    ✅ SUCCESS: {method} works with config {i+1}")
                print(f"    📄 Response: {resp.datain if hasattr(resp, 'datain') else 'No response data'}")
                
                # Try to clean up
                try:
                    ws.call(obs_requests.CallVendorRequest(
                        vendorName=vendor_name,
                        requestType="RemoveOutput",
                        requestData={"name": config["name"]}
                    ))
                    print(f"    🧹 Cleaned up test output")
                except:
                    pass
                
                return method, config  # Return working method and config
                
            except Exception as e:
                print(f"    ❌ {method} config {i+1} failed: {e}")
    
    print("❌ No working creation methods found")
    return None, None

def inspect_plugin_gui_integration(ws, vendor_name):
    """Check if the plugin integrates with OBS GUI in a way we can access"""
    print(f"\n🔍 CHECKING GUI INTEGRATION...")
    
    try:
        # Get OBS scenes to see if plugin adds sources
        scenes_resp = ws.call(obs_requests.GetSceneList())
        scenes = scenes_resp.getScenes()
        
        print(f"📊 Checking {len(scenes)} scenes for Multi-RTMP sources...")
        
        multi_rtmp_sources = []
        
        for scene in scenes:
            scene_name = scene.get("sceneName") or scene.get("name")
            if not scene_name:
                continue
                
            try:
                items_resp = ws.call(obs_requests.GetSceneItemList(sceneName=scene_name))
                items = items_resp.getSceneItems()
                
                for item in items:
                    source_name = item.get("sourceName")
                    source_type = item.get("sourceType") 
                    
                    if source_name and ("multi" in source_name.lower() or "rtmp" in source_name.lower()):
                        multi_rtmp_sources.append({
                            "scene": scene_name,
                            "source": source_name,
                            "type": source_type
                        })
                        
            except Exception as e:
                print(f"    ⚠️ Could not inspect scene {scene_name}: {e}")
        
        if multi_rtmp_sources:
            print(f"  ✅ Found {len(multi_rtmp_sources)} potential Multi-RTMP sources:")
            for source in multi_rtmp_sources:
                print(f"    📺 {source['scene']} → {source['source']} ({source['type']})")
        else:
            print("  ❌ No Multi-RTMP sources found in scenes")
        
        # Check if plugin adds menu items
        try:
            # This won't work via WebSocket, but we can suggest manual checking
            print("\n💡 Manual checks to perform in OBS GUI:")
            print("  1. Check Tools menu for Multi-RTMP options")
            print("  2. Check if there's a Multi-RTMP dock panel")
            print("  3. Look for Multi-RTMP in Filters or Sources")
            print("  4. Check OBS settings for Multi-RTMP configuration")
            
        except:
            pass
            
    except Exception as e:
        print(f"❌ GUI integration check failed: {e}")

def generate_configuration_guide(vendor_name, working_methods):
    """Generate a guide for configuring this specific plugin"""
    print(f"\n📋 CONFIGURATION GUIDE FOR: {vendor_name}")
    print("=" * 60)
    
    if "AddOutput" in working_methods and working_methods["AddOutput"]["status"] == "success":
        print("✅ PROGRAMMATIC CONFIGURATION POSSIBLE")
        print("Use AddOutput method with these parameters:")
        print("""
        ws.call(obs_requests.CallVendorRequest(
            vendorName="{vendor_name}",
            requestType="AddOutput",
            requestData={{
                "name": "Stream Name",
                "server": "rtmp://a.rtmp.youtube.com/live2",
                "key": "your_stream_key"
            }}
        ))
        """.format(vendor_name=vendor_name))
    
    elif "GetOutputs" in working_methods and working_methods["GetOutputs"]["status"] == "success":
        print("⚠️ READ-ONLY ACCESS - MANUAL CONFIGURATION REQUIRED")
        print("Plugin can be monitored but not configured programmatically")
        print("Configure manually in OBS, then use GetOutputs to verify")
    
    else:
        print("❌ NO API ACCESS DETECTED")
        print("This plugin may only support manual configuration via OBS GUI")
    
    print("\n📋 AVAILABLE METHODS:")
    available = [m for m, info in working_methods.items() if info["status"] == "success"]
    if available:
        for method in available:
            print(f"  ✅ {method}")
    else:
        print("  ❌ No working methods found")

def main():
    print("=" * 80)
    print("🔍 MULTI-RTMP PLUGIN IDENTIFICATION & API DISCOVERY")
    print("=" * 80)
    
    try:
        # Connect to OBS
        ws = obsws(OBS_HOST, OBS_PORT, OBS_PASSWORD)
        ws.connect()
        print("✅ OBS WebSocket connected")
        
        # Step 1: Identify the plugin
        vendor_name = identify_plugin_type(ws)
        if not vendor_name:
            print("❌ No Multi-RTMP plugin found!")
            return
        
        # Step 2: Discover API methods
        working_methods = discover_plugin_api(ws, vendor_name)
        
        # Step 3: Test output creation
        if any(method in working_methods and working_methods[method]["status"] == "success" 
               for method in ["AddOutput", "CreateOutput", "NewOutput"]):
            working_method, working_config = test_manual_output_creation(ws, vendor_name)
        
        # Step 4: Check GUI integration
        inspect_plugin_gui_integration(ws, vendor_name)
        
        # Step 5: Generate configuration guide
        generate_configuration_guide(vendor_name, working_methods)
        
        # Cleanup
        ws.disconnect()
        
    except Exception as e:
        print(f"❌ Failed to connect to OBS: {e}")
        print("💡 Make sure OBS is running with WebSocket enabled")

if __name__ == "__main__":
    main()
