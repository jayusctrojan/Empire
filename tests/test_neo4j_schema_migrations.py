# tests/test_neo4j_schema_migrations.py
"""
Unit tests for Neo4j Schema Migrations.

Task 102: Graph Agent - Neo4j Schema Extensions
Feature: 005-graph-agent

These tests validate:
1. Migration files are syntactically valid
2. Constraints and indexes are correctly defined
3. Migrations are idempotent (safe to run multiple times)
"""

import pytest
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch
import re


class TestMigrationFilesExist:
    """Test migration files exist and have correct structure."""

    MIGRATIONS_DIR = Path(__file__).parent.parent / "migrations" / "neo4j"

    def test_migrations_directory_exists(self):
        """Test migrations/neo4j directory exists."""
        assert self.MIGRATIONS_DIR.exists(), "migrations/neo4j directory should exist"
        assert self.MIGRATIONS_DIR.is_dir(), "migrations/neo4j should be a directory"

    def test_customer360_schema_exists(self):
        """Test 001_customer360_schema.cypher exists."""
        migration_file = self.MIGRATIONS_DIR / "001_customer360_schema.cypher"
        assert migration_file.exists(), "001_customer360_schema.cypher should exist"

    def test_document_structure_schema_exists(self):
        """Test 002_document_structure_schema.cypher exists."""
        migration_file = self.MIGRATIONS_DIR / "002_document_structure_schema.cypher"
        assert migration_file.exists(), "002_document_structure_schema.cypher should exist"

    def test_entity_relationships_schema_exists(self):
        """Test 003_entity_relationships.cypher exists."""
        migration_file = self.MIGRATIONS_DIR / "003_entity_relationships.cypher"
        assert migration_file.exists(), "003_entity_relationships.cypher should exist"


class TestCustomer360Schema:
    """Test Customer 360 schema migration content."""

    MIGRATIONS_DIR = Path(__file__).parent.parent / "migrations" / "neo4j"

    @pytest.fixture
    def schema_content(self):
        """Load the Customer 360 schema file."""
        migration_file = self.MIGRATIONS_DIR / "001_customer360_schema.cypher"
        return migration_file.read_text()

    def test_customer_node_constraint(self, schema_content):
        """Test Customer node has unique ID constraint."""
        assert "CREATE CONSTRAINT customer_id" in schema_content
        assert "(c:Customer) REQUIRE c.id IS UNIQUE" in schema_content

    def test_customer_indexes(self, schema_content):
        """Test Customer indexes are defined."""
        assert "CREATE INDEX customer_name" in schema_content
        assert "CREATE INDEX customer_type" in schema_content
        assert "CREATE INDEX customer_industry" in schema_content

    def test_ticket_node_constraint(self, schema_content):
        """Test Ticket node has unique ID constraint."""
        assert "CREATE CONSTRAINT ticket_id" in schema_content
        assert "(t:Ticket) REQUIRE t.id IS UNIQUE" in schema_content

    def test_ticket_indexes(self, schema_content):
        """Test Ticket indexes are defined."""
        assert "CREATE INDEX ticket_customer_id" in schema_content
        assert "CREATE INDEX ticket_status" in schema_content

    def test_order_node_constraint(self, schema_content):
        """Test Order node has unique ID constraint."""
        assert "CREATE CONSTRAINT order_id" in schema_content
        assert "(o:Order) REQUIRE o.id IS UNIQUE" in schema_content

    def test_interaction_node_constraint(self, schema_content):
        """Test Interaction node has unique ID constraint."""
        assert "CREATE CONSTRAINT interaction_id" in schema_content
        assert "(i:Interaction) REQUIRE i.id IS UNIQUE" in schema_content

    def test_product_node_constraint(self, schema_content):
        """Test Product node has unique ID constraint."""
        assert "CREATE CONSTRAINT product_id" in schema_content
        assert "(p:Product) REQUIRE p.id IS UNIQUE" in schema_content

    def test_relationship_indexes(self, schema_content):
        """Test relationship indexes are defined."""
        assert "CREATE INDEX rel_has_document" in schema_content
        assert "CREATE INDEX rel_has_ticket" in schema_content
        assert "CREATE INDEX rel_placed_order" in schema_content
        assert "CREATE INDEX rel_had_interaction" in schema_content
        assert "CREATE INDEX rel_uses_product" in schema_content

    def test_idempotent_statements(self, schema_content):
        """Test all CREATE statements use IF NOT EXISTS for idempotency."""
        create_statements = re.findall(r"CREATE (CONSTRAINT|INDEX)", schema_content)
        if_not_exists = re.findall(r"IF NOT EXISTS", schema_content)
        assert len(create_statements) == len(if_not_exists), \
            "All CREATE statements should have IF NOT EXISTS"


class TestDocumentStructureSchema:
    """Test Document Structure schema migration content."""

    MIGRATIONS_DIR = Path(__file__).parent.parent / "migrations" / "neo4j"

    @pytest.fixture
    def schema_content(self):
        """Load the Document Structure schema file."""
        migration_file = self.MIGRATIONS_DIR / "002_document_structure_schema.cypher"
        return migration_file.read_text()

    def test_section_node_constraint(self, schema_content):
        """Test Section node has unique ID constraint."""
        assert "CREATE CONSTRAINT section_id" in schema_content
        assert "(s:Section) REQUIRE s.id IS UNIQUE" in schema_content

    def test_section_indexes(self, schema_content):
        """Test Section indexes are defined."""
        assert "CREATE INDEX section_document_id" in schema_content
        assert "CREATE INDEX section_number" in schema_content
        assert "CREATE INDEX section_level" in schema_content

    def test_defined_term_node_constraint(self, schema_content):
        """Test DefinedTerm node has unique ID constraint."""
        assert "CREATE CONSTRAINT defined_term_id" in schema_content
        assert "(dt:DefinedTerm) REQUIRE dt.id IS UNIQUE" in schema_content

    def test_citation_node_constraint(self, schema_content):
        """Test Citation node has unique ID constraint."""
        assert "CREATE CONSTRAINT citation_id" in schema_content
        assert "(c:Citation) REQUIRE c.id IS UNIQUE" in schema_content

    def test_hierarchy_relationships(self, schema_content):
        """Test hierarchy relationship indexes are defined."""
        assert "CREATE INDEX rel_has_section" in schema_content
        assert "CREATE INDEX rel_has_subsection" in schema_content
        assert "CREATE INDEX rel_parent_section" in schema_content

    def test_cross_reference_relationships(self, schema_content):
        """Test cross-reference relationship indexes are defined."""
        assert "CREATE INDEX rel_references_section" in schema_content

    def test_term_relationships(self, schema_content):
        """Test term relationship indexes are defined."""
        assert "CREATE INDEX rel_defines_term" in schema_content
        assert "CREATE INDEX rel_uses_term" in schema_content

    def test_fulltext_indexes(self, schema_content):
        """Test full-text indexes are defined."""
        assert "CREATE FULLTEXT INDEX section_content_fulltext" in schema_content
        assert "CREATE FULLTEXT INDEX defined_term_fulltext" in schema_content

    def test_idempotent_statements(self, schema_content):
        """Test all CREATE statements use IF NOT EXISTS for idempotency."""
        create_statements = re.findall(r"CREATE (CONSTRAINT|INDEX|FULLTEXT)", schema_content)
        if_not_exists = re.findall(r"IF NOT EXISTS", schema_content)
        assert len(create_statements) == len(if_not_exists), \
            "All CREATE statements should have IF NOT EXISTS"


class TestEntityRelationshipsSchema:
    """Test Entity Relationships schema migration content."""

    MIGRATIONS_DIR = Path(__file__).parent.parent / "migrations" / "neo4j"

    @pytest.fixture
    def schema_content(self):
        """Load the Entity Relationships schema file."""
        migration_file = self.MIGRATIONS_DIR / "003_entity_relationships.cypher"
        return migration_file.read_text()

    def test_entity_node_constraint(self, schema_content):
        """Test Entity node has unique ID constraint."""
        assert "CREATE CONSTRAINT entity_id" in schema_content
        assert "(e:Entity) REQUIRE e.id IS UNIQUE" in schema_content

    def test_entity_indexes(self, schema_content):
        """Test Entity indexes are defined."""
        assert "CREATE INDEX entity_name" in schema_content
        assert "CREATE INDEX entity_type" in schema_content
        assert "CREATE INDEX entity_normalized_name" in schema_content

    def test_chunk_node_constraint(self, schema_content):
        """Test Chunk node has unique ID constraint."""
        assert "CREATE CONSTRAINT chunk_id" in schema_content
        assert "(ch:Chunk) REQUIRE ch.id IS UNIQUE" in schema_content

    def test_chunk_indexes(self, schema_content):
        """Test Chunk indexes are defined."""
        assert "CREATE INDEX chunk_document_id" in schema_content
        assert "CREATE INDEX chunk_position" in schema_content
        assert "CREATE INDEX chunk_embedding_id" in schema_content

    def test_entity_document_relationships(self, schema_content):
        """Test entity-document relationship indexes are defined."""
        assert "CREATE INDEX rel_mentions" in schema_content
        assert "CREATE INDEX rel_mentioned_in" in schema_content
        assert "CREATE INDEX rel_contains_entity" in schema_content

    def test_entity_entity_relationships(self, schema_content):
        """Test entity-entity relationship indexes are defined."""
        assert "CREATE INDEX rel_related_to" in schema_content
        assert "CREATE INDEX rel_co_occurs" in schema_content
        assert "CREATE INDEX rel_similar_to" in schema_content

    def test_chunk_chunk_relationships(self, schema_content):
        """Test chunk-chunk relationship indexes for RAG."""
        assert "CREATE INDEX rel_next_chunk" in schema_content
        assert "CREATE INDEX rel_prev_chunk" in schema_content
        assert "CREATE INDEX rel_in_section" in schema_content
        assert "CREATE INDEX rel_semantically_similar" in schema_content

    def test_fulltext_indexes(self, schema_content):
        """Test full-text indexes are defined."""
        assert "CREATE FULLTEXT INDEX entity_fulltext" in schema_content
        assert "CREATE FULLTEXT INDEX chunk_fulltext" in schema_content

    def test_composite_indexes(self, schema_content):
        """Test composite indexes are defined."""
        assert "CREATE INDEX entity_type_name" in schema_content
        assert "CREATE INDEX chunk_doc_position" in schema_content

    def test_idempotent_statements(self, schema_content):
        """Test all CREATE statements use IF NOT EXISTS for idempotency."""
        create_statements = re.findall(r"CREATE (CONSTRAINT|INDEX|FULLTEXT)", schema_content)
        if_not_exists = re.findall(r"IF NOT EXISTS", schema_content)
        assert len(create_statements) == len(if_not_exists), \
            "All CREATE statements should have IF NOT EXISTS"


class TestMigrationSyntax:
    """Test migration files have valid Cypher syntax patterns."""

    MIGRATIONS_DIR = Path(__file__).parent.parent / "migrations" / "neo4j"

    @pytest.fixture
    def all_migrations(self):
        """Load all migration files."""
        migrations = {}
        for f in sorted(self.MIGRATIONS_DIR.glob("*.cypher")):
            migrations[f.name] = f.read_text()
        return migrations

    def test_no_drop_statements(self, all_migrations):
        """Test migrations don't contain DROP statements (safety check)."""
        for name, content in all_migrations.items():
            assert "DROP" not in content.upper(), \
                f"Migration {name} should not contain DROP statements"

    def test_no_delete_statements(self, all_migrations):
        """Test migrations don't contain DELETE statements (safety check)."""
        for name, content in all_migrations.items():
            # Allow DELETE in comments (validation queries)
            lines = [l for l in content.split('\n') if not l.strip().startswith('//')]
            non_comment_content = '\n'.join(lines)
            assert "DELETE" not in non_comment_content.upper(), \
                f"Migration {name} should not contain DELETE statements"

    def test_valid_constraint_syntax(self, all_migrations):
        """Test CONSTRAINT statements have valid syntax."""
        constraint_pattern = r"CREATE CONSTRAINT \w+ IF NOT EXISTS\s+FOR \([a-z]+:[A-Z][a-zA-Z]+\) REQUIRE"
        for name, content in all_migrations.items():
            constraints = re.findall(r"CREATE CONSTRAINT \w+ IF NOT EXISTS", content)
            valid = re.findall(constraint_pattern, content)
            # Each constraint should match the valid pattern
            assert len(constraints) == len(valid), \
                f"Migration {name} has invalid constraint syntax"

    def test_valid_index_syntax(self, all_migrations):
        """Test INDEX statements have valid syntax."""
        # Both node and relationship index patterns
        node_index_pattern = r"CREATE INDEX \w+ IF NOT EXISTS\s+FOR \([a-z]+:[A-Z][a-zA-Z]+\) ON"
        rel_index_pattern = r"CREATE INDEX \w+ IF NOT EXISTS\s+FOR \(\)-\[r:[A-Z_]+\]-\(\) ON"

        for name, content in all_migrations.items():
            # Skip fulltext indexes which have different syntax
            content_no_fulltext = re.sub(r"CREATE FULLTEXT INDEX.*?;", "", content, flags=re.DOTALL)

            indexes = re.findall(r"CREATE INDEX \w+ IF NOT EXISTS", content_no_fulltext)
            node_valid = re.findall(node_index_pattern, content_no_fulltext)
            rel_valid = re.findall(rel_index_pattern, content_no_fulltext)

            total_valid = len(node_valid) + len(rel_valid)
            assert len(indexes) == total_valid, \
                f"Migration {name} has {len(indexes)} indexes but only {total_valid} are valid"

    def test_migrations_are_ordered(self, all_migrations):
        """Test migration files follow numeric ordering."""
        names = list(all_migrations.keys())
        expected = ["001_customer360_schema.cypher",
                    "002_document_structure_schema.cypher",
                    "003_entity_relationships.cypher"]
        assert names == expected, f"Migration files should be ordered: {expected}"


class TestSchemaCompleteness:
    """Test schema covers all required node types and relationships."""

    MIGRATIONS_DIR = Path(__file__).parent.parent / "migrations" / "neo4j"

    @pytest.fixture
    def all_content(self):
        """Load all migration content concatenated."""
        content = ""
        for f in sorted(self.MIGRATIONS_DIR.glob("*.cypher")):
            content += f.read_text() + "\n"
        return content

    def test_all_customer360_nodes(self, all_content):
        """Test all Customer 360 node types are defined."""
        required_nodes = ["Customer", "Ticket", "Order", "Interaction", "Product"]
        for node in required_nodes:
            assert f":{node})" in all_content or f":{node} " in all_content, \
                f"Node type {node} should be defined"

    def test_all_document_structure_nodes(self, all_content):
        """Test all Document Structure node types are defined."""
        required_nodes = ["Section", "DefinedTerm", "Citation"]
        for node in required_nodes:
            assert f":{node})" in all_content or f":{node} " in all_content, \
                f"Node type {node} should be defined"

    def test_all_entity_nodes(self, all_content):
        """Test all Entity node types are defined."""
        required_nodes = ["Entity", "Chunk"]
        for node in required_nodes:
            assert f":{node})" in all_content or f":{node} " in all_content, \
                f"Node type {node} should be defined"

    def test_all_customer_relationships(self, all_content):
        """Test all Customer 360 relationship types are indexed."""
        required_rels = ["HAS_DOCUMENT", "HAS_TICKET", "PLACED_ORDER",
                         "HAD_INTERACTION", "USES_PRODUCT"]
        for rel in required_rels:
            assert f":{rel}]" in all_content, \
                f"Relationship type {rel} should be indexed"

    def test_all_document_relationships(self, all_content):
        """Test all Document Structure relationship types are indexed."""
        required_rels = ["HAS_SECTION", "HAS_SUBSECTION", "PARENT_SECTION",
                         "REFERENCES_SECTION", "DEFINES_TERM", "USES_TERM"]
        for rel in required_rels:
            assert f":{rel}]" in all_content, \
                f"Relationship type {rel} should be indexed"

    def test_all_entity_relationships(self, all_content):
        """Test all Entity relationship types are indexed."""
        required_rels = ["MENTIONS", "MENTIONED_IN", "CONTAINS_ENTITY",
                         "RELATED_TO", "CO_OCCURS_WITH", "SIMILAR_TO"]
        for rel in required_rels:
            assert f":{rel}]" in all_content, \
                f"Relationship type {rel} should be indexed"
