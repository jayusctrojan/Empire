"""
RAGAS Evaluation Script for Empire v7.2
Implements automated RAG quality evaluation using RAGAS metrics
"""

import json
import os
import asyncio
from datetime import datetime
from typing import List, Dict, Optional
from pathlib import Path

# RAGAS imports
from ragas import evaluate
from ragas.metrics import (
    faithfulness,
    answer_relevancy,
    context_precision,
    context_recall
)
from datasets import Dataset

# Supabase for storage
from supabase import create_client, Client
from dotenv import load_dotenv

# Load environment variables
load_dotenv()


class RAGASEvaluator:
    """Handles RAGAS evaluation and storage for Empire RAG pipeline"""

    def __init__(
        self,
        supabase_url: str = None,
        supabase_key: str = None,
        test_dataset_path: str = ".taskmaster/docs/ragas_test_dataset.json"
    ):
        self.supabase_url = supabase_url or os.getenv("SUPABASE_URL")
        self.supabase_key = supabase_key or os.getenv("SUPABASE_SERVICE_KEY")
        self.supabase: Client = create_client(self.supabase_url, self.supabase_key)
        self.test_dataset_path = Path(test_dataset_path)

        # Configuration
        self.config_version = os.getenv("RAG_CONFIG_VERSION", "v7.2")
        self.search_method = os.getenv("SEARCH_METHOD", "hybrid_4method_rrf")
        self.reranker = os.getenv("RERANKER", "bge-reranker-v2-local")

    def load_test_dataset(self) -> Dict:
        """Load the RAGAS test dataset from JSON file"""
        with open(self.test_dataset_path, 'r') as f:
            return json.load(f)

    def prepare_ragas_dataset(self, test_samples: List[Dict]) -> Dataset:
        """
        Convert test samples to RAGAS-compatible dataset format

        RAGAS expects:
        - question: List[str]
        - contexts: List[List[str]]
        - answer: List[str]
        - ground_truth: List[str] (optional)
        """
        questions = []
        contexts = []
        answers = []
        ground_truths = []

        for sample in test_samples:
            questions.append(sample["question"])
            contexts.append(sample["contexts"])
            # For now, use ground_truth as answer (will be replaced by actual RAG output)
            answers.append(sample["ground_truth"])
            ground_truths.append(sample.get("ground_truth", ""))

        return Dataset.from_dict({
            "question": questions,
            "contexts": contexts,
            "answer": answers,
            "ground_truth": ground_truths
        })

    async def run_evaluation(
        self,
        dataset: Dataset,
        metrics: List = None
    ) -> Dict:
        """
        Run RAGAS evaluation on the dataset

        Args:
            dataset: RAGAS-compatible dataset
            metrics: List of RAGAS metrics to evaluate (default: all 4)

        Returns:
            Dictionary of evaluation results
        """
        if metrics is None:
            metrics = [
                faithfulness,
                answer_relevancy,
                context_precision,
                context_recall
            ]

        print(f"🔍 Evaluating {len(dataset)} samples with RAGAS...")
        print(f"📊 Metrics: {[m.name for m in metrics]}")

        # Run RAGAS evaluation
        # Note: RAGAS uses the LLM specified in environment (OPENAI_API_KEY or ANTHROPIC_API_KEY)
        results = evaluate(
            dataset=dataset,
            metrics=metrics
        )

        print(f"✅ Evaluation complete!")
        return results

    async def store_results(
        self,
        results: Dict,
        test_sample: Dict,
        evaluation_mode: str = "test"
    ) -> Dict:
        """
        Store RAGAS evaluation results in Supabase

        Args:
            results: RAGAS evaluation results for a single sample
            test_sample: Original test sample with metadata
            evaluation_mode: 'test', 'batch', or 'live'

        Returns:
            Inserted record from Supabase
        """
        record = {
            "created_at": datetime.utcnow().isoformat(),
            "query": test_sample["question"],
            "query_type": test_sample.get("query_type"),
            "contexts": test_sample["contexts"],
            "ground_truth": test_sample.get("ground_truth"),
            "generated_answer": test_sample.get("ground_truth"),  # Will be replaced with actual answer

            # RAGAS scores
            "faithfulness_score": results.get("faithfulness"),
            "answer_relevancy_score": results.get("answer_relevancy"),
            "context_precision_score": results.get("context_precision"),
            "context_recall_score": results.get("context_recall"),

            # Configuration
            "config_version": self.config_version,
            "search_method": self.search_method,
            "reranker": self.reranker,
            "query_expansion": True,  # Empire uses query expansion by default

            # Metadata
            "dataset_id": test_sample.get("id"),
            "is_production": False,
            "evaluation_mode": evaluation_mode,
            "metadata": {
                "category": test_sample.get("category"),
                "difficulty": test_sample.get("difficulty"),
                "expected_search_method": test_sample.get("expected_search_method")
            }
        }

        response = self.supabase.table("ragas_evaluations").insert(record).execute()
        return response.data[0] if response.data else None

    async def run_batch_evaluation(
        self,
        limit: Optional[int] = None,
        category_filter: Optional[str] = None
    ) -> Dict:
        """
        Run batch evaluation on test dataset and store results

        Args:
            limit: Maximum number of samples to evaluate
            category_filter: Filter samples by category

        Returns:
            Summary of evaluation results
        """
        # Load test dataset
        dataset_dict = self.load_test_dataset()
        test_samples = dataset_dict["test_samples"]

        # Apply filters
        if category_filter:
            test_samples = [s for s in test_samples if s["category"] == category_filter]
        if limit:
            test_samples = test_samples[:limit]

        print(f"\n🚀 Starting RAGAS Batch Evaluation")
        print(f"📦 Dataset: {dataset_dict['dataset_info']['name']}")
        print(f"📊 Samples: {len(test_samples)}")
        print(f"🏷️  Category: {category_filter or 'All'}")
        print(f"⚙️  Config: {self.config_version} / {self.search_method}\n")

        # Prepare RAGAS dataset
        ragas_dataset = self.prepare_ragas_dataset(test_samples)

        # Run evaluation
        results = await self.run_evaluation(ragas_dataset)

        # Store individual results
        print(f"\n💾 Storing results in Supabase...")
        stored_count = 0

        for i, sample in enumerate(test_samples):
            # Extract individual sample results
            sample_results = {
                "faithfulness": results["faithfulness"][i] if "faithfulness" in results else None,
                "answer_relevancy": results["answer_relevancy"][i] if "answer_relevancy" in results else None,
                "context_precision": results["context_precision"][i] if "context_precision" in results else None,
                "context_recall": results["context_recall"][i] if "context_recall" in results else None,
            }

            await self.store_results(sample_results, sample, evaluation_mode="batch")
            stored_count += 1

            if (i + 1) % 5 == 0:
                print(f"  ✓ Stored {i + 1}/{len(test_samples)} results")

        # Summary
        summary = {
            "total_samples": len(test_samples),
            "stored_count": stored_count,
            "avg_faithfulness": results["faithfulness"].mean() if "faithfulness" in results else None,
            "avg_answer_relevancy": results["answer_relevancy"].mean() if "answer_relevancy" in results else None,
            "avg_context_precision": results["context_precision"].mean() if "context_precision" in results else None,
            "avg_context_recall": results["context_recall"].mean() if "context_recall" in results else None,
            "config_version": self.config_version,
            "search_method": self.search_method
        }

        # Calculate overall average
        scores = [v for k, v in summary.items() if k.startswith('avg_') and v is not None]
        summary["avg_overall"] = sum(scores) / len(scores) if scores else None

        return summary

    async def get_latest_metrics(self, hours_back: int = 24) -> Dict:
        """Query latest RAGAS metrics from Supabase using the helper function"""
        response = self.supabase.rpc(
            "get_latest_ragas_metrics",
            {"hours_back": hours_back, "production_only": False}
        ).execute()

        return response.data if response.data else []

    async def get_low_performing_queries(
        self,
        score_threshold: float = 0.6,
        limit_count: int = 10
    ) -> List[Dict]:
        """Query low-performing queries for improvement analysis"""
        response = self.supabase.rpc(
            "get_low_performing_queries",
            {"score_threshold": score_threshold, "limit_count": limit_count}
        ).execute()

        return response.data if response.data else []


async def main():
    """Main execution function"""
    # Initialize evaluator
    evaluator = RAGASEvaluator()

    # Run batch evaluation on all samples
    print("\n" + "="*80)
    print("EMPIRE v7.2 - RAGAS EVALUATION")
    print("="*80)

    # Option 1: Run on all samples
    summary = await evaluator.run_batch_evaluation()

    # Option 2: Run on specific category with limit
    # summary = await evaluator.run_batch_evaluation(
    #     limit=10,
    #     category_filter="architecture_queries"
    # )

    # Print summary
    print("\n" + "="*80)
    print("📊 EVALUATION SUMMARY")
    print("="*80)
    print(f"Total Samples:        {summary['total_samples']}")
    print(f"Stored in Supabase:   {summary['stored_count']}")
    print(f"\n🎯 Average Scores:")
    print(f"  Faithfulness:       {summary['avg_faithfulness']:.3f}" if summary['avg_faithfulness'] else "  Faithfulness:       N/A")
    print(f"  Answer Relevancy:   {summary['avg_answer_relevancy']:.3f}" if summary['avg_answer_relevancy'] else "  Answer Relevancy:   N/A")
    print(f"  Context Precision:  {summary['avg_context_precision']:.3f}" if summary['avg_context_precision'] else "  Context Precision:  N/A")
    print(f"  Context Recall:     {summary['avg_context_recall']:.3f}" if summary['avg_context_recall'] else "  Context Recall:     N/A")
    print(f"  Overall:            {summary['avg_overall']:.3f}" if summary['avg_overall'] else "  Overall:            N/A")
    print(f"\n⚙️  Configuration:")
    print(f"  Version:            {summary['config_version']}")
    print(f"  Search Method:      {summary['search_method']}")
    print("="*80)

    # Query latest metrics
    print("\n📈 Latest Metrics (24h):")
    metrics = await evaluator.get_latest_metrics(hours_back=24)
    for metric in metrics:
        trend_icon = metric.get("trend", "")
        print(f"  {metric['metric_name']:20s}: {metric['current_score']:.3f} {trend_icon}")

    # Query low-performing queries
    print("\n⚠️  Low-Performing Queries (score < 0.6):")
    low_queries = await evaluator.get_low_performing_queries(score_threshold=0.6, limit_count=5)
    for i, query in enumerate(low_queries, 1):
        print(f"\n  {i}. Query: {query['query'][:80]}...")
        print(f"     Overall Score: {query['overall_score']:.3f}")
        print(f"     Search Method: {query['search_method']}")


if __name__ == "__main__":
    asyncio.run(main())
