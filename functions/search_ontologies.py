from functions_framework import http
from flask import Request
import json
import logging
from typing import Optional
from .model_ontology import Ontology, OntologyResponse
from datetime import datetime
from .n4j import get_neo4j_driver
from .auth_utils import get_auth_headers_and_email, verify_firebase_token
from flask import Request
from typing import Optional, Tuple, Dict, Any
from .cache import cache_search_results


@cache_search_results
async def search_ontologies(
    search_term: str = None,
    limit: int = 100,
    offset: int = 0,
    request: Optional[Request] = None
) -> OntologyResponse:
    """
    Search for ontologies in the database.

    Args:
        search_term: Optional term to search in title and description
        limit: Maximum number of results to return (default: 100, max: 100)
        offset: Number of results to skip for pagination (default: 0)
        request: Optional Flask request object for authentication

    Returns:
        Tuple of (response_data, status_code, headers)
    """
    # If a request is provided, attempt to decode token for fuid; otherwise proceed as public.
    fuid = None
    if request is not None:
        try:
            auth_header = None
            if hasattr(request, 'headers') and isinstance(request.headers, dict):
                auth_header = request.headers.get('Authorization')
            elif hasattr(request, 'headers') and hasattr(request.headers, 'get'):
                auth_header = request.headers.get('Authorization')
            if auth_header:
                parts = auth_header.split()
                if len(parts) == 2 and parts[0].lower() == 'bearer':
                    decoded = verify_firebase_token(parts[1])
                    fuid = decoded.get('uid')
        except Exception:
            fuid = None

    # Validate pagination parameters
    limit = min(max(1, limit), 100)  # Ensure limit is between 1 and 100
    offset = max(0, offset)  # Ensure offset is not negative

    try:
        driver = get_neo4j_driver()

        # Build WHERE clause conditionally based on whether fuid is present
        if fuid:
            permission_clause = "(o.is_public = true OR EXISTS((:User {fuid: $fuid})-[:CREATED|CAN_EDIT|CAN_DELETE]->(o)))"
            permission_params = {'fuid': fuid}
        else:
            permission_clause = "o.is_public = true"
            permission_params = {}

        # Build combined data + count query
        if search_term:
            where_clause = f"WHERE {permission_clause} AND (toLower(o.name) CONTAINS toLower($search_term) OR toLower(o.description) CONTAINS toLower($search_term))"
            params = {
                **permission_params,
                'search_term': search_term,
                'offset': offset,
                'limit': limit
            }
        else:
            where_clause = f"WHERE {permission_clause}"
            params = {
                **permission_params,
                'offset': offset,
                'limit': limit
            }

        # Single combined query: count via subquery + paginated data
        query = f"""
            CALL () {{
                MATCH (o:Ontology)
                {where_clause}
                RETURN count(o) AS total
            }}
            WITH total
            MATCH (o:Ontology)
            {where_clause}
            OPTIONAL MATCH (o)-[:TAGGED]->(t:Tag)
            WITH o, collect(DISTINCT toLower(t.name)) AS tags, total
            ORDER BY o.created_at DESC
            SKIP $offset
            LIMIT $limit
            RETURN o, tags, total
            """

        async with driver.session() as session:
            result = await session.run(query, params)
            records = [(record['o'], record['tags'], record['total']) async for record in result]

        # Process results
        ontologies = []
        total_count = 0
        for node, tags, total in records:
            total_count = total  # Same value in every row
            try:
                ontology = Ontology(
                    uuid=node['uuid'],
                    name=node['name'],
                    source_url=node['source_url'],
                    image_url=node.get('image_url'),
                    description=node.get('description'),
                    node_count=node.get('node_count'),
                    score=node.get('score'),
                    relationship_count=node.get('relationship_count'),
                    is_public=node.get('is_public', False),
                    created_at=(
                        node.get('created_at').to_native()
                        if hasattr(node.get('created_at'), 'to_native')
                        else node.get('created_at')
                    )
                )
                data = ontology.model_dump()
                data['tags'] = tags or []
                ontologies.append(data)
            except Exception as e:
                logging.error(f"Error processing ontology record: {e}")
                continue

        response_data = {
            'success': True,
            'message': 'Ontologies retrieved successfully',
            'data': {
                'results': ontologies,
                'count': len(ontologies),
                'total': total_count,
                'offset': offset,
                'limit': limit
            }
        }

        return OntologyResponse(**response_data)

    except Exception as e:
        logging.error(f"Database error: {str(e)}")
        return OntologyResponse(
            success=False,
            message='Database error occurred',
            data=None
        )


# Entry point for Google Cloud Run
@http
def search_ontologies_by_request(request: Request):
    """
    HTTP Cloud Function for searching ontologies.
    Args:
        request (flask.Request): The request object.
        Can accept:
        - GET with query parameter 'search_term'
    Returns:
        JSON response with matching ontologies.
    """
    # Get query parameters
    search_term = request.args.get('search_term')
    limit = min(int(request.args.get('limit', 100)), 100)
    offset = max(int(request.args.get('offset', 0)), 0)

    # Pass the request object for authentication
    return search_ontologies(
        search_term=search_term,
        limit=limit,
        offset=offset,
        request=request
    )
