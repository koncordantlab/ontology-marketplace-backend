import re
from typing import Optional
from urllib.parse import urlparse
import tempfile
import os
from collections import defaultdict

from rdflib import Graph, RDFS, URIRef
from neo4j import GraphDatabase
import requests


def _download_to_tempfile(source: str) -> str:
    """
    Download a remote file to a temporary path and return the path.
    If source is a local path, return it unchanged.
    """
    parsed = urlparse(source)
    if parsed.scheme in ("http", "https"):
        try:
            response = requests.get(source, timeout=60)
        except requests.exceptions.ConnectionError:
            raise ValueError(f"Could not connect to URL: {source}")
        except requests.exceptions.Timeout:
            raise ValueError(f"Request timed out for URL: {source}")

        if response.status_code == 404:
            raise ValueError(f"File not found at URL (404): {source}")
        elif response.status_code == 403:
            raise ValueError(f"Access denied for URL (403): {source}")
        response.raise_for_status()

        # Check content type - warn if HTML instead of ontology file
        content_type = response.headers.get('Content-Type', '').lower()
        if 'text/html' in content_type and not any(
            ext in source.lower() for ext in ('.owl', '.ttl', '.rdf', '.xml')
        ):
            raise ValueError(
                f"URL returned an HTML page instead of an ontology file. "
                f"The URL may not point directly to a downloadable OWL/TTL file: {source}"
            )

        suffix = os.path.splitext(parsed.path)[1] or ".ttl"
        fd, tmp_path = tempfile.mkstemp(suffix=suffix)
        with os.fdopen(fd, "wb") as tmp:
            tmp.write(response.content)
        return tmp_path
    return source


def convert_owl_to_ttl(input_path: str) -> str:
    """Convert OWL file to TTL format."""
    g = Graph()
    g.parse(input_path, format="xml")
    temp_ttl = tempfile.NamedTemporaryFile(delete=False, suffix=".ttl")
    g.serialize(destination=temp_ttl.name, format="turtle")
    return temp_ttl.name


def sanitize_label(label: str) -> str:
    """Sanitize label for Neo4j node labels."""
    sanitized = re.sub(r'[^a-zA-Z0-9_]', '', label.replace(" ", "_").replace("-", "_"))
    if re.match(r'^\d', sanitized):
        sanitized = "L_" + sanitized
    return sanitized or "Unknown"


def extract_fragment(uri: str) -> str:
    """Extracts the last part of a URI (after # or /)"""
    if "#" in uri:
        return uri.split("#")[-1]
    return uri.rstrip("/").split("/")[-1]


def parse_ttl_to_json(ttl_path: str, root_label: Optional[str] = None) -> list:
    """Parse TTL file to JSON tree structure."""
    g = Graph()
    g.parse(ttl_path, format="ttl")

    children = defaultdict(list)
    labels = {}
    parents = set()
    all_classes = set()

    for s, p, o in g:
        if p == RDFS.label:
            labels[s] = str(o)
        elif p == RDFS.subClassOf and isinstance(o, URIRef):
            children[o].append(s)
            parents.add(s)
            all_classes.add(s)
            all_classes.add(o)

    # Ensure every class has a label (fall back to fragment)
    for cls in all_classes:
        if cls not in labels:
            labels[cls] = extract_fragment(str(cls))

    # Filter top-level roots: those that are not children
    if root_label:
        def get_uri_by_label(search_label):
            for uri, label in labels.items():
                if label.lower() == search_label.lower():
                    return uri
            return None

        root_uri = get_uri_by_label(root_label)
        if not root_uri:
            raise ValueError(f"Root label '{root_label}' not found in TTL file.")
        roots = [root_uri]
    else:
        roots = [cls for cls in all_classes if cls not in parents]

    def build_json_tree(node):
        return {
            "id": str(node),
            "label": labels.get(node, extract_fragment(str(node))),
            "children": [build_json_tree(child) for child in children.get(node, [])]
        }

    return [build_json_tree(r) for r in roots]


def count_nodes(node: dict, children_field: str) -> int:
    """Count total nodes in tree."""
    count = 1
    for child in node.get(children_field, []):
        count += count_nodes(child, children_field)
    return count


def upload_node(tx, node_id: str, label: str, assigned_label: str):
    """Upload a single node to Neo4j."""
    tx.run(f"""
        MERGE (n:{assigned_label} {{id: $id}})
        SET n.name = $label
    """, id=node_id, label=label)


def create_relationship(tx, parent_id: str, child_id: str):
    """Create SUBCLASS_OF relationship between nodes."""
    tx.run("""
        MATCH (p {id: $parent_id})
        MATCH (c {id: $child_id})
        MERGE (c)-[:SUBCLASS_OF]->(p)
    """, parent_id=parent_id, child_id=child_id)


def traverse_and_upload(tx, root_node: dict, id_field: str, label_field: str, children_field: str, counters: dict):
    """Traverse tree and upload nodes to Neo4j."""
    def recurse(node, parent_id=None, parent_label=None, level=0):
        node_id = node.get(id_field)
        raw_label = node.get(label_field, node_id)
        children = node.get(children_field, [])

        current_label = sanitize_label(raw_label)
        assigned_label = current_label if level <= 1 else parent_label

        if node_id:
            upload_node(tx, node_id, raw_label, assigned_label)
            counters['nodes'] += 1
            if parent_id:
                create_relationship(tx, parent_id, node_id)
                counters['relationships'] += 1

            for child in children:
                recurse(child, parent_id=node_id, parent_label=assigned_label, level=level+1)

    recurse(root_node)


def upload_ontology(
    source: str,
    ontology_uuid: Optional[str] = None,
    neo4j_uri: Optional[str] = None,
    neo4j_username: Optional[str] = None,
    neo4j_password: Optional[str] = None,
    neo4j_database: Optional[str] = None,
    root_label: Optional[str] = None,
) -> dict:
    """
    Load a TTL/OWL file from a URL or local path into Neo4j.

    Args:
        source: HTTP(S) URL or filesystem path to a TTL/OWL file.
        ontology_uuid: Optional Ontology uuid (not used currently).
        neo4j_uri: Neo4j connection URI.
        neo4j_username: Neo4j username.
        neo4j_password: Neo4j password.
        neo4j_database: Neo4j database name.
        root_label: Optional root label to start tree from.

    Returns:
        Dict with counts: {"nodes": int, "relationships": int}
    """
    local_path: Optional[str] = None
    converted_path: Optional[str] = None

    try:
        # Download if URL
        local_path = _download_to_tempfile(source)

        # Convert OWL to TTL if needed
        if local_path.endswith(".owl"):
            converted_path = convert_owl_to_ttl(local_path)
            ttl_path = converted_path
        else:
            ttl_path = local_path

        # Parse TTL to JSON tree
        json_data = parse_ttl_to_json(ttl_path, root_label=root_label)

        if not json_data:
            return {"nodes": 0, "relationships": 0, "message": "No data found in ontology file"}

        # Connect to Neo4j
        if not neo4j_uri or not neo4j_username or not neo4j_password:
            raise ValueError("Neo4j credentials are required")

        driver = GraphDatabase.driver(neo4j_uri, auth=(neo4j_username, neo4j_password))

        counters = {'nodes': 0, 'relationships': 0}

        try:
            def upload_all(tx):
                for tree in json_data:
                    traverse_and_upload(tx, tree, "id", "label", "children", counters)

            with driver.session(database=neo4j_database) as session:
                session.execute_write(upload_all)
        finally:
            driver.close()

        return {"nodes": counters['nodes'], "relationships": counters['relationships']}

    finally:
        # Clean up temp files
        if local_path and local_path != source and os.path.exists(local_path):
            try:
                os.remove(local_path)
            except OSError:
                pass
        if converted_path and os.path.exists(converted_path):
            try:
                os.remove(converted_path)
            except OSError:
                pass
