from functions.n4j import get_neo4j_driver
from functions.model_comment import VALID_EMOJIS
from functions.cache import invalidate_comments_cache
import uuid


async def toggle_reaction(comment_id: str, emoji: str, user_fuid: str) -> dict:
    """Toggle a reaction on a comment. If exists, remove it. If not, add it."""
    if emoji not in VALID_EMOJIS:
        return {"success": False, "error": f"Invalid emoji. Must be one of: {', '.join(VALID_EMOJIS)}", "status": 400}

    driver = get_neo4j_driver()
    async with driver.session() as session:
        existing = await session.run(
            "MATCH (u:User {fuid: $fuid})-[:REACTION_BY]-(r:Reaction {emoji: $emoji})-[:HAS_REACTION]-(c:Comment {uuid: $cid}) "
            "RETURN r.uuid AS uuid",
            fuid=user_fuid, emoji=emoji, cid=comment_id
        )
        record = await existing.single()

        if record:
            await session.run(
                "MATCH (u:User {fuid: $fuid})-[:REACTION_BY]-(r:Reaction {emoji: $emoji})-[:HAS_REACTION]-(c:Comment {uuid: $cid}) "
                "DETACH DELETE r",
                fuid=user_fuid, emoji=emoji, cid=comment_id
            )
            invalidate_comments_cache()
            return {"success": True, "data": {"action": "removed", "emoji": emoji}}
        else:
            reaction_uuid = str(uuid.uuid4())
            await session.run(
                "MATCH (c:Comment {uuid: $cid}) "
                "MERGE (u:User {fuid: $fuid}) "
                "CREATE (r:Reaction {uuid: $ruuid, emoji: $emoji, created_at: datetime()}) "
                "CREATE (c)<-[:HAS_REACTION]-(r) "
                "CREATE (r)-[:REACTION_BY]->(u) ",
                cid=comment_id, fuid=user_fuid, ruuid=reaction_uuid, emoji=emoji
            )
            invalidate_comments_cache()
            return {"success": True, "data": {"action": "added", "emoji": emoji, "uuid": reaction_uuid}, "status": 201}


async def remove_reaction(comment_id: str, emoji: str, user_fuid: str) -> dict:
    """Remove a user's own reaction."""
    driver = get_neo4j_driver()
    async with driver.session() as session:
        result = await session.run(
            "MATCH (u:User {fuid: $fuid})-[:REACTION_BY]-(r:Reaction {emoji: $emoji})-[:HAS_REACTION]-(c:Comment {uuid: $cid}) "
            "RETURN r.uuid AS uuid",
            fuid=user_fuid, emoji=emoji, cid=comment_id
        )
        if not await result.single():
            return {"success": False, "error": "Reaction not found", "status": 404}

        await session.run(
            "MATCH (u:User {fuid: $fuid})-[:REACTION_BY]-(r:Reaction {emoji: $emoji})-[:HAS_REACTION]-(c:Comment {uuid: $cid}) "
            "DETACH DELETE r",
            fuid=user_fuid, emoji=emoji, cid=comment_id
        )
        invalidate_comments_cache()
        return {"success": True, "data": {"emoji": emoji, "removed": True}}


async def remove_reaction_by_owner(comment_id: str, reaction_id: str, user_fuid: str) -> dict:
    """Remove a reaction by the ontology owner (moderation)."""
    driver = get_neo4j_driver()
    async with driver.session() as session:
        auth = await session.run(
            "MATCH (r:Reaction {uuid: $rid})-[:HAS_REACTION]-(c:Comment {uuid: $cid})-[:COMMENTED_ON]->(o:Ontology)<-[:CREATED]-(u:User {fuid: $fuid}) "
            "RETURN r.uuid AS uuid",
            rid=reaction_id, cid=comment_id, fuid=user_fuid
        )
        if not await auth.single():
            return {"success": False, "error": "Not authorized", "status": 403}

        await session.run(
            "MATCH (r:Reaction {uuid: $rid}) DETACH DELETE r",
            rid=reaction_id
        )
        invalidate_comments_cache()
        return {"success": True, "data": {"reaction_id": reaction_id, "removed": True}}


async def get_reaction_counts(comment_id: str, user_fuid: str = None) -> dict:
    """Get reaction counts for a comment, including whether the current user reacted."""
    driver = get_neo4j_driver()
    async with driver.session() as session:
        result = await session.run(
            "MATCH (r:Reaction)-[:HAS_REACTION]-(c:Comment {uuid: $cid}) "
            "OPTIONAL MATCH (r)-[:REACTION_BY]->(u:User) "
            "RETURN r.emoji AS emoji, count(r) AS count, collect(u.fuid) AS user_fuids",
            cid=comment_id
        )
        reactions = {}
        async for record in result:
            emoji = record["emoji"]
            reactions[emoji] = {
                "count": record["count"],
                "user_reacted": user_fuid in record["user_fuids"] if user_fuid else False,
            }
        return {"success": True, "data": reactions}
