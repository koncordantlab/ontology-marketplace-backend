from functools import wraps
from typing import Optional, Callable, Any
import firebase_admin
from firebase_admin import auth, credentials, exceptions
from flask import Request, jsonify
from typing import Tuple, Dict, Any, Optional, Union
import os
import logging

# Module-level logger
logger = logging.getLogger(__name__)

# Track whether we've logged Firebase initialization details to avoid noise
_firebase_init_logged = False

def initialize_firebase():
    """Initialize the Firebase Admin SDK if not already initialized."""
    try:
        firebase_admin.get_app()
    except ValueError:
        # Determine project ID from common environment variables
        project_id = (
            os.getenv('GOOGLE_CLOUD_PROJECT')
            or os.getenv('GCP_PROJECT')
            or os.getenv('FIREBASE_PROJECT_ID')
            or os.getenv('GOOGLE_PROJECT_ID')
            or os.getenv('PROJECT_ID')
        )

        # Prefer explicit service account if provided
        cred = None
        sa_path = os.getenv('GOOGLE_APPLICATION_CREDENTIALS')
        sa_json = os.getenv('GOOGLE_APPLICATION_CREDENTIALS_JSON')
        
        try:
            if sa_json:
                # Parse stringified JSON credentials
                import json
                sa_data = json.loads(sa_json)
                cred = credentials.Certificate(sa_data)
            elif sa_path and os.path.exists(sa_path):
                # Use file path credentials
                cred = credentials.Certificate(sa_path)
            else:
                cred = credentials.ApplicationDefault()
        except Exception:
            cred = None

        options = {'projectId': project_id} if project_id else None

        if cred is not None:
            firebase_admin.initialize_app(cred, options)
        elif options is not None:
            # Initialize with options only; Firebase Admin supports credential=None
            firebase_admin.initialize_app(options=options)
        else:
            raise RuntimeError(
                "Firebase project ID is required. Set GOOGLE_CLOUD_PROJECT, GCP_PROJECT, or "
                "FIREBASE_PROJECT_ID, or provide GOOGLE_APPLICATION_CREDENTIALS (file path) or "
                "GOOGLE_APPLICATION_CREDENTIALS_JSON (stringified JSON) for service account credentials."
            )

        global _firebase_init_logged
        if not _firebase_init_logged:
            emulator = os.getenv('FIREBASE_AUTH_EMULATOR_HOST')
            logger.info(
                "Initialized Firebase Admin SDK | project_id=%s | using_sa=%s | sa_type=%s | emulator=%s",
                project_id or "<unset>", 
                bool(sa_json or (sa_path and os.path.exists(sa_path))),
                "json" if sa_json else ("file" if sa_path and os.path.exists(sa_path) else "default"),
                emulator or "<none>"
            )
            _firebase_init_logged = True

def verify_firebase_token(id_token: str) -> dict:
    """
    Verify a Firebase ID token.
    
    Args:
        id_token: The Firebase ID token string to verify
        
    Returns:
        dict: The decoded token claims
        
    Raises:
        ValueError: If the token is invalid, expired, or revoked
    """
    try:
        initialize_firebase()
        decoded_token = auth.verify_id_token(id_token)
        return decoded_token
    except exceptions.ExpiredIdTokenError as e:
        logger.warning("Firebase token expired: %s", str(e))
        raise ValueError("Authentication failed: token has expired. Please sign in again.")
    except exceptions.RevokedIdTokenError as e:
        logger.warning("Firebase token revoked: %s", str(e))
        raise ValueError("Authentication failed: token has been revoked. Please sign in again.")
    except exceptions.InvalidIdTokenError as e:
        logger.warning("Firebase invalid token: %s", str(e))
        raise ValueError("Authentication failed: invalid ID token.")
    except (ValueError, exceptions.FirebaseError) as e:
        # Provide concise, safe error message (do not echo token)
        msg = getattr(e, 'message', None) or str(e)
        logger.warning("Firebase token verification failed: %s", msg)
        raise ValueError(f"Authentication failed: {msg}")

def get_authenticated_email(request: Request) -> str:
    """
    Get the authenticated user's email from the Authorization header.
    
    Args:
        request: Flask request object
        
    Returns:
        str: The authenticated user's email
        
    Raises:
        ValueError: If authentication fails or email is not verified
    """
    # Development bypass (useful for local testing of endpoints without Firebase)
    if os.getenv('ALLOW_DEV_AUTH_BYPASS') == '1':
        dev_email = request.headers.get('X-Dev-Email') or os.getenv('DEV_AUTH_EMAIL')
        if dev_email:
            logger.info("DEV AUTH BYPASS active, using email=%s", dev_email)
            return str(dev_email)

    auth_header = request.headers.get('Authorization')
    if not auth_header:
        raise ValueError('Authorization header is missing')

    # Accept case-insensitive "Bearer" and extra spaces
    parts = auth_header.split()
    if len(parts) != 2 or parts[0].lower() != 'bearer':
        raise ValueError('Authorization header must be in the format: Bearer <token>')

    id_token = parts[1]
    decoded_token = verify_firebase_token(id_token)
    
    if not decoded_token.get('email_verified', False):
        raise ValueError('Email not verified')
    
    return decoded_token['email']

def get_auth_headers_and_email(request: Optional[Request] = None, email: Optional[str] = None) -> Tuple[Dict[str, str], Union[str, Tuple[Dict[str, Any], int, Dict[str, str]]]]:
    """
    Get authentication headers and verify user authentication.
    
    Args:
        request: Flask request object (optional if email is provided)
        email: Pre-authenticated email (optional if request is provided)
        
    Returns:
        If authenticated: (headers, email)
        If authentication fails: (error_response, status_code, headers)
    """
    # Set CORS response headers
    headers = {
        'Access-Control-Allow-Origin': '*',
        'Access-Control-Allow-Methods': 'GET, POST, OPTIONS',
        'Access-Control-Allow-Headers': 'Authorization, Content-Type, X-Dev-Email',
        'Content-Type': 'application/json'
    }

    # Handle CORS preflight early
    if request is not None and getattr(request, 'method', '').upper() == 'OPTIONS':
        return {'success': True}, 204, headers

    # If email is already provided, return it with headers
    if email is not None:
        return headers, email
        
    # Otherwise, try to get email from request
    if request is not None:
        try:
            email = get_authenticated_email(request)
            return headers, email
        except ValueError as e:
            error_response = {
                'success': False,
                'error': str(e)
            }
            return error_response, 401, headers
    
    # If we get here, neither email nor valid request was provided
    error_response = {
        'success': False,
        'error': 'Authentication required. Please provide a valid Firebase ID token.'
    }
    return error_response, 401, headers

def firebase_auth_required(f: Callable) -> Callable:
    """
    Decorator to require Firebase authentication for a route.
    
    Args:
        f: The route function to decorate
        
    Returns:
        The decorated function that includes authentication
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):
        try:
            email = get_authenticated_email(args[0] if args else kwargs.get('request'))
            # Add the authenticated email to the function's kwargs
            if 'email' in kwargs:
                kwargs['email'] = email
            else:
                kwargs['authenticated_email'] = email
            return f(*args, **kwargs)
        except ValueError as e:
            return jsonify({
                'success': False,
                'error': str(e)
            }), 401
    return decorated_function
