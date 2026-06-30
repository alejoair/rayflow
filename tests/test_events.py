"""Tests for the EventBroker: fire-and-forget pub/sub with namespaces.

Communication between flows is verified using only builtin nodes: the
receiving flow (OnEvent) re-emits a 'done' event when it runs, and the test
observes it via the broker's publish counter. This avoids needing a custom
node (which wouldn't travel to the worker running the receiver).
"""
import time

import pytest
import ray

import rayflow
from rayflow.api import serve_events
from rayflow.events.bus import get_event_broker
from rayflow.nodes.registry import reset_catalog


@pytest.fixture(autouse=True)
def ray_init():
    if not ray.is_initialized():
        ray.init(ignore_reinit_error=True, namespace="rayflow")
    reset_catalog()
    yield


def _wait_count(event_name, n, timeout=20.0):
    broker = get_event_broker()
    deadline = time.time() + timeout
    while time.time() < deadline:
        c = ray.get(broker.publish_count.remote(event_name))
        if c >= n:
            return c
        time.sleep(0.3)
    return ray.get(broker.publish_count.remote(event_name))


def test_emit_triggers_onevent_of_another_flow():
    """A flow emits to 'demo/ping'; another subscribed to it runs and re-emits 'demo/done'."""
    done_event = f"demo/done/{time.time_ns()}"  # unique per run

    receiver = {
        "name": "receiver",
        "events": ["demo/ping"],
        "nodes": [
            {"id": "on", "type": "OnEvent", "inputs": {"event_name": "demo/ping"}},
            {"id": "emit_done", "type": "EmitEvent", "exec_in": "on",
             "inputs": {"event_name": done_event, "payload": "on.payload"}},
        ],
    }
    serve_events(receiver)

    sender = {
        "name": "sender",
        "nodes": [
            {"id": "s", "type": "OnStart"},
            {"id": "emit", "type": "EmitEvent", "exec_in": "s",
             "inputs": {"event_name": "demo/ping", "payload": "hola"}},
        ],
    }
    rayflow.run(sender)

    # If the receiver ran, it will have published 'demo/done/...' exactly once.
    assert _wait_count(done_event, 1) == 1


def test_onvariablechange_triggers_when_variable_changes():
    """Changing a watched variable triggers the flow watching it.

    src_var writes the `counter` variable; watcher_var watches it with
    OnVariableChange and re-emits a 'done' event when triggered. Also
    verifies that writing the same value does NOT trigger it again.
    """
    done_event = f"varchg/done/{time.time_ns()}"

    src = {
        "name": "src_var",
        "inputs": {"n": "int"},
        "variables": [{"name": "counter", "type": "int", "default": 0}],
        "nodes": [
            {"id": "s", "type": "OnStart"},
            {"id": "set", "type": "Set", "exec_in": "s",
             "inputs": {"variable_name": "counter", "value": "s.n"}},
        ],
    }
    watcher = {
        "name": "watcher_var",
        "nodes": [
            {"id": "on", "type": "OnVariableChange",
             "inputs": {"source": "src_var", "variable": "counter"}},
            {"id": "emit", "type": "EmitEvent", "exec_in": "on",
             "inputs": {"event_name": done_event, "payload": "on.value"}},
        ],
    }

    rayflow.load(src)       # creates gs_src_var before registering the watch
    serve_events(watcher)   # registers the watch on gs_src_var
    try:
        for _ in rayflow.execute("src_var", {"n": 42}):
            pass
        assert _wait_count(done_event, 1) == 1

        # Writing the same value again must not trigger it again.
        for _ in rayflow.execute("src_var", {"n": 42}):
            pass
        time.sleep(2)
        assert ray.get(get_event_broker().publish_count.remote(done_event)) == 1
    finally:
        rayflow.unload("watcher_var")
        rayflow.unload("src_var")


def test_isolated_namespaces_dont_cross():
    """Emitting to 'ns_a/ev' doesn't trigger a subscriber of 'ns_b/ev' (exact matching)."""
    done_event = f"ns_b/done/{time.time_ns()}"

    receiver_b = {
        "name": "receiver_b",
        "events": ["ns_b/ev"],
        "nodes": [
            {"id": "on", "type": "OnEvent", "inputs": {"event_name": "ns_b/ev"}},
            {"id": "emit_done", "type": "EmitEvent", "exec_in": "on",
             "inputs": {"event_name": done_event, "payload": "x"}},
        ],
    }
    serve_events(receiver_b)

    sender_a = {
        "name": "sender_a",
        "nodes": [
            {"id": "s", "type": "OnStart"},
            {"id": "emit", "type": "EmitEvent", "exec_in": "s",
             "inputs": {"event_name": "ns_a/ev", "payload": "should-not-arrive"}},
        ],
    }
    rayflow.run(sender_a)

    # Give it time for (nothing) to fire; the ns_b receiver must not run.
    time.sleep(3)
    assert ray.get(get_event_broker().publish_count.remote(done_event)) == 0


def test_publish_without_subscribers_does_not_fail():
    """Publishing to an event with no subscribers returns 0 and doesn't raise."""
    broker = get_event_broker()
    n = ray.get(broker.publish.remote("nobody/listening", "x"))
    assert n == 0
