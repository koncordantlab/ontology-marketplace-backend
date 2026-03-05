from dotenv import load_dotenv
from neo4j import AsyncGraphDatabase
import os

# Load environment variables
load_dotenv()

# Neo4j connection configuration from environment variables
NEO4J_URI = os.getenv('NEO4J_URI', 'bolt://localhost:7687')
NEO4J_USER = os.getenv('NEO4J_USERNAME', 'neo4j')
NEO4J_PASSWORD = os.getenv('NEO4J_PASSWORD')

if not NEO4J_PASSWORD:
    raise ValueError("NEO4J_PASSWORD environment variable is required")

_driver = None


def get_neo4j_driver():
    """Return a singleton async Neo4j driver instance (connection pooling)."""
    global _driver
    if _driver is None:
        _driver = AsyncGraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD))
    return _driver


async def close_neo4j_driver():
    """Close the Neo4j driver and reset the singleton."""
    global _driver
    if _driver is not None:
        await _driver.close()
        _driver = None
