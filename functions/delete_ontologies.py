from functions_framework import http
from flask import Request
from typing import List
import logging
from .auth_utils import verify_firebase_token
from .model_ontology import OntologyResponse
from .n4j import get_neo4j_driver
from .cache import invalidate_search_cache

async def delete_ontologies(fuid: str, ontology_ids: List[str]) -> OntologyResponse:
    """
    Soft-delete ontologies by setting is_deleted = true.

    Args:
        fuid: Firebase UID of the user performing the deletion
        ontology_ids: List of ontology uuids to delete

    Returns:
        OntologyResponse with the result of the operation
    """
    if not ontology_ids:
        return OntologyResponse(
            success=False,
            message="No ontology IDs provided",
            data=None
        )

    try:
        driver = get_neo4j_driver()

        # Soft delete: set is_deleted = true instead of removing the node
        query = """
            UNWIND $ontology_ids AS ontology_id
            MATCH (o:Ontology {uuid: ontology_id})
            MATCH (u:User {fuid: $fuid})
            WHERE EXISTS((u)-[:CREATED|CAN_DELETE]->(o))
            SET o.is_deleted = true
            RETURN count(o) as deleted_count
        """

        async with driver.session() as session:
            result = await session.run(query, fuid=fuid, ontology_ids=ontology_ids)
            record = await result.single()
            deleted_count = record["deleted_count"] if record else 0

        if deleted_count == 0:
            return OntologyResponse(
                success=False,
                message="No ontologies found with the provided IDs for the given user",
                data={"deleted_count": 0}
            )

        # Invalidate search cache when ontologies are deleted
        invalidate_search_cache()

        return OntologyResponse(
            success=True,
            message=f"Successfully deleted {deleted_count} ontologies",
            data={"deleted_count": deleted_count}
        )

    except Exception as e:
        logging.error(f"Database error: {str(e)}")
        return OntologyResponse(
            success=False,
            message="Failed to delete ontologies",
            data=None
        )


async def purge_ontologies(fuid: str, ontology_ids: List[str]) -> OntologyResponse:
    """
    Permanently delete soft-deleted ontologies. Cascades to comments, replies,
    tags-relationships, and any reaction relationships/nodes attached to them.

    Only the creator of an ontology can purge it (CAN_DELETE alone is not
    sufficient — purge is destructive and irreversible).
    """
    if not ontology_ids:
        return OntologyResponse(
            success=False,
            message="No ontology IDs provided",
            data=None
        )

    try:
        driver = get_neo4j_driver()

        # Cascade: delete the ontology, its comments (and replies), and any
        # Reaction nodes attached to those comments. DETACH DELETE removes the
        # node and all attached relationships in one shot.
        query = """
            UNWIND $ontology_ids AS ontology_id
            MATCH (o:Ontology {uuid: ontology_id, is_deleted: true})
            MATCH (creator:User {fuid: $fuid})-[:CREATED]->(o)
            OPTIONAL MATCH (c:Comment)-[:COMMENTED_ON]->(o)
            OPTIONAL MATCH (reply:Comment)-[:REPLY_TO]->(c)
            OPTIONAL MATCH (c)<-[:HAS_REACTION]-(r:Reaction)
            OPTIONAL MATCH (reply)<-[:HAS_REACTION]-(rr:Reaction)
            DETACH DELETE r, rr, reply, c, o
            RETURN count(DISTINCT ontology_id) AS purged_count
        """

        async with driver.session() as session:
            result = await session.run(query, fuid=fuid, ontology_ids=ontology_ids)
            record = await result.single()
            purged_count = record["purged_count"] if record else 0

        if purged_count == 0:
            return OntologyResponse(
                success=False,
                message="No purgeable ontologies found (must be soft-deleted and owned by you)",
                data={"purged_count": 0}
            )

        invalidate_search_cache()

        return OntologyResponse(
            success=True,
            message=f"Permanently deleted {purged_count} ontologies",
            data={"purged_count": purged_count}
        )

    except Exception as e:
        logging.error(f"Database error during purge: {str(e)}")
        return OntologyResponse(
            success=False,
            message="Failed to purge ontologies",
            data=None
        )


async def restore_ontologies(fuid: str, ontology_ids: List[str]) -> OntologyResponse:
    """
    Restore soft-deleted ontologies by setting is_deleted = false.

    Args:
        fuid: Firebase UID of the user performing the restore
        ontology_ids: List of ontology uuids to restore

    Returns:
        OntologyResponse with the result of the operation
    """
    if not ontology_ids:
        return OntologyResponse(
            success=False,
            message="No ontology IDs provided",
            data=None
        )

    try:
        driver = get_neo4j_driver()

        query = """
            UNWIND $ontology_ids AS ontology_id
            MATCH (o:Ontology {uuid: ontology_id, is_deleted: true})
            MATCH (u:User {fuid: $fuid})
            WHERE EXISTS((u)-[:CREATED|CAN_DELETE]->(o))
            SET o.is_deleted = false
            RETURN count(o) as restored_count
        """

        async with driver.session() as session:
            result = await session.run(query, fuid=fuid, ontology_ids=ontology_ids)
            record = await result.single()
            restored_count = record["restored_count"] if record else 0

        if restored_count == 0:
            return OntologyResponse(
                success=False,
                message="No deleted ontologies found with the provided IDs for the given user",
                data={"restored_count": 0}
            )

        # Invalidate search cache when ontologies are restored
        invalidate_search_cache()

        return OntologyResponse(
            success=True,
            message=f"Successfully restored {restored_count} ontologies",
            data={"restored_count": restored_count}
        )

    except Exception as e:
        logging.error(f"Database error: {str(e)}")
        return OntologyResponse(
            success=False,
            message="Failed to restore ontologies",
            data=None
        )

@http
def delete_ontologies_by_request(request: Request):
    """
    HTTP Cloud Function for deleting ontologies.
    
    Args:
        request (flask.Request): The request object.
        Should contain a JSON array of ontology IDs to delete.
        
    Returns:
        JSON response with the result of the operation.
    """
    # Set CORS headers for the preflight request
    if request.method == 'OPTIONS':
        headers = {
            'Access-Control-Allow-Origin': '*',
            'Access-Control-Allow-Methods': 'DELETE, OPTIONS',
            'Access-Control-Allow-Headers': 'Content-Type',
            'Access-Control-Max-Age': '3600'
        }
        return ('', 204, headers)

    # Set CORS headers for the main request
    headers = {
        'Access-Control-Allow-Origin': '*',
        'Content-Type': 'application/json'
    }

    try:
        # Get JSON data from request
        request_json = request.get_json(silent=True)
        if not request_json:
            return OntologyResponse(
                success=False,
                message="No JSON data provided",
                data=None
            )
        
        # Extract ontology_ids from request
        if not isinstance(request_json, list):
            return OntologyResponse(
                success=False,
                message="Expected an array of ontology IDs",
                data=None
            )

        # Decode Firebase token to get fuid
        auth_header = request.headers.get('Authorization')
        if not auth_header or len(auth_header.split()) != 2 or auth_header.split()[0].lower() != 'bearer':
            return OntologyResponse(
                success=False,
                message="Missing or invalid Authorization header",
                data=None
            )
        decoded = verify_firebase_token(auth_header.split()[1])
        fuid = decoded.get('uid')
        if not fuid:
            return OntologyResponse(
                success=False,
                message="Invalid token: no uid",
                data=None
            )

        return delete_ontologies(fuid, request_json)

    except Exception as e:
        logging.error(f"Unexpected error: {str(e)}")
        return OntologyResponse(
            success=False,
            message="An unexpected error occurred",
            data=None
        )