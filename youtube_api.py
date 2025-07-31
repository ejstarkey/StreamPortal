import os
import datetime
import json
import traceback
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

SCOPES = ['https://www.googleapis.com/auth/youtube']
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
                creds = flow.run_console()
            
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

def create_youtube_stream(event_name, lane_pair_name):
    """
    Create YouTube live stream with improved error handling and debugging.
    Returns dict with stream_key and youtube_live_id or None on failure.
    """
    print(f"\n[YouTube] 🚀 Starting stream creation for: {event_name} - {lane_pair_name}")
    
    try:
        # Get authenticated service
        youtube = get_authenticated_service()
        
        # Generate titles and descriptions
        full_title = f"{event_name} – {lane_pair_name}"
        stream_title = f"{full_title} Stream"
        description = f"Live broadcast from {lane_pair_name} during {event_name}"
        
        print(f"[YouTube] 📝 Broadcast title: '{full_title}'")
        print(f"[YouTube] 📝 Stream title: '{stream_title}'")
        
        # Step 1: Check for existing reusable broadcast
        broadcast_id = find_or_create_broadcast(youtube, full_title, description)
        if not broadcast_id:
            print("[YouTube] ❌ Failed to create or find broadcast")
            return None
        
        # Step 2: Check for existing reusable stream
        stream_id, stream_key = find_or_create_stream(youtube, stream_title, description)
        if not stream_id or not stream_key:
            print("[YouTube] ❌ Failed to create or find stream")
            return None
        
        # Step 3: Bind stream to broadcast
        if not bind_stream_to_broadcast(youtube, broadcast_id, stream_id):
            print("[YouTube] ❌ Failed to bind stream to broadcast")
            # Even if binding fails, we might already be bound, so continue
        
        # IMPORTANT: If we're reusing a broadcast, make sure we have the bound stream's key
        if not stream_key:
            print("[YouTube] 🔍 Fetching stream key from bound stream...")
            try:
                broadcast_resp = youtube.liveBroadcasts().list(
                    part="contentDetails",
                    id=broadcast_id
                ).execute()
                
                if broadcast_resp.get("items"):
                    bound_stream_id = broadcast_resp["items"][0]["contentDetails"].get("boundStreamId")
                    if bound_stream_id:
                        stream_resp = youtube.liveStreams().list(
                            part="cdn",
                            id=bound_stream_id
                        ).execute()
                        
                        if stream_resp.get("items"):
                            stream_key = stream_resp["items"][0]["cdn"]["ingestionInfo"]["streamName"]
                            print(f"[YouTube] ✅ Retrieved stream key from bound stream")
            except Exception as e:
                print(f"[YouTube] ⚠️ Failed to fetch stream key: {e}")
        
        # Success - return the details
        youtube_url = f"https://youtube.com/live/{broadcast_id}"
        
        print("\n=================== ✅ STREAM CREATION SUCCESS ===================")
        print(f"🔗 YouTube Live URL   : {youtube_url}")
        print(f"📡 RTMP Stream Key    : {stream_key}")
        print(f"🆔 Broadcast ID       : {broadcast_id}")
        print(f"🆔 Stream ID          : {stream_id}")
        print("================================================================\n")
        
        return {
            "stream_key": stream_key,
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
        print(f"[YouTube] ❌ Unexpected error creating stream: {e}")
        traceback.print_exc()
        return None

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
    """Create a new YouTube live broadcast optimized for reusability within API constraints."""
    try:
        # First attempt: Try without scheduled time (ideal for reusability)
        print("[YouTube] 📤 Attempting to create perpetual broadcast (no schedule)...")
        
        broadcast_body = {
            "snippet": {
                "title": full_title,
                "description": description
                # No scheduledStartTime - makes it perpetually reusable
            },
            "status": {
                "privacyStatus": "unlisted"  # Unlisted for embedding
            },
            "contentDetails": {
                "monitorStream": {
                    "enableMonitorStream": False
                }
            }
        }
        
        try:
            response = youtube.liveBroadcasts().insert(
                part="snippet,status,contentDetails",
                body=broadcast_body
            ).execute()
            
            broadcast_id = response["id"]
            print(f"[YouTube] ✅ Created perpetual broadcast: {broadcast_id}")
            return broadcast_id
            
        except HttpError as e:
            if "scheduledStartTimeRequired" in str(e):
                print("[YouTube] ⚠️ Channel requires scheduled time - using reusable approach...")
                # Fall through to scheduled approach
            else:
                raise e
        
        # Second attempt: Channel requires scheduled time, so use a very long-lived one
        from datetime import datetime, timedelta, timezone
        
        # Schedule for 6 months in future - long enough to be very reusable
        # but not so far that it seems unrealistic
        future_time = (datetime.now(timezone.utc) + timedelta(days=180)).isoformat().replace("+00:00", "Z")
        
        broadcast_body["snippet"]["scheduledStartTime"] = future_time
        
        print(f"[YouTube] 📅 Creating long-lived broadcast scheduled for: {future_time}")
        print("[YouTube] 💡 This will be reusable for ~6 months without API quota burn")
        
        response = youtube.liveBroadcasts().insert(
            part="snippet,status,contentDetails",
            body=broadcast_body
        ).execute()
        
        broadcast_id = response["id"]
        print(f"[YouTube] ✅ Created long-lived broadcast: {broadcast_id}")
        
        return broadcast_id
        
    except HttpError as e:
        print(f"[YouTube] ❌ Failed to create broadcast: {e}")
        if hasattr(e, 'error_details'):
            print(f"[YouTube] ❌ Error details: {e.error_details}")
        return None

def find_or_create_stream(youtube, stream_title, description):
    """Find existing reusable stream or create new one."""
    print(f"[YouTube] 🔍 Searching for existing stream: '{stream_title}'")
    
    try:
        # Search for existing streams
        response = youtube.liveStreams().list(
            part="id,snippet,cdn,status",
            mine=True,
            maxResults=50
        ).execute()
        
        # Check each stream for reusability
        for stream in response.get("items", []):
            if stream["snippet"]["title"].strip() == stream_title.strip():
                status = stream["status"]["streamStatus"]
                stream_id = stream["id"]
                
                print(f"[YouTube] 🔍 Found existing stream {stream_id} with status: {status}")
                
                # Check if stream is reusable
                if status in ["created", "ready"]:
                    stream_key = stream["cdn"]["ingestionInfo"]["streamName"]
                    print(f"[YouTube] ✅ Reusing stream: {stream_id}")
                    return stream_id, stream_key
                else:
                    print(f"[YouTube] ⚠️ Stream {stream_id} not reusable (status: {status})")
        
        # No reusable stream found, create new one
        print("[YouTube] 🆕 Creating new stream...")
        return create_new_stream(youtube, stream_title, description)
        
    except HttpError as e:
        print(f"[YouTube] ❌ Error searching for streams: {e}")
        return create_new_stream(youtube, stream_title, description)

def create_new_stream(youtube, stream_title, description):
    """Create a new YouTube live stream."""
    try:
        stream_body = {
            "snippet": {
                "title": stream_title,
                "description": description
            },
            "cdn": {
                "ingestionType": "rtmp",
                "resolution": "1080p",
                "frameRate": "30fps"
            }
        }
        
        print(f"[YouTube] 📤 Creating stream with body: {json.dumps(stream_body, indent=2)}")
        
        response = youtube.liveStreams().insert(
            part="snippet,cdn",
            body=stream_body
        ).execute()
        
        stream_id = response["id"]
        stream_key = response["cdn"]["ingestionInfo"]["streamName"]
        print(f"[YouTube] ✅ Created new stream: {stream_id}")
        return stream_id, stream_key
        
    except HttpError as e:
        print(f"[YouTube] ❌ Failed to create stream: {e}")
        if hasattr(e, 'error_details'):
            print(f"[YouTube] ❌ Error details: {e.error_details}")
        return None, None

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

# Test function to verify everything works
def test_stream_creation():
    """Test function to create a test stream."""
    print("[YouTube] 🧪 Testing stream creation...")
    
    # Test authentication first
    if not test_authentication():
        return False
    
    # Try to create a test stream
    result = create_youtube_stream("TEST_EVENT", "Test Lane Pair")
    
    if result:
        print("[YouTube] ✅ Test stream creation successful!")
        print(f"Stream Key: {result['stream_key']}")
        print(f"YouTube URL: {result['youtube_url']}")
        return True
    else:
        print("[YouTube] ❌ Test stream creation failed!")
        return False

if __name__ == "__main__":
    # Run tests when called directly
    test_stream_creation()