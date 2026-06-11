"""Nodo CallFlow — ejecuta un subflow desde dentro de un flow.

Tras el flatten() del validator, el subflow ya está expandido inline en el
grafo plano (ids prefijados "{callflow_id}/..."). El CallFlow shell ya NO crea
un FlowEngine: es orquestado por el engine, que dispara el entry del subgrafo
inline (bloqueante), lee el FlowOutput de retorno como 'result', y continúa.

Ver FlowEngine._fire_callflow_node y validator.flatten().
"""
from rayflow.nodes.decorators import (
    ExecContext,
    ExecInput,
    ExecOutput,
    Input,
    Output,
    engine_node,
)


@engine_node
class CallFlow:
    """Ejecuta otro flow como subgrafo, ya aplanado inline por el build.

    Modos según 'isolated' (resuelto en build como state_path del subgrafo):
    - False (default): el subgrafo comparte el GraphState del padre.
    - True: el subgrafo tiene su propio GraphState (segmento de ruta).

    El output 'result' es un dict con los outputs del subflow ("callflow_id.result").
    Los inputs extra (más allá de 'flow'/'isolated') se pasan al FlowInput del
    subgrafo (cableados en build).

    run() no se invoca: el engine orquesta el nodo vía _fire_callflow_node a
    partir de subflow_entry/subflow_exit del NodeDef. Este cuerpo existe solo
    como declaración de pins.
    """
    exec_in  = ExecInput()
    flow     = Input("Any",  default="")
    isolated = Input("bool", default=False)
    result   = Output("dict")
    exec_out = ExecOutput()

    def run(self, ctx: ExecContext, flow: str, isolated: bool, **extra_inputs) -> dict:
        # No se usa: el engine orquesta CallFlow directamente (ver
        # FlowEngine._fire_callflow_node). Se deja por simetría de declaración.
        return {}
