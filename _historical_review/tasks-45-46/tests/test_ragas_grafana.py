"""
Tests for RAGAS Grafana Dashboard Configuration

Tests Grafana dashboard setup for RAGAS metrics visualization:
- Dashboard JSON configuration exists and is valid
- Required panels for each RAGAS metric
- Proper data source configuration
- Time range and refresh settings
"""

import pytest
import json
from pathlib import Path
from typing import Dict, Any


class TestGrafanaDashboardConfiguration:
    """Test Grafana dashboard configuration file"""

    @pytest.fixture
    def dashboard_path(self):
        """Path to RAGAS Grafana dashboard JSON"""
        return Path("monitoring/grafana/dashboards/ragas_metrics.json")

    def test_dashboard_file_exists(self, dashboard_path):
        """Test dashboard JSON file exists"""
        assert dashboard_path.exists(), f"Dashboard file not found at {dashboard_path}"

    def test_dashboard_is_valid_json(self, dashboard_path):
        """Test dashboard file is valid JSON"""
        try:
            with open(dashboard_path, 'r') as f:
                json.load(f)
        except json.JSONDecodeError as e:
            pytest.fail(f"Dashboard is not valid JSON: {e}")

    def test_dashboard_has_required_structure(self, dashboard_path):
        """Test dashboard has required Grafana structure"""
        with open(dashboard_path, 'r') as f:
            dashboard = json.load(f)

        assert 'dashboard' in dashboard or 'title' in dashboard
        assert 'panels' in dashboard or 'dashboard' in dashboard

    def test_dashboard_metadata(self, dashboard_path):
        """Test dashboard has proper metadata"""
        with open(dashboard_path, 'r') as f:
            dashboard = json.load(f)

        # Get the actual dashboard object
        dash = dashboard.get('dashboard', dashboard)

        assert 'title' in dash
        assert dash['title'] == 'RAGAS Metrics - Empire v7.2'
        assert 'tags' in dash
        assert 'ragas' in dash['tags']


class TestGrafanaDashboardPanels:
    """Test dashboard panels for RAGAS metrics"""

    @pytest.fixture
    def dashboard_path(self):
        """Path to RAGAS Grafana dashboard JSON"""
        return Path("monitoring/grafana/dashboards/ragas_metrics.json")

    @pytest.fixture
    def dashboard(self, dashboard_path):
        """Load dashboard configuration"""
        with open(dashboard_path, 'r') as f:
            return json.load(f)

    def test_dashboard_has_panels(self, dashboard):
        """Test dashboard contains panels"""
        dash = dashboard.get('dashboard', dashboard)
        assert 'panels' in dash
        assert len(dash['panels']) > 0

    def test_dashboard_has_faithfulness_panel(self, dashboard):
        """Test dashboard has Faithfulness metric panel"""
        dash = dashboard.get('dashboard', dashboard)
        panels = dash['panels']

        faithfulness_panel = None
        for panel in panels:
            if 'title' in panel and 'faithfulness' in panel['title'].lower():
                faithfulness_panel = panel
                break

        assert faithfulness_panel is not None, "Faithfulness panel not found"

    def test_dashboard_has_answer_relevancy_panel(self, dashboard):
        """Test dashboard has Answer Relevancy metric panel"""
        dash = dashboard.get('dashboard', dashboard)
        panels = dash['panels']

        relevancy_panel = None
        for panel in panels:
            if 'title' in panel and 'relevancy' in panel['title'].lower():
                relevancy_panel = panel
                break

        assert relevancy_panel is not None, "Answer Relevancy panel not found"

    def test_dashboard_has_context_precision_panel(self, dashboard):
        """Test dashboard has Context Precision metric panel"""
        dash = dashboard.get('dashboard', dashboard)
        panels = dash['panels']

        precision_panel = None
        for panel in panels:
            if 'title' in panel and 'precision' in panel['title'].lower():
                precision_panel = panel
                break

        assert precision_panel is not None, "Context Precision panel not found"

    def test_dashboard_has_context_recall_panel(self, dashboard):
        """Test dashboard has Context Recall metric panel"""
        dash = dashboard.get('dashboard', dashboard)
        panels = dash['panels']

        recall_panel = None
        for panel in panels:
            if 'title' in panel and 'recall' in panel['title'].lower():
                recall_panel = panel
                break

        assert recall_panel is not None, "Context Recall panel not found"

    def test_dashboard_has_aggregate_score_panel(self, dashboard):
        """Test dashboard has Aggregate Score panel"""
        dash = dashboard.get('dashboard', dashboard)
        panels = dash['panels']

        aggregate_panel = None
        for panel in panels:
            if 'title' in panel and 'aggregate' in panel['title'].lower():
                aggregate_panel = panel
                break

        assert aggregate_panel is not None, "Aggregate Score panel not found"


class TestGrafanaDashboardDataSource:
    """Test dashboard data source configuration"""

    @pytest.fixture
    def dashboard_path(self):
        """Path to RAGAS Grafana dashboard JSON"""
        return Path("monitoring/grafana/dashboards/ragas_metrics.json")

    @pytest.fixture
    def dashboard(self, dashboard_path):
        """Load dashboard configuration"""
        with open(dashboard_path, 'r') as f:
            return json.load(f)

    def test_panels_use_prometheus_datasource(self, dashboard):
        """Test panels are configured to use Prometheus data source"""
        dash = dashboard.get('dashboard', dashboard)
        panels = dash['panels']

        for panel in panels:
            if 'targets' in panel and len(panel['targets']) > 0:
                # At least one panel should have datasource configured
                assert 'datasource' in panel['targets'][0] or 'datasource' in panel


class TestGrafanaDashboardSettings:
    """Test dashboard general settings"""

    @pytest.fixture
    def dashboard_path(self):
        """Path to RAGAS Grafana dashboard JSON"""
        return Path("monitoring/grafana/dashboards/ragas_metrics.json")

    @pytest.fixture
    def dashboard(self, dashboard_path):
        """Load dashboard configuration"""
        with open(dashboard_path, 'r') as f:
            return json.load(f)

    def test_dashboard_has_refresh_interval(self, dashboard):
        """Test dashboard has refresh interval configured"""
        dash = dashboard.get('dashboard', dashboard)
        assert 'refresh' in dash

    def test_dashboard_has_time_range(self, dashboard):
        """Test dashboard has time range configured"""
        dash = dashboard.get('dashboard', dashboard)
        assert 'time' in dash or 'timepicker' in dash
