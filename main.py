from fastapi import FastAPI, Depends, HTTPException, status, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from fastapi.middleware.cors import CORSMiddleware
from typing import List, Optional
from pydantic import BaseModel
from functions.search_ontologies import search_ontologies
from functions.add_ontologies import add_ontologies
from functions.delete_ontologies import delete_ontologies
from functions.update_ontology import update_ontology
from functions.model_ontology import UpdateOntology, Ontology, NewOntology, OntologyResponse
from functions.auth_utils import initialize_firebase
from firebase_admin import auth
import os

# Initialize Firebase Admin using the proper credential handling
initialize_firebase()

app = FastAPI(title="Ontology Marketplace API")

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

security = HTTPBearer()

async def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security)):
    try:
        token = credentials.credentials
        print(f"Verifying token: {token[:20]}...")  # Log first 20 chars of token
        decoded_token = auth.verify_id_token(token)
        print("Token verified successfully")
        return decoded_token
    except Exception as e:
        print(f"Token verification failed: {str(e)}")  # Log the actual error
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Authentication failed: {str(e)}",  # Include error in response
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
    current_user: dict = Depends(get_current_user)
):
    """
    Search for ontologies based on query parameters
    """
    return search_ontologies(search_term, limit, offset, request)

@app.post("/add_ontologies", response_model=OntologyResponse)
async def add_ontologies_endpoint(
    ontologies: List[NewOntology],
    current_user: dict = Depends(get_current_user)
):
    """
    Add new ontologies to the system
    """
    try:
        ontology_dicts = [onto.model_dump() for onto in ontologies]
        return add_ontologies(ontology_dicts, email=current_user.get('email'))
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
        email=current_user.get('email')
        return delete_ontologies(email, ontology_ids)
    except Exception as e:
        return OntologyResponse(
            success=False,
            message=f"Failed to process request: {str(e)}",
            data=None
        )

@app.put("/update_ontology/{ontology_id}", response_model=OntologyResponse)
async def update_ontology_endpoint(
    ontology_id: str, 
    ontology: UpdateOntology,
    current_user: dict = Depends(get_current_user)
):
    """
    Update an existing ontology

    Args:
        email: String email of the owner of ontologies
        ontology_id: The UID of the ontology to update
        ontology: UpdateOntology object containing fields to update
    """
    try:
        email=current_user.get('email')
        return update_ontology(email, ontology_id, ontology)
    except Exception as e:
        return OntologyResponse(
            success=False,
            message=f"Failed to process request: {str(e)}",
            data=None
        )

@app.post("/like_ontology/{ontology_id}", response_model=OntologyResponse)
async def like_ontology_endpoint(
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

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
