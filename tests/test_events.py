"""Tests del EventBroker: pub/sub fire-and-forget con namespaces.

La comunicación entre flows se verifica con solo nodos builtin: el flow
receptor (OnEvent) re-emite un evento de 'done' al ejecutarse, y el test lo
observa con el contador de publicaciones del broker. Así se evita un nodo
custom (que no viajaría al worker que ejecuta el receptor).
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


def test_emit_dispara_onevent_de_otro_flow():
    """Un flow emite a 'demo/ping'; otro suscrito se ejecuta y re-emite 'demo/done'."""
    done_event = f"demo/done/{time.time_ns()}"  # único por corrida

    receptor = {
        "name": "receptor",
        "events": ["demo/ping"],
        "nodes": [
            {"id": "on", "type": "OnEvent", "inputs": {"event_name": "demo/ping"}},
            {"id": "emit_done", "type": "EmitEvent", "exec_in": "on",
             "inputs": {"event_name": done_event, "payload": "on.payload"}},
        ],
    }
    serve_events(receptor)

    emisor = {
        "name": "emisor",
        "nodes": [
            {"id": "s", "type": "OnStart"},
            {"id": "emit", "type": "EmitEvent", "exec_in": "s",
             "inputs": {"event_name": "demo/ping", "payload": "hola"}},
        ],
    }
    rayflow.run(emisor)

    # Si el receptor se ejecutó, habrá publicado 'demo/done/...' exactamente 1 vez.
    assert _wait_count(done_event, 1) == 1


def test_namespaces_aislados_no_se_cruzan():
    """Emitir a 'ns_a/ev' no dispara un suscriptor de 'ns_b/ev' (matching exacto)."""
    done_event = f"ns_b/done/{time.time_ns()}"

    receptor_b = {
        "name": "receptor_b",
        "events": ["ns_b/ev"],
        "nodes": [
            {"id": "on", "type": "OnEvent", "inputs": {"event_name": "ns_b/ev"}},
            {"id": "emit_done", "type": "EmitEvent", "exec_in": "on",
             "inputs": {"event_name": done_event, "payload": "x"}},
        ],
    }
    serve_events(receptor_b)

    emisor_a = {
        "name": "emisor_a",
        "nodes": [
            {"id": "s", "type": "OnStart"},
            {"id": "emit", "type": "EmitEvent", "exec_in": "s",
             "inputs": {"event_name": "ns_a/ev", "payload": "no-deberia-llegar"}},
        ],
    }
    rayflow.run(emisor_a)

    # Dar tiempo a que (no) se dispare nada; el receptor de ns_b no debe ejecutarse.
    time.sleep(3)
    assert ray.get(get_event_broker().publish_count.remote(done_event)) == 0


def test_publish_sin_suscriptores_no_falla():
    """Publicar a un evento sin suscriptores devuelve 0 y no lanza."""
    broker = get_event_broker()
    n = ray.get(broker.publish.remote("nadie/escucha", "x"))
    assert n == 0
