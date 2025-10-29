from pydantic import BaseModel
from datetime import datetime, timezone
from pydantic import Field
from typing import List, Optional
from .n4j import get_neo4j_driver

# class User(BaseModel):
#     name: str | None = None
#     email: str | None = None
#     email_verified: bool
#     fuid : str
#     uuid: str = Field(default_factory=lambda: str(uuid.uuid4()))
#     image_url: str | None = None
#     is_public: bool = False
#     is_admin: bool = False
#     created_at: datetime
#     updated_at: datetime

#     def get_edit_ontology_uuids(self) -> List[str]:
#         """
#         Returns a list of ontology UUIDs that the user can edit.
#         Authorization is determined by checking Neo4j for Ontology nodes 
#         connected via :CREATED and/or :CAN_EDIT relationships.
        
#         Returns:
#             List[str]: List of ontology UUIDs the user can edit
#         """
#         if not self.email:
#             return []
        
#         from .n4j import get_neo4j_driver
        
#         query = """
#             MATCH (u:User {uuid: $uuid})
#             MATCH (u)-[:CREATED|CAN_EDIT]->(o:Ontology)
#             RETURN DISTINCT o.uuid as uuid
#         """
        
#         try:
#             with get_neo4j_driver() as driver:
#                 result = driver.execute_query(
#                     query,
#                     uuid=self.uuid,
#                     database_="neo4j",
#                     result_transformer_=lambda r: [record['uuid'] for record in r]
#                 )
#                 return result
#         except Exception as e:
#             print(f"Error querying edit ontology UUIDs: {str(e)}")
#             return []


#     def can_edit_ontology(self, ontology_id: str, email: str) -> bool:
#         """
#         Check if the user can edit the ontology
#         """
#         return ontology_id in self.get_edit_ontology_uuids()

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


def can_user_edit_ontology(uuid: str, ontology_id: str) -> dict:
    """
    Check if the user can edit the ontology by their UUID.
    
    Args:
        uuid: User UUID
        ontology_id: Ontology UUID to check
        
    Returns:
        Dictionary with success status and message
    """
    if not uuid:
        return {
            "success": False,
            "message": "User authentication required",
            "data": None
        }
    
    try:
        edit_uuids = get_edit_ontologies_by_uuid(uuid)
        can_edit = ontology_id in edit_uuids
        
        return {
            "success": True,
            "message": "Authorization check complete",
            "data": {
                "ontology_id": ontology_id,
                "can_edit": can_edit
            }
        }
    except Exception as e:
        print(f"Error checking edit permission: {str(e)}")
        return {
            "success": False,
            "message": f"Failed authorization check: {str(e)}",
            "data": None
        }


def can_user_delete_ontology(uuid: str, ontology_id: str) -> dict:
    """
    Check if the user can delete the ontology by their UUID.
    
    Args:
        uuid: User UUID
        ontology_id: Ontology UUID to check
        
    Returns:
        Dictionary with success status and message
    """
    if not uuid:
        return {
            "success": False,
            "message": "User authentication required",
            "data": None
        }
    
    try:
        delete_uuids = get_delete_ontologies_by_uuid(uuid)
        can_delete = ontology_id in delete_uuids
        
        return {
            "success": True,
            "message": "Authorization check complete",
            "data": {
                "ontology_id": ontology_id,
                "can_delete": can_delete
            }
        }
    except Exception as e:
        print(f"Error checking delete permission: {str(e)}")
        return {
            "success": False,
            "message": f"Failed authorization check: {str(e)}",
            "data": None
        }


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