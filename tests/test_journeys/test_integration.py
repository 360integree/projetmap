"""Integration tests for user journey detection."""

import json
import tempfile
from pathlib import Path

from projetmap.journeys import detect_journeys
from projetmap.journeys.html_export import export_journeys_html
from projetmap.journeys.models import JourneyReport
from projetmap.journeys.report import export_journeys_report


def _make_graph_data():
    """Build a realistic graph data dict for testing."""
    return {
        "entities": [
            {"id": "route:/", "type": "route", "name": "/", "file": "lib/main.dart", "line": 10, "metadata": {}},
            {"id": "route:/checkout", "type": "route", "name": "/checkout", "file": "lib/main.dart", "line": 15, "metadata": {}},
            {"id": "HomeScreen", "type": "class", "name": "HomeScreen", "file": "lib/screens/home.dart", "line": 5, "metadata": {}},
            {"id": "CheckoutScreen", "type": "class", "name": "CheckoutScreen", "file": "lib/screens/checkout.dart", "line": 5, "metadata": {}},
            {"id": "onCheckoutPressed", "type": "function", "name": "onCheckoutPressed", "file": "lib/screens/home.dart", "line": 20, "metadata": {}},
            {"id": "onSubmit", "type": "function", "name": "onSubmit", "file": "lib/screens/checkout.dart", "line": 25, "metadata": {}},
            {"id": "CheckoutService", "type": "class", "name": "CheckoutService", "file": "lib/services/checkout.dart", "line": 10, "metadata": {}},
            {"id": "processCheckout", "type": "function", "name": "processCheckout", "file": "lib/services/checkout.dart", "line": 30, "metadata": {}},
            {"id": "PaymentGateway", "type": "class", "name": "PaymentGateway", "file": "lib/services/payment.dart", "line": 10, "metadata": {}},
            {"id": "charge", "type": "function", "name": "charge", "file": "lib/services/payment.dart", "line": 20, "metadata": {}},
            {"id": "OrderRepository", "type": "class", "name": "OrderRepository", "file": "lib/repositories/order.dart", "line": 10, "metadata": {}},
            {"id": "saveOrder", "type": "function", "name": "saveOrder", "file": "lib/repositories/order.dart", "line": 25, "metadata": {}},
            {"id": "Navigator", "type": "class", "name": "Navigator", "file": "lib/navigation.dart", "line": 5, "metadata": {}},
            {"id": "push", "type": "function", "name": "push", "file": "lib/navigation.dart", "line": 15, "metadata": {}},
            {"id": "setState", "type": "function", "name": "setState", "file": "lib/screens/checkout.dart", "line": 40, "metadata": {}},
            {"id": "fetchUser", "type": "function", "name": "fetchUser", "file": "lib/services/user.dart", "line": 20, "metadata": {}},
        ],
        "relationships": [
            {"source": "HomeScreen", "target": "onCheckoutPressed", "type": "calls", "confidence": "EXTRACTED", "evidence": "", "line": 0},
            {"source": "onCheckoutPressed", "target": "CheckoutService", "type": "calls", "confidence": "EXTRACTED", "evidence": "", "line": 0},
            {"source": "CheckoutService", "target": "processCheckout", "type": "calls", "confidence": "EXTRACTED", "evidence": "", "line": 0},
            {"source": "processCheckout", "target": "PaymentGateway", "type": "calls", "confidence": "EXTRACTED", "evidence": "", "line": 0},
            {"source": "PaymentGateway", "target": "charge", "type": "calls", "confidence": "EXTRACTED", "evidence": "", "line": 0},
            {"source": "charge", "target": "OrderRepository", "type": "calls", "confidence": "EXTRACTED", "evidence": "", "line": 0},
            {"source": "OrderRepository", "target": "saveOrder", "type": "calls", "confidence": "EXTRACTED", "evidence": "", "line": 0},
            {"source": "saveOrder", "target": "setState", "type": "calls", "confidence": "EXTRACTED", "evidence": "", "line": 0},
            {"source": "CheckoutScreen", "target": "onSubmit", "type": "calls", "confidence": "EXTRACTED", "evidence": "", "line": 0},
            {"source": "onSubmit", "target": "CheckoutService", "type": "calls", "confidence": "EXTRACTED", "evidence": "", "line": 0},
        ],
        "clusters": [],
        "metadata": {"entity_count": 16, "relationship_count": 10},
    }


class TestFullDetection:
    def test_detect_journeys(self):
        graph_data = _make_graph_data()
        report = detect_journeys(graph_data)
        assert isinstance(report, JourneyReport)
        assert report.total_journeys >= 1
        assert len(report.journeys) >= 1

    def test_journey_has_steps(self):
        graph_data = _make_graph_data()
        report = detect_journeys(graph_data)
        for journey in report.journeys:
            assert len(journey.steps) >= 3
            assert journey.confidence > 0

    def test_journey_feature_grouping(self):
        graph_data = _make_graph_data()
        report = detect_journeys(graph_data)
        assert len(report.by_feature) >= 1


class TestHTMLExport:
    def test_export_html(self):
        graph_data = _make_graph_data()
        report = detect_journeys(graph_data)

        with tempfile.NamedTemporaryFile(suffix=".html", delete=False) as f:
            output_path = Path(f.name)

        export_journeys_html(report, output_path)
        assert output_path.exists()
        content = output_path.read_text()
        assert "vis.js" in content or "vis-network" in content
        assert "User Journeys" in content

        output_path.unlink()


class TestMarkdownReport:
    def test_export_report(self):
        graph_data = _make_graph_data()
        report = detect_journeys(graph_data)

        with tempfile.NamedTemporaryFile(suffix=".md", delete=False) as f:
            output_path = Path(f.name)

        export_journeys_report(report, output_path)
        assert output_path.exists()
        content = output_path.read_text()
        assert "# User Journeys" in content

        output_path.unlink()


class TestJSONExport:
    def test_to_dict(self):
        graph_data = _make_graph_data()
        report = detect_journeys(graph_data)
        d = report.to_dict()
        assert "journeys" in d
        assert "summary" in d
        assert d["summary"]["total_journeys"] >= 1
        # Verify JSON serializable
        json_str = json.dumps(d, default=str)
        assert len(json_str) > 0


class TestEdgeCases:
    def test_empty_graph(self):
        graph_data = {"entities": [], "relationships": [], "clusters": [], "metadata": {}}
        report = detect_journeys(graph_data)
        assert report.total_journeys == 0

    def test_no_ui_entry_points(self):
        graph_data = {
            "entities": [
                {"id": "UserService", "type": "class", "name": "UserService", "file": "lib/service.dart", "line": 10, "metadata": {}},
            ],
            "relationships": [],
            "clusters": [],
            "metadata": {"entity_count": 1, "relationship_count": 0},
        }
        report = detect_journeys(graph_data)
        assert report.total_journeys == 0

    def test_short_journey_filtered(self):
        """Journeys with <3 steps should be filtered out."""
        graph_data = {
            "entities": [
                {"id": "route:/test", "type": "route", "name": "/test", "file": "lib/main.dart", "line": 10, "metadata": {}},
                {"id": "TestScreen", "type": "class", "name": "TestScreen", "file": "lib/test.dart", "line": 5, "metadata": {}},
                {"id": "onTap", "type": "function", "name": "onTap", "file": "lib/test.dart", "line": 15, "metadata": {}},
            ],
            "relationships": [
                {"source": "TestScreen", "target": "onTap", "type": "calls", "confidence": "EXTRACTED", "evidence": "", "line": 0},
            ],
            "clusters": [],
            "metadata": {"entity_count": 3, "relationship_count": 1},
        }
        report = detect_journeys(graph_data)
        # Only 2 steps (route + handler), should be filtered
        assert report.total_journeys == 0
