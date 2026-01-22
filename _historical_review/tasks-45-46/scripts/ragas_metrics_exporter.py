"""
RAGAS Metrics Exporter for Prometheus
Queries latest RAGAS metrics from Supabase and exposes them as Prometheus metrics
"""

import os
import time
import asyncio
from prometheus_client import Gauge, start_http_server, REGISTRY
from dotenv import load_dotenv
from supabase import create_client, Client

load_dotenv()

# Prometheus Gauges for RAGAS metrics
ragas_faithfulness_score = Gauge(
    'ragas_faithfulness_score',
    'RAGAS Faithfulness Score (factual consistency)'
)

ragas_answer_relevancy_score = Gauge(
    'ragas_answer_relevancy_score',
    'RAGAS Answer Relevancy Score (query alignment)'
)

ragas_context_precision_score = Gauge(
    'ragas_context_precision_score',
    'RAGAS Context Precision Score (signal-to-noise ratio)'
)

ragas_context_recall_score = Gauge(
    'ragas_context_recall_score',
    'RAGAS Context Recall Score (information completeness)'
)

ragas_aggregate_score = Gauge(
    'ragas_aggregate_score',
    'RAGAS Aggregate Score (average of all metrics)'
)


class RAGASMetricsExporter:
    """Export RAGAS metrics from Supabase to Prometheus"""

    def __init__(self):
        self.supabase: Client = create_client(
            os.getenv("SUPABASE_URL"),
            os.getenv("SUPABASE_SERVICE_KEY")
        )

    async def get_latest_metrics(self, hours_back: int = 24):
        """Query latest RAGAS metrics from Supabase"""
        try:
            response = self.supabase.rpc(
                "get_latest_ragas_metrics",
                {"hours_back": hours_back, "production_only": False}
            ).execute()

            return response.data if response.data else []
        except Exception as e:
            print(f"Error fetching metrics: {e}")
            return []

    async def update_prometheus_metrics(self):
        """Update Prometheus gauges with latest RAGAS metrics from Supabase"""
        metrics = await self.get_latest_metrics(hours_back=24)

        if not metrics:
            print("No metrics found in database")
            return

        # Map metric names to Prometheus gauges
        metric_map = {
            "Faithfulness": ragas_faithfulness_score,
            "Answer Relevancy": ragas_answer_relevancy_score,
            "Context Precision": ragas_context_precision_score,
            "Context Recall": ragas_context_recall_score,
            "Overall Score": ragas_aggregate_score
        }

        for metric in metrics:
            metric_name = metric.get("metric_name")
            current_score = metric.get("current_score")

            if metric_name in metric_map and current_score is not None:
                metric_map[metric_name].set(current_score)
                print(f"Updated {metric_name}: {current_score:.3f}")

    async def run_continuous(self, update_interval: int = 30):
        """
        Continuously update Prometheus metrics

        Args:
            update_interval: Seconds between updates (default: 30)
        """
        print(f"🚀 Starting RAGAS Metrics Exporter")
        print(f"📊 Updating every {update_interval} seconds")
        print(f"🔗 Metrics available at http://localhost:8001/metrics")

        while True:
            try:
                await self.update_prometheus_metrics()
            except Exception as e:
                print(f"Error updating metrics: {e}")

            await asyncio.sleep(update_interval)


async def main():
    """Main execution"""
    exporter = RAGASMetricsExporter()

    # Start Prometheus HTTP server on port 8001
    start_http_server(8001)
    print("✅ Prometheus metrics server started on port 8001")

    # Run continuous updates
    await exporter.run_continuous(update_interval=30)


if __name__ == "__main__":
    asyncio.run(main())
