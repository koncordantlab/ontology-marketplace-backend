from functions.n4j import get_neo4j_driver
from functions.model_comment import NewComment, Comment, NewReply
from functions.cache import invalidate_comments_cache
from datetime import datetime, timezone, timedelta
from typing import Optional
import uuid


RATE_LIMIT_WINDOW = 60  # seconds
RATE_LIMIT_MAX = 6
EDIT_WINDOW_MINUTES = 15


async def create_comment(ontology_id: str, content: str, user_fuid: str, user_email: str) -> dict:
    """Create a comment on an ontology."""
    driver = get_neo4j_driver()
    async with driver.session() as session:
        # Check ontology is accessible
        result = await session.run(
            "MATCH (o:Ontology {uuid: $oid}) "
            "OPTIONAL MATCH (u:User {fuid: $fuid}) "
            "WHERE o.is_public = true OR EXISTS((u)-[:CREATED|CAN_EDIT]->(o)) "
            "RETURN o.uuid AS oid, u.uuid AS user_uuid",
            oid=ontology_id, fuid=user_fuid
        )
        record = await result.single()
        if not record or not record["oid"]:
            return {"success": False, "error": "Ontology not found or not accessible", "status": 404}

        # Rate limit check
        rate_result = await session.run(
            "MATCH (u:User {fuid: $fuid})-[:AUTHORED]->(c:Comment) "
            "WHERE c.created_at > datetime() - duration({seconds: $window}) "
            "RETURN count(c) AS recent_count",
            fuid=user_fuid, window=RATE_LIMIT_WINDOW
        )
        rate_record = await rate_result.single()
        if rate_record and rate_record["recent_count"] >= RATE_LIMIT_MAX:
            return {"success": False, "error": "Rate limit exceeded. Max 6 comments per minute.", "status": 429}

        # Create the comment
        comment_uuid = str(uuid.uuid4())
        now = datetime.now(timezone.utc).isoformat()
        await session.run(
            "MATCH (o:Ontology {uuid: $oid}) "
            "MERGE (u:User {fuid: $fuid}) "
            "  ON CREATE SET u.created_at = datetime(), u.uuid = randomUUID(), u.email = $email "
            "  ON MATCH SET u.email = COALESCE(u.email, $email) "
            "CREATE (c:Comment {uuid: $cuuid, content: $content, is_deleted: false, "
            "  created_at: datetime($now), updated_at: null}) "
            "CREATE (u)-[:AUTHORED]->(c) "
            "CREATE (c)-[:COMMENTED_ON]->(o) "
            "RETURN c.uuid AS uuid",
            oid=ontology_id, fuid=user_fuid, email=user_email,
            cuuid=comment_uuid, content=content, now=now
        )
        invalidate_comments_cache(ontology_id)
        return {"success": True, "data": {"uuid": comment_uuid}, "status": 201}


async def get_comments(ontology_id: str, limit: int = 20, offset: int = 0, current_user_fuid: str = None) -> dict:
    """Get comments for an ontology with pagination."""
    driver = get_neo4j_driver()
    async with driver.session() as session:
        result = await session.run(
            "MATCH (c:Comment)-[:COMMENTED_ON]->(o:Ontology {uuid: $oid}) "
            "WHERE NOT EXISTS((c)-[:REPLY_TO]->()) "
            "MATCH (author:User)-[:AUTHORED]->(c) "
            "OPTIONAL MATCH (reply:Comment)-[:REPLY_TO]->(c) WHERE reply.is_deleted = false "
            "OPTIONAL MATCH (c)<-[:HAS_REACTION]-(r:Reaction) "
            "WITH c, author, count(DISTINCT reply) AS reply_count, "
            "  collect(DISTINCT r.emoji) AS reaction_emojis, "
            "  count(DISTINCT r) AS reaction_total "
            "ORDER BY c.created_at DESC "
            "SKIP $offset LIMIT $limit "
            "RETURN c.uuid AS uuid, c.content AS content, c.is_deleted AS is_deleted, "
            "  c.created_at AS created_at, c.updated_at AS updated_at, "
            "  author.email AS author_email, author.name AS author_name, author.fuid AS author_fuid, "
            "  reply_count, reaction_emojis, reaction_total",
            oid=ontology_id, limit=limit, offset=offset
        )
        comments = []
        async for record in result:
            is_editable = False
            if current_user_fuid and record["author_fuid"] == current_user_fuid:
                created = record["created_at"]
                if hasattr(created, 'to_native'):
                    created = created.to_native()
                if isinstance(created, datetime):
                    diff = datetime.now(timezone.utc) - created.replace(tzinfo=timezone.utc) if created.tzinfo is None else datetime.now(timezone.utc) - created
                    is_editable = diff < timedelta(minutes=EDIT_WINDOW_MINUTES)

            comments.append({
                "uuid": record["uuid"],
                "content": "[deleted]" if record["is_deleted"] else record["content"],
                "is_deleted": record["is_deleted"],
                "created_at": str(record["created_at"]),
                "updated_at": str(record["updated_at"]) if record["updated_at"] else None,
                "author_email": record["author_email"],
                "author_name": record["author_name"],
                "reply_count": record["reply_count"],
                "is_editable": is_editable,
            })

        # Get total count
        count_result = await session.run(
            "MATCH (c:Comment)-[:COMMENTED_ON]->(o:Ontology {uuid: $oid}) "
            "WHERE NOT EXISTS((c)-[:REPLY_TO]->()) "
            "RETURN count(c) AS total",
            oid=ontology_id
        )
        count_record = await count_result.single()
        total = count_record["total"]

        return {"success": True, "data": {"comments": comments, "total": total}}


async def edit_comment(comment_id: str, content: str, user_fuid: str) -> dict:
    """Edit a comment within the 15-minute window."""
    driver = get_neo4j_driver()
    async with driver.session() as session:
        result = await session.run(
            "MATCH (u:User {fuid: $fuid})-[:AUTHORED]->(c:Comment {uuid: $cid}) "
            "WHERE c.is_deleted = false "
            "RETURN c.created_at AS created_at",
            fuid=user_fuid, cid=comment_id
        )
        record = await result.single()
        if not record:
            return {"success": False, "error": "Comment not found or not authorized", "status": 403}

        created = record["created_at"]
        if hasattr(created, 'to_native'):
            created = created.to_native()
        if isinstance(created, datetime):
            if created.tzinfo is None:
                created = created.replace(tzinfo=timezone.utc)
            diff = datetime.now(timezone.utc) - created
            if diff >= timedelta(minutes=EDIT_WINDOW_MINUTES):
                return {"success": False, "error": "Edit window has expired (15 minutes)", "status": 403}

        now = datetime.now(timezone.utc).isoformat()
        await session.run(
            "MATCH (c:Comment {uuid: $cid}) "
            "SET c.content = $content, c.updated_at = datetime($now)",
            cid=comment_id, content=content, now=now
        )
        invalidate_comments_cache()  # Don't know ontology_id here, clear all
        return {"success": True, "data": {"uuid": comment_id}}


async def delete_comment(comment_id: str, user_fuid: str) -> dict:
    """Delete a comment. Hard-delete if no replies/reactions, soft-delete otherwise."""
    driver = get_neo4j_driver()
    async with driver.session() as session:
        # Check authorization: author or ontology owner
        auth_result = await session.run(
            "MATCH (c:Comment {uuid: $cid}) "
            "OPTIONAL MATCH (author:User {fuid: $fuid})-[:AUTHORED]->(c) "
            "OPTIONAL MATCH (c)-[:COMMENTED_ON]->(o:Ontology)<-[:CREATED]-(owner:User {fuid: $fuid}) "
            "RETURN author IS NOT NULL OR owner IS NOT NULL AS authorized",
            cid=comment_id, fuid=user_fuid
        )
        auth_record = await auth_result.single()
        if not auth_record or not auth_record["authorized"]:
            return {"success": False, "error": "Not authorized to delete this comment", "status": 403}

        # Check if comment has replies or reactions
        dep_result = await session.run(
            "MATCH (c:Comment {uuid: $cid}) "
            "OPTIONAL MATCH (reply:Comment)-[:REPLY_TO]->(c) "
            "OPTIONAL MATCH (c)<-[:HAS_REACTION]-(r:Reaction) "
            "RETURN count(reply) + count(r) AS dep_count",
            cid=comment_id
        )
        dep_record = await dep_result.single()
        dep_count = dep_record["dep_count"]

        if dep_count > 0:
            # Soft delete
            await session.run(
                "MATCH (c:Comment {uuid: $cid}) SET c.is_deleted = true, c.content = '[deleted]'",
                cid=comment_id
            )
        else:
            # Hard delete
            await session.run(
                "MATCH (c:Comment {uuid: $cid}) DETACH DELETE c",
                cid=comment_id
            )
        invalidate_comments_cache()  # Don't know ontology_id here, clear all
        return {"success": True, "data": {"uuid": comment_id, "hard_deleted": dep_count == 0}}


async def create_reply(parent_comment_id: str, content: str, user_fuid: str, user_email: str) -> dict:
    """Create a reply to a comment. Replies are flattened (no nested replies)."""
    driver = get_neo4j_driver()
    async with driver.session() as session:
        # Find the root comment (flatten nested replies)
        result = await session.run(
            "MATCH (parent:Comment {uuid: $pid}) "
            "OPTIONAL MATCH (parent)-[:REPLY_TO]->(root:Comment) "
            "RETURN COALESCE(root.uuid, parent.uuid) AS root_uuid, parent.uuid AS parent_uuid",
            pid=parent_comment_id
        )
        record = await result.single()
        if not record:
            return {"success": False, "error": "Parent comment not found", "status": 404}

        root_uuid = record["root_uuid"]

        reply_uuid = str(uuid.uuid4())
        now = datetime.now(timezone.utc).isoformat()
        await session.run(
            "MATCH (root:Comment {uuid: $root_uuid}) "
            "MERGE (u:User {fuid: $fuid}) "
            "  ON CREATE SET u.created_at = datetime(), u.uuid = randomUUID(), u.email = $email "
            "  ON MATCH SET u.email = COALESCE(u.email, $email) "
            "CREATE (reply:Comment {uuid: $ruuid, content: $content, is_deleted: false, "
            "  created_at: datetime($now), updated_at: null}) "
            "CREATE (u)-[:AUTHORED]->(reply) "
            "CREATE (reply)-[:REPLY_TO]->(root) "
            "RETURN reply.uuid AS uuid",
            root_uuid=root_uuid, fuid=user_fuid, email=user_email,
            ruuid=reply_uuid, content=content, now=now
        )
        invalidate_comments_cache()  # Reply affects parent comment's count
        return {"success": True, "data": {"uuid": reply_uuid}, "status": 201}


async def get_replies(comment_id: str, limit: int = 20, offset: int = 0) -> dict:
    """Get replies to a comment."""
    driver = get_neo4j_driver()
    async with driver.session() as session:
        result = await session.run(
            "MATCH (reply:Comment)-[:REPLY_TO]->(c:Comment {uuid: $cid}) "
            "MATCH (author:User)-[:AUTHORED]->(reply) "
            "ORDER BY reply.created_at ASC "
            "SKIP $offset LIMIT $limit "
            "RETURN reply.uuid AS uuid, reply.content AS content, "
            "  reply.is_deleted AS is_deleted, reply.created_at AS created_at, "
            "  author.email AS author_email, author.name AS author_name",
            cid=comment_id, limit=limit, offset=offset
        )
        replies = []
        async for record in result:
            replies.append({
                "uuid": record["uuid"],
                "content": "[deleted]" if record["is_deleted"] else record["content"],
                "is_deleted": record["is_deleted"],
                "created_at": str(record["created_at"]),
                "author_email": record["author_email"],
                "author_name": record["author_name"],
            })
        return {"success": True, "data": {"replies": replies}}
