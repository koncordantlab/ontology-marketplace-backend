from functions_framework import http
from flask import Request
from typing import Dict, Any
from datetime import datetime
from .model_ontology import UpdateOntology,Ontology, OntologyResponse
from .n4j import get_neo4j_driver

def update_ontology(email: str, ontology_id: str, update_data: UpdateOntology) -> OntologyResponse:
    """
    Update an existing ontology in the database.
    
    Args:
        email: String email of the owner or editor of ontologies
        ontology_id: The uuid of the ontology to update
        update_data: Dictionary containing fields to update
        
    Returns:
        OntologyResponse with the result of the operation
    """
    if not ontology_id:
        return OntologyResponse(
            success=False,
            message="No ontology ID provided",
            data=None
        )
    
    try:
        driver = get_neo4j_driver()
        
        # First, check if the user is authorized to update this ontology
        auth_check_query = """
            MATCH (o:Ontology {uuid: $ontology_id})
            OPTIONAL MATCH (u:User {email: $email})
            WITH o, u, 
                CASE WHEN u IS NULL THEN false 
                    ELSE EXISTS((u)-[:CREATED|CAN_ADMIN|CAN_EDIT]->(o)) 
                END as is_authorized
            RETURN 
                o IS NOT NULL as ontology_exists,
                is_authorized
        """
        
        is_authorized = driver.execute_query(
            auth_check_query,
            email=email,
            ontology_id=ontology_id,
            database_="neo4j",
            result_transformer_=lambda r: r.single()
        )
        
        if not is_authorized or not is_authorized.get('ontology_exists'):
            return OntologyResponse(
                success=False,
                message="No ontology found with the provided ID",
                data=None
            )

        if not is_authorized.get('is_authorized'):
            return OntologyResponse(
                success=False,
                message="Not authorized to update this ontology",
                data=None
            )
        
        # Prepare the SET clause for the update
        set_clauses = []
        params = {
            'email': email,
            'ontology_id': ontology_id
        }
    
    except Exception as e:
        print(f"Database error: {str(e)}")
        return OntologyResponse(
            success=False,
            message="Failed authorization check. User may not have access to edit this ontology",
            data=None
        )
    
    try:
        driver = get_neo4j_driver()
        
        # Prepare the SET clause for the update
        set_clauses = []
        params = {
            'email': email,
            'ontology_id': ontology_id
        }
        
        # Only include fields that are present in update_data
        allowed_fields = {
            'name': str,
            'source_url': str,
            'image_url': str,
            'description': str,
            'node_count': int,
            'relationship_count': int,
            'is_public': bool
        }
        
        # Convert Pydantic model to dict and filter out None values
        update_dict = {k: v for k, v in update_data.model_dump().items() if v is not None}

        for field, field_type in allowed_fields.items():
            if field in update_dict:
                param_name = f"new_{field}"
                set_clauses.append(f"o.{field} = ${param_name}")
                params[param_name] = field_type(update_dict[field])
        
        if not set_clauses:
            return OntologyResponse(
                success=False,
                message="No valid fields to update",
                data=None
            )
        
        # Add updated timestamp
        set_clauses.append("o.updated_time = datetime()")
        
        query = f"""
            MATCH (u:User {{email: $email}})
            MATCH (o:Ontology {{uuid: $ontology_id}})
            WITH u, o
            WHERE EXISTS((u)-[:CREATED|CAN_ADMIN|CAN_EDIT]->(o))
            SET {', '.join(set_clauses)}
            RETURN o
        """
        
        result = driver.execute_query(
            query,
            **params,
            database_="neo4j",
            result_transformer_=lambda r: r.single()
        )
        
        if not result:
            return OntologyResponse(
                success=False,
                message="No ontology found with the provided ID",
                data=None
            )
        
        # Convert the Neo4j node to an Ontology object
        created_at = result['o']['created_at']
        if hasattr(created_at, 'to_native'):
            created_at = created_at.to_native()  # Convert Neo4j DateTime to Python datetime

        updated_ontology = Ontology(
            uuid=result['o']['uuid'],
            name=result['o']['name'],
            source_url=result['o']['source_url'],
            image_url=result['o'].get('image_url'),
            description=result['o'].get('description'),
            node_count=result['o'].get('node_count'),
            relationship_count=result['o'].get('relationship_count'),
            is_public=result['o'].get('is_public', False),
            score=result['o'].get('score'),
            created_at=created_at
        )
        
        return OntologyResponse(
            success=True,
            message="Ontology updated successfully",
            data=updated_ontology.model_dump()
        )
            
    except Exception as e:
        print(f"Database error: {str(e)}")
        return OntologyResponse(
            success=False,
            message="Failed to update ontology",
            data=None
        )

@http
def update_ontology_by_request(request: Request):
    """
    HTTP Cloud Function for updating an ontology.
    
    Args:
        request (flask.Request): The request object.
        Should contain a JSON object with the fields to update.
        
    Returns:
        JSON response with the result of the operation.
    """
    # Set CORS headers for the preflight request
    if request.method == 'OPTIONS':
        headers = {
            'Access-Control-Allow-Origin': '*',
            'Access-Control-Allow-Methods': 'PUT, OPTIONS',
            'Access-Control-Allow-Headers': 'Content-Type',
            'Access-Control-Max-Age': '3600'
        }
        return ('', 204, headers)

    # Set CORS headers for the main request
    headers = {
        'Access-Control-Allow-Origin': '*',
        'Content-Type': 'application/json'
    }

    try:
        # Get JSON data from request
        request_json = request.get_json(silent=True)
        if not request_json:
            return OntologyResponse(
                success=False,
                message="No JSON data provided",
                data=None
            )
        
        # Get ontology_id from URL path
        ontology_id = request.view_args.get('ontology_id')
        if not ontology_id:
            return OntologyResponse(
                success=False,
                message="No ontology ID provided in URL",
                data=None
            )
            
        return update_ontology(ontology_id, request_json)

    except Exception as e:
        print(f"Unexpected error: {str(e)}")
        return OntologyResponse(
            success=False,
            message="An unexpected error occurred",
            data=None
        )