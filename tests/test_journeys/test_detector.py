"""Unit tests for journey detector and classifier."""


from projetmap.journeys.classifier import classify_step
from projetmap.journeys.detector import JourneyDetector, _esc
from projetmap.journeys.models import StepType

# ── Classifier Tests ──────────────────────────────────────────────────


class TestClassifyStep:
    def test_route_is_ui_entry(self):
        entity = {"name": "HomeScreen", "type": "route", "file": "lib/main.dart"}
        result = classify_step("route:/home", entity, set())
        assert result == StepType.UI_ENTRY

    def test_screen_class_is_ui_entry(self):
        entity = {"name": "CheckoutScreen", "type": "class", "file": "lib/checkout.dart"}
        result = classify_step("CheckoutScreen", entity, set())
        assert result == StepType.UI_ENTRY

    def test_page_class_is_ui_entry(self):
        entity = {"name": "LoginPage", "type": "class", "file": "lib/auth.dart"}
        result = classify_step("LoginPage", entity, set())
        assert result == StepType.UI_ENTRY

    def test_handler_onpressed(self):
        entity = {"name": "onPressed", "type": "function", "file": "lib/checkout.dart"}
        result = classify_step("onPressed", entity, set())
        assert result == StepType.HANDLER

    def test_handler_handlesubmit(self):
        entity = {"name": "handleSubmit", "type": "function", "file": "lib/form.dart"}
        result = classify_step("handleSubmit", entity, set())
        assert result == StepType.HANDLER

    def test_state_update_setstate(self):
        entity = {"name": "setState", "type": "function", "file": "lib/widget.dart"}
        result = classify_step("setState", entity, set())
        assert result == StepType.STATE_UPDATE

    def test_state_update_notifylisteners(self):
        entity = {"name": "notifyListeners", "type": "function", "file": "lib/model.dart"}
        result = classify_step("notifyListeners", entity, set())
        assert result == StepType.STATE_UPDATE

    def test_navigation_push(self):
        entity = {"name": "push", "type": "function", "file": "lib/nav.dart"}
        result = classify_step("push", entity, set())
        assert result == StepType.NAVIGATION

    def test_navigation_by_routes_to_edge(self):
        entity = {"name": "goToCheckout", "type": "function", "file": "lib/nav.dart"}
        result = classify_step("goToCheckout", entity, {"routes_to"})
        assert result == StepType.NAVIGATION

    def test_service_call_default(self):
        entity = {"name": "processOrder", "type": "function", "file": "lib/service.dart"}
        result = classify_step("processOrder", entity, {"calls"})
        assert result == StepType.SERVICE_CALL

    def test_api_call_pattern(self):
        entity = {"name": "fetchUsers", "type": "function", "file": "lib/api.dart"}
        result = classify_step("fetchUsers", entity, set())
        assert result == StepType.API_CALL


# ── Detector Tests ────────────────────────────────────────────────────


class TestJourneyDetector:
    def setup_method(self):
        self.detector = JourneyDetector()

    def test_find_ui_entry_points_routes(self):
        entities = {
            "route:/home": {"id": "route:/home", "type": "route", "name": "/home", "file": "lib/main.dart"},
            "UserService": {"id": "UserService", "type": "class", "name": "UserService", "file": "lib/service.dart"},
        }
        relationships = []
        eps = self.detector._find_ui_entry_points(entities, relationships)
        assert len(eps) == 1
        assert eps[0]["id"] == "route:/home"

    def test_find_ui_entry_points_screen_class(self):
        entities = {
            "CheckoutScreen": {"id": "CheckoutScreen", "type": "class", "name": "CheckoutScreen", "file": "lib/checkout.dart"},
            "OrderService": {"id": "OrderService", "type": "class", "name": "OrderService", "file": "lib/service.dart"},
        }
        relationships = []
        eps = self.detector._find_ui_entry_points(entities, relationships)
        assert len(eps) == 1
        assert eps[0]["id"] == "CheckoutScreen"

    def test_find_event_handlers(self):
        entities = {
            "HomeScreen": {"id": "HomeScreen", "type": "class", "name": "HomeScreen", "file": "lib/home.dart"},
            "onPressed": {"id": "onPressed", "type": "function", "name": "onPressed", "file": "lib/home.dart"},
            "onChanged": {"id": "onChanged", "type": "function", "name": "onChanged", "file": "lib/home.dart"},
            "unrelated": {"id": "unrelated", "type": "function", "name": "processData", "file": "lib/home.dart"},
        }
        relationships = [
            {"source": "HomeScreen", "target": "onPressed", "type": "calls"},
        ]
        handlers = self.detector._find_event_handlers("HomeScreen", entities, relationships)
        assert len(handlers) == 2
        # onPressed should have higher confidence (has direct call)
        pressed = next(h for h in handlers if h["id"] == "onPressed")
        assert pressed["confidence"] == 0.8

    def test_trace_journey(self):
        entities = {
            "CheckoutScreen": {"id": "CheckoutScreen", "type": "class", "name": "CheckoutScreen", "file": "lib/checkout.dart"},
            "onPressed": {"id": "onPressed", "type": "function", "name": "onPressed", "file": "lib/checkout.dart"},
            "OrderService": {"id": "OrderService", "type": "class", "name": "OrderService", "file": "lib/service.dart"},
            "OrderRepository": {"id": "OrderRepository", "type": "class", "name": "OrderRepository", "file": "lib/repo.dart"},
            "setState": {"id": "setState", "type": "function", "name": "setState", "file": "lib/checkout.dart"},
        }
        relationships = [
            {"source": "CheckoutScreen", "target": "onPressed", "type": "calls"},
            {"source": "onPressed", "target": "OrderService", "type": "calls"},
            {"source": "OrderService", "target": "OrderRepository", "type": "calls"},
            {"source": "OrderRepository", "target": "setState", "type": "calls"},
        ]
        steps = self.detector._trace_journey("onPressed", entities, relationships)
        step_ids = [s["id"] for s in steps]
        assert "onPressed" in step_ids
        assert "OrderService" in step_ids
        assert "OrderRepository" in step_ids
        assert "setState" in step_ids

    def test_full_detection(self):
        graph_data = {
            "entities": [
                {"id": "route:/checkout", "type": "route", "name": "/checkout", "file": "lib/main.dart", "line": 10, "metadata": {}},
                {"id": "CheckoutScreen", "type": "class", "name": "CheckoutScreen", "file": "lib/checkout.dart", "line": 5, "metadata": {}},
                {"id": "onPressed", "type": "function", "name": "onPressed", "file": "lib/checkout.dart", "line": 15, "metadata": {}},
                {"id": "OrderService", "type": "class", "name": "OrderService", "file": "lib/service.dart", "line": 10, "metadata": {}},
                {"id": "processOrder", "type": "function", "name": "processOrder", "file": "lib/service.dart", "line": 20, "metadata": {}},
                {"id": "OrderRepository", "type": "class", "name": "OrderRepository", "file": "lib/repo.dart", "line": 10, "metadata": {}},
                {"id": "saveOrder", "type": "function", "name": "saveOrder", "file": "lib/repo.dart", "line": 20, "metadata": {}},
                {"id": "setState", "type": "function", "name": "setState", "file": "lib/checkout.dart", "line": 30, "metadata": {}},
            ],
            "relationships": [
                {"source": "CheckoutScreen", "target": "onPressed", "type": "calls", "confidence": "EXTRACTED", "evidence": "", "line": 0},
                {"source": "onPressed", "target": "OrderService", "type": "calls", "confidence": "EXTRACTED", "evidence": "", "line": 0},
                {"source": "OrderService", "target": "processOrder", "type": "calls", "confidence": "EXTRACTED", "evidence": "", "line": 0},
                {"source": "processOrder", "target": "OrderRepository", "type": "calls", "confidence": "EXTRACTED", "evidence": "", "line": 0},
                {"source": "OrderRepository", "target": "saveOrder", "type": "calls", "confidence": "EXTRACTED", "evidence": "", "line": 0},
                {"source": "saveOrder", "target": "setState", "type": "calls", "confidence": "EXTRACTED", "evidence": "", "line": 0},
            ],
        }
        report = self.detector.detect(graph_data)
        assert report.total_journeys >= 1
        assert len(report.journeys[0].steps) >= 3

    def test_deduplication(self):
        journeys_data = {
            "entities": [
                {"id": "route:/home", "type": "route", "name": "/home", "file": "lib/main.dart", "line": 10, "metadata": {}},
                {"id": "HomeScreen", "type": "class", "name": "HomeScreen", "file": "lib/home.dart", "line": 5, "metadata": {}},
                {"id": "onPressed", "type": "function", "name": "onPressed", "file": "lib/home.dart", "line": 15, "metadata": {}},
                {"id": "AuthService", "type": "class", "name": "AuthService", "file": "lib/auth.dart", "line": 10, "metadata": {}},
                {"id": "login", "type": "function", "name": "login", "file": "lib/auth.dart", "line": 20, "metadata": {}},
                {"id": "fetchUser", "type": "function", "name": "fetchUser", "file": "lib/auth.dart", "line": 30, "metadata": {}},
                {"id": "setState", "type": "function", "name": "setState", "file": "lib/home.dart", "line": 40, "metadata": {}},
            ],
            "relationships": [
                {"source": "HomeScreen", "target": "onPressed", "type": "calls", "confidence": "EXTRACTED", "evidence": "", "line": 0},
                {"source": "onPressed", "target": "AuthService", "type": "calls", "confidence": "EXTRACTED", "evidence": "", "line": 0},
                {"source": "AuthService", "target": "login", "type": "calls", "confidence": "EXTRACTED", "evidence": "", "line": 0},
                {"source": "login", "target": "fetchUser", "type": "calls", "confidence": "EXTRACTED", "evidence": "", "line": 0},
                {"source": "fetchUser", "target": "setState", "type": "calls", "confidence": "EXTRACTED", "evidence": "", "line": 0},
            ],
        }
        report = self.detector.detect(journeys_data)
        # Should have at least one journey
        assert report.total_journeys >= 1


# ── Model Tests ───────────────────────────────────────────────────────


class TestJourneyReport:
    def test_to_dict(self):
        from projetmap.journeys.models import Journey, JourneyReport, JourneyStep

        step = JourneyStep(
            id="test_step",
            node_id="test_step",
            step_type=StepType.HANDLER,
            name="onPressed",
            file="lib/test.dart",
            line=10,
        )
        journey = Journey(
            id="test_journey",
            name="Test Flow",
            feature="Test",
            steps=[step],
            entry_point="route:/test",
            confidence=0.85,
        )
        report = JourneyReport(
            journeys=[journey],
            total_journeys=1,
            by_feature={"Test": 1},
            by_step_type={"handler": 1},
            files_analyzed=5,
        )
        d = report.to_dict()
        assert d["summary"]["total_journeys"] == 1
        assert d["journeys"][0]["name"] == "Test Flow"
        assert d["journeys"][0]["steps"][0]["step_type"] == "handler"


# ── Utility Tests ─────────────────────────────────────────────────────


class TestEsc:
    def test_esc_slashes(self):
        assert _esc("lib/main.dart") == "lib_main_dart"

    def test_esc_dashes(self):
        assert _esc("my-module") == "my_module"

    def test_esc_spaces(self):
        assert _esc("my module") == "my_module"
