from fastapi import FastAPI, Depends, HTTPException, status, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from fastapi.middleware.cors import CORSMiddleware
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

async def get_current_user(request: Request, credentials: HTTPAuthorizationCredentials = Depends(security_bearer)):
    # Development bypass (useful for local testing of endpoints without Firebase)
    if os.getenv('ALLOW_DEV_AUTH_BYPASS') == '1':
        dev_email = request.headers.get('X-Dev-Email') or os.getenv('DEV_AUTH_EMAIL')
        if dev_email:
            print(f"DEV AUTH BYPASS active, using email={dev_email}")
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
        
        print(f"Verifying token (length: {len(token)}, starts with: {token[:20]}...)")
        decoded_token = auth.verify_id_token(token)
        print(f"Token verified successfully for user: {decoded_token.get('email', 'N/A')}")
        return decoded_token
    except ValueError as ve:
        # Re-raise ValueError exceptions (like from verify_firebase_token)
        print(f"ValueError during token verification: {str(ve)}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(ve),
            headers={"WWW-Authenticate": "Bearer"},
        )
    except Exception as e:
        # Catch other exceptions (network, Firebase SDK errors, etc.)
        error_detail = str(e)
        print(f"Token verification failed: {error_detail}")
        print(f"Error type: {type(e).__name__}")
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
    return search_ontologies(search_term, limit, offset, request)

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
        ontology_dicts = [onto.model_dump() for onto in ontologies]
        return add_ontologies(
            ontology_dicts,
            email=current_user.get('email'),
            fuid=current_user.get('uid'),
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
        fuid=current_user.get('uid')
        return delete_ontologies(fuid, ontology_ids)
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
        fuid=current_user.get('uid')
        print(f"Updating ontology {ontology_uuid} for uid {fuid} with data {ontology.model_dump()}")
        return update_ontology(fuid, ontology_uuid, ontology)
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
    return get_all_tags(neo4j_database=db)

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
    return create_tags(payload.tags, neo4j_database=db)


class UpdateUser(BaseModel):
    is_public: bool


@app.get("/get_user")
async def get_user_endpoint(current_user: dict = Depends(get_current_user)):
    """
    Return the current user's public flag and permissions.
    """
    fuid = current_user.get('uid')
    profile = get_user_profile_by_fuid(fuid)
    return profile


@app.put("/update_user")
async def update_user_endpoint(payload: UpdateUser, current_user: dict = Depends(get_current_user)):
    """
    Update the current user's public visibility flag.
    """
    fuid = current_user.get('uid')
    success = update_user_is_public_by_fuid(fuid, payload.is_public)
    if not success:
        raise HTTPException(status_code=500, detail="Failed to update user")
    # Return updated state
    return get_user_profile_by_fuid(fuid)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
