from google.oauth2 import service_account
from googleapiclient.discovery import build
from datetime import datetime, timedelta
from dateutil import tz
import re
from typing import Dict, Any


SERVICE_ACCOUNT_FILE = "/etc/secrets/calendarbot.json"
SCOPES = ['https://www.googleapis.com/auth/calendar']

CALENDAR_ID = "yourcalendar7@gmail.com"


credentials = service_account.Credentials.from_service_account_file(
    SERVICE_ACCOUNT_FILE, scopes=SCOPES)
service = build("calendar", "v3", credentials=credentials)

def check_calendar_availability(start_time_str, duration_minutes, user_timezone="Asia/Kolkata"):
    """
    Check if the calendar is available during the requested time slot
    Returns: (is_available: bool, conflicting_events: list)
    """
    try:
        
        user_tz = tz.gettz(user_timezone)
        naive_dt = datetime.fromisoformat(start_time_str)
        user_dt = naive_dt.replace(tzinfo=user_tz)

       
        ist_tz = tz.gettz("Asia/Kolkata")
        ist_start = user_dt.astimezone(ist_tz)
        ist_end = ist_start + timedelta(minutes=duration_minutes)

        print(f"🔍 Checking availability from {ist_start.strftime('%Y-%m-%d %H:%M')} to {ist_end.strftime('%Y-%m-%d %H:%M')} IST")

       
        events_result = service.events().list(
            calendarId=CALENDAR_ID,
            timeMin=ist_start.isoformat(),
            timeMax=ist_end.isoformat(),
            singleEvents=True,
            orderBy='startTime'
        ).execute()

        events = events_result.get('items', [])
        
        if not events:
            print("✅ No conflicts found - time slot is available")
            return True, []
        
       
        conflicting_events = []
        for event in events:
            event_start = event['start'].get('dateTime', event['start'].get('date'))
            event_end = event['end'].get('dateTime', event['end'].get('date'))
            
           
            if 'T' in event_start:  
                existing_start = datetime.fromisoformat(event_start.replace('Z', '+00:00'))
                existing_end = datetime.fromisoformat(event_end.replace('Z', '+00:00'))
                
               
                if existing_start.tzinfo is None:
                    existing_start = existing_start.replace(tzinfo=ist_tz)
                else:
                    existing_start = existing_start.astimezone(ist_tz)
                    
                if existing_end.tzinfo is None:
                    existing_end = existing_end.replace(tzinfo=ist_tz)
                else:
                    existing_end = existing_end.astimezone(ist_tz)
                
             
                if (ist_start < existing_end) and (ist_end > existing_start):
                    conflicting_events.append({
                        'summary': event.get('summary', 'Untitled Event'),
                        'start': existing_start.strftime('%Y-%m-%d %H:%M'),
                        'end': existing_end.strftime('%Y-%m-%d %H:%M'),
                        'id': event.get('id')
                    })
        
        if conflicting_events:
            print(f"❌ Found {len(conflicting_events)} conflicting event(s)")
            for conflict in conflicting_events:
                print(f"   • {conflict['summary']} ({conflict['start']} - {conflict['end']})")
            return False, conflicting_events
        else:
            print("✅ No conflicts found - time slot is available")
            return True, []

    except Exception as e:
        print(f"❌ Error checking availability: {e}")
        return False, [{"error": str(e)}]

def suggest_alternative_times(start_time_str, duration_minutes, user_timezone="Asia/Kolkata", num_suggestions=3):
    """
    Suggest alternative time slots if the requested time is not available
    """
    try:
        user_tz = tz.gettz(user_timezone)
        naive_dt = datetime.fromisoformat(start_time_str)
        user_dt = naive_dt.replace(tzinfo=user_tz)
        
        suggestions = []
        
        
        for i in range(1, 9):  
            alternative_time = user_dt + timedelta(minutes=30 * i)
            is_available, _ = check_calendar_availability(
                alternative_time.isoformat(), 
                duration_minutes, 
                user_timezone
            )
            
            if is_available:
                suggestions.append(alternative_time.strftime('%Y-%m-%d %H:%M'))
                if len(suggestions) >= num_suggestions:
                    break
        
        return suggestions
        
    except Exception as e:
        print(f"❌ Error suggesting alternatives: {e}")
        return []

def create_event(start_time_str, duration_minutes, summary="Meeting with Asma", description="Booked via chatbot", user_timezone="Asia/Kolkata"):
    try:
        is_available, conflicts = check_calendar_availability(start_time_str, duration_minutes, user_timezone)
        
        if not is_available:
            conflict_details = []
            for conflict in conflicts:
                if 'error' in conflict:
                    conflict_details.append(f"Error: {conflict['error']}")
                else:
                    conflict_details.append(f"'{conflict['summary']}' from {conflict['start']} to {conflict['end']}")
            
       
            alternatives = suggest_alternative_times(start_time_str, duration_minutes, user_timezone)
            
            error_msg = f"❌ Time slot not available! Conflicting with:\n" + "\n".join([f"   • {detail}" for detail in conflict_details])
            
            if alternatives:
                error_msg += f"\n\n💡 Alternative time slots available:\n" + "\n".join([f"   • {alt}" for alt in alternatives])
            else:
                error_msg += "\n\n💡 No alternative slots found in the next 4 hours. Please try a different time."
            
            return {"error": error_msg}


        user_tz = tz.gettz(user_timezone)
        naive_dt = datetime.fromisoformat(start_time_str)
        user_dt = naive_dt.replace(tzinfo=user_tz)

  
        ist_tz = tz.gettz("Asia/Kolkata")
        ist_dt = user_dt.astimezone(ist_tz)
        ist_end = ist_dt + timedelta(minutes=duration_minutes)


        event = {
            'summary': summary,
            'description': description,
            'start': {
                'dateTime': ist_dt.isoformat(),
                'timeZone': 'Asia/Kolkata',
            },
            'end': {
                'dateTime': ist_end.isoformat(),
                'timeZone': 'Asia/Kolkata',
            },
        }

        event_result = service.events().insert(calendarId=CALENDAR_ID, body=event).execute()
        print(f"✅ Event created: {event_result.get('htmlLink')}")
        return event_result

    except Exception as e:
        print("❌ Error creating event:", e)
        return {"error": str(e)}


def get_events_for_day(date_str, user_timezone="Asia/Kolkata"):
    """
    Get all events for a specific day
    date_str: YYYY-MM-DD format
    """
    try:
        user_tz = tz.gettz(user_timezone)
        date_obj = datetime.strptime(date_str, "%Y-%m-%d")
        
        
        start_of_day = date_obj.replace(hour=0, minute=0, second=0, tzinfo=user_tz)
        end_of_day = date_obj.replace(hour=23, minute=59, second=59, tzinfo=user_tz)
        
 
        ist_tz = tz.gettz("Asia/Kolkata")
        ist_start = start_of_day.astimezone(ist_tz)
        ist_end = end_of_day.astimezone(ist_tz)
        
        events_result = service.events().list(
            calendarId=CALENDAR_ID,
            timeMin=ist_start.isoformat(),
            timeMax=ist_end.isoformat(),
            singleEvents=True,
            orderBy='startTime'
        ).execute()
        
        events = events_result.get('items', [])
        return events
        
    except Exception as e:
        print(f"❌ Error getting events for day: {e}")
        return []
    
def check_availability(start_time_str: str, end_time_str: str, user_timezone: str) -> Dict[str, Any]:
    """
    Check availability between two datetime strings
    Returns: {
        "available": bool,
        "conflicts": list of conflicting events if not available
    }
    """
    try:
        
        start_dt = datetime.fromisoformat(start_time_str)
        end_dt = datetime.fromisoformat(end_time_str)
        
       
        duration_minutes = int((end_dt - start_dt).total_seconds() / 60)
        
        
        is_available, conflicts = check_calendar_availability(
            start_time_str,
            duration_minutes,
            user_timezone
        )
        
        
        formatted_conflicts = []
        for conflict in conflicts:
            formatted_conflicts.append({
                "title": conflict.get("summary", "Untitled Event"),
                "start": conflict.get("start"),
                "end": conflict.get("end")
            })
        
        return {
            "available": is_available,
            "conflicts": formatted_conflicts if not is_available else []
        }
        
    except Exception as e:
        return {
            "error": f"Error checking availability: {str(e)}",
            "available": False,
            "conflicts": []
        }

def check_availability_interface(text: str) -> str:
    """Handle availability check requests"""
    print(f"\n🔍 Checking availability for: '{text}'")
    user_timezone = "Asia/Kolkata"
    

    date_match = re.search(r"(today|tomorrow|next week|next month|\d{4}-\d{2}-\d{2}|[a-z]+ \d{1,2},? \d{4})", text.lower())
    date = date_match.group(1) if date_match else None
    
    time_range_match = re.search(r"(\d{1,2}(?::\d{2})?\s*(?:am|pm)?)\s*(?:to|-)\s*(\d{1,2}(?::\d{2})?\s*(?:am|pm)?)", text.lower())
    if time_range_match:
        start_time = parse_time_input(time_range_match.group(1))
        end_time = parse_time_input(time_range_match.group(2))
    else:
        start_time = None
        end_time = None
    

    if not date:
        date = prompt_missing_field("date for availability check", "(e.g., 'tomorrow', 'next Friday', 'June 30')")
    
    parsed_date = parse_natural_date(date)
    if not parsed_date:
        parsed_date = prompt_missing_field("valid date", "(e.g., '2025-06-30')")
    
    if not start_time or not end_time:
        print("⏱️ Please specify the time range you want to check:")
        start_time = prompt_missing_field("start time", "(e.g., '9am', '14:30')")
        end_time = prompt_missing_field("end time", "(e.g., '5pm', '17:00')")
    
    start_time_parsed = parse_time_input(start_time)
    end_time_parsed = parse_time_input(end_time)
    
    if not start_time_parsed or not end_time_parsed:
        return "❌ Could not parse the time range. Please try again with clear times."
    

    start_datetime = f"{parsed_date} {start_time_parsed}"
    end_datetime = f"{parsed_date} {end_time_parsed}"
    

    result = check_availability(start_datetime, end_datetime, user_timezone)
    
    if "error" in result:
        return f"❌ Error checking availability: {result['error']}"
    
    if result["available"]:
        return f"✅ You're available from {start_time} to {end_time} on {parsed_date}!"
    else:
        conflicts = result.get("conflicts", [])
        conflict_msg = "\n".join([f"  - {c['title']} ({c['start']} to {c['end']})" for c in conflicts])
        return f"❌ You have conflicts during that time:\n{conflict_msg}"



def parse_time_input(time_input):
    """Parse various time input formats and return 24-hour format (HH:MM)"""
    import re
    from datetime import datetime
    time_input = time_input.strip()
    time_clean = re.sub(r'\s+', ' ', time_input.lower())
    try:
        if re.match(r'^\d{1,2}(am|pm)$', time_clean):
            time_obj = datetime.strptime(time_clean.upper(), "%I%p")
            return time_obj.strftime("%H:%M")
        if re.match(r'^\d{1,2} (am|pm)$', time_clean):
            time_obj = datetime.strptime(time_clean.upper(), "%I %p")
            return time_obj.strftime("%H:%M")
        if re.match(r'^\d{1,2}:\d{2}(am|pm)$', time_clean):
            time_obj = datetime.strptime(time_clean.upper(), "%I:%M%p")
            return time_obj.strftime("%H:%M")
        if re.match(r'^\d{1,2}:\d{2} (am|pm)$', time_clean):
            time_obj = datetime.strptime(time_clean.upper(), "%I:%M %p")
            return time_obj.strftime("%H:%M")
        if re.match(r'^\d{1,2}:\d{2}$', time_input):
            datetime.strptime(time_input, "%H:%M")
            return time_input
        if re.match(r'^\d{1,2}:\d{2}$', time_input):
            parts = time_input.split(':')
            hour = int(parts[0])
            minute = int(parts[1])
            if 0 <= hour <= 23 and 0 <= minute <= 59:
                return f"{hour:02d}:{minute:02d}"
        return None
    except ValueError:
        return None

def parse_natural_date(date_input):
    """Parse natural language dates and convert to YYYY-MM-DD format"""
    import re
    from datetime import datetime
    date_input = date_input.strip().lower()
    months = {
        'january': '01', 'jan': '01', 'february': '02', 'feb': '02',
        'march': '03', 'mar': '03', 'april': '04', 'apr': '04',
        'may': '05', 'june': '06', 'jun': '06', 'july': '07', 'jul': '07',
        'august': '08', 'aug': '08', 'september': '09', 'sep': '09', 'sept': '09',
        'october': '10', 'oct': '10', 'november': '11', 'nov': '11',
        'december': '12', 'dec': '12'
    }
    date_patterns = [
        (r'^(\d{4})-(\d{1,2})-(\d{1,2})$', lambda m: f"{m.group(1)}-{m.group(2).zfill(2)}-{m.group(3).zfill(2)}"),
        (r'^(\d{1,2})\s+([a-z]+)\s+(\d{4})$',
         lambda m: f"{m.group(3)}-{months.get(m.group(2), '00')}-{m.group(1).zfill(2)}" if m.group(2) in months else None),
        (r'^([a-z]+)\s+(\d{1,2}),?\s+(\d{4})$',
         lambda m: f"{m.group(3)}-{months.get(m.group(1), '00')}-{m.group(2).zfill(2)}" if m.group(1) in months else None),
        (r'^(\d{1,2})/(\d{1,2})/(\d{4})$',
         lambda m: f"{m.group(3)}-{m.group(1).zfill(2)}-{m.group(2).zfill(2)}"),
        (r'^(\d{1,2})-(\d{1,2})-(\d{4})$',
         lambda m: f"{m.group(3)}-{m.group(2).zfill(2)}-{m.group(1).zfill(2)}"),
    ]
    for pattern, formatter in date_patterns:
        match = re.match(pattern, date_input)
        if match:
            try:
                formatted_date = formatter(match)
                if formatted_date and formatted_date != "0000-00-00":
                    datetime.strptime(formatted_date, "%Y-%m-%d")
                    return formatted_date
            except (ValueError, AttributeError):
                continue
    return None

def prompt_missing_field(field_name, format_hint=""):
    """Prompt user for missing field with validation"""
    while True:
        prompt_text = f"🤖 Could you tell me the {field_name}"
        if format_hint:
            prompt_text += f" {format_hint}"
        prompt_text += ": "
        value = input(prompt_text).strip()
        if value:
            return value
        print("❌ Please provide a valid value.")