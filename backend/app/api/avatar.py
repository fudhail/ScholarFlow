"""Avatar API endpoints for Anam.ai integration"""

from fastapi import APIRouter, HTTPException, Depends
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
from pydantic import BaseModel
import httpx
import logging
import json
from app.core.config import settings
from app.models.database import get_db

router = APIRouter(prefix="/avatar", tags=["avatar"])
logger = logging.getLogger(__name__)

class PersonaConfig(BaseModel):
    name: str = "ScholarMate"  # Updated to match the persona
    avatarId: str = "30fa96d0-26c4-4e55-94a0-517025942e18"
    voiceId: str = "6bfbe25a-979d-40f3-a92b-5394170af54b"
    llmId: str = "CUSTOMER_CLIENT_V1"  # Use custom client-side LLM logic
    systemPrompt: str = "You are ScholarMate, a research co-author (PhD level). You speak naturally to your colleague (the user). Use 'we', 'our', and collaborative language. Be concise but insightful. Do not behave like an AI assistant; behave like a peer."
    voiceDetectionOptions: dict | None = {
        "endOfSpeechSensitivity": 0.5,
        "silenceBeforeSkipTurnSeconds": 5.0,  # Increased to 5.0 as per API requirement
        "silenceBeforeAutoEndTurnSeconds": 1.0 # This seems fine
    }

class SessionRequest(BaseModel):
    personaConfig: PersonaConfig | None = None

class ChatMessage(BaseModel):
    role: str
    content: str

class AvatarChatRequest(BaseModel):
    messages: list[ChatMessage]
    # Optional context fields if needed for research
    project_id: str | None = None

@router.post("/session")
async def get_session_token(request: SessionRequest | None = None):
    """
    Get a session token for Anam.ai avatar with custom LLM enabled
    """
    if not settings.anam_api_key:
        raise HTTPException(status_code=500, detail="ANAM_API_KEY is not configured")

    # Use default config if not provided
    config = request.personaConfig if request and request.personaConfig else PersonaConfig()
    
    # Ensure llmId is set to CUSTOMER_CLIENT_V1 if not already
    if config.llmId != "CUSTOMER_CLIENT_V1":
         config.llmId = "CUSTOMER_CLIENT_V1"

    try:
        # Reverted URL to auth endpoint as per 405 investigation
        url = "https://api.anam.ai/v1/auth/session-token"
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {settings.anam_api_key}",
        }
        # Payload
        payload = {"personaConfig": config.model_dump()}
        
        print(f"DEBUG: Requesting Anam Session from {url}")
        print(f"DEBUG: Payload: {json.dumps(payload, indent=2)}")
        # maximize debugging
        
        async with httpx.AsyncClient() as client:
            response = await client.post(
                url,
                headers=headers,
                json=payload,
                timeout=15.0
            )

            print(f"DEBUG: Anam Response Status: {response.status_code}")
            print(f"DEBUG: Anam Response Body: {response.text}")

            if response.status_code != 200:
                logger.error(f"Anam.ai API error: {response.text}")
                # return the error directly to frontend for easier debugging
                raise HTTPException(status_code=response.status_code, detail=f"Anam Error: {response.text}")

            return response.json()

    except HTTPException as he:
        # Re-raise HTTP exceptions directly
        raise he
    except Exception as e:
        logger.error(f"Error fetching Anam.ai session: {e}")
        print(f"DEBUG: Exception: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/chat")
async def avatar_chat_stream(
    request: AvatarChatRequest,
    db: Session = Depends(get_db)
):
    """
    Stream internal agent response to Avatar as NDJSON
    Format: {"content": "text chunk"}\n
    """
    from app.agents.graph import research_graph
    from app.agents.state import create_initial_state
    
    # Extract last user message
    user_message = request.messages[-1].content if request.messages else ""
    if not user_message:
        return StreamingResponse(iter([]), media_type="application/x-ndjson")

    async def event_generator():
        try:
             # Create initial state (simplified for avatar chat)
            initial_state = create_initial_state(
                query=user_message,
                project_id=request.project_id or "default", # Fallback project
                session_id=None # ephemeral session
            )
            
            # 1. Immediate Acknowledgement
            yield json.dumps({"content": "Interesting question. Let's see what the literature says about that."}) + "\n"
            
            # State tracking to avoid reduced repetition
            has_mentioned_papers = False
            
            # Stream graph execution
            async for chunk in research_graph.astream(initial_state):
                 for node_name, state_update in chunk.items():
                    
                    # 2. Status Updates (Papers Found)
                    if not has_mentioned_papers:
                        papers = state_update.get("ranked_papers") or state_update.get("found_papers")
                        if papers:
                            count = len(papers)
                            yield json.dumps({"content": f"I've uncovered {count} papers that seem relevant. I'm reading through them now to extract the key insights."}) + "\n"
                            has_mentioned_papers = True

                    # 3. Final Content (Answer / Synthesis)
                    text_to_speak = ""
                    
                    # Check for direct answer (from Rag Response Node)
                    if "current_draft" in state_update:
                        draft = state_update["current_draft"]
                        # Relaxed section check and status check
                        section = draft.get("section")
                        if section in ["Response", "Research Response"] and draft.get("content"):
                             if draft.get("status") in ["completed", "grounded"] or node_name == "rag_response":
                                 # PRIORITIZE NARRATION for avatar speech
                                 text_to_speak = draft.get("narration") or draft["content"]

                    # Check for synthesis
                    elif "synthesis_summary" in state_update:
                        text_to_speak = state_update["synthesis_summary"]

                    # Emit content if found
                    if text_to_speak:
                        # For avatar, speak the narration (conversational)
                        # But also include the full content as data if frontend needs it
                        yield json.dumps({"content": text_to_speak}) + "\n"
            # If no content was yielded (e.g. just a search step), maybe say something?
            # yielded locally.
            
        except Exception as e:
            logger.error(f"Avatar chat error: {e}")
            yield json.dumps({"content": "Sorry, I encountered an error."}) + "\n"

    return StreamingResponse(
        event_generator(),
        media_type="application/x-ndjson"
    )
