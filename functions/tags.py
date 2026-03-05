from typing import List

from .n4j import get_neo4j_driver


async def get_tags(neo4j_database: str | None = None) -> List[str]:
    """Return all tag names in lowercase as a list of strings."""
    async with get_neo4j_driver().session(database=neo4j_database) as session:
        result = await session.run(
            """
            MATCH (t:Tag)
            WITH toLower(t.name) AS name
            RETURN DISTINCT name AS name
            ORDER BY name
            """
        )
        records = [record async for record in result]
        return [record["name"] for record in records]


async def add_tags(tags: List[str], neo4j_database: str | None = None) -> List[str]:
    """Create Tag nodes for the provided tag strings, enforcing lowercase and uniqueness."""
    if not tags:
        return []

    lowered = [t.strip().lower() for t in tags if isinstance(t, str) and t.strip()]
    if not lowered:
        return []

    async with get_neo4j_driver().session(database=neo4j_database) as session:
        await session.run(
            """
            UNWIND $names AS name
            MERGE (:Tag {name: name})
            """,
            names=lowered,
        )
        result = await session.run(
            """
            MATCH (t:Tag)
            WITH toLower(t.name) AS name
            RETURN DISTINCT name AS name
            ORDER BY name
            """
        )
        records = [record async for record in result]
        return [record["name"] for record in records]
