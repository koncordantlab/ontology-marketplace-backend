from functions.n4j import get_neo4j_driver
import uuid
from datetime import datetime, timezone


def create_flag(comment_id: str, reason: str, details: str, user_fuid: str) -> dict:
    """Flag a comment."""
    driver = get_neo4j_driver()
    with driver.session() as session:
        # Check for duplicate flag
        dup = session.run(
            "MATCH (u:User {fuid: $fuid})-[:FLAGGED_BY]-(f:Flag)-[:FLAGGED_CONTENT]-(c:Comment {uuid: $cid}) "
            "RETURN f.uuid AS uuid",
            fuid=user_fuid, cid=comment_id
        )
        if dup.single():
            return {"success": False, "error": "You have already flagged this comment", "status": 409}

        flag_uuid = str(uuid.uuid4())
        now = datetime.now(timezone.utc).isoformat()
        session.run(
            "MATCH (c:Comment {uuid: $cid}) "
            "MERGE (u:User {fuid: $fuid}) "
            "CREATE (f:Flag {uuid: $fuuid, reason: $reason, details: $details, "
            "  status: 'pending', created_at: datetime($now), reviewed_at: null}) "
            "CREATE (f)-[:FLAGGED_CONTENT]->(c) "
            "CREATE (f)-[:FLAGGED_BY]->(u) ",
            cid=comment_id, fuid=user_fuid, fuuid=flag_uuid,
            reason=reason, details=details, now=now
        )
        return {"success": True, "data": {"uuid": flag_uuid}, "status": 201}


def check_user_has_flagged(comment_id: str, user_fuid: str) -> dict:
    """Check if a user has already flagged a comment."""
    driver = get_neo4j_driver()
    with driver.session() as session:
        result = session.run(
            "MATCH (u:User {fuid: $fuid})-[:FLAGGED_BY]-(f:Flag)-[:FLAGGED_CONTENT]-(c:Comment {uuid: $cid}) "
            "RETURN f.uuid AS uuid",
            fuid=user_fuid, cid=comment_id
        )
        record = result.single()
        return {"success": True, "data": {"has_flagged": record is not None}}
