import pytest

pytest.importorskip("langgraph")

"""Graph routing tests that do not require any API calls."""
from src.graph.workflow import route_after_input, route_after_planner, route_after_react


def test_valid_input_routes_to_context_understanding():
    """Valid input should go to LLM1 context understanding."""
    state = {"user_input": "Deployment completed but changes are not reflecting in Prod."}
    assert route_after_input(state) == "context_understanding"


def test_planner_can_select_external_only():
    """The planner is allowed to choose only the external worker; internal is not forced."""
    state = {
        "research_plan": {
            "selected_workers": [
                {
                    "role": "external_research",
                    "objective": "Check current Kafka migration guidance.",
                    "queries": ["Kafka 4.0 authentication migration"],
                }
            ],
        }
    }
    routes = route_after_planner(state)
    assert len(routes) == 1
    assert getattr(routes[0], "node", None) == "specialist_worker"


def test_planner_routes_to_workers_without_pre_research_clarification():
    """Planner routing should never interrupt for clarification before research."""
    state = {
        "research_plan": {
            "selected_workers": [
                {
                    "role": "internal_knowledge",
                    "objective": "Find relevant deployment evidence.",
                    "queries": ["REL-10250 deployment server startup"],
                }
            ]
        }
    }
    routes = route_after_planner(state)
    assert len(routes) == 1
    assert getattr(routes[0], "node", None) == "specialist_worker"


def test_react_routes_to_clarification_when_required():
    state = {
        "react_decision": {
            "require_clarification": True,
            "clarification_question": "Was migration MIG-4821 completed?",
        },
        "clarification_count": 0,
    }
    assert route_after_react(state) == "ask_clarification"


def test_react_routes_to_recommendation_when_clarification_is_not_required():
    state = {
        "react_decision": {
            "require_clarification": False,
        },
        "clarification_count": 0,
    }
    assert route_after_react(state) == "recommendation_agent"


def test_react_routes_to_recommendation_after_clarification_limit():
    state = {
        "react_decision": {
            "require_clarification": True,
            "clarification_question": "Was migration MIG-4821 completed?",
        },
        "clarification_count": 2,
    }
    assert route_after_react(state) == "recommendation_agent"
