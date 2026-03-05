import logging
from fastapi import FastAPI, Depends, HTTPException, status, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.gzip import GZipMiddleware
from typing import List, Optional
from pydantic import BaseModel
from functions.search_ontologies import search_ontologies
from functions.add_ontologies import add_ontologies
from functions.delete_ontologies import delete_ontologies
from functions.update_ontology import update_ontology
from functions.model_ontology import UpdateOntology, Ontology, NewOntology, OntologyResponse, UploadOntology
from functions.auth_utils import initialize_firebase
from firebase_admin import auth
import os
from dotenv import load_dotenv
from functions.model_user import (
    get_user_uuid_by_fuid,
    get_user_profile_by_fuid,
    update_user_is_public_by_fuid,
)
from functions.upload_ontology import upload_ontology
from functions.tags import get_tags as get_all_tags, add_tags as create_tags
from functions.comments import (
    create_comment, get_comments, edit_comment, delete_comment,
    create_reply, get_replies
)
from functions.model_comment import NewComment, NewReply, NewReaction
from functions.reactions import toggle_reaction, remove_reaction, remove_reaction_by_owner, get_reaction_counts
from functions.flags import create_flag, check_user_has_flagged
from functions.model_flag import NewFlag
from functions.messages import send_message, get_messages, get_message, reply_to_message, mark_message_read
from functions.model_message import NewMessage, MessageReply
from functions.activity import get_activity_feed, get_unread_count, mark_read, mark_all_read
from functions.get_ontology import get_ontology_by_id
from functions.n4j import close_neo4j_driver

# Load environment variables from .env file
load_dotenv()

# Initialize Firebase Admin using the proper credential handling
initialize_firebase()

# Configure security for Swagger UI
security_bearer = HTTPBearer(scheme_name="Bearer", description="Firebase ID Token")

app = FastAPI(
    title="Ontology Marketplace API",
    description="API for managing and searching ontologies with Firebase authentication",
    version="1.0.0"
)

# Configure CORS origins from environment variable
cors_origins_env = os.getenv('CORS_ALLOWED_ORIGINS', '*')
if cors_origins_env == '*':
    cors_origins = ["*"]
else:
    # Split by comma and strip whitespace for multiple origins
    cors_origins = [origin.strip() for origin in cors_origins_env.split(',')]

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins,
    allow_credentials=True,
    allow_methods=["*"],  # Allows all HTTP methods
    allow_headers=["*"],  # Allows all headers
)

# Add GZip compression for responses > 500 bytes
app.add_middleware(GZipMiddleware, minimum_size=500)

async def get_current_user(request: Request, credentials: HTTPAuthorizationCredentials = Depends(security_bearer)):
    # Development bypass (useful for local testing of endpoints without Firebase)
    if os.getenv('ALLOW_DEV_AUTH_BYPASS') == '1':
        dev_email = request.headers.get('X-Dev-Email') or os.getenv('DEV_AUTH_EMAIL')
        if dev_email:
            logging.warning(f"DEV AUTH BYPASS active, using email={dev_email}")
            return {
                'email': dev_email,
                'email_verified': True,
                'uid': f'dev-{dev_email}'
            }
    
    try:
        token = credentials.credentials
        
        # Check if token is not empty
        if not token or len(token) < 10:
            raise ValueError("Token is empty or too short")
        
        decoded_token = auth.verify_id_token(token)
        return decoded_token
    except ValueError as ve:
        # Re-raise ValueError exceptions (like from verify_firebase_token)
        logging.warning(f"ValueError during token verification: {str(ve)}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(ve),
            headers={"WWW-Authenticate": "Bearer"},
        )
    except Exception as e:
        # Catch other exceptions (network, Firebase SDK errors, etc.)
        error_detail = str(e)
        logging.error(f"Token verification failed: {error_detail} (type: {type(e).__name__})")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Authentication failed: {error_detail}",
            headers={"WWW-Authenticate": "Bearer"},
        )


@app.options("/{path:path}")
async def options_handler(path: str):
    """Handle preflight OPTIONS requests for CORS"""
    return {"message": "OK"}

@app.get("/test-auth")
async def test_auth(current_user: dict = Depends(get_current_user)):
    return {
        "status": "authenticated",
        "user": current_user.get("email"),
        "uid": current_user.get("uid")
    }
    
@app.get("/search_ontologies", response_model=OntologyResponse)
async def search_ontologies_endpoint(
    request: Request,
    search_term: Optional[str] = None,
    limit: int = 100,
    offset: int = 0,
):
    """
    Search for ontologies based on query parameters
    """
    return await search_ontologies(search_term, limit, offset, request)

@app.post("/add_ontologies", response_model=OntologyResponse)
async def add_ontologies_endpoint(
    request: Request,
    ontologies: List[NewOntology],
    current_user: dict = Depends(get_current_user)
):
    """
    Add new ontologies to the system
    """
    try:
        fuid = current_user.get('uid')
        if not fuid:
            return OntologyResponse(
                success=False,
                message="Missing user ID in authentication token",
                data=None
            )
        ontology_dicts = [onto.model_dump() for onto in ontologies]
        return await add_ontologies(
            ontology_dicts,
            email=current_user.get('email'),
            fuid=fuid,
            request=request
        )
    except Exception as e:
        return {"success": False, "error": str(e)}, 500


@app.delete("/delete_ontologies", response_model=OntologyResponse)
async def delete_ontologies_endpoint(
    ontology_ids: List[str],
    current_user: dict = Depends(get_current_user)
):
    """
    Delete ontologies by their IDs

    Args:
        email: String email of the owner/admin/editor of ontologies
        ontology_ids: List of ontology uuids to delete
    """
    try:
        fuid = current_user.get('uid')
        if not fuid:
            return OntologyResponse(
                success=False,
                message="Missing user ID in authentication token",
                data=None
            )
        return await delete_ontologies(fuid, ontology_ids)
    except Exception as e:
        return OntologyResponse(
            success=False,
            message=f"Failed to process request: {str(e)}",
            data=None
        )

@app.put("/update_ontology/{ontology_uuid}", response_model=OntologyResponse)
async def update_ontology_endpoint(
    ontology_uuid: str, 
    ontology: UpdateOntology,
    current_user: dict = Depends(get_current_user)
):
    """
    Update an existing ontology

    Args:
        email: String email of the owner of ontologies
        ontology_uuid: The UUID of the ontology to update
        ontology: UpdateOntology object containing fields to update
    """
    try:
        fuid = current_user.get('uid')
        if not fuid:
            return OntologyResponse(
                success=False,
                message="Missing user ID in authentication token",
                data=None
            )
        return await update_ontology(fuid, ontology_uuid, ontology)
    except Exception as e:
        return OntologyResponse(
            success=False,
            message=f"Failed to process request: {str(e)}",
            data=None
        )

@app.post("/upload_ontology", response_model=OntologyResponse)
async def upload_ontology_endpoint(
    request: Request,
    ontology: UploadOntology,
    current_user: dict = Depends(get_current_user)
):
    """
    Upload an ontology
    """
    try:
        result = upload_ontology(
            source=ontology.source_url,
            ontology_uuid=None,
            neo4j_uri=ontology.neo4j_uri,
            neo4j_username=ontology.neo4j_username,
            neo4j_password=ontology.neo4j_password,
            neo4j_database=ontology.neo4j_database,
        )
        return OntologyResponse(success=True, message="Upload complete", data=result)
    except Exception as e:
        return OntologyResponse(
            success=False,
            message=f"Failed to process request: {str(e)}",
            data=None
        )

@app.post("/like_ontology/{ontology_id}", response_model=OntologyResponse)
async def like_ontology_endpoint(
    request: Request,
    ontology_id: str,
    current_user: dict = Depends(get_current_user)
):
    """
    Like an ontology
    """
    
    email=current_user.get('email')
    
    # TODO: Implement like logic
    return OntologyResponse(
        success=True,
        message="Like functionality to be implemented",
        data={"ontology_id": ontology_id}
    )

@app.get("/get_tags", response_model=List[str])
async def get_tags_endpoint():
    """
    Retrieve all Tags as lowercase strings.
    """
    # Optional: allow overriding database via env if needed later
    db = os.getenv('NEO4J_DATABASE', 'neo4j')
    return await get_all_tags(neo4j_database=db)

class TagList(BaseModel):
    tags: List[str]

@app.post("/add_tags", response_model=List[str])
async def add_tags_endpoint(
    payload: TagList,
    current_user: dict = Depends(get_current_user)
):
    """
    Create Tag nodes for the provided strings and return all tags in lowercase.
    """
    db = os.getenv('NEO4J_DATABASE', 'neo4j')
    return await create_tags(payload.tags, neo4j_database=db)


class UpdateUser(BaseModel):
    is_public: bool


@app.get("/get_user")
async def get_user_endpoint(current_user: dict = Depends(get_current_user)):
    """
    Return the current user's public flag and permissions.
    """
    fuid = current_user.get('uid')
    profile = await get_user_profile_by_fuid(fuid)
    return profile


@app.put("/update_user")
async def update_user_endpoint(payload: UpdateUser, current_user: dict = Depends(get_current_user)):
    """
    Update the current user's public visibility flag.
    """
    fuid = current_user.get('uid')
    success = await update_user_is_public_by_fuid(fuid, payload.is_public)
    if not success:
        raise HTTPException(status_code=500, detail="Failed to update user")
    # Return updated state
    return await get_user_profile_by_fuid(fuid)

@app.get("/ontologies/{ontology_id}")
async def get_ontology_endpoint(
    ontology_id: str,
    request: Request,
):
    """Get a single ontology by ID. Supports both authenticated and unauthenticated access."""
    fuid = None
    try:
        auth_header = request.headers.get('Authorization')
        if auth_header:
            parts = auth_header.split()
            if len(parts) == 2 and parts[0].lower() == 'bearer':
                from functions.auth_utils import verify_firebase_token
                decoded = verify_firebase_token(parts[1])
                fuid = decoded.get('uid')
    except Exception:
        fuid = None

    return await get_ontology_by_id(ontology_id, fuid)

# --- Comment Endpoints ---

@app.get("/ontologies/{ontology_id}/comments")
async def get_comments_endpoint(
    ontology_id: str,
    limit: int = 20,
    offset: int = 0,
    current_user: dict = Depends(get_current_user)
):
    result = await get_comments(ontology_id, limit, offset, current_user.get("uid"))
    return result

@app.post("/ontologies/{ontology_id}/comments", status_code=201)
async def create_comment_endpoint(
    ontology_id: str,
    comment: NewComment,
    current_user: dict = Depends(get_current_user)
):
    fuid = current_user.get("uid")
    email = current_user.get("email")
    if not fuid:
        raise HTTPException(status_code=401, detail="Missing user ID")
    result = await create_comment(ontology_id, comment.content, fuid, email)
    if not result["success"]:
        raise HTTPException(status_code=result.get("status", 400), detail=result["error"])
    return result

@app.put("/comments/{comment_id}")
async def edit_comment_endpoint(
    comment_id: str,
    comment: NewComment,
    current_user: dict = Depends(get_current_user)
):
    fuid = current_user.get("uid")
    result = await edit_comment(comment_id, comment.content, fuid)
    if not result["success"]:
        raise HTTPException(status_code=result.get("status", 400), detail=result["error"])
    return result

@app.delete("/comments/{comment_id}")
async def delete_comment_endpoint(
    comment_id: str,
    current_user: dict = Depends(get_current_user)
):
    fuid = current_user.get("uid")
    result = await delete_comment(comment_id, fuid)
    if not result["success"]:
        raise HTTPException(status_code=result.get("status", 400), detail=result["error"])
    return result

@app.post("/comments/{comment_id}/replies", status_code=201)
async def create_reply_endpoint(
    comment_id: str,
    reply: NewReply,
    current_user: dict = Depends(get_current_user)
):
    fuid = current_user.get("uid")
    email = current_user.get("email")
    result = await create_reply(comment_id, reply.content, fuid, email)
    if not result["success"]:
        raise HTTPException(status_code=result.get("status", 400), detail=result["error"])
    return result

@app.get("/comments/{comment_id}/replies")
async def get_replies_endpoint(
    comment_id: str,
    limit: int = 20,
    offset: int = 0,
    current_user: dict = Depends(get_current_user)
):
    result = await get_replies(comment_id, limit, offset)
    return result

# --- Reaction Endpoints ---

@app.post("/comments/{comment_id}/reactions", status_code=201)
async def toggle_reaction_endpoint(
    comment_id: str,
    reaction: NewReaction,
    current_user: dict = Depends(get_current_user)
):
    fuid = current_user.get("uid")
    result = await toggle_reaction(comment_id, reaction.emoji, fuid)
    if not result["success"]:
        raise HTTPException(status_code=result.get("status", 400), detail=result["error"])
    return result

@app.delete("/comments/{comment_id}/reactions/{emoji}")
async def remove_reaction_endpoint(
    comment_id: str,
    emoji: str,
    current_user: dict = Depends(get_current_user)
):
    fuid = current_user.get("uid")
    result = await remove_reaction(comment_id, emoji, fuid)
    if not result["success"]:
        raise HTTPException(status_code=result.get("status", 400), detail=result["error"])
    return result

@app.delete("/comments/{comment_id}/reactions/by-id/{reaction_id}")
async def remove_reaction_by_owner_endpoint(
    comment_id: str,
    reaction_id: str,
    current_user: dict = Depends(get_current_user)
):
    fuid = current_user.get("uid")
    result = await remove_reaction_by_owner(comment_id, reaction_id, fuid)
    if not result["success"]:
        raise HTTPException(status_code=result.get("status", 400), detail=result["error"])
    return result

@app.get("/comments/{comment_id}/reactions")
async def get_reaction_counts_endpoint(
    comment_id: str,
    current_user: dict = Depends(get_current_user)
):
    fuid = current_user.get("uid")
    return await get_reaction_counts(comment_id, fuid)

# --- Flag Endpoints ---

@app.post("/comments/{comment_id}/flag", status_code=201)
async def flag_comment_endpoint(
    comment_id: str,
    flag: NewFlag,
    current_user: dict = Depends(get_current_user)
):
    fuid = current_user.get("uid")
    result = await create_flag(comment_id, flag.reason, flag.details, fuid)
    if not result["success"]:
        raise HTTPException(status_code=result.get("status", 400), detail=result["error"])
    return result

# --- Message Endpoints ---

@app.post("/messages", status_code=201)
async def send_message_endpoint(
    message: NewMessage,
    current_user: dict = Depends(get_current_user)
):
    if not current_user.get("is_admin"):
        raise HTTPException(status_code=403, detail="Only admins can send messages")
    fuid = current_user.get("uid")
    email = current_user.get("email")
    result = await send_message(message.recipient_fuid, message.subject, message.content, fuid, email)
    if not result["success"]:
        raise HTTPException(status_code=result.get("status", 400), detail=result["error"])
    return result

@app.get("/messages")
async def get_messages_endpoint(
    limit: int = 20,
    offset: int = 0,
    current_user: dict = Depends(get_current_user)
):
    fuid = current_user.get("uid")
    return await get_messages(fuid, limit, offset)

@app.get("/messages/{message_id}")
async def get_message_endpoint(
    message_id: str,
    current_user: dict = Depends(get_current_user)
):
    fuid = current_user.get("uid")
    result = await get_message(message_id, fuid)
    if not result["success"]:
        raise HTTPException(status_code=result.get("status", 400), detail=result["error"])
    return result

@app.post("/messages/{message_id}/reply", status_code=201)
async def reply_to_message_endpoint(
    message_id: str,
    reply: MessageReply,
    current_user: dict = Depends(get_current_user)
):
    fuid = current_user.get("uid")
    email = current_user.get("email")
    result = await reply_to_message(message_id, reply.content, fuid, email)
    if not result["success"]:
        raise HTTPException(status_code=result.get("status", 400), detail=result["error"])
    return result

@app.put("/messages/{message_id}/read")
async def mark_message_read_endpoint(
    message_id: str,
    current_user: dict = Depends(get_current_user)
):
    fuid = current_user.get("uid")
    result = await mark_message_read(message_id, fuid)
    if not result["success"]:
        raise HTTPException(status_code=result.get("status", 400), detail=result["error"])
    return result

# --- Activity Feed Endpoints ---

@app.get("/users/me/activity")
async def get_activity_endpoint(
    limit: int = 20,
    offset: int = 0,
    type: str = None,
    search: str = None,
    current_user: dict = Depends(get_current_user)
):
    fuid = current_user.get("uid")
    return await get_activity_feed(fuid, limit, offset, type, search)

@app.get("/users/me/activity/unread-count")
async def get_unread_count_endpoint(
    current_user: dict = Depends(get_current_user)
):
    fuid = current_user.get("uid")
    return await get_unread_count(fuid)

@app.put("/users/me/activity/{item_id}/read")
async def mark_read_endpoint(
    item_id: str,
    current_user: dict = Depends(get_current_user)
):
    fuid = current_user.get("uid")
    result = await mark_read(item_id, fuid)
    if not result["success"]:
        raise HTTPException(status_code=result.get("status", 400), detail=result["error"])
    return result

@app.put("/users/me/activity/read-all")
async def mark_all_read_endpoint(
    current_user: dict = Depends(get_current_user)
):
    fuid = current_user.get("uid")
    return await mark_all_read(fuid)

@app.on_event("shutdown")
async def shutdown_event():
    await close_neo4j_driver()

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
