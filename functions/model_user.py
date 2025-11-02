from pydantic import BaseModel
from datetime import datetime, timezone
from pydantic import Field
from typing import List, Optional
from .n4j import get_neo4j_driver


def get_user_uuid_by_fuid(fuid: str) -> Optional[str]:
    """
    Get the user's UUID from Neo4j by their Firebase UID (fuid).
    
    Args:
        fuid: Firebase User ID
        
    Returns:
        User's UUID if found, None otherwise
    """
    if not fuid:
        return None
    
    from .n4j import get_neo4j_driver
    
    query = """
        MATCH (u:User {fuid: $fuid})
        RETURN u.uuid as uuid
    """
    
    try:
        with get_neo4j_driver() as driver:
            result = driver.execute_query(
                query,
                fuid=fuid,
                database_="neo4j",
                result_transformer_=lambda r: (r.single() or {}).get('uuid')
            )
            return result
    except Exception as e:
        print(f"Error querying user UUID by fuid: {str(e)}")
        return None



def get_edit_ontologies_by_uuid(uuid: str) -> List[str]:
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
        with get_neo4j_driver() as driver:
            result = driver.execute_query(
                query,
                uuid=uuid,
                database_="neo4j",
                result_transformer_=lambda r: [record['uuid'] for record in r]
            )
            return result
    except Exception as e:
        print(f"Error querying edit ontology UUIDs: {str(e)}")
        return []


def get_delete_ontologies_by_uuid(uuid: str) -> List[str]:
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
        with get_neo4j_driver() as driver:
            result = driver.execute_query(
                query,
                uuid=uuid,
                database_="neo4j",
                result_transformer_=lambda r: [record['uuid'] for record in r]
            )
            return result
    except Exception as e:
        print(f"Error querying delete ontology UUIDs: {str(e)}")
        return []


def get_user_profile_by_fuid(fuid: str) -> dict:
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
        with get_neo4j_driver() as driver:
            # Fetch user uuid and is_public
            user_info = driver.execute_query(
                """
                MATCH (u:User {fuid: $fuid})
                RETURN u.uuid as uuid, coalesce(u.is_public, false) as is_public
                """,
                fuid=fuid,
                database_="neo4j",
                result_transformer_=lambda r: (r.single() or {})
            )

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

        can_edit = get_edit_ontologies_by_uuid(user_uuid)
        can_delete = get_delete_ontologies_by_uuid(user_uuid)

        return {
            "is_public": bool(is_public),
            "permissions": {
                "can_edit_ontologies": can_edit,
                "can_delete_ontologies": can_delete
            }
        }
    except Exception as e:
        print(f"Error building user profile: {str(e)}")
        return {
            "is_public": False,
            "permissions": {
                "can_edit_ontologies": [],
                "can_delete_ontologies": []
            }
        }


def update_user_is_public_by_fuid(fuid: str, is_public: bool) -> bool:
    """
    Upsert the User node by fuid and set is_public flag.
    Returns True if succeeded.
    """
    if not fuid:
        return False

    try:
        with get_neo4j_driver() as driver:
            driver.execute_query(
                """
                MERGE (u:User {fuid: $fuid})
                ON CREATE SET u.created_at = datetime(), u.uuid = randomUUID()
                SET u.is_public = $is_public
                RETURN u
                """,
                fuid=fuid,
                is_public=bool(is_public),
                database_="neo4j",
            )
        return True
    except Exception as e:
        print(f"Error updating user is_public: {str(e)}")
        return False