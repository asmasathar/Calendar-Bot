import streamlit as st
import requests
import json
import uuid
from datetime import datetime
import time
import pytz

st.set_page_config(
    page_title="📅 AI Calendar Assistant",
    page_icon="🤖",
    layout="wide",
    initial_sidebar_state="expanded"
)


st.markdown("""
<style>
    .main-header {
        text-align: center;
        padding: 1rem 0;
        background: linear-gradient(90deg, #667eea 0%, #764ba2 100%);
        color: white;
        border-radius: 10px;
        margin-bottom: 2rem;
    }
    
    .chat-container {
        max-height: 500px;
        overflow-y: auto;
        padding: 1rem;
        border: 1px solid #e0e0e0;
        border-radius: 10px;
        background-color: #f8f9fa;
    }
    
    .user-message {
        background-color: #007bff;
        color: white;
        padding: 0.5rem 1rem;
        border-radius: 15px 15px 5px 15px;
        margin: 0.5rem 0;
        margin-left: 2rem;
        text-align: right;
    }
    
    .assistant-message {
        background-color: #e9ecef;
        color: #333;
        padding: 0.5rem 1rem;
        border-radius: 15px 15px 15px 5px;
        margin: 0.5rem 0;
        margin-right: 2rem;
    }
    
    .status-success {
        color: #28a745;
        font-weight: bold;
    }
    
    .status-error {
        color: #dc3545;
        font-weight: bold;
    }
    
   .feature-card {
    background-color: rgb(26, 28, 36);
    padding: 1rem;
    border-radius: 8px;
    border-left: 4px solid #007bff;
    margin: 0.5rem 0;
    box-shadow: 0 2px 4px rgba(0,0,0,0.1);
}
    
    



</style>
""", unsafe_allow_html=True)

# FastAPI backend URL
API_BASE_URL = "https://calendar-bot-o41f.onrender.com"

# Timezone selection
if "timezone" not in st.session_state:
    st.session_state["timezone"] = "Asia/Kolkata"
timezones = pytz.all_timezones
st.sidebar.header("🌐 Timezone Settings")
st.session_state["timezone"] = st.sidebar.selectbox(
    "Select your timezone:",
    options=timezones,
    index=timezones.index(st.session_state["timezone"])
)

# Initialize session state
if "session_id" not in st.session_state:
    st.session_state.session_id = str(uuid.uuid4())
    
if "messages" not in st.session_state:
    st.session_state.messages = []
    
if "api_status" not in st.session_state:
    st.session_state.api_status = "unknown"

def check_api_health():
    """Check if the FastAPI backend is running"""
    try:
        response = requests.get(f"{API_BASE_URL}/health", timeout=5)
        if response.status_code == 200:
            st.session_state.api_status = "healthy"
            return True
        else:
            st.session_state.api_status = "unhealthy"
            return False
    except Exception as e:
        st.session_state.api_status = f"error: {str(e)}"
        return False

def send_message_to_agent(message: str):
    """Send message to FastAPI backend and get response"""
    try:
        payload = {
            "message": message,
            "session_id": st.session_state.session_id,
            "timezone": st.session_state["timezone"]
        }
        
        response = requests.post(
            f"{API_BASE_URL}/chat",
            json=payload,
            timeout=30
        )
        
        if response.status_code == 200:
            return response.json()
        else:
            return {
                "response": f"Error: Received status code {response.status_code}",
                "status": "error"
            }
            
    except requests.exceptions.RequestException as e:
        return {
            "response": f"Connection error: {str(e)}. Please make sure the backend is running.",
            "status": "error"
        }
    except Exception as e:
        return {
            "response": f"Unexpected error: {str(e)}",
            "status": "error"
        }

def display_message(message, is_user=False):
    """Display a message in the chat interface"""
    if is_user:
        st.markdown(f'<div class="user-message">👤 {message}</div>', unsafe_allow_html=True)
    else:
        st.markdown(f'<div class="assistant-message">🤖 {message}</div>', unsafe_allow_html=True)


st.markdown('<div class="main-header"><h1>🤖 AI Calendar Assistant</h1><p>Your intelligent booking companion</p></div>', unsafe_allow_html=True)


with st.sidebar:
    st.header("📊 Session Info")
    

    api_healthy = check_api_health()
    status_color = "🟢" if api_healthy else "🔴"
    st.write(f"{status_color} **API Status:** {st.session_state.api_status}")
    
    st.write(f"**Session ID:** `{st.session_state.session_id[:8]}...`")
    st.write(f"**Messages:** {len(st.session_state.messages)}")
    st.write(f"**Time:** {datetime.now().strftime('%H:%M:%S')}")
    
    # Controls
    st.header("🔧 Controls")
    
    if st.button("🔄 Refresh API Status"):
        check_api_health()
        st.rerun()
    
    if st.button("🗑️ Clear Chat"):
        st.session_state.messages = []
        st.rerun()
    
    if st.button("🆕 New Session"):
        st.session_state.session_id = str(uuid.uuid4())
        st.session_state.messages = []
        st.rerun()
    

    st.header("✨ Features")
    st.markdown("""
    <div class="feature-card">
        <strong>📅 Availability Check</strong><br>
        Check if a specific time slot is available, e.g., "Is there availability tomorrow at 2pm?"
    </div>
    <div class="feature-card">
        <strong>📝 Meeting Booking</strong><br>
        Schedule a meeting, e.g., "Book a meeting with John next Friday"
    </div>
    <div class="feature-card">
        <strong>💬 Natural Language</strong><br>
        Use natural language to manage the calendar.
    </div>
    """, unsafe_allow_html=True)

# Main chat interface
col1, col2 = st.columns([3, 1])

with col1:
    st.header("💬 Chat with your Assistant")
    

    if not api_healthy:
        st.error(f"⚠️ Backend API is not responding. Status: {st.session_state.api_status}")
        st.info("Please make sure the FastAPI server is running on the correct port.")
    

    chat_container = st.container()
    
    with chat_container:
        st.markdown('<div class="chat-container">', unsafe_allow_html=True)
        

        if not st.session_state.messages:
            st.markdown("""
            <div class="assistant-message">
                🤖 Hi! I'm your AI Calendar Assistant. I can help you:<br>
                • Check your availability<br>
                • Schedule meetings and appointments<br>
                • Manage your calendar naturally<br><br>
                Try asking me something like "Am I free tomorrow afternoon?" or "Book a meeting with Sarah next week"
            </div>
            """, unsafe_allow_html=True)
        

        for message in st.session_state.messages:
            display_message(message["content"], message["role"] == "user")
        
        st.markdown('</div>', unsafe_allow_html=True)

with col2:
    st.header("📈 Quick Stats")
    

    user_messages = len([m for m in st.session_state.messages if m["role"] == "user"])
    assistant_messages = len([m for m in st.session_state.messages if m["role"] == "assistant"])
    
    col2_1, col2_2 = st.columns(2)
    with col2_1:
        st.metric("User Messages", user_messages)
    with col2_2:
        st.metric("Assistant Replies", assistant_messages)
    

    st.subheader("🕐 Recent Activity")
    if st.session_state.messages:
        last_message = st.session_state.messages[-1]
        st.write(f"**Last:** {last_message['role'].title()}")
        st.write(f"**Content:** {last_message['content'][:50]}...")
    else:
        st.write("No recent activity")


st.markdown("---")
input_container = st.container()

with input_container:

    with st.form(key="chat_form", clear_on_submit=True):
        col_input, col_send = st.columns([4, 1])
        
        with col_input:
            user_input = st.text_input(
                "Type your message here...",
                placeholder="e.g., 'Check availability for tomorrow at 3pm' or 'Book a meeting with John on Friday'",
                key="user_input"
            )
        
        with col_send:
            st.write("")  
            send_button = st.form_submit_button("Send 📤", use_container_width=True)
    

    if send_button and user_input.strip():
        if not api_healthy:
            st.error("Cannot send message: API is not available")
        else:
   
            st.session_state.messages.append({
                "role": "user", 
                "content": user_input,
                "timestamp": datetime.now().isoformat()
            })
            
 
            with st.spinner("🤖 Thinking..."):
               
                response_data = send_message_to_agent(user_input)
            
         
            st.session_state.messages.append({
                "role": "assistant",
                "content": response_data["response"],
                "status": response_data.get("status", "unknown"),
                "timestamp": datetime.now().isoformat()
            })
            
            
            st.rerun()


st.markdown("---")
st.subheader("💡 Example Prompts")

example_col1, example_col2, example_col3 = st.columns(3)

with example_col1:
    if st.button("📅 Check Availability"):
        if api_healthy:
            example_prompt = "Am I free tomorrow afternoon?"
            st.session_state.messages.append({"role": "user", "content": example_prompt, "timestamp": datetime.now().isoformat()})
            with st.spinner("Processing..."):
                response_data = send_message_to_agent(example_prompt)
            st.session_state.messages.append({"role": "assistant", "content": response_data["response"], "timestamp": datetime.now().isoformat()})
            st.rerun()

with example_col2:
    if st.button("📝 Schedule Meeting"):
        if api_healthy:
            example_prompt = "Schedule a 1-hour meeting with the team next Monday at 2pm"
            st.session_state.messages.append({"role": "user", "content": example_prompt, "timestamp": datetime.now().isoformat()})
            with st.spinner("Processing..."):
                response_data = send_message_to_agent(example_prompt)
            st.session_state.messages.append({"role": "assistant", "content": response_data["response"], "timestamp": datetime.now().isoformat()})
            st.rerun()

with example_col3:
    if st.button("🔍 Find Time Slots"):
        if api_healthy:
            example_prompt = "When am I free this week for a 30-minute call?"
            st.session_state.messages.append({"role": "user", "content": example_prompt, "timestamp": datetime.now().isoformat()})
            with st.spinner("Processing..."):
                response_data = send_message_to_agent(example_prompt)
            st.session_state.messages.append({"role": "assistant", "content": response_data["response"], "timestamp": datetime.now().isoformat()})
            st.rerun()


st.markdown("---")
st.markdown("**📅 AI Calendar Assistant** | Built with FastAPI + Streamlit + LangGraph")