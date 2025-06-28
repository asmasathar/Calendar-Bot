import sys, os, re
from datetime import datetime, timedelta
from dotenv import load_dotenv
from typing import TypedDict, List, Dict, Any
from langgraph.graph import StateGraph, END
from langchain_core.messages import AIMessage
from huggingface_hub import InferenceClient

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from backend.calendar_api import create_event, check_availability

if os.path.exists("/etc/secrets/.env"):
    load_dotenv("/etc/secrets/.env")
else:
    load_dotenv() 
hf_token = os.getenv("HUGGINGFACEHUB_API_TOKEN")

client = InferenceClient(
    model="microsoft/DialoGPT-medium",
    token=hf_token,
)

DEFAULT_TIMEZONE = "Asia/Kolkata"

# Enhanced conversation context to track all details
conversation_context = {
    'last_topic': None,
    'last_date_mentioned': None,
    'last_time_mentioned': None,
    'last_duration_mentioned': None,
    'last_title_mentioned': None,
    'last_location_mentioned': None,
    'available_slots': [],  # Store available slots from last availability check
    'last_availability_date': None,
    'booking_in_progress': False,
    'accumulated_booking_info': {}
}

def parse_relative_date(date_input, reference_date=None):
    if reference_date is None:
        reference_date = datetime.now()
    date_input = date_input.strip().lower()
    if date_input in ['today']:
        return reference_date.strftime("%Y-%m-%d")
    elif date_input in ['tomorrow']:
        return (reference_date + timedelta(days=1)).strftime("%Y-%m-%d")
    elif date_input in ['day after tomorrow', 'day after']:
        return (reference_date + timedelta(days=2)).strftime("%Y-%m-%d")
    elif date_input in ['yesterday']:
        return (reference_date - timedelta(days=1)).strftime("%Y-%m-%d")
    weekdays = ['monday', 'tuesday', 'wednesday', 'thursday', 'friday', 'saturday', 'sunday']
    current_weekday = reference_date.weekday()
    for i, day in enumerate(weekdays):
        if day in date_input:
            days_ahead = i - current_weekday
            if 'next week' in date_input or 'coming week' in date_input:
                days_to_next_week = 7 - current_weekday
                target_date = reference_date + timedelta(days=days_to_next_week + i)
            elif 'this week' in date_input:
                if days_ahead <= 0:
                    days_ahead += 7
                target_date = reference_date + timedelta(days=days_ahead)
            elif 'next' in date_input and not 'next week' in date_input:
                if days_ahead <= 0:
                    days_ahead += 7
                target_date = reference_date + timedelta(days=days_ahead)
            else:
                if days_ahead <= 0:
                    days_ahead += 7
                target_date = reference_date + timedelta(days=days_ahead)
            return target_date.strftime("%Y-%m-%d")
    months = {
        'january': 1, 'jan': 1, 'february': 2, 'feb': 2, 'march': 3, 'mar': 3,
        'april': 4, 'apr': 4, 'may': 5, 'june': 6, 'jun': 6, 'july': 7, 'jul': 7,
        'august': 8, 'aug': 8, 'september': 9, 'sep': 9, 'sept': 9,
        'october': 10, 'oct': 10, 'november': 11, 'nov': 11, 'december': 12, 'dec': 12
    }
    day_match = re.search(r'(\d{1,2})(?:st|nd|rd|th)?', date_input)
    month_match = None
    year = reference_date.year
    for month_name, month_num in months.items():
        if month_name in date_input:
            month_match = month_num
            break
    if day_match:
        day = int(day_match.group(1))
        if month_match:
            month = month_match
        elif 'coming' in date_input or 'next' in date_input:
            month = reference_date.month
            try:
                test_date = datetime(year, month, day)
                if test_date <= reference_date:
                    month += 1
                    if month > 12:
                        month = 1
                        year += 1
            except ValueError:
                month = reference_date.month + 1
                if month > 12:
                    month = 1
                    year += 1
        else:
            month = reference_date.month
            try:
                test_date = datetime(year, month, day)
                if test_date < reference_date:
                    month += 1
                    if month > 12:
                        month = 1
                        year += 1
            except ValueError:
                month = reference_date.month + 1
                if month > 12:
                    month = 1
                    year += 1
        try:
            parsed_date = datetime(year, month, day)
            return parsed_date.strftime("%Y-%m-%d")
        except ValueError:
            pass
    year_match = re.search(r'\b(20\d{2})\b', date_input)
    if year_match:
        year = int(year_match.group(1))
        if day_match and month_match:
            try:
                parsed_date = datetime(year, month_match, int(day_match.group(1)))
                return parsed_date.strftime("%Y-%m-%d")
            except ValueError:
                pass
    if re.match(r'^\d{4}-\d{2}-\d{2}$', date_input):
        try:
            datetime.strptime(date_input, "%Y-%m-%d")
            return date_input
        except ValueError:
            pass
    return None

def parse_time_input(time_input):
    if not time_input:
        return None
    time_input = time_input.strip().lower()
    relative_times = {
        'morning': '09:00',
        'afternoon': '14:00', 
        'evening': '18:00',
        'night': '20:00',
        'noon': '12:00',
        'midnight': '00:00'
    }
    for term, time_str in relative_times.items():
        if term in time_input:
            return time_str
    time_clean = re.sub(r'\s+', ' ', time_input)
    try:
        patterns = [
            (r'^(\d{1,2})(am|pm)$', lambda m: f"{int(m.group(1)) % 12 + (12 if m.group(2) == 'pm' else 0):02d}:00"),
            (r'^(\d{1,2}) (am|pm)$', lambda m: f"{int(m.group(1)) % 12 + (12 if m.group(2) == 'pm' else 0):02d}:00"),
            (r'^(\d{1,2}):(\d{2})(am|pm)$', lambda m: f"{int(m.group(1)) % 12 + (12 if m.group(3) == 'pm' else 0):02d}:{m.group(2)}"),
            (r'^(\d{1,2}):(\d{2}) (am|pm)$', lambda m: f"{int(m.group(1)) % 12 + (12 if m.group(3) == 'pm' else 0):02d}:{m.group(2)}"),
            (r'^(\d{1,2}):(\d{2})$', lambda m: f"{int(m.group(1)):02d}:{m.group(2)}")
        ]
        for pattern, formatter in patterns:
            match = re.match(pattern, time_clean)
            if match:
                result = formatter(match)
                try:
                    datetime.strptime(result, "%H:%M")
                    return result
                except ValueError:
                    continue
        return None
    except Exception:
        return None

def parse_duration(text: str) -> int:
    """Parse duration from text and return minutes"""
    text_lower = text.lower()
    
    # Direct duration mentions
    duration_match = re.search(r'(half an hour|30 ?min|1 ?hour|\d+ ?(hour|hr|minute|min)s?)', text_lower)
    if duration_match:
        duration_str = duration_match.group(0)
        if 'half an hour' in duration_str or '30' in duration_str:
            return 30
        elif '1 hour' in duration_str or '1hour' in duration_str:
            return 60
        else:
            num_match = re.search(r'\d+', duration_str)
            unit_match = re.search(r'(hour|hr|minute|min)', duration_str)
            if num_match and unit_match:
                num = int(num_match.group(0))
                unit = unit_match.group(1)
                if unit in ['hour', 'hr']:
                    return num * 60
                else:
                    return num
    
    # Just number mentions that could be duration
    if re.search(r'\b(30|60|90|120)\b', text_lower):
        num = int(re.search(r'\b(30|60|90|120)\b', text_lower).group(0))
        return num
    
    return None

def is_availability_request(text: str) -> bool:
    availability_keywords = [
        'available', 'free', 'availability', 'busy', 'schedule',
        'am i free', 'are you free', 'check my', 'what time', 'when am i',
        'do i have', 'any meetings', 'open slots', 'time slots', 'what about'
    ]
    text_lower = text.lower()
    if any(keyword in text_lower for keyword in availability_keywords):
        booking_indicators = ['book', 'schedule', 'create', 'set up', 'arrange', 'plan']
        if not any(indicator in text_lower for indicator in booking_indicators):
            return True
    return False

def is_booking_request(text: str) -> bool:
    booking_keywords = [
        'book', 'schedule', 'set up', 'create', 'arrange', 'plan',
        'meeting with', 'call with', 'event', 'reserve', 'add to calendar'
    ]
    text_lower = text.lower()
    return any(keyword in text_lower for keyword in booking_keywords)

def is_duration_only(text: str) -> bool:
    """Check if the text is just providing duration information"""
    text_lower = text.lower().strip()
    duration_patterns = [
        r'^\d+\s*(min|minute|minutes|hour|hours|hr)s?$',
        r'^(half an hour|30 min|1 hour)$',
        r'^\d+$'  # Just a number
    ]
    return any(re.match(pattern, text_lower) for pattern in duration_patterns)

def generate_natural_response(text: str, response_type: str = "casual") -> str:
    try:
        if response_type == "casual":
            prompt = f"You are a helpful calendar assistant. Respond naturally and conversationally to: '{text}'. Keep it brief and friendly."
        elif response_type == "availability":
            prompt = f"You are checking calendar availability. The user asked: '{text}'. Generate a brief, natural response asking for clarification if needed."
        elif response_type == "booking":
            prompt = f"You are helping schedule a meeting. The user said: '{text}'. Generate a brief, natural response."
        response = client.text_generation(
            prompt,
            max_new_tokens=50,
            temperature=0.7,
            return_full_text=False
        )
        return response.strip() if response else "I'm here to help with your calendar!"
    except Exception:
        if response_type == "casual":
            return "I'm here to help you with your calendar! What would you like to do?"
        elif response_type == "availability":
            return "I can check your availability. When would you like to check?"
        else:
            return "I can help you schedule that. What details do you need to add?"

def extract_availability_request(text: str) -> Dict[str, Any]:
    text_lower = text.lower()
    date_str = None
    date_patterns = [
        r'\b(today|tomorrow|yesterday)\b',
        r'\b(day after tomorrow|day after)\b',
        r'\bnext week (monday|tuesday|wednesday|thursday|friday|saturday|sunday)\b',
        r'\b(this|next|coming)\s+(monday|tuesday|wednesday|thursday|friday|saturday|sunday)\b',
        r'\b(this|next|coming)\s+(week|month)\b',
        r'\b(monday|tuesday|wednesday|thursday|friday|saturday|sunday)\b',
        r'\b(\d{1,2})(?:st|nd|rd|th)?\b',
        r'\b(january|february|march|april|may|june|july|august|september|october|november|december|jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)\s+\d{1,2}\b',
        r'\b\d{1,2}\s+(january|february|march|april|may|june|july|august|september|october|november|december|jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)\b'
    ]
    for pattern in date_patterns:
        match = re.search(pattern, text_lower)
        if match:
            date_str = match.group(0)
            break
    time_start = None
    time_end = None
    time_range_match = re.search(r'(\d{1,2}(?::\d{2})?\s*(?:am|pm)?)\s*(?:to|-|until)\s*(\d{1,2}(?::\d{2})?\s*(?:am|pm)?)', text_lower)
    if time_range_match:
        time_start = parse_time_input(time_range_match.group(1))
        time_end = parse_time_input(time_range_match.group(2))
    else:
        time_patterns = [
            r'\b(\d{1,2}(?::\d{2})?\s*(?:am|pm))\b',
            r'\b(morning|afternoon|evening|night)\b'
        ]
        for pattern in time_patterns:
            match = re.search(pattern, text_lower)
            if match:
                time_start = parse_time_input(match.group(1))
                break
    return {
        'date': date_str,
        'time_start': time_start,
        'time_end': time_end
    }

def suggest_alternative_times(date: str, conflicts: List[Dict]) -> List[str]:
    """Return list of available time slots"""
    try:
        base_date = datetime.strptime(date, "%Y-%m-%d")
        available_slots = []
        for hour in range(9, 18):
            slot_start = base_date.replace(hour=hour, minute=0)
            slot_end = slot_start + timedelta(hours=1)
            is_free = True
            for conflict in conflicts:
                conflict_start = datetime.fromisoformat(conflict['start'].replace('Z', '+00:00'))
                conflict_end = datetime.fromisoformat(conflict['end'].replace('Z', '+00:00'))
                if (slot_start < conflict_end and slot_end > conflict_start):
                    is_free = False
                    break
            if is_free:
                available_slots.append(slot_start.strftime("%H:%M"))
        return available_slots
    except Exception:
        return []

def check_availability_smart(text: str, user_timezone: str = DEFAULT_TIMEZONE) -> str:
    global conversation_context
    
    availability_info = extract_availability_request(text)
    date_str = availability_info['date']
    if not date_str:
        date_str = 'today'
    parsed_date = parse_relative_date(date_str)
    if not parsed_date:
        return "The date could not be understood. Please specify more clearly."

    start_time = availability_info['time_start']
    end_time = availability_info['time_end']
    if not start_time and not end_time:
        start_time = "09:00"
        end_time = "17:00"
        time_desc = "during business hours"
    elif start_time and not end_time:
        try:
            start_dt = datetime.strptime(start_time, "%H:%M")
            end_dt = start_dt + timedelta(hours=1)
            end_time = end_dt.strftime("%H:%M")
            time_desc = f"around {start_time}"
        except:
            end_time = "17:00"
            time_desc = f"from {start_time} onwards"
    else:
        time_desc = f"from {start_time} to {end_time}"

    try:
        start_dt = datetime.strptime(f"{parsed_date} {start_time}", "%Y-%m-%d %H:%M")
        end_dt = datetime.strptime(f"{parsed_date} {end_time}", "%Y-%m-%d %H:%M")
        result = check_availability(
            start_dt.isoformat(),
            end_dt.isoformat(),
            user_timezone=user_timezone
        )
        if isinstance(result, dict) and "error" in result:
            return f"Error checking availability: {result['error']}"

        display_date = start_dt.strftime("%A, %B %d, %Y")
        
        # Store context for potential booking
        conversation_context['last_availability_date'] = parsed_date
        
        if result.get("available"):
            return f"You're free on {display_date} {time_desc}."
        else:
            conflicts = result.get("conflicts", [])
            available_slots = suggest_alternative_times(parsed_date, conflicts)
            conversation_context['available_slots'] = available_slots
            
            if available_slots:
                slots_text = ", ".join([datetime.strptime(slot, "%H:%M").strftime("%I:%M %p").lstrip('0') for slot in available_slots[:5]])
                return f"Not available on {display_date} {time_desc}. Available slots: {slots_text}"
            else:
                return f"Not available on {display_date} {time_desc}. No available slots found."
    except Exception as e:
        return f"Error checking availability: {str(e)}"

def extract_comprehensive_booking_info(text: str) -> Dict[str, Any]:
    """Extract all possible booking information from text"""
    info = {
        'title': None,
        'date': None,
        'time': None,
        'duration_minutes': None,
        'location': None
    }
    
    text_lower = text.lower()
    
    # Extract title/subject
    title_patterns = [
        r'meeting with ([^,\n]+)',
        r'call with ([^,\n]+)',
        r'([\w\s]+) meeting',
        r'schedule ([\w\s]+)',
        r'book ([\w\s]+)',
    ]
    for pattern in title_patterns:
        match = re.search(pattern, text_lower)
        if match:
            info['title'] = match.group(1).strip().title()
            break
    
    # Extract date
    if 'next week' in text_lower:
        weekdays = ['monday', 'tuesday', 'wednesday', 'thursday', 'friday', 'saturday', 'sunday']
        for day in weekdays:
            if day in text_lower:
                info['date'] = parse_relative_date(f"next week {day}")
                break
    else:
        date_match = re.search(r'\b(today|tomorrow|next \w+|this \w+|\w+ \d+|coming \w+|\d+(?:st|nd|rd|th)?)', text_lower)
        if date_match:
            info['date'] = parse_relative_date(date_match.group(0))
    
    # Extract time
    time_match = re.search(r'(\d{1,2}(?::\d{2})?\s*(?:am|pm))', text_lower)
    if time_match:
        info['time'] = parse_time_input(time_match.group(1))
    
    # Extract duration
    info['duration_minutes'] = parse_duration(text)
    
    return info

def get_accumulated_booking_info() -> Dict[str, Any]:
    """Get all booking information from context and current accumulated data"""
    global conversation_context
    
    info = conversation_context['accumulated_booking_info'].copy()
    
    # Use context data as fallback
    if not info.get('date') and conversation_context['last_date_mentioned']:
        info['date'] = parse_relative_date(conversation_context['last_date_mentioned'])
    if not info.get('date') and conversation_context['last_availability_date']:
        info['date'] = conversation_context['last_availability_date']
    
    if not info.get('time') and conversation_context['last_time_mentioned']:
        info['time'] = conversation_context['last_time_mentioned']
    
    if not info.get('duration_minutes') and conversation_context['last_duration_mentioned']:
        info['duration_minutes'] = conversation_context['last_duration_mentioned']
    
    if not info.get('title') and conversation_context['last_title_mentioned']:
        info['title'] = conversation_context['last_title_mentioned']
    
    return info

def update_accumulated_booking_info(new_info: Dict[str, Any]):
    """Update the accumulated booking information"""
    global conversation_context
    
    for key, value in new_info.items():
        if value is not None:
            conversation_context['accumulated_booking_info'][key] = value

def book_meeting_smart(text: str, user_timezone: str = DEFAULT_TIMEZONE) -> str:
    global conversation_context
    
    # Extract info from current text
    current_info = extract_comprehensive_booking_info(text)
    
    # Check if this is just duration information
    if is_duration_only(text):
        duration = parse_duration(text)
        if duration:
            current_info = {'duration_minutes': duration}
    
    # Update accumulated information
    update_accumulated_booking_info(current_info)
    
    # Get all available information
    complete_info = get_accumulated_booking_info()
    
    # Check what's missing
    missing_fields = []
    if not complete_info.get('title'):
        missing_fields.append("title")
    if not complete_info.get('date'):
        missing_fields.append("date")
    if not complete_info.get('time'):
        missing_fields.append("time")
    if not complete_info.get('duration_minutes'):
        missing_fields.append("duration")
    
    if missing_fields:
        conversation_context['booking_in_progress'] = True
        return f"Need {', '.join(missing_fields)}."
    
    # All information available, create the meeting
    try:
        datetime_str = f"{complete_info['date']} {complete_info['time']}"
        dt = datetime.strptime(datetime_str, "%Y-%m-%d %H:%M")
        
        event = create_event(
            dt.isoformat(),
            complete_info['duration_minutes'],
            complete_info['title'],
            user_timezone=user_timezone
        )
        
        if isinstance(event, dict) and "error" in event:
            return f"❌ {event['error']}"
        
        # Clear accumulated info after successful booking
        conversation_context['accumulated_booking_info'] = {}
        conversation_context['booking_in_progress'] = False
        
        return f"✅ Meeting '{complete_info['title']}' scheduled for {dt.strftime('%A, %B %d at %I:%M %p')} ({complete_info['duration_minutes']} minutes)!"
    except Exception as e:
        return f"❌ Error creating meeting: {str(e)}"

def update_context(text: str, topic: str):
    global conversation_context
    conversation_context['last_topic'] = topic
    
    # Extract and store all relevant information
    info = extract_comprehensive_booking_info(text)
    availability_info = extract_availability_request(text)
    
    if info['date'] or availability_info['date']:
        conversation_context['last_date_mentioned'] = info['date'] or availability_info['date']
    if info['time'] or availability_info['time_start']:
        conversation_context['last_time_mentioned'] = info['time'] or availability_info['time_start']
    if info['duration_minutes']:
        conversation_context['last_duration_mentioned'] = info['duration_minutes']
    if info['title']:
        conversation_context['last_title_mentioned'] = info['title']

def process_contextual_input(text: str, user_timezone: str = DEFAULT_TIMEZONE) -> str:
    global conversation_context
    text_lower = text.lower().strip()
    
    # Handle continuation phrases
    continuation_patterns = [
        r'^(what about|and|how about)',
        r'^(that day|then|after that)',
        r'^(day after tomorrow|day after)$'
    ]
    
    for pattern in continuation_patterns:
        if re.match(pattern, text_lower):
            if conversation_context['last_topic'] == 'availability':
                return check_availability_smart(text, user_timezone)
            elif conversation_context['last_topic'] == 'booking' or conversation_context['booking_in_progress']:
                return book_meeting_smart(text, user_timezone)
    
    # If booking is in progress, treat most inputs as booking-related
    if conversation_context['booking_in_progress']:
        return book_meeting_smart(text, user_timezone)
    
    return None

def process_input(text: str, user_timezone: str = DEFAULT_TIMEZONE) -> str:
    text = text.strip()
    
    # Check for contextual input first
    contextual_response = process_contextual_input(text, user_timezone)
    if contextual_response:
        return contextual_response
    
    if is_availability_request(text):
        update_context(text, 'availability')
        return check_availability_smart(text, user_timezone)
    elif is_booking_request(text):
        update_context(text, 'booking')
        return book_meeting_smart(text, user_timezone)
    else:
        update_context(text, 'casual')
        return generate_natural_response(text, "casual")

class AgentState(TypedDict):
    input: str
    steps: List[AIMessage]

def agent_logic(state: AgentState) -> AgentState:
    user_input = state["input"]
    response = process_input(user_input)
    state["steps"].append(AIMessage(content=response))
    return state

graph = StateGraph(state_schema=AgentState)
graph.add_node("agent", agent_logic)
graph.set_entry_point("agent")
graph.add_conditional_edges("agent", lambda s: True, {True: END})
app = graph.compile()