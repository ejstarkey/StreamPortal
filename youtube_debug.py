#!/usr/bin/env python3
"""
YouTube API Debug and Troubleshooting Script
Run this to diagnose YouTube streaming issues
"""

import os
import json
import sys
from datetime import datetime
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

SCOPES = ['https://www.googleapis.com/auth/youtube']
CREDENTIALS_FILE = '/home/cornerpins/portal/credentials.json'
TOKEN_FILE = '/home/cornerpins/portal/token.json'

def check_file_permissions():
    """Check if credential files exist and are readable."""
    print("🔍 CHECKING FILE PERMISSIONS...")
    print("-" * 50)
    
    files_to_check = [CREDENTIALS_FILE, TOKEN_FILE]
    
    for file_path in files_to_check:
        print(f"📁 Checking: {file_path}")
        
        if os.path.exists(file_path):
            print(f"   ✅ File exists")
            
            # Check if readable
            if os.access(file_path, os.R_OK):
                print(f"   ✅ File is readable")
                
                # Check file size
                size = os.path.getsize(file_path)
                print(f"   📏 File size: {size} bytes")
                
                if size == 0:
                    print(f"   ⚠️ WARNING: File is empty!")
                    
            else:
                print(f"   ❌ File is not readable")
                
        else:
            print(f"   ❌ File does not exist")
            if file_path == CREDENTIALS_FILE:
                print(f"   💡 You need to download credentials.json from Google Cloud Console")
            elif file_path == TOKEN_FILE:
                print(f"   💡 Token file will be created during first authentication")
    
    print()

def check_credentials_content():
    """Check the content of credentials file."""
    print("🔑 CHECKING CREDENTIALS CONTENT...")
    print("-" * 50)
    
    if not os.path.exists(CREDENTIALS_FILE):
        print("❌ credentials.json not found!")
        print("💡 Download it from: https://console.cloud.google.com/apis/credentials")
        return False
    
    try:
        with open(CREDENTIALS_FILE, 'r') as f:
            creds_data = json.load(f)
        
        # Check if it's the right type of credentials
        if 'installed' in creds_data:
            client_info = creds_data['installed']
            print("✅ Found desktop application credentials")
            print(f"   📧 Client ID: {client_info.get('client_id', 'Missing')}")
            print(f"   🔐 Client Secret: {'***' if client_info.get('client_secret') else 'Missing'}")
            print(f"   🌐 Auth URI: {client_info.get('auth_uri', 'Missing')}")
            print(f"   🎫 Token URI: {client_info.get('token_uri', 'Missing')}")
            return True
            
        elif 'web' in creds_data:
            print("⚠️ Found web application credentials")
            print("💡 You need 'Desktop Application' credentials for this script")
            return False
            
        else:
            print("❌ Unknown credentials format")
            return False
            
    except json.JSONDecodeError as e:
        print(f"❌ Invalid JSON in credentials file: {e}")
        return False
    except Exception as e:
        print(f"❌ Error reading credentials: {e}")
        return False

def check_youtube_api_quota():
    """Check YouTube API quota and permissions."""
    print("📊 CHECKING YOUTUBE API ACCESS...")
    print("-" * 50)
    
    try:
        # Try to get authenticated service
        creds = None
        if os.path.exists(TOKEN_FILE):
            creds = Credentials.from_authorized_user_file(TOKEN_FILE, SCOPES)
        
        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                print("🔄 Refreshing expired token...")
                creds.refresh(Request())
            else:
                print("🔐 Starting OAuth flow...")
                print("💡 A browser window should open for authentication")
                flow = InstalledAppFlow.from_client_secrets_file(CREDENTIALS_FILE, SCOPES)
                creds = flow.run_console()
            
            # Save credentials
            with open(TOKEN_FILE, 'w') as token:
                token.write(creds.to_json())
            print("✅ Credentials saved")
        
        # Build YouTube service
        youtube = build('youtube', 'v3', credentials=creds)
        print("✅ YouTube service created successfully")
        
        # Test basic API call
        print("🧪 Testing basic API access...")
        channels_response = youtube.channels().list(
            part="snippet,statistics,status",
            mine=True
        ).execute()
        
        if channels_response.get("items"):
            channel = channels_response["items"][0]
            print(f"✅ Connected to channel: {channel['snippet']['title']}")
            print(f"   📺 Channel ID: {channel['id']}")
            print(f"   👥 Subscribers: {channel['statistics'].get('subscriberCount', 'Hidden')}")
            print(f"   📹 Videos: {channel['statistics'].get('videoCount', 'Hidden')}")
            
            # Check if live streaming is enabled
            status = channel.get('status', {})
            if status.get('isLinked'):
                print("✅ Channel is linked to Google account")
            else:
                print("⚠️ Channel may not be linked properly")
                
        else:
            print("❌ No channels found for this account")
            return False
        
        # Test live streaming capabilities
        print("\n🔴 TESTING LIVE STREAMING CAPABILITIES...")
        print("-" * 50)
        
        # Check existing live broadcasts
        try:
            broadcasts_response = youtube.liveBroadcasts().list(
                part="id,snippet,status",
                mine=True,
                maxResults=5
            ).execute()
            
            broadcast_count = len(broadcasts_response.get("items", []))
            print(f"📺 Found {broadcast_count} existing broadcasts")
            
            for broadcast in broadcasts_response.get("items", []):
                title = broadcast['snippet']['title']
                status = broadcast['status']['lifeCycleStatus']
                print(f"   • {title} ({status})")
                
        except HttpError as e:
            if e.resp.status == 403:
                print("❌ Live streaming not enabled for this channel")
                print("💡 Enable it at: https://youtube.com/live_dashboard")
                return False
            else:
                print(f"❌ Error checking broadcasts: {e}")
                return False
        
        # Check existing live streams
        try:
            streams_response = youtube.liveStreams().list(
                part="id,snippet,status",
                mine=True,
                maxResults=5
            ).execute()
            
            stream_count = len(streams_response.get("items", []))
            print(f"📡 Found {stream_count} existing streams")
            
            for stream in streams_response.get("items", []):
                title = stream['snippet']['title']
                status = stream['status']['streamStatus']
                print(f"   • {title} ({status})")
                
        except HttpError as e:
            print(f"⚠️ Error checking streams: {e}")
        
        print("✅ YouTube API access confirmed")
        return True
        
    except HttpError as e:
        print(f"❌ YouTube API error: {e}")
        if e.resp.status == 403:
            print("💡 Possible causes:")
            print("   • YouTube Data API not enabled in Google Cloud Console")
            print("   • Insufficient permissions in OAuth scope")
            print("   • Live streaming not enabled for channel")
        return False
        
    except Exception as e:
        print(f"❌ Unexpected error: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_stream_creation():
    """Test creating a simple stream."""
    print("\n🚀 TESTING STREAM CREATION...")
    print("-" * 50)
    
    try:
        from youtube_api import create_youtube_stream
        
        # Create test stream
        print("Creating test stream...")
        result = create_youtube_stream("DEBUG_TEST", "Debug Lane Pair")
        
        if result:
            print("✅ Stream creation successful!")
            print(f"   🔑 Stream Key: {result['stream_key']}")
            print(f"   🔗 YouTube URL: {result['youtube_live_id']}")
            return True
        else:
            print("❌ Stream creation failed!")
            return False
            
    except ImportError:
        print("❌ Cannot import youtube_api module")
        return False
    except Exception as e:
        print(f"❌ Error during stream creation: {e}")
        import traceback
        traceback.print_exc()
        return False

def main():
    """Run all diagnostic checks."""
    print("🔧 YOUTUBE API DIAGNOSTIC TOOL")
    print("=" * 50)
    print(f"📅 Timestamp: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print()
    
    # Check 1: File permissions
    check_file_permissions()
    
    # Check 2: Credentials content
    if not check_credentials_content():
        print("\n❌ DIAGNOSIS: Invalid or missing credentials file")
        print("💡 SOLUTION: Download proper credentials.json from Google Cloud Console")
        return
    
    # Check 3: YouTube API access
    if not check_youtube_api_quota():
        print("\n❌ DIAGNOSIS: YouTube API access failed")
        print("💡 SOLUTION: Check API enablement and channel permissions")
        return
    
    # Check 4: Stream creation test
    if not test_stream_creation():
        print("\n❌ DIAGNOSIS: Stream creation failed")
        print("💡 SOLUTION: Check the detailed error messages above")
        return
    
    print("\n🎉 ALL TESTS PASSED!")
    print("✅ YouTube streaming should be working correctly")

if __name__ == "__main__":
    main()
