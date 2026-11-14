"""Botón mágico: lanza el lote completo contra un motor y clasifica las respuestas."""
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime

from . import datos, llm, prompts

HILOS = 5  # llamadas en paralelo, para no saturar a OpenAI


def preparar_entrada(nivel, texto):
    return datos.solo_mensaje(texto) if nivel == "n0" else texto


def _una(api_key, modelo, system, nivel, t):
    ficha = datos.ficha(t)
    ultimo_error = None
    for _ in range(2):
        try:
            resp = llm.llamar(api_key, modelo, [
                {"role": "system", "content": system},
                {"role": "user", "content": preparar_entrada(nivel, ficha)},
            ])
            dec = llm.clasificar(api_key, modelo, prompts.CLASIFICADOR, ficha, resp)
            return {"respuesta": resp, **dec}
        except llm.ErrorLLM as e:
            ultimo_error = str(e)
    return {"respuesta": f"[Error: {ultimo_error}]", "accion": "sin_decision", "importe": None, "error": True}


def lanzar(api_key, modelo, system, nivel, clave, etiqueta, tickets, verdad, progreso=None):
    trabajos = [(t, "tickets") for t in tickets]
    trabajos += [(t, "repeticiones") for t in tickets if verdad[t["id"]]["se_repite"]]
    res = {"clave": clave, "etiqueta": etiqueta, "nivel": nivel, "modelo": modelo,
           "fecha": datetime.now().isoformat(timespec="minutes"), "tickets": {}, "repeticiones": {}}
    hechos = 0
    with ThreadPoolExecutor(max_workers=HILOS) as ex:
        futuros = {ex.submit(_una, api_key, modelo, system, nivel, t): (t["id"], grupo) for t, grupo in trabajos}
        for f in as_completed(futuros):
            tid, grupo = futuros[f]
            res[grupo][tid] = f.result()
            hechos += 1
            if progreso:
                progreso(hechos, len(trabajos))
    res["errores"] = sum(1 for g in ("tickets", "repeticiones") for d in res[g].values() if d.get("error"))
    return res
