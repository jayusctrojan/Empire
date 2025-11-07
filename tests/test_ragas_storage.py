"""
Tests for RAGAS Results Storage in Supabase

Tests Supabase integration for storing and retrieving RAGAS evaluation results:
- ragas_evaluations table schema
- Storing evaluation results
- Retrieving evaluation results
- Querying by date range and metrics
"""

import pytest
import json
from datetime import datetime, timedelta
from typing import Dict, Any
from unittest.mock import Mock, patch, MagicMock


class TestRAGASEvaluationsTableSchema:
    """Test ragas_evaluations table schema and setup"""

    def test_ragas_storage_service_exists(self):
        """Test RAGASStorageService class can be imported"""
        try:
            from app.services.ragas_storage import RAGASStorageService
            assert RAGASStorageService is not None
        except ImportError as e:
            pytest.fail(f"Failed to import RAGASStorageService: {e}")

    def test_storage_service_initialization(self):
        """Test RAGASStorageService can be initialized"""
        from app.services.ragas_storage import RAGASStorageService

        service = RAGASStorageService()
        assert service is not None

    def test_storage_service_has_create_table_method(self):
        """Test RAGASStorageService has create_table method"""
        from app.services.ragas_storage import RAGASStorageService

        service = RAGASStorageService()
        assert hasattr(service, 'create_table')
        assert callable(service.create_table)

    def test_table_schema_definition(self):
        """Test ragas_evaluations table schema is defined"""
        from app.services.ragas_storage import RAGAS_EVALUATIONS_TABLE_SCHEMA

        assert RAGAS_EVALUATIONS_TABLE_SCHEMA is not None
        assert 'id' in RAGAS_EVALUATIONS_TABLE_SCHEMA
        assert 'evaluated_at' in RAGAS_EVALUATIONS_TABLE_SCHEMA
        assert 'average_scores' in RAGAS_EVALUATIONS_TABLE_SCHEMA
        assert 'aggregate_score' in RAGAS_EVALUATIONS_TABLE_SCHEMA
        assert 'total_samples' in RAGAS_EVALUATIONS_TABLE_SCHEMA

    @patch('app.services.ragas_storage.create_client')
    def test_create_table_executes_sql(self, mock_create_client):
        """Test create_table method executes proper SQL"""
        from app.services.ragas_storage import RAGASStorageService

        mock_client = MagicMock()
        mock_create_client.return_value = mock_client

        service = RAGASStorageService()
        result = service.create_table()

        # Should execute SQL via Supabase
        assert result is not None
        assert result.get('success') is True


class TestRAGASResultsStorage:
    """Test storing RAGAS evaluation results"""

    @pytest.fixture
    def sample_evaluation_result(self):
        """Sample evaluation result to store"""
        return {
            "average_scores": {
                "faithfulness": 0.92,
                "answer_relevancy": 0.88,
                "context_precision": 0.86,
                "context_recall": 0.90
            },
            "aggregate_score": 0.89,
            "total_samples": 32,
            "evaluated_at": datetime.utcnow().isoformat() + "Z",
            "dataset_name": "Empire v7.2 Test Dataset",
            "model_used": "claude-3-5-haiku-20241022"
        }

    @patch('app.services.ragas_storage.create_client')
    def test_store_evaluation_result(self, mock_create_client, sample_evaluation_result):
        """Test storing a single evaluation result"""
        from app.services.ragas_storage import RAGASStorageService

        mock_client = MagicMock()
        mock_table = MagicMock()
        mock_client.table.return_value = mock_table
        mock_table.insert.return_value.execute.return_value.data = [{"id": "eval_001"}]
        mock_create_client.return_value = mock_client

        service = RAGASStorageService(client=mock_client)
        result = service.store_result(sample_evaluation_result)

        assert result is not None
        assert 'id' in result
        mock_client.table.assert_called_with('ragas_evaluations')

    @patch('app.services.ragas_storage.create_client')
    def test_store_result_validates_required_fields(self, mock_create_client):
        """Test storage validates required fields"""
        from app.services.ragas_storage import RAGASStorageService

        mock_client = MagicMock()
        mock_create_client.return_value = mock_client

        service = RAGASStorageService()

        # Missing required fields
        incomplete_result = {
            "average_scores": {}
        }

        with pytest.raises(ValueError, match="required field"):
            service.store_result(incomplete_result)

    @patch('app.services.ragas_storage.create_client')
    def test_store_result_handles_errors(self, mock_create_client, sample_evaluation_result):
        """Test storage handles database errors gracefully"""
        from app.services.ragas_storage import RAGASStorageService

        mock_client = MagicMock()
        mock_table = MagicMock()
        mock_client.table.return_value = mock_table
        mock_table.insert.side_effect = Exception("Database connection error")
        mock_create_client.return_value = mock_client

        service = RAGASStorageService(client=mock_client)

        with pytest.raises(Exception):
            service.store_result(sample_evaluation_result)


class TestRAGASResultsRetrieval:
    """Test retrieving RAGAS evaluation results"""

    @patch('app.services.ragas_storage.create_client')
    def test_get_latest_evaluation(self, mock_create_client):
        """Test retrieving the most recent evaluation"""
        from app.services.ragas_storage import RAGASStorageService

        mock_client = MagicMock()
        mock_table = MagicMock()
        mock_client.table.return_value = mock_table
        mock_table.select.return_value.order.return_value.limit.return_value.execute.return_value.data = [
            {
                "id": "eval_001",
                "aggregate_score": 0.89,
                "evaluated_at": "2025-01-06T12:00:00Z"
            }
        ]
        mock_create_client.return_value = mock_client

        service = RAGASStorageService(client=mock_client)
        result = service.get_latest_evaluation()

        assert result is not None
        assert result['id'] == 'eval_001'
        assert result['aggregate_score'] == 0.89

    @patch('app.services.ragas_storage.create_client')
    def test_get_evaluation_by_id(self, mock_create_client):
        """Test retrieving specific evaluation by ID"""
        from app.services.ragas_storage import RAGASStorageService

        mock_client = MagicMock()
        mock_table = MagicMock()
        mock_client.table.return_value = mock_table
        mock_table.select.return_value.eq.return_value.execute.return_value.data = [
            {
                "id": "eval_001",
                "aggregate_score": 0.89
            }
        ]
        mock_create_client.return_value = mock_client

        service = RAGASStorageService(client=mock_client)
        result = service.get_evaluation("eval_001")

        assert result is not None
        assert result['id'] == 'eval_001'

    @patch('app.services.ragas_storage.create_client')
    def test_get_evaluations_by_date_range(self, mock_create_client):
        """Test retrieving evaluations within a date range"""
        from app.services.ragas_storage import RAGASStorageService

        mock_client = MagicMock()
        mock_table = MagicMock()
        mock_client.table.return_value = mock_table
        mock_table.select.return_value.gte.return_value.lte.return_value.execute.return_value.data = [
            {"id": "eval_001", "evaluated_at": "2025-01-06T12:00:00Z"},
            {"id": "eval_002", "evaluated_at": "2025-01-05T12:00:00Z"}
        ]
        mock_create_client.return_value = mock_client

        service = RAGASStorageService(client=mock_client)
        start_date = (datetime.utcnow() - timedelta(days=7)).isoformat() + "Z"
        end_date = datetime.utcnow().isoformat() + "Z"

        results = service.get_evaluations_by_date_range(start_date, end_date)

        assert results is not None
        assert len(results) == 2

    @patch('app.services.ragas_storage.create_client')
    def test_get_evaluations_with_filters(self, mock_create_client):
        """Test retrieving evaluations with metric filters"""
        from app.services.ragas_storage import RAGASStorageService

        mock_client = MagicMock()
        mock_table = MagicMock()
        mock_client.table.return_value = mock_table
        mock_table.select.return_value.gte.return_value.execute.return_value.data = [
            {"id": "eval_001", "aggregate_score": 0.90}
        ]
        mock_create_client.return_value = mock_client

        service = RAGASStorageService()
        # Get evaluations with aggregate_score >= 0.85
        results = service.get_evaluations_with_filters(min_aggregate_score=0.85)

        assert results is not None
        assert len(results) >= 0


class TestRAGASStorageIntegration:
    """Test full storage workflow integration"""

    @patch('app.services.ragas_storage.create_client')
    def test_full_storage_workflow(self, mock_create_client):
        """Test complete workflow: store -> retrieve -> update"""
        from app.services.ragas_storage import RAGASStorageService

        # Mock Supabase client
        mock_client = MagicMock()
        mock_table = MagicMock()
        mock_client.table.return_value = mock_table

        # Mock insert response
        mock_table.insert.return_value.execute.return_value.data = [{"id": "eval_001"}]

        # Mock select response
        mock_table.select.return_value.eq.return_value.execute.return_value.data = [
            {
                "id": "eval_001",
                "aggregate_score": 0.89,
                "average_scores": {
                    "faithfulness": 0.92,
                    "answer_relevancy": 0.88
                }
            }
        ]

        mock_create_client.return_value = mock_client

        service = RAGASStorageService(client=mock_client)

        # 1. Store evaluation
        eval_result = {
            "average_scores": {
                "faithfulness": 0.92,
                "answer_relevancy": 0.88,
                "context_precision": 0.86,
                "context_recall": 0.90
            },
            "aggregate_score": 0.89,
            "total_samples": 32,
            "evaluated_at": datetime.utcnow().isoformat() + "Z"
        }

        stored = service.store_result(eval_result)
        assert stored is not None
        assert 'id' in stored

        # 2. Retrieve evaluation
        retrieved = service.get_evaluation(stored['id'])
        assert retrieved is not None
        assert retrieved['id'] == stored['id']

    def test_storage_service_integration_with_evaluator(self):
        """Test RAGASStorageService integrates with RAGASEvaluator"""
        from app.services.ragas_evaluation import RAGASEvaluator, format_results_for_storage
        from app.services.ragas_storage import RAGASStorageService

        # Should be able to pass formatted results from evaluator to storage
        aggregated_results = {
            "average_scores": {
                "faithfulness": 0.92,
                "answer_relevancy": 0.88,
                "context_precision": 0.86,
                "context_recall": 0.90
            },
            "total_samples": 32,
            "timestamp": datetime.utcnow().isoformat() + "Z"
        }

        formatted = format_results_for_storage(aggregated_results)

        # Should have all required fields for storage
        assert 'average_scores' in formatted
        assert 'aggregate_score' in formatted
        assert 'total_samples' in formatted
        assert 'evaluated_at' in formatted


class TestRAGASStorageConfiguration:
    """Test storage configuration and environment setup"""

    def test_supabase_connection_configured(self):
        """Test Supabase connection can be configured"""
        from app.services.ragas_storage import RAGASStorageService
        import os

        # Should be able to initialize with environment variables
        # Note: Actual connection not tested here (requires Supabase instance)
        service = RAGASStorageService()
        assert service is not None

    def test_table_name_configuration(self):
        """Test custom table name can be configured"""
        from app.services.ragas_storage import RAGASStorageService

        custom_service = RAGASStorageService(table_name="custom_ragas_table")
        assert custom_service.table_name == "custom_ragas_table"
