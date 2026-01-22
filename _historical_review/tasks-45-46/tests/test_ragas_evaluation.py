"""
Tests for RAGAS Core Metrics Evaluation Logic

Tests the core evaluation engine:
- Running RAGAS evaluations with 4 metrics
- Processing evaluation results
- Calculating aggregate scores
- Error handling and validation
"""

import pytest
import json
from pathlib import Path
from typing import Dict, List, Any
from unittest.mock import Mock, patch, MagicMock


class TestRAGASEvaluationEngine:
    """Test core RAGAS evaluation functionality"""

    @pytest.fixture
    def sample_evaluation_input(self):
        """Sample input for RAGAS evaluation"""
        return {
            "question": ["What is Empire v7.2?"],
            "answer": ["Empire v7.2 is a hybrid RAG system using PostgreSQL and Neo4j."],
            "contexts": [["Empire v7.2 uses a hybrid database architecture with PostgreSQL for vector search and Neo4j for knowledge graphs."]],
            "ground_truth": ["Empire v7.2 is a hybrid RAG system using PostgreSQL and Neo4j."]
        }

    @pytest.fixture
    def expected_metrics(self):
        """Expected RAGAS metrics to evaluate"""
        return ["faithfulness", "answer_relevancy", "context_precision", "context_recall"]

    def test_ragas_evaluator_class_exists(self):
        """Test RAGASEvaluator class can be imported"""
        try:
            from app.services.ragas_evaluation import RAGASEvaluator
            assert RAGASEvaluator is not None
        except ImportError as e:
            pytest.fail(f"Failed to import RAGASEvaluator: {e}")

    def test_evaluator_initialization(self):
        """Test RAGASEvaluator can be initialized"""
        from app.services.ragas_evaluation import RAGASEvaluator

        evaluator = RAGASEvaluator()
        assert evaluator is not None

    def test_evaluator_has_evaluate_method(self):
        """Test RAGASEvaluator has evaluate method"""
        from app.services.ragas_evaluation import RAGASEvaluator

        evaluator = RAGASEvaluator()
        assert hasattr(evaluator, 'evaluate')
        assert callable(evaluator.evaluate)

    @patch('app.services.ragas_evaluation.evaluate')
    def test_evaluate_returns_results(self, mock_evaluate, sample_evaluation_input):
        """Test evaluate method returns structured results"""
        from app.services.ragas_evaluation import RAGASEvaluator
        from datasets import Dataset

        # Mock RAGAS evaluate response
        mock_evaluate.return_value = {
            'faithfulness': 0.95,
            'answer_relevancy': 0.90,
            'context_precision': 0.85,
            'context_recall': 0.88
        }

        evaluator = RAGASEvaluator()
        dataset = Dataset.from_dict(sample_evaluation_input)

        results = evaluator.evaluate(dataset)

        assert results is not None
        assert isinstance(results, dict)
        assert 'scores' in results
        assert 'aggregate' in results

    @patch('app.services.ragas_evaluation.evaluate')
    def test_evaluate_contains_all_metrics(self, mock_evaluate, sample_evaluation_input, expected_metrics):
        """Test evaluation results contain all 4 metrics"""
        from app.services.ragas_evaluation import RAGASEvaluator
        from datasets import Dataset

        mock_evaluate.return_value = {
            'faithfulness': 0.95,
            'answer_relevancy': 0.90,
            'context_precision': 0.85,
            'context_recall': 0.88
        }

        evaluator = RAGASEvaluator()
        dataset = Dataset.from_dict(sample_evaluation_input)

        results = evaluator.evaluate(dataset)

        for metric in expected_metrics:
            assert metric in results['scores'], f"Missing metric: {metric}"

    @patch('app.services.ragas_evaluation.evaluate')
    def test_evaluate_scores_in_valid_range(self, mock_evaluate, sample_evaluation_input):
        """Test all metric scores are between 0 and 1"""
        from app.services.ragas_evaluation import RAGASEvaluator
        from datasets import Dataset

        mock_evaluate.return_value = {
            'faithfulness': 0.95,
            'answer_relevancy': 0.90,
            'context_precision': 0.85,
            'context_recall': 0.88
        }

        evaluator = RAGASEvaluator()
        dataset = Dataset.from_dict(sample_evaluation_input)

        results = evaluator.evaluate(dataset)

        for metric, score in results['scores'].items():
            assert 0 <= score <= 1, f"Score for {metric} out of range: {score}"

    @patch('app.services.ragas_evaluation.evaluate')
    def test_evaluate_calculates_aggregate_score(self, mock_evaluate, sample_evaluation_input):
        """Test aggregate score is calculated as average of all metrics"""
        from app.services.ragas_evaluation import RAGASEvaluator
        from datasets import Dataset

        mock_scores = {
            'faithfulness': 0.95,
            'answer_relevancy': 0.90,
            'context_precision': 0.85,
            'context_recall': 0.88
        }
        mock_evaluate.return_value = mock_scores

        evaluator = RAGASEvaluator()
        dataset = Dataset.from_dict(sample_evaluation_input)

        results = evaluator.evaluate(dataset)

        expected_avg = sum(mock_scores.values()) / len(mock_scores)
        assert 'aggregate' in results
        assert abs(results['aggregate'] - expected_avg) < 0.01

    def test_evaluate_handles_empty_dataset(self):
        """Test evaluation handles empty dataset gracefully"""
        from app.services.ragas_evaluation import RAGASEvaluator
        from datasets import Dataset

        evaluator = RAGASEvaluator()
        empty_dataset = Dataset.from_dict({
            "question": [],
            "answer": [],
            "contexts": [],
            "ground_truth": []
        })

        with pytest.raises(ValueError, match="empty|no data"):
            evaluator.evaluate(empty_dataset)

    @patch('app.services.ragas_evaluation.evaluate')
    def test_evaluate_handles_api_errors(self, mock_evaluate, sample_evaluation_input):
        """Test evaluation handles API errors gracefully"""
        from app.services.ragas_evaluation import RAGASEvaluator
        from datasets import Dataset

        mock_evaluate.side_effect = Exception("API rate limit exceeded")

        evaluator = RAGASEvaluator()
        dataset = Dataset.from_dict(sample_evaluation_input)

        with pytest.raises(Exception):
            evaluator.evaluate(dataset)


class TestRAGASBatchEvaluation:
    """Test batch evaluation functionality"""

    @pytest.fixture
    def dataset_path(self):
        """Path to test dataset"""
        return Path(".taskmaster/docs/ragas_test_dataset.json")

    @pytest.fixture
    def dataset(self, dataset_path):
        """Load test dataset"""
        with open(dataset_path, 'r') as f:
            data = json.load(f)
            return data.get("test_samples", [])

    @patch('app.services.ragas_evaluation.evaluate')
    def test_batch_evaluate_full_dataset(self, mock_evaluate, dataset):
        """Test batch evaluation of full dataset"""
        from app.services.ragas_evaluation import RAGASEvaluator

        mock_evaluate.return_value = {
            'faithfulness': 0.92,
            'answer_relevancy': 0.88,
            'context_precision': 0.86,
            'context_recall': 0.90
        }

        evaluator = RAGASEvaluator()
        results = evaluator.evaluate_batch(dataset)

        assert results is not None
        assert len(results) == len(dataset)

    @patch('app.services.ragas_evaluation.evaluate')
    def test_batch_evaluate_with_limit(self, mock_evaluate, dataset):
        """Test batch evaluation with sample limit"""
        from app.services.ragas_evaluation import RAGASEvaluator

        mock_evaluate.return_value = {
            'faithfulness': 0.92,
            'answer_relevancy': 0.88,
            'context_precision': 0.86,
            'context_recall': 0.90
        }

        evaluator = RAGASEvaluator()
        limit = 5
        results = evaluator.evaluate_batch(dataset, limit=limit)

        assert len(results) == limit

    @patch('app.services.ragas_evaluation.evaluate')
    def test_batch_evaluate_returns_per_sample_scores(self, mock_evaluate, dataset):
        """Test batch evaluation returns per-sample scores"""
        from app.services.ragas_evaluation import RAGASEvaluator

        mock_evaluate.return_value = {
            'faithfulness': 0.92,
            'answer_relevancy': 0.88,
            'context_precision': 0.86,
            'context_recall': 0.90
        }

        evaluator = RAGASEvaluator()
        results = evaluator.evaluate_batch(dataset[:5])

        for result in results:
            assert 'sample_id' in result
            assert 'scores' in result
            assert all(metric in result['scores'] for metric in ['faithfulness', 'answer_relevancy', 'context_precision', 'context_recall'])


class TestRAGASResultProcessing:
    """Test RAGAS result processing and aggregation"""

    def test_aggregate_results_function_exists(self):
        """Test aggregate_results function exists"""
        try:
            from app.services.ragas_evaluation import aggregate_results
            assert aggregate_results is not None
        except ImportError as e:
            pytest.fail(f"Failed to import aggregate_results: {e}")

    def test_aggregate_results_calculates_averages(self):
        """Test aggregate_results calculates metric averages"""
        from app.services.ragas_evaluation import aggregate_results

        sample_results = [
            {
                'sample_id': 'arch_001',
                'scores': {
                    'faithfulness': 0.95,
                    'answer_relevancy': 0.90,
                    'context_precision': 0.85,
                    'context_recall': 0.88
                }
            },
            {
                'sample_id': 'arch_002',
                'scores': {
                    'faithfulness': 0.90,
                    'answer_relevancy': 0.85,
                    'context_precision': 0.80,
                    'context_recall': 0.83
                }
            }
        ]

        aggregated = aggregate_results(sample_results)

        assert 'average_scores' in aggregated
        assert 'faithfulness' in aggregated['average_scores']
        assert abs(aggregated['average_scores']['faithfulness'] - 0.925) < 0.01

    def test_aggregate_results_includes_metadata(self):
        """Test aggregate_results includes evaluation metadata"""
        from app.services.ragas_evaluation import aggregate_results

        sample_results = [
            {
                'sample_id': 'arch_001',
                'scores': {
                    'faithfulness': 0.95,
                    'answer_relevancy': 0.90,
                    'context_precision': 0.85,
                    'context_recall': 0.88
                }
            }
        ]

        aggregated = aggregate_results(sample_results)

        assert 'total_samples' in aggregated
        assert aggregated['total_samples'] == 1
        assert 'timestamp' in aggregated

    def test_format_results_for_storage(self):
        """Test formatting results for database storage"""
        from app.services.ragas_evaluation import format_results_for_storage

        evaluation_results = {
            'average_scores': {
                'faithfulness': 0.92,
                'answer_relevancy': 0.88,
                'context_precision': 0.86,
                'context_recall': 0.90
            },
            'aggregate': 0.89,
            'total_samples': 32,
            'timestamp': '2025-01-06T12:00:00Z'
        }

        formatted = format_results_for_storage(evaluation_results)

        # Should be ready for Supabase insert
        assert 'average_scores' in formatted
        assert 'aggregate_score' in formatted
        assert 'total_samples' in formatted
        assert 'evaluated_at' in formatted


class TestRAGASMetricsConfiguration:
    """Test RAGAS metrics configuration and customization"""

    def test_default_metrics_configuration(self):
        """Test default RAGAS metrics are properly configured"""
        from app.services.ragas_evaluation import RAGASEvaluator

        evaluator = RAGASEvaluator()
        metrics = evaluator.get_metrics()

        assert len(metrics) == 4
        metric_names = [m.name if hasattr(m, 'name') else str(m) for m in metrics]
        assert any('faithfulness' in str(m).lower() for m in metric_names)

    def test_custom_metrics_configuration(self):
        """Test RAGASEvaluator can use custom metrics"""
        from app.services.ragas_evaluation import RAGASEvaluator
        from ragas.metrics import faithfulness, answer_relevancy

        custom_metrics = [faithfulness, answer_relevancy]
        evaluator = RAGASEvaluator(metrics=custom_metrics)

        assert evaluator.get_metrics() == custom_metrics

    def test_llm_configuration(self):
        """Test RAGASEvaluator can configure LLM for evaluation"""
        from app.services.ragas_evaluation import RAGASEvaluator

        # Should support Claude via Anthropic
        evaluator = RAGASEvaluator(llm_provider="anthropic", model="claude-3-5-haiku-20241022")

        assert evaluator.llm_provider == "anthropic"
        assert evaluator.model == "claude-3-5-haiku-20241022"
