from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Dict, Any, Optional
import sys
import os
import logging

sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from agents.agent1 import app as agent_app, conversation_context

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="Calendar Booking Agent API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], 
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class ChatMessage(BaseModel):
    message: str
    session_id: Optional[str] = "default"
    timezone: Optional[str] = None

class ChatResponse(BaseModel):
    response: str
    status: str = "success"
    conversation_context: Dict[str, Any] = {}

class HealthResponse(BaseModel):
    status: str
    message: str
conversation_sessions: Dict[str, Dict] = {}

@app.get("/", response_model=HealthResponse)
async def root():
    """Health check endpoint"""
    return HealthResponse(status="healthy", message="Calendar Booking Agent API is running!")

@app.get("/health", response_model=HealthResponse)
async def health_check():
    """Health check endpoint"""
    return HealthResponse(status="healthy", message="API is operational")

@app.post("/chat", response_model=ChatResponse)
async def chat_with_agent(chat_message: ChatMessage):
    """
    Main chat endpoint - processes user messages and returns agent responses
    """
    try:
        user_input = chat_message.message.strip()
        session_id = chat_message.session_id
        user_timezone = chat_message.timezone or "Asia/Kolkata"
        
        if not user_input:
            return ChatResponse(
                response="I'm here to help! Please tell me what you'd like to do with your calendar.",
                status="success"
            )
        
        if session_id not in conversation_sessions:
            conversation_sessions[session_id] = {
                "messages": [],
                "context": {}
            }
        
        conversation_sessions[session_id]["messages"].append({
            "role": "user",
            "content": user_input
        })
        
        logger.info(f"Processing message for session {session_id}: {user_input}")
        
       
        result = agent_app.invoke({
            "input": user_input, 
            "steps": [],
            "user_timezone": user_timezone
        })
        
        agent_response = result['steps'][-1].content if result['steps'] else "I'm sorry, I couldn't process that request."
        
        
        conversation_sessions[session_id]["messages"].append({
            "role": "assistant",
            "content": agent_response
        })
        
        
        conversation_sessions[session_id]["context"] = {
            "last_topic": conversation_context.get('last_topic'),
            "last_date_mentioned": conversation_context.get('last_date_mentioned'),
            "last_time_mentioned": conversation_context.get('last_time_mentioned')
        }
        
        logger.info(f"Agent response for session {session_id}: {agent_response}")
        
        return ChatResponse(
            response=agent_response,
            status="success",
            conversation_context=conversation_sessions[session_id]["context"]
        )
        
    except Exception as e:
        logger.error(f"Error processing chat message: {str(e)}")
        return ChatResponse(
            response="I apologize, but I encountered an error while processing your request. Please try again or rephrase your message.",
            status="error"
        )

@app.get("/conversation/{session_id}")
async def get_conversation_history(session_id: str):
    """Get conversation history for a session"""
    if session_id not in conversation_sessions:
        raise HTTPException(status_code=404, detail="Session not found")
    
    return {
        "session_id": session_id,
        "messages": conversation_sessions[session_id]["messages"],
        "context": conversation_sessions[session_id]["context"]
    }

@app.delete("/conversation/{session_id}")
async def clear_conversation(session_id: str):
    """Clear conversation history for a session"""
    if session_id in conversation_sessions:
        del conversation_sessions[session_id]
        return {"message": f"Conversation {session_id} cleared successfully"}
    else:
        raise HTTPException(status_code=404, detail="Session not found")

@app.get("/sessions")
async def list_active_sessions():
    """List all active conversation sessions"""
    return {
        "active_sessions": list(conversation_sessions.keys()),
        "total_sessions": len(conversation_sessions)
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "main:app",
        host="0.0.0.0", 
        port=8000, 
        reload=True,
        log_level="info"
    )