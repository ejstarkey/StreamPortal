import os
import datetime
import json
import traceback
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

SCOPES = ['https://www.googleapis.com/auth/youtube', 'https://www.googleapis.com/auth/yt-analytics.readonly']
CREDENTIALS_FILE = '/home/cornerpins/portal/credentials.json'
TOKEN_FILE = '/home/cornerpins/portal/token.json'

def get_authenticated_service():
    """Get authenticated YouTube service with proper error handling."""
    creds = None
    try:
        if os.path.exists(TOKEN_FILE):
            creds = Credentials.from_authorized_user_file(TOKEN_FILE, SCOPES)
        
        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                print("[YouTube] 🔄 Refreshing expired credentials...")
                creds.refresh(Request())
            else:
                print("[YouTube] 🔐 Starting OAuth flow...")
                flow = InstalledAppFlow.from_client_secrets_file(CREDENTIALS_FILE, SCOPES)
                creds = flow.run_local_server(port=0)
            
            # Save refreshed/new credentials
            with open(TOKEN_FILE, 'w') as token:
                token.write(creds.to_json())
            print("[YouTube] ✅ Credentials saved successfully")
        
        service = build('youtube', 'v3', credentials=creds)
        print("[YouTube] ✅ YouTube service authenticated successfully")
        return service
        
    except Exception as e:
        print(f"[YouTube] ❌ Authentication failed: {e}")
        traceback.print_exc()
        raise

# REMOVED create_youtube_stream - No longer needed!
# The app now uses create_youtube_broadcast_only which reuses existing stream keys

def find_or_create_broadcast(youtube, full_title, description):
    """Find existing reusable broadcast or create new one."""
    print(f"[YouTube] 🔍 Searching for existing broadcast: '{full_title}'")
    
    try:
        # Search for existing broadcasts
        response = youtube.liveBroadcasts().list(
            part="id,snippet,status,contentDetails",
            broadcastStatus="all",
            maxResults=50
        ).execute()
        
        # Check each broadcast for reusability
        for broadcast in response.get("items", []):
            # Check if this is a broadcast for the same lane pair (even if event name changed)
            existing_title = broadcast["snippet"]["title"].strip()
            
            # Extract lane pair from both titles
            if "–" in existing_title and "–" in full_title:
                existing_lane = existing_title.split("–")[-1].strip()
                new_lane = full_title.split("–")[-1].strip()
                
                if existing_lane == new_lane:  # Same lane pair
                    status = broadcast["status"]["lifeCycleStatus"]
                    privacy = broadcast["status"]["privacyStatus"]
                    broadcast_id = broadcast["id"]
                    
                    print(f"[YouTube] 🔍 Found existing broadcast {broadcast_id} with status: {status}")
                    
                    # Check if broadcast is reusable
                    if status in ["created", "ready", "testing"] and privacy != "complete":
                        # UPDATE THE TITLE if it's different
                        if existing_title != full_title:
                            print(f"[YouTube] 🔄 Updating broadcast title from '{existing_title}' to '{full_title}'")
                            try:
                                broadcast["snippet"]["title"] = full_title
                                broadcast["snippet"]["description"] = description
                                
                                youtube.liveBroadcasts().update(
                                    part="snippet",
                                    body={
                                        "id": broadcast_id,
                                        "snippet": broadcast["snippet"]
                                    }
                                ).execute()
                                print(f"[YouTube] ✅ Updated broadcast title successfully")
                            except Exception as e:
                                print(f"[YouTube] ⚠️ Failed to update title: {e}")
                        
                        # Check if scheduled in the past and reschedule
                        if reschedule_if_needed(youtube, broadcast, broadcast_id):
                            print(f"[YouTube] ✅ Reusing broadcast: {broadcast_id}")
                            return broadcast_id
                    else:
                        print(f"[YouTube] ⚠️ Broadcast {broadcast_id} not reusable (status: {status}, privacy: {privacy})")
        
        # No reusable broadcast found, create new one
        print("[YouTube] 🆕 Creating new broadcast...")
        return create_new_broadcast(youtube, full_title, description)
        
    except HttpError as e:
        print(f"[YouTube] ❌ Error searching for broadcasts: {e}")
        return create_new_broadcast(youtube, full_title, description)

def create_new_broadcast(youtube, full_title, description):
    """Create a new YouTube live broadcast with ALL required fields to avoid manual setup."""
    try:
        from datetime import datetime, timedelta, timezone
        
        # Create a broadcast that's ready to go live immediately
        broadcast_body = {
            "snippet": {
                "title": full_title,
                "description": description,
                # Set scheduled time to 1 minute from now (can go live immediately)
                "scheduledStartTime": (datetime.now(timezone.utc) + timedelta(minutes=1)).isoformat().replace("+00:00", "Z")
            },
            "status": {
                "privacyStatus": "unlisted",  # or "public" if you prefer
                "selfDeclaredMadeForKids": False,  # REQUIRED - prevents manual prompt
                "madeForKids": False  # REQUIRED - prevents manual prompt
            },
            "contentDetails": {
                "monitorStream": {
                    "enableMonitorStream": True,  # Enable monitor stream
                    "broadcastStreamDelayMs": 0   # No delay
                },
                "enableDvr": True,           # Enable DVR
                "enableContentEncryption": False,
                "enableEmbed": True,         # Allow embedding
                "recordFromStart": True,     # Record from start
                "startWithSlate": False,     # Don't start with slate
                "enableAutoStart": True,     # AUTO START - This is key!
                "enableAutoStop": False,     # Don't auto stop
                "enableClosedCaptions": False,
                "closedCaptionsType": "closedCaptionsDisabled",
                "enableLowLatency": False,   # Standard latency
                "latencyPreference": "normal",
                "projection": "rectangular"   # Standard projection
            }
        }
        
        print(f"[YouTube] 📤 Creating broadcast with auto-start enabled...")
        
        response = youtube.liveBroadcasts().insert(
            part="snippet,status,contentDetails",
            body=broadcast_body
        ).execute()
        
        broadcast_id = response["id"]
        print(f"[YouTube] ✅ Created broadcast {broadcast_id} with all required fields")
        
        # Immediately transition to testing/ready if possible
        try:
            # Try to transition to ready state
            youtube.liveBroadcasts().transition(
                part="status",
                id=broadcast_id,
                broadcastStatus="testing"
            ).execute()
            print(f"[YouTube] ✅ Transitioned broadcast to testing state")
        except Exception as e:
            print(f"[YouTube] ℹ️ Could not transition to testing: {e}")
            # This is OK - it might need a bound stream first
        
        return broadcast_id
        
    except HttpError as e:
        print(f"[YouTube] ❌ Failed to create broadcast: {e}")
        if hasattr(e, 'error_details'):
            print(f"[YouTube] ❌ Error details: {e.error_details}")
        return None

def reschedule_if_needed(youtube, broadcast, broadcast_id):
    """Reschedule broadcast if it's scheduled in the past."""
    try:
        scheduled_time = broadcast["snippet"].get("scheduledStartTime")
        if scheduled_time:
            from datetime import datetime, timedelta, timezone
            scheduled_dt = datetime.fromisoformat(scheduled_time.replace("Z", "+00:00"))
            now = datetime.now(timezone.utc)
            
            if scheduled_dt < now:
                # Reschedule to 2 minutes from now
                new_time = (now + timedelta(minutes=2)).isoformat().replace("+00:00", "Z")
                
                update_body = {
                    "id": broadcast_id,
                    "snippet": broadcast["snippet"]
                }
                update_body["snippet"]["scheduledStartTime"] = new_time
                
                youtube.liveBroadcasts().update(
                    part="snippet",
                    body=update_body
                ).execute()
                
                print(f"[YouTube] 🔄 Rescheduled broadcast {broadcast_id} to {new_time}")
        
        return True
        
    except Exception as e:
        print(f"[YouTube] ⚠️ Failed to reschedule broadcast {broadcast_id}: {e}")
        return True  # Continue anyway

def bind_stream_to_broadcast(youtube, broadcast_id, stream_id):
    """Bind a stream to a broadcast."""
    print(f"[YouTube] 🔗 Binding stream {stream_id} to broadcast {broadcast_id}")
    
    try:
        response = youtube.liveBroadcasts().bind(
            part="id,contentDetails",
            id=broadcast_id,
            streamId=stream_id
        ).execute()
        
        print(f"[YouTube] ✅ Successfully bound stream to broadcast")
        return True
        
    except HttpError as e:
        print(f"[YouTube] ❌ Failed to bind stream to broadcast: {e}")
        if hasattr(e, 'error_details'):
            print(f"[YouTube] ❌ Error details: {e.error_details}")
        return False

def make_broadcast_ready_for_streaming(youtube, broadcast_id):
    """
    Make a broadcast ready for immediate streaming by removing scheduled time.
    This allows the broadcast to be used right away.
    """
    try:
        # Get current broadcast details
        response = youtube.liveBroadcasts().list(
            part="snippet,status",
            id=broadcast_id
        ).execute()
        
        if not response.get("items"):
            print(f"[YouTube] ❌ Broadcast {broadcast_id} not found")
            return False
        
        broadcast = response["items"][0]
        current_status = broadcast["status"]["lifeCycleStatus"]
        
        print(f"[YouTube] 📊 Current broadcast status: {current_status}")
        
        # If broadcast has a scheduled time, remove it to make it immediately available
        if broadcast["snippet"].get("scheduledStartTime"):
            print("[YouTube] 🔄 Removing scheduled time to make broadcast immediately available...")
            
            # Remove the scheduled start time
            if "scheduledStartTime" in broadcast["snippet"]:
                del broadcast["snippet"]["scheduledStartTime"]
            
            # Update the broadcast
            youtube.liveBroadcasts().update(
                part="snippet",
                body={
                    "id": broadcast_id,
                    "snippet": broadcast["snippet"]
                }
            ).execute()
            
            print(f"[YouTube] ✅ Removed scheduled time from broadcast {broadcast_id}")
        
        # Try to transition to ready state if it's still in created state
        if current_status == "created":
            try:
                youtube.liveBroadcasts().transition(
                    part="status",
                    id=broadcast_id,
                    broadcastStatus="ready"
                ).execute()
                print(f"[YouTube] ✅ Transitioned broadcast {broadcast_id} to ready state")
            except Exception as e:
                print(f"[YouTube] ⚠️ Could not transition to ready: {e}")
        
        return True
        
    except Exception as e:
        print(f"[YouTube] ❌ Failed to make broadcast ready: {e}")
        return False

def test_authentication():
    """Test YouTube API authentication and permissions."""
    print("[YouTube] 🧪 Testing authentication...")
    
    try:
        youtube = get_authenticated_service()
        
        # Test basic API access
        channels_response = youtube.channels().list(
            part="snippet,statistics",
            mine=True
        ).execute()
        
        if channels_response.get("items"):
            channel = channels_response["items"][0]
            print(f"[YouTube] ✅ Connected to channel: {channel['snippet']['title']}")
            print(f"[YouTube] 📊 Subscriber count: {channel['statistics'].get('subscriberCount', 'N/A')}")
            return True
        else:
            print("[YouTube] ❌ No channels found for authenticated user")
            return False
            
    except Exception as e:
        print(f"[YouTube] ❌ Authentication test failed: {e}")
        return False

def get_stream_status(broadcast_id):
    """Get the current status of a YouTube live stream."""
    try:
        youtube = get_authenticated_service()
        
        response = youtube.liveBroadcasts().list(
            part="status,contentDetails",
            id=broadcast_id
        ).execute()
        
        if response.get("items"):
            broadcast = response["items"][0]
            return {
                "lifecycle_status": broadcast["status"]["lifeCycleStatus"],
                "privacy_status": broadcast["status"]["privacyStatus"],
                "bound_stream_id": broadcast["contentDetails"].get("boundStreamId")
            }
        
        return None
        
    except Exception as e:
        print(f"[YouTube] ❌ Failed to get stream status for {broadcast_id}: {e}")
        return None

def transition_broadcast_to_live(broadcast_id):
    """Transition a broadcast from 'ready' to 'live' state."""
    try:
        youtube = get_authenticated_service()
        
        youtube.liveBroadcasts().transition(
            part="status",
            id=broadcast_id,
            broadcastStatus="live"
        ).execute()
        
        print(f"[YouTube] ✅ Transitioned broadcast {broadcast_id} to live")
        return True
        
    except Exception as e:
        print(f"[YouTube] ❌ Failed to transition broadcast {broadcast_id} to live: {e}")
        return False

def end_broadcast(broadcast_id):
    """End a live broadcast."""
    try:
        youtube = get_authenticated_service()
        
        youtube.liveBroadcasts().transition(
            part="status",
            id=broadcast_id,
            broadcastStatus="complete"
        ).execute()
        
        print(f"[YouTube] ✅ Ended broadcast {broadcast_id}")
        return True
        
    except Exception as e:
        print(f"[YouTube] ❌ Failed to end broadcast {broadcast_id}: {e}")
        return False

def cleanup_old_broadcasts(youtube=None, days_old=7):
    """Clean up old broadcasts that are completed or revoked."""
    try:
        if youtube is None:
            youtube = get_authenticated_service()
            
        cutoff_date = datetime.datetime.now() - datetime.timedelta(days=days_old)
        
        broadcasts = youtube.liveBroadcasts().list(
            part="id,snippet,status",
            broadcastStatus="completed",
            maxResults=50
        ).execute()
        
        deleted_count = 0
        for broadcast in broadcasts.get("items", []):
            published_at = broadcast["snippet"].get("publishedAt")
            if published_at:
                published_date = datetime.datetime.fromisoformat(published_at.replace('Z', '+00:00'))
                if published_date < cutoff_date:
                    try:
                        youtube.liveBroadcasts().delete(id=broadcast["id"]).execute()
                        deleted_count += 1
                        print(f"[YouTube] 🗑️ Deleted old broadcast: {broadcast['snippet']['title']}")
                    except Exception as e:
                        print(f"[YouTube] ⚠️ Failed to delete broadcast {broadcast['id']}: {e}")
        
        print(f"[YouTube] ✅ Cleaned up {deleted_count} old broadcasts")
        
    except Exception as e:
        print(f"[YouTube] ❌ Failed to cleanup old broadcasts: {e}")

def start_enabled_youtube_broadcasts():
    """Start YouTube broadcasts for all ENABLED streams (AutoCreate or Manual)"""
    import time
    print("Starting YouTube broadcasts for enabled streams...")
    
    try:
        youtube = get_authenticated_service()
        started_count = 0
        failed_count = 0
        already_live = 0
        
        # Load config to get ONLY enabled streams
        with open('/home/cornerpins/portal/streams_config.json', 'r') as f:
            config = json.load(f)
        
        # Process ONLY enabled pairs
        enabled_pairs = [p for p in config.get('lane_pairs', []) if p.get('enabled')]
        print(f"Found {len(enabled_pairs)} enabled lane pairs")
        
        for pair in enabled_pairs:
            pair_name = pair['name']
            youtube_id = pair.get('youtube_live_id', '').strip()
            
            # Skip if no YouTube ID
            if not youtube_id:
                print(f"{pair_name}: No YouTube ID configured")
                continue
            
            print(f"{pair_name}: Processing broadcast {youtube_id}")
            
            try:
                # Get broadcast status
                broadcast = youtube.liveBroadcasts().list(
                    part="id,status,snippet",
                    id=youtube_id
                ).execute()
                
                if not broadcast.get('items'):
                    print(f"{pair_name}: Broadcast {youtube_id} not found on YouTube")
                    failed_count += 1
                    continue
                
                item = broadcast['items'][0]
                status = item['status']['lifeCycleStatus']
                title = item['snippet']['title']
                
                print(f"{pair_name}: '{title}' is {status}")
                
                if status == 'ready':
                    # First transition to testing
                    print(f"{pair_name}: Transitioning to testing...")
                    try:
                        youtube.liveBroadcasts().transition(
                            id=youtube_id,
                            part="id,status",
                            broadcastStatus="testing"
                        ).execute()
                        
                        # Wait a moment for the transition
                        time.sleep(2)
                        
                        # Now transition to live
                        print(f"{pair_name}: Transitioning to live...")
                        youtube.liveBroadcasts().transition(
                            id=youtube_id,
                            part="id,status",
                            broadcastStatus="live"
                        ).execute()
                        
                        started_count += 1
                        print(f"✅ {pair_name}: Successfully started streaming")
                        
                    except Exception as e:
                        print(f"{pair_name}: Failed to transition: {e}")
                        if "redundantTransition" in str(e):
                            print(f"{pair_name}: Already in target state")
                            already_live += 1
                        else:
                            failed_count += 1
                    
                elif status == 'testing':
                    # Can go directly to live from testing
                    print(f"{pair_name}: Transitioning from testing to live...")
                    try:
                        youtube.liveBroadcasts().transition(
                            id=youtube_id,
                            part="id,status",
                            broadcastStatus="live"
                        ).execute()
                        
                        started_count += 1
                        print(f"✅ {pair_name}: Successfully started streaming")
                        
                    except Exception as e:
                        print(f"{pair_name}: Failed to transition: {e}")
                        failed_count += 1
                        
                elif status == 'live':
                    print(f"✅ {pair_name}: Already live")
                    already_live += 1
                    
                elif status == 'complete':
                    print(f"{pair_name}: Broadcast already completed")
                    failed_count += 1
                    
                else:
                    print(f"{pair_name}: Cannot start - status is {status}")
                    print(f"   Stream might not be active yet. Wait longer after OBS starts.")
                    failed_count += 1
                    
                # Small delay between broadcasts to avoid rate limiting
                time.sleep(1)
                    
            except Exception as e:
                print(f"{pair_name}: Failed to process broadcast: {e}")
                failed_count += 1
        
        print(f"\nYouTube Broadcast Summary:")
        print(f"  Started: {started_count}")
        print(f"  Already Live: {already_live}")
        print(f"  Failed: {failed_count}")
        print(f"  Total Enabled: {len(enabled_pairs)}")
        
        return {
            "started": started_count,
            "already_live": already_live,
            "failed": failed_count,
            "total": len(enabled_pairs)
        }
        
    except Exception as e:
        print(f"Failed to start YouTube broadcasts: {e}")
        return {"error": str(e), "started": 0, "failed": 0}

def create_youtube_broadcast_only(event_name, lane_pair_name, existing_stream_key):
    """
    Create ONLY a YouTube broadcast (not a stream) and bind it to an existing stream.
    This saves API quota by reusing existing stream keys.
    
    Args:
        event_name: Name of the event
        lane_pair_name: Lane pair identifier (e.g. "1&2")
        existing_stream_key: The stream key to reuse (from dashboard)
    
    Returns:
        dict with youtube_live_id and youtube_url, or None on failure
    """
    print(f"\n[YouTube] 🚀 Creating broadcast ONLY for: {event_name} - {lane_pair_name}")
    print(f"[YouTube] 🔑 Using existing stream key: {existing_stream_key[:8]}...")
    
    try:
        # Get authenticated service
        youtube = get_authenticated_service()
        
        # Generate title and description
        full_title = f"{event_name} – {lane_pair_name}"
        description = f"Live broadcast from {lane_pair_name} during {event_name}"
        
        print(f"[YouTube] 📝 Broadcast title: '{full_title}'")
        
        # Step 1: Find or create broadcast
        broadcast_id = find_or_create_broadcast(youtube, full_title, description)
        if not broadcast_id:
            print("[YouTube] ❌ Failed to create or find broadcast")
            return None
        
        # Step 2: Find the existing stream by key
        print(f"[YouTube] 🔍 Finding existing stream with key: {existing_stream_key[:8]}...")
        stream_id = find_stream_by_key(youtube, existing_stream_key)
        
        if not stream_id:
            print(f"[YouTube] ❌ Could not find stream with key {existing_stream_key[:8]}...")
            return None
        
        print(f"[YouTube] ✅ Found existing stream: {stream_id}")
        
        # Step 3: Bind existing stream to broadcast
        if not bind_stream_to_broadcast(youtube, broadcast_id, stream_id):
            print("[YouTube] ❌ Failed to bind stream to broadcast")
            # Continue anyway - might already be bound
        
        # Success - return the details
        youtube_url = f"https://youtube.com/live/{broadcast_id}"
        
        print("\n=================== ✅ BROADCAST CREATION SUCCESS ===================")
        print(f"🔗 YouTube Live URL   : {youtube_url}")
        print(f"🔑 Reused Stream Key  : {existing_stream_key[:8]}...")
        print(f"🆔 Broadcast ID       : {broadcast_id}")
        print(f"🆔 Stream ID          : {stream_id}")
        print("====================================================================\n")
        
        return {
            "stream_key": existing_stream_key,  # Return the same key we were given
            "youtube_live_id": broadcast_id,
            "youtube_url": youtube_url,
            "stream_id": stream_id
        }
        
    except HttpError as e:
        error_details = e.error_details if hasattr(e, 'error_details') else 'Unknown'
        print(f"[YouTube] ❌ YouTube API error: {e}")
        print(f"[YouTube] ❌ Error details: {error_details}")
        return None
        
    except Exception as e:
        print(f"[YouTube] ❌ Unexpected error creating broadcast: {e}")
        traceback.print_exc()
        return None

def find_stream_by_key(youtube, stream_key):
    """
    Find an existing stream by its stream key.
    
    Args:
        youtube: Authenticated YouTube service
        stream_key: The stream key to search for
    
    Returns:
        stream_id if found, None otherwise
    """
    try:
        # List all streams
        response = youtube.liveStreams().list(
            part="id,cdn,snippet",
            mine=True,
            maxResults=50
        ).execute()
        
        # Search through streams for matching key
        for stream in response.get("items", []):
            if stream["cdn"]["ingestionInfo"]["streamName"] == stream_key:
                stream_id = stream["id"]
                stream_title = stream["snippet"]["title"]
                print(f"[YouTube] ✅ Found stream '{stream_title}' with matching key")
                return stream_id
        
        # If we have more pages, check them too
        while "nextPageToken" in response:
            response = youtube.liveStreams().list(
                part="id,cdn,snippet",
                mine=True,
                maxResults=50,
                pageToken=response["nextPageToken"]
            ).execute()
            
            for stream in response.get("items", []):
                if stream["cdn"]["ingestionInfo"]["streamName"] == stream_key:
                    stream_id = stream["id"]
                    stream_title = stream["snippet"]["title"]
                    print(f"[YouTube] ✅ Found stream '{stream_title}' with matching key")
                    return stream_id
        
        print(f"[YouTube] ❌ No stream found with key {stream_key[:8]}...")
        return None
        
    except Exception as e:
        print(f"[YouTube] ❌ Error searching for stream: {e}")
        return None

# Test function to verify everything works
def test_broadcast_creation():
    """Test function to create a test broadcast with existing stream key."""
    print("[YouTube] 🧪 Testing broadcast creation with existing stream key...")
    
    # Test authentication first
    if not test_authentication():
        return False
    
    # You would need to provide an existing stream key for testing
    test_stream_key = input("Enter an existing stream key to test with: ").strip()
    
    if not test_stream_key:
        print("[YouTube] ❌ No stream key provided")
        return False
    
    # Try to create a test broadcast
    result = create_youtube_broadcast_only("TEST_EVENT", "Test Lane Pair", test_stream_key)
    
    if result:
        print("[YouTube] ✅ Test broadcast creation successful!")
        print(f"Stream Key: {result['stream_key']}")
        print(f"YouTube URL: {result['youtube_url']}")
        return True
    else:
        print("[YouTube] ❌ Test broadcast creation failed!")
        return False

if __name__ == "__main__":
    # Run tests when called directly
    test_broadcast_creation()