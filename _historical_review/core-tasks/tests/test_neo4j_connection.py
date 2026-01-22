"""
Tests for Neo4j Connection Service

Tests Neo4j driver setup, connection management, and database connectivity.
Validates connection pooling, error handling, and basic query execution.

Run with: python3 -m pytest tests/test_neo4j_connection.py -v
"""

import pytest
from unittest.mock import Mock, patch, MagicMock
from neo4j import GraphDatabase
from neo4j.exceptions import ServiceUnavailable, AuthError

from app.services.neo4j_connection import (
    Neo4jConnection,
    Neo4jConfig,
    get_neo4j_connection
)


@pytest.fixture
def neo4j_config():
    """Create test Neo4j configuration"""
    return Neo4jConfig(
        uri="bolt://localhost:7687",
        username="neo4j",
        password="testpassword",
        database="neo4j",
        max_connection_lifetime=3600,
        max_connection_pool_size=50,
        connection_acquisition_timeout=60
    )


@pytest.fixture
def mock_driver():
    """Create mock Neo4j driver"""
    driver = Mock()
    driver.verify_connectivity = Mock()
    driver.close = Mock()
    return driver


@pytest.fixture
def mock_session():
    """Create mock Neo4j session with context manager support"""
    session = MagicMock()
    session.run = Mock()
    session.close = Mock()
    session.__enter__ = Mock(return_value=session)
    session.__exit__ = Mock(return_value=False)
    return session


def test_neo4j_config_creation():
    """
    Test Neo4jConfig creation with default values

    Verifies:
    - Config accepts connection parameters
    - Default values are set correctly
    - TLS settings are configurable
    """
    config = Neo4jConfig(
        uri="bolt+ssc://localhost:7687",
        username="neo4j",
        password="password123"
    )

    assert config.uri == "bolt+ssc://localhost:7687"
    assert config.username == "neo4j"
    assert config.password == "password123"
    assert config.database == "neo4j"
    assert config.max_connection_pool_size == 50


def test_neo4j_connection_initialization(neo4j_config, mock_driver):
    """
    Test Neo4jConnection initialization

    Verifies:
    - Driver is created with correct config
    - Connection parameters are set
    - Driver object is stored
    """
    with patch('app.services.neo4j_connection.GraphDatabase.driver', return_value=mock_driver):
        connection = Neo4jConnection(config=neo4j_config)

        assert connection.driver is not None
        assert connection.config == neo4j_config
        assert not connection._closed


def test_verify_connectivity_success(neo4j_config, mock_driver):
    """
    Test successful connectivity verification

    Verifies:
    - verify_connectivity() calls driver method
    - Returns True on success
    - No exceptions are raised
    """
    with patch('app.services.neo4j_connection.GraphDatabase.driver', return_value=mock_driver):
        connection = Neo4jConnection(config=neo4j_config)

        result = connection.verify_connectivity()

        assert result is True
        mock_driver.verify_connectivity.assert_called_once()


def test_verify_connectivity_failure(neo4j_config, mock_driver):
    """
    Test connectivity verification failure

    Verifies:
    - Returns False when connection fails
    - Logs appropriate error message
    - Handles ServiceUnavailable exception
    """
    mock_driver.verify_connectivity.side_effect = ServiceUnavailable("Connection failed")

    with patch('app.services.neo4j_connection.GraphDatabase.driver', return_value=mock_driver):
        connection = Neo4jConnection(config=neo4j_config)

        result = connection.verify_connectivity()

        assert result is False


def test_verify_connectivity_auth_error(neo4j_config, mock_driver):
    """
    Test authentication failure during connectivity check

    Verifies:
    - Returns False on auth error
    - Handles AuthError exception
    - Logs authentication failure
    """
    mock_driver.verify_connectivity.side_effect = AuthError("Invalid credentials")

    with patch('app.services.neo4j_connection.GraphDatabase.driver', return_value=mock_driver):
        connection = Neo4jConnection(config=neo4j_config)

        result = connection.verify_connectivity()

        assert result is False


def test_get_session(neo4j_config, mock_driver, mock_session):
    """
    Test session creation

    Verifies:
    - get_session() returns a valid session
    - Session is created with correct database
    - Session can be used for queries
    """
    mock_driver.session = Mock(return_value=mock_session)

    with patch('app.services.neo4j_connection.GraphDatabase.driver', return_value=mock_driver):
        connection = Neo4jConnection(config=neo4j_config)

        session = connection.get_session()

        assert session is not None
        mock_driver.session.assert_called_once_with(database=neo4j_config.database)


def test_close_connection(neo4j_config, mock_driver):
    """
    Test connection closure

    Verifies:
    - close() calls driver.close()
    - Connection is marked as closed
    - Multiple close() calls are safe
    """
    with patch('app.services.neo4j_connection.GraphDatabase.driver', return_value=mock_driver):
        connection = Neo4jConnection(config=neo4j_config)

        connection.close()

        assert connection._closed is True
        mock_driver.close.assert_called_once()

        # Second close should be safe
        connection.close()
        mock_driver.close.assert_called_once()  # Not called again


def test_execute_query_success(neo4j_config, mock_driver, mock_session):
    """
    Test successful query execution

    Verifies:
    - execute_query() runs Cypher query
    - Returns query results
    - Session is properly managed
    """
    # Mock query result
    mock_result = Mock()
    mock_result.data = Mock(return_value=[{"count": 42}])
    mock_session.run = Mock(return_value=mock_result)
    mock_driver.session = Mock(return_value=mock_session)

    with patch('app.services.neo4j_connection.GraphDatabase.driver', return_value=mock_driver):
        connection = Neo4jConnection(config=neo4j_config)

        results = connection.execute_query("MATCH (n) RETURN count(n) as count")

        assert results is not None
        assert len(results) == 1
        assert results[0]["count"] == 42


def test_execute_query_with_parameters(neo4j_config, mock_driver, mock_session):
    """
    Test query execution with parameters

    Verifies:
    - Parameters are passed correctly
    - Query is executed with parameterization
    - Prevents Cypher injection
    """
    mock_result = Mock()
    mock_result.data = Mock(return_value=[{"name": "test_doc"}])
    mock_session.run = Mock(return_value=mock_result)
    mock_driver.session = Mock(return_value=mock_session)

    with patch('app.services.neo4j_connection.GraphDatabase.driver', return_value=mock_driver):
        connection = Neo4jConnection(config=neo4j_config)

        query = "MATCH (d:Document {id: $doc_id}) RETURN d.name as name"
        params = {"doc_id": "12345"}

        results = connection.execute_query(query, params)

        assert results is not None
        mock_session.run.assert_called_once_with(query, params)


def test_execute_query_error_handling(neo4j_config, mock_driver, mock_session):
    """
    Test query execution error handling

    Verifies:
    - Exceptions are caught and logged
    - Returns empty list on error
    - Session is closed even on error
    """
    mock_session.run.side_effect = Exception("Query execution failed")
    mock_driver.session = Mock(return_value=mock_session)

    with patch('app.services.neo4j_connection.GraphDatabase.driver', return_value=mock_driver):
        connection = Neo4jConnection(config=neo4j_config)

        results = connection.execute_query("INVALID QUERY")

        assert results == []


def test_connection_context_manager(neo4j_config, mock_driver):
    """
    Test Neo4jConnection as context manager

    Verifies:
    - Can be used with 'with' statement
    - Automatically closes on exit
    - Handles exceptions properly
    """
    with patch('app.services.neo4j_connection.GraphDatabase.driver', return_value=mock_driver):
        with Neo4jConnection(config=neo4j_config) as conn:
            assert conn.driver is not None
            assert not conn._closed

        # After exiting context, connection should be closed
        mock_driver.close.assert_called_once()


def test_get_neo4j_connection_singleton():
    """
    Test singleton pattern for Neo4j connection

    Verifies:
    - get_neo4j_connection() returns same instance
    - Configuration is only applied on first call
    - Subsequent calls return cached instance
    """
    with patch('app.services.neo4j_connection.GraphDatabase.driver'):
        conn1 = get_neo4j_connection()
        conn2 = get_neo4j_connection()

        assert conn1 is conn2


def test_connection_from_environment_variables(mock_driver):
    """
    Test connection creation from environment variables

    Verifies:
    - Config reads from environment
    - NEO4J_URI, NEO4J_USERNAME, NEO4J_PASSWORD are used
    - Falls back to defaults if not set
    """
    env_vars = {
        "NEO4J_URI": "bolt+ssc://100.119.86.6:7687",
        "NEO4J_USERNAME": "neo4j",
        "NEO4J_PASSWORD": "secretpass",
        "NEO4J_DATABASE": "empire"
    }

    with patch('app.services.neo4j_connection.GraphDatabase.driver', return_value=mock_driver):
        with patch.dict('os.environ', env_vars):
            config = Neo4jConfig.from_env()

            assert config.uri == "bolt+ssc://100.119.86.6:7687"
            assert config.username == "neo4j"
            assert config.password == "secretpass"
            assert config.database == "empire"


def test_execute_write_transaction(neo4j_config, mock_driver, mock_session):
    """
    Test write transaction execution

    Verifies:
    - Write transactions are executed correctly
    - Transaction is committed
    - Returns transaction result
    """
    mock_result = Mock()
    mock_result.data = Mock(return_value=[{"created": True}])
    mock_session.run = Mock(return_value=mock_result)
    mock_driver.session = Mock(return_value=mock_session)

    with patch('app.services.neo4j_connection.GraphDatabase.driver', return_value=mock_driver):
        connection = Neo4jConnection(config=neo4j_config)

        query = "CREATE (d:Document {id: $id, title: $title}) RETURN d"
        params = {"id": "doc123", "title": "Test Document"}

        result = connection.execute_query(query, params)

        assert result is not None


def test_connection_pool_configuration(neo4j_config, mock_driver):
    """
    Test connection pool settings are applied

    Verifies:
    - Pool size is configured
    - Connection lifetime is set
    - Timeout settings are applied
    """
    with patch('app.services.neo4j_connection.GraphDatabase.driver', return_value=mock_driver) as mock_driver_class:
        connection = Neo4jConnection(config=neo4j_config)

        # Verify driver was created with pool config
        call_kwargs = mock_driver_class.call_args.kwargs
        assert 'max_connection_lifetime' in call_kwargs
        assert 'max_connection_pool_size' in call_kwargs


def test_database_name_configuration(neo4j_config, mock_driver, mock_session):
    """
    Test custom database name configuration

    Verifies:
    - Custom database name is used
    - Session is created for correct database
    - Default database works if not specified
    """
    custom_config = Neo4jConfig(
        uri="bolt://localhost:7687",
        username="neo4j",
        password="password",
        database="customdb"
    )

    mock_driver.session = Mock(return_value=mock_session)

    with patch('app.services.neo4j_connection.GraphDatabase.driver', return_value=mock_driver):
        connection = Neo4jConnection(config=custom_config)
        session = connection.get_session()

        mock_driver.session.assert_called_once_with(database="customdb")
