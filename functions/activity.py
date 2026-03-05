from functions.n4j import get_neo4j_driver
from datetime import datetime, timezone


def get_activity_feed(user_fuid: str, limit: int = 20, offset: int = 0,
                      type_filter: str = None, search: str = None) -> dict:
    """Get unified activity feed for a user (comments, replies, reactions, messages)."""
    driver = get_neo4j_driver()
    with driver.session() as session:
        # Build UNION query for all activity types
        where_clauses = []
        params = {"fuid": user_fuid, "limit": limit, "offset": offset}

        search_filter = ""
        if search:
            search_filter = "AND (toLower(item.content) CONTAINS toLower($search) OR toLower(item.subject) CONTAINS toLower($search))"
            params["search"] = search

        queries = []

        if not type_filter or type_filter == "comment":
            queries.append(
                f"MATCH (u:User {{fuid: $fuid}})-[:AUTHORED]->(c:Comment)-[:COMMENTED_ON]->(o:Ontology) "
                f"WHERE NOT EXISTS((c)-[:REPLY_TO]->()) "
                f"WITH c AS item, 'comment' AS type, o.name AS ontology_name, o.uuid AS ontology_id, "
                f"  c.content AS content, null AS subject "
                f"WHERE true {search_filter.replace('item.subject', 'subject').replace('item.content', 'content') if search else ''} "
                f"RETURN item.uuid AS id, type, item.created_at AS created_at, "
                f"  content, subject, ontology_name, ontology_id, "
                f"  COALESCE(item.is_read, false) AS is_read"
            )

        if not type_filter or type_filter == "reply":
            queries.append(
                f"MATCH (reply:Comment)-[:REPLY_TO]->(c:Comment)<-[:AUTHORED]-(u:User {{fuid: $fuid}}) "
                f"MATCH (replier:User)-[:AUTHORED]->(reply) "
                f"MATCH (c)-[:COMMENTED_ON]->(o:Ontology) "
                f"WITH reply AS item, 'reply' AS type, o.name AS ontology_name, o.uuid AS ontology_id, "
                f"  reply.content AS content, null AS subject, replier.email AS actor_email "
                f"RETURN item.uuid AS id, type, item.created_at AS created_at, "
                f"  content, subject, ontology_name, ontology_id, "
                f"  COALESCE(item.is_read, false) AS is_read"
            )

        if not type_filter or type_filter == "message":
            queries.append(
                f"MATCH (m:Message)-[:RECEIVED_MESSAGE]->(u:User {{fuid: $fuid}}) "
                f"WHERE NOT EXISTS((m)-[:REPLY_TO_MESSAGE]->()) "
                f"OPTIONAL MATCH (sender:User)-[:SENT_MESSAGE]->(m) "
                f"WITH m AS item, 'message' AS type, null AS ontology_name, null AS ontology_id, "
                f"  m.content AS content, m.subject AS subject "
                f"RETURN item.uuid AS id, type, item.created_at AS created_at, "
                f"  content, subject, ontology_name, ontology_id, "
                f"  COALESCE(item.is_read, false) AS is_read"
            )

        if not queries:
            return {"success": True, "data": {"items": [], "total": 0}}

        union_query = " UNION ALL ".join(queries)
        full_query = (
            f"CALL {{ {union_query} }} "
            f"WITH id, type, created_at, content, subject, ontology_name, ontology_id, is_read "
            f"ORDER BY created_at DESC "
            f"SKIP $offset LIMIT $limit "
            f"RETURN id, type, created_at, content, subject, ontology_name, ontology_id, is_read"
        )

        result = session.run(full_query, **params)
        items = []
        for record in result:
            items.append({
                "id": record["id"],
                "type": record["type"],
                "created_at": str(record["created_at"]),
                "content": record["content"],
                "subject": record["subject"],
                "ontology_name": record["ontology_name"],
                "ontology_id": record["ontology_id"],
                "is_read": record["is_read"],
            })

        return {"success": True, "data": {"items": items}}


def get_unread_count(user_fuid: str) -> dict:
    """Get count of unread activity items."""
    driver = get_neo4j_driver()
    with driver.session() as session:
        # Count unread messages
        result = session.run(
            "MATCH (m:Message)-[:RECEIVED_MESSAGE]->(u:User {fuid: $fuid}) "
            "WHERE m.is_read = false "
            "RETURN count(m) AS count",
            fuid=user_fuid
        )
        count = result.single()["count"]
        return {"success": True, "data": {"count": count}}


def mark_read(item_id: str, user_fuid: str) -> dict:
    """Mark an activity item as read."""
    driver = get_neo4j_driver()
    with driver.session() as session:
        # Try marking as message
        result = session.run(
            "MATCH (m:Message {uuid: $id})-[:RECEIVED_MESSAGE]->(u:User {fuid: $fuid}) "
            "SET m.is_read = true "
            "RETURN m.uuid AS uuid",
            id=item_id, fuid=user_fuid
        )
        if result.single():
            return {"success": True, "data": {"id": item_id, "is_read": True}}

        # Try marking as comment
        result = session.run(
            "MATCH (c:Comment {uuid: $id}) "
            "SET c.is_read = true "
            "RETURN c.uuid AS uuid",
            id=item_id
        )
        if result.single():
            return {"success": True, "data": {"id": item_id, "is_read": True}}

        return {"success": False, "error": "Item not found", "status": 404}


def mark_all_read(user_fuid: str) -> dict:
    """Mark all activity items as read for a user."""
    driver = get_neo4j_driver()
    with driver.session() as session:
        session.run(
            "MATCH (m:Message)-[:RECEIVED_MESSAGE]->(u:User {fuid: $fuid}) "
            "WHERE m.is_read = false "
            "SET m.is_read = true",
            fuid=user_fuid
        )
        return {"success": True, "data": {"marked_all_read": True}}
