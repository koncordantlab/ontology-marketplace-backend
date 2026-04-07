from pydantic import BaseModel
from datetime import datetime, timezone
from pydantic import Field
from typing import List, Optional
import logging
from .n4j import get_neo4j_driver


async def get_user_uuid_by_fuid(fuid: str) -> Optional[str]:
    """
    Get the user's UUID from Neo4j by their Firebase UID (fuid).

    Args:
        fuid: Firebase User ID

    Returns:
        User's UUID if found, None otherwise
    """
    if not fuid:
        return None

    query = """
        MATCH (u:User {fuid: $fuid})
        RETURN u.uuid as uuid
    """

    try:
        async with get_neo4j_driver().session(database="neo4j") as session:
            result = await session.run(query, fuid=fuid)
            record = await result.single()
            return record.get('uuid') if record else None
    except Exception as e:
        logging.error(f"Error querying user UUID by fuid: {str(e)}")
        return None



async def get_edit_ontologies_by_uuid(uuid: str) -> List[str]:
    """
    Returns a list of ontology UUIDs that the user can edit by their UUID.
    Authorization is determined by checking Neo4j for Ontology nodes
    connected via :CREATED and/or :CAN_EDIT relationships.

    Args:
        uuid: User UUID

    Returns:
        List[str]: List of ontology UUIDs the user can edit
    """
    if not uuid:
        return []

    query = """
        MATCH (u:User {uuid: $uuid})
        MATCH (u)-[:CREATED|CAN_EDIT]->(o:Ontology)
        RETURN DISTINCT o.uuid as uuid
    """

    try:
        async with get_neo4j_driver().session(database="neo4j") as session:
            result = await session.run(query, uuid=uuid)
            records = [record async for record in result]
            return [record['uuid'] for record in records]
    except Exception as e:
        logging.error(f"Error querying edit ontology UUIDs: {str(e)}")
        return []


async def get_delete_ontologies_by_uuid(uuid: str) -> List[str]:
    """
    Returns a list of ontology UUIDs that the user can delete by their UUID.
    Authorization is determined by checking Neo4j for Ontology nodes
    connected via :CREATED and/or :CAN_DELETE relationships.

    Args:
        uuid: User UUID

    Returns:
        List[str]: List of ontology UUIDs the user can delete
    """
    if not uuid:
        return []

    query = """
        MATCH (u:User {uuid: $uuid})
        MATCH (u)-[:CREATED|CAN_DELETE]->(o:Ontology)
        RETURN DISTINCT o.uuid as uuid
    """

    try:
        async with get_neo4j_driver().session(database="neo4j") as session:
            result = await session.run(query, uuid=uuid)
            records = [record async for record in result]
            return [record['uuid'] for record in records]
    except Exception as e:
        logging.error(f"Error querying delete ontology UUIDs: {str(e)}")
        return []


async def get_user_profile_by_fuid(fuid: str) -> dict:
    """
    Return user's public flag and ontology permissions using Firebase UID.

    Response format:
    {
        "is_public": bool,
        "permissions": {
            "can_edit_ontologies": [uuid...],
            "can_delete_ontologies": [uuid...]
        }
    }
    """
    if not fuid:
        return {
            "is_public": False,
            "permissions": {
                "can_edit_ontologies": [],
                "can_delete_ontologies": []
            }
        }

    try:
        async with get_neo4j_driver().session(database="neo4j") as session:
            # Fetch user uuid and is_public
            result = await session.run(
                """
                MATCH (u:User {fuid: $fuid})
                RETURN u.uuid as uuid, coalesce(u.is_public, false) as is_public
                """,
                fuid=fuid
            )
            user_info = await result.single()

        user_uuid = user_info.get("uuid") if user_info else None
        is_public = user_info.get("is_public") if user_info else False

        if not user_uuid:
            # If the user does not exist, return empty permissions with default is_public False
            return {
                "is_public": bool(is_public),
                "permissions": {
                    "can_edit_ontologies": [],
                    "can_delete_ontologies": []
                }
            }

        can_edit = await get_edit_ontologies_by_uuid(user_uuid)
        can_delete = await get_delete_ontologies_by_uuid(user_uuid)

        return {
            "is_public": bool(is_public),
            "permissions": {
                "can_edit_ontologies": can_edit,
                "can_delete_ontologies": can_delete
            }
        }
    except Exception as e:
        logging.error(f"Error building user profile: {str(e)}")
        return {
            "is_public": False,
            "permissions": {
                "can_edit_ontologies": [],
                "can_delete_ontologies": []
            }
        }


async def sync_user_info(fuid: str, email: str = None, name: str = None):
    """
    Sync user name and email from Firebase token to Neo4j.
    Only fills in missing values, never overwrites existing ones.
    """
    if not fuid:
        return
    try:
        async with get_neo4j_driver().session(database="neo4j") as session:
            await session.run(
                """
                MERGE (u:User {fuid: $fuid})
                ON CREATE SET u.created_at = datetime(), u.uuid = randomUUID(),
                    u.email = $email, u.name = $name
                ON MATCH SET u.email = COALESCE(u.email, $email),
                    u.name = COALESCE(u.name, $name)
                """,
                fuid=fuid, email=email, name=name,
            )
    except Exception as e:
        logging.error(f"Error syncing user info: {str(e)}")


async def update_user_is_public_by_fuid(fuid: str, is_public: bool) -> bool:
    """
    Upsert the User node by fuid and set is_public flag.
    Returns True if succeeded.
    """
    if not fuid:
        return False

    try:
        async with get_neo4j_driver().session(database="neo4j") as session:
            await session.run(
                """
                MERGE (u:User {fuid: $fuid})
                ON CREATE SET u.created_at = datetime(), u.uuid = randomUUID()
                SET u.is_public = $is_public
                RETURN u
                """,
                fuid=fuid,
                is_public=bool(is_public),
            )
        return True
    except Exception as e:
        logging.error(f"Error updating user is_public: {str(e)}")
        return False
