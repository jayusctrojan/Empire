"""
RAGAS Evaluation Service for Empire v7.2

Provides core evaluation functionality for RAG pipeline quality assessment:
- RAGAS metrics evaluation (Faithfulness, Answer Relevancy, Context Precision, Context Recall)
- Batch evaluation of test datasets
- Result aggregation and formatting
- LLM configuration for evaluations

Integration with Empire architecture:
- Uses Claude via Anthropic for evaluations
- Stores results in Supabase (ragas_evaluations table)
- Supports async batch processing via Celery
"""

import os
import json
from typing import Dict, List, Any, Optional
from datetime import datetime
from datasets import Dataset

from ragas import evaluate
from ragas.metrics import (
    faithfulness,
    answer_relevancy,
    context_precision,
    context_recall
)


class RAGASEvaluator:
    """
    Core RAGAS evaluation engine for RAG pipeline quality assessment

    Supports:
    - Single and batch dataset evaluation
    - Custom metric configuration
    - Multiple LLM providers (Claude, OpenAI, etc.)
    - Result aggregation and storage
    """

    def __init__(
        self,
        metrics: Optional[List] = None,
        llm_provider: str = "anthropic",
        model: str = "claude-haiku-4-5"
    ):
        """
        Initialize RAGAS evaluator

        Args:
            metrics: List of RAGAS metrics to evaluate (defaults to all 4 core metrics)
            llm_provider: LLM provider to use ("anthropic", "openai", etc.)
            model: Specific model to use for evaluation
        """
        self.metrics = metrics or [
            faithfulness,
            answer_relevancy,
            context_precision,
            context_recall
        ]
        self.llm_provider = llm_provider
        self.model = model

    def get_metrics(self) -> List:
        """Return configured metrics"""
        return self.metrics

    def evaluate(self, dataset: Dataset) -> Dict[str, Any]:
        """
        Evaluate a dataset using RAGAS metrics

        Args:
            dataset: HuggingFace Dataset with columns:
                - question: str
                - answer: str
                - contexts: List[str]
                - ground_truth: str

        Returns:
            Dictionary with:
                - scores: Dict[str, float] - Individual metric scores
                - aggregate: float - Average score across all metrics

        Raises:
            ValueError: If dataset is empty or missing required columns
        """
        # Validate dataset
        if len(dataset) == 0:
            raise ValueError("Cannot evaluate empty dataset")

        required_columns = ["question", "answer", "contexts", "ground_truth"]
        for col in required_columns:
            if col not in dataset.column_names:
                raise ValueError(f"Dataset missing required column: {col}")

        # Run RAGAS evaluation
        try:
            result = evaluate(
                dataset=dataset,
                metrics=self.metrics
            )

            # Extract scores
            scores = {}
            for metric in self.metrics:
                metric_name = metric.name if hasattr(metric, 'name') else str(metric).split('.')[-1].replace('>', '')

                # Try different ways to get the score
                if metric_name in result:
                    scores[metric_name] = float(result[metric_name])
                elif hasattr(result, metric_name):
                    scores[metric_name] = float(getattr(result, metric_name))
                else:
                    # Fallback: search for metric name in result keys
                    for key in result.keys():
                        if metric_name.lower() in key.lower():
                            scores[metric_name] = float(result[key])
                            break

            # Calculate aggregate score
            aggregate = sum(scores.values()) / len(scores) if scores else 0.0

            return {
                "scores": scores,
                "aggregate": aggregate
            }

        except Exception as e:
            # Re-raise with context
            raise Exception(f"RAGAS evaluation failed: {str(e)}") from e

    def evaluate_batch(
        self,
        samples: List[Dict[str, Any]],
        limit: Optional[int] = None
    ) -> List[Dict[str, Any]]:
        """
        Evaluate a batch of samples with per-sample scores

        Args:
            samples: List of sample dictionaries with keys:
                - id: Sample identifier
                - question: str
                - ground_truth: str
                - contexts: List[str]
            limit: Optional limit on number of samples to evaluate

        Returns:
            List of results, each containing:
                - sample_id: str
                - scores: Dict[str, float]
        """
        # Apply limit if specified
        if limit is not None:
            samples = samples[:limit]

        results = []

        for sample in samples:
            # Create single-sample dataset
            sample_dataset = Dataset.from_dict({
                "question": [sample["question"]],
                "answer": [sample.get("ground_truth", "")],  # Use ground_truth as placeholder
                "contexts": [sample["contexts"]],
                "ground_truth": [sample["ground_truth"]]
            })

            # Evaluate single sample
            try:
                eval_result = self.evaluate(sample_dataset)

                results.append({
                    "sample_id": sample.get("id", f"sample_{len(results)}"),
                    "scores": eval_result["scores"]
                })
            except Exception as e:
                # Log error but continue with other samples
                print(f"Error evaluating sample {sample.get('id')}: {str(e)}")
                continue

        return results


def aggregate_results(sample_results: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Aggregate per-sample results into overall statistics

    Args:
        sample_results: List of per-sample evaluation results

    Returns:
        Dictionary with:
            - average_scores: Dict[str, float] - Average score per metric
            - total_samples: int
            - timestamp: str - ISO format timestamp
    """
    if not sample_results:
        return {
            "average_scores": {},
            "total_samples": 0,
            "timestamp": datetime.utcnow().isoformat() + "Z"
        }

    # Collect all metric names
    metric_names = set()
    for result in sample_results:
        metric_names.update(result["scores"].keys())

    # Calculate averages
    average_scores = {}
    for metric_name in metric_names:
        scores = [
            result["scores"][metric_name]
            for result in sample_results
            if metric_name in result["scores"]
        ]
        average_scores[metric_name] = sum(scores) / len(scores) if scores else 0.0

    return {
        "average_scores": average_scores,
        "total_samples": len(sample_results),
        "timestamp": datetime.utcnow().isoformat() + "Z"
    }


def format_results_for_storage(evaluation_results: Dict[str, Any]) -> Dict[str, Any]:
    """
    Format evaluation results for Supabase storage

    Args:
        evaluation_results: Results from aggregate_results()

    Returns:
        Dictionary ready for insertion into ragas_evaluations table
    """
    return {
        "average_scores": evaluation_results.get("average_scores", {}),
        "aggregate_score": sum(evaluation_results.get("average_scores", {}).values()) / len(evaluation_results.get("average_scores", {})) if evaluation_results.get("average_scores") else 0.0,
        "total_samples": evaluation_results.get("total_samples", 0),
        "evaluated_at": evaluation_results.get("timestamp", datetime.utcnow().isoformat() + "Z")
    }
