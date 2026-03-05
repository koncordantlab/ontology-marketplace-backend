from functions.n4j import get_neo4j_driver
from functions.model_ontology import Ontology, OntologyResponse
from functions.auth_utils import verify_firebase_token
from typing import Optional
import logging


async def get_ontology_by_id(ontology_uuid: str, fuid: Optional[str] = None) -> OntologyResponse:
    """
    Get a single ontology by UUID.

    Args:
        ontology_uuid: The UUID of the ontology to retrieve
        fuid: Optional Firebase UID for permission checks (private ontologies)

    Returns:
        OntologyResponse with the ontology data or error
    """
    try:
        driver = get_neo4j_driver()
        if fuid:
            permission_clause = "(o.is_public = true OR EXISTS((:User {fuid: $fuid})-[:CREATED|CAN_EDIT|CAN_DELETE]->(o)))"
            params = {'uuid': ontology_uuid, 'fuid': fuid}
        else:
            permission_clause = "o.is_public = true"
            params = {'uuid': ontology_uuid}

        query = f"""
            MATCH (o:Ontology {{uuid: $uuid}})
            WHERE {permission_clause}
            OPTIONAL MATCH (o)-[:TAGGED]->(t:Tag)
            RETURN o, collect(DISTINCT toLower(t.name)) AS tags
            """

        async with driver.session() as session:
            result = await session.run(query, params)
            records = [(record['o'], record['tags']) async for record in result]

        if not records:
            return OntologyResponse(
                success=False,
                message='Ontology not found',
                data=None
            )

        node, tags = records[0]
        ontology = Ontology(
            uuid=node['uuid'],
            name=node['name'],
            source_url=node['source_url'],
            image_url=node.get('image_url'),
            description=node.get('description'),
            node_count=node.get('node_count'),
            score=node.get('score'),
            relationship_count=node.get('relationship_count'),
            is_public=node.get('is_public', False),
            created_at=(
                node.get('created_at').to_native()
                if hasattr(node.get('created_at'), 'to_native')
                else node.get('created_at')
            )
        )
        data = ontology.model_dump()
        data['tags'] = tags or []

        return OntologyResponse(
            success=True,
            message='Ontology retrieved successfully',
            data=data
        )

    except Exception as e:
        logging.error(f"Database error: {str(e)}")
        return OntologyResponse(
            success=False,
            message='Database error occurred',
            data=None
        )
