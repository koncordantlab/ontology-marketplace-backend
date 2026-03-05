from functions.n4j import get_neo4j_driver
import uuid
from datetime import datetime, timezone


def send_message(recipient_fuid: str, subject: str, content: str, sender_fuid: str, sender_email: str) -> dict:
    """Send a message (admin-only)."""
    driver = get_neo4j_driver()
    with driver.session() as session:
        msg_uuid = str(uuid.uuid4())
        now = datetime.now(timezone.utc).isoformat()
        session.run(
            "MERGE (sender:User {fuid: $sender_fuid}) "
            "  ON CREATE SET sender.created_at = datetime(), sender.uuid = randomUUID(), sender.email = $sender_email "
            "MERGE (recipient:User {fuid: $recipient_fuid}) "
            "CREATE (m:Message {uuid: $muuid, subject: $subject, content: $content, "
            "  is_read: false, created_at: datetime($now)}) "
            "CREATE (sender)-[:SENT_MESSAGE]->(m) "
            "CREATE (m)-[:RECEIVED_MESSAGE]->(recipient) ",
            sender_fuid=sender_fuid, sender_email=sender_email,
            recipient_fuid=recipient_fuid, muuid=msg_uuid,
            subject=subject, content=content, now=now
        )
        return {"success": True, "data": {"uuid": msg_uuid}, "status": 201}


def get_messages(user_fuid: str, limit: int = 20, offset: int = 0) -> dict:
    """Get messages for a user (inbox)."""
    driver = get_neo4j_driver()
    with driver.session() as session:
        result = session.run(
            "MATCH (m:Message)-[:RECEIVED_MESSAGE]->(u:User {fuid: $fuid}) "
            "WHERE NOT EXISTS((m)-[:REPLY_TO_MESSAGE]->()) "
            "OPTIONAL MATCH (sender:User)-[:SENT_MESSAGE]->(m) "
            "ORDER BY m.created_at DESC "
            "SKIP $offset LIMIT $limit "
            "RETURN m.uuid AS uuid, m.subject AS subject, m.content AS content, "
            "  m.is_read AS is_read, m.created_at AS created_at, "
            "  sender.email AS sender_email",
            fuid=user_fuid, limit=limit, offset=offset
        )
        messages = []
        for record in result:
            messages.append({
                "uuid": record["uuid"],
                "subject": record["subject"],
                "content": record["content"],
                "is_read": record["is_read"],
                "created_at": str(record["created_at"]),
                "sender_email": record["sender_email"],
            })
        return {"success": True, "data": {"messages": messages}}


def get_message(message_id: str, user_fuid: str) -> dict:
    """Get a single message with thread."""
    driver = get_neo4j_driver()
    with driver.session() as session:
        # Get the message
        result = session.run(
            "MATCH (m:Message {uuid: $mid}) "
            "OPTIONAL MATCH (sender:User)-[:SENT_MESSAGE]->(m) "
            "OPTIONAL MATCH (m)-[:RECEIVED_MESSAGE]->(recipient:User) "
            "RETURN m.uuid AS uuid, m.subject AS subject, m.content AS content, "
            "  m.is_read AS is_read, m.created_at AS created_at, "
            "  sender.email AS sender_email, sender.fuid AS sender_fuid, "
            "  recipient.fuid AS recipient_fuid",
            mid=message_id
        )
        record = result.single()
        if not record:
            return {"success": False, "error": "Message not found", "status": 404}

        # Verify access
        if record["recipient_fuid"] != user_fuid and record["sender_fuid"] != user_fuid:
            return {"success": False, "error": "Not authorized", "status": 403}

        # Get replies in thread
        replies_result = session.run(
            "MATCH (reply:Message)-[:REPLY_TO_MESSAGE]->(m:Message {uuid: $mid}) "
            "OPTIONAL MATCH (rs:User)-[:SENT_MESSAGE]->(reply) "
            "ORDER BY reply.created_at ASC "
            "RETURN reply.uuid AS uuid, reply.content AS content, "
            "  reply.created_at AS created_at, rs.email AS sender_email",
            mid=message_id
        )
        replies = []
        for r in replies_result:
            replies.append({
                "uuid": r["uuid"],
                "content": r["content"],
                "created_at": str(r["created_at"]),
                "sender_email": r["sender_email"],
            })

        message = {
            "uuid": record["uuid"],
            "subject": record["subject"],
            "content": record["content"],
            "is_read": record["is_read"],
            "created_at": str(record["created_at"]),
            "sender_email": record["sender_email"],
            "replies": replies,
        }
        return {"success": True, "data": message}


def reply_to_message(message_id: str, content: str, user_fuid: str, user_email: str) -> dict:
    """Reply to a message (only the recipient can reply)."""
    driver = get_neo4j_driver()
    with driver.session() as session:
        # Verify user is recipient
        auth = session.run(
            "MATCH (m:Message {uuid: $mid})-[:RECEIVED_MESSAGE]->(u:User {fuid: $fuid}) "
            "RETURN m.uuid AS uuid",
            mid=message_id, fuid=user_fuid
        )
        if not auth.single():
            return {"success": False, "error": "Only the recipient can reply", "status": 403}

        reply_uuid = str(uuid.uuid4())
        now = datetime.now(timezone.utc).isoformat()
        session.run(
            "MATCH (m:Message {uuid: $mid}) "
            "MERGE (u:User {fuid: $fuid}) "
            "  ON CREATE SET u.created_at = datetime(), u.uuid = randomUUID(), u.email = $email "
            "CREATE (reply:Message {uuid: $ruuid, subject: '', content: $content, "
            "  is_read: false, created_at: datetime($now)}) "
            "CREATE (u)-[:SENT_MESSAGE]->(reply) "
            "CREATE (reply)-[:REPLY_TO_MESSAGE]->(m) ",
            mid=message_id, fuid=user_fuid, email=user_email,
            ruuid=reply_uuid, content=content, now=now
        )
        return {"success": True, "data": {"uuid": reply_uuid}, "status": 201}


def mark_message_read(message_id: str, user_fuid: str) -> dict:
    """Mark a message as read."""
    driver = get_neo4j_driver()
    with driver.session() as session:
        result = session.run(
            "MATCH (m:Message {uuid: $mid})-[:RECEIVED_MESSAGE]->(u:User {fuid: $fuid}) "
            "SET m.is_read = true "
            "RETURN m.uuid AS uuid",
            mid=message_id, fuid=user_fuid
        )
        if not result.single():
            return {"success": False, "error": "Message not found or not authorized", "status": 404}
        return {"success": True, "data": {"uuid": message_id, "is_read": True}}
