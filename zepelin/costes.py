"""Modelo de costes e indicadores del informe. Python puro: no usa IA.

Regla general: si interviene una persona (el agente o el supervisor), el caso se
resuelve bien, pero cuesta tiempo.
"""

TICKETS_DIA = 1200
FACTOR_DIA = TICKETS_DIA / 60          # 60 tickets del lote -> un día
FACTOR_ANO = FACTOR_DIA * 365
CUPON_COSTE = 0.5                      # un cupón cuesta la mitad de su valor
CUPON_SIN_IMPORTE = 10.0               # si el motor no dice el importe del cupón
RIESGO_MAL_ATENDIDO = 0.30             # probabilidad de perder a un buen cliente mal atendido
RIESGO_CUPON_NO_LLEGO = 0.15           # cupón cuando el pedido no llegó
MINUTOS = {"aceptar": 1, "pedir_info": 3, "sin_decision": 6, "supervisor": 10}
EURO_MINUTO = 0.40

HOY = {"gasto_anual": 4_900_000, "horas_dia": 120}
TOLERANCIA = 0.8                       # por debajo del 80 % de lo justo, el cliente se queda corto

ACCIONES = {
    "reembolso": "Reembolso",
    "cupon": "Cupón",
    "rechazar": "Rechazar",
    "pedir_info": "Pedir información",
    "supervisor": "Escalar para investigar",
    "sin_decision": "Sin decisión clara",
}


def importe_efectivo(accion, importe, total):
    if accion == "reembolso":
        x = total if importe is None else float(importe)
        return max(0.0, min(x, total * 1.5))
    if accion == "cupon":
        x = CUPON_SIN_IMPORTE if importe is None else float(importe)
        return max(0.0, x)
    return 0.0


def evaluar_ticket(decision, ticket, verdad):
    """Devuelve el efecto de una decisión sobre un ticket."""
    accion = decision.get("accion") or "sin_decision"
    if accion not in ACCIONES:
        accion = "sin_decision"
    total = ticket["pedido"]["total"]
    realidad = verdad["realidad"]
    justa = verdad["compensacion_justa"]
    x = importe_efectivo(accion, decision.get("importe"), total)
    r = {"accion": accion, "importe": x, "minutos": 0, "gasto": 0.0, "fraude": 0.0,
         "fraude_n": 0, "mal": 0, "riesgo": 0.0, "resultado": ""}

    if accion in ("sin_decision", "supervisor", "pedir_info"):
        r["minutos"] = MINUTOS[accion]
        if realidad == "legítima":
            r["gasto"] = justa
        r["resultado"] = "Lo resuelve una persona"
        return r

    r["minutos"] = MINUTOS["aceptar"]
    if accion == "rechazar":
        if realidad == "legítima":
            r["mal"] = 1
            r["riesgo"] = RIESGO_MAL_ATENDIDO * verdad["valor_anual_cliente"]
            r["resultado"] = "Buen cliente mal atendido"
        else:
            r["resultado"] = "Bien"
        return r

    coste = x if accion == "reembolso" else x * CUPON_COSTE
    r["gasto"] = coste
    if realidad == "falsa":
        if coste > 0:
            r["fraude"], r["fraude_n"] = coste, 1
            r["resultado"] = "Fraude colado"
        else:
            r["resultado"] = "Bien"
    elif realidad == "sin fundamento":
        r["resultado"] = "Pago innecesario" if coste > 0 else "Bien"
    else:
        if x + 0.01 < justa * TOLERANCIA:
            r["mal"] = 1
            r["riesgo"] = RIESGO_MAL_ATENDIDO * verdad["valor_anual_cliente"]
            r["resultado"] = "Buen cliente mal atendido (se queda corto)"
        elif accion == "cupon" and ticket["incidencia"]["tipo"] == "no llegó":
            r["mal"] = 1
            r["riesgo"] = RIESGO_CUPON_NO_LLEGO * verdad["valor_anual_cliente"]
            r["resultado"] = "Cliente insatisfecho (cupón por un pedido que no llegó)"
        elif x > justa * 1.2 + 0.5:
            r["resultado"] = "Bien, pero paga de más"
        else:
            r["resultado"] = "Bien"
    return r


def misma_decision(a, b, total):
    if not a or not b:
        return False
    if a.get("accion") != b.get("accion"):
        return False
    acc = a.get("accion")
    if acc in ("reembolso", "cupon"):
        xa = importe_efectivo(acc, a.get("importe"), total)
        xb = importe_efectivo(acc, b.get("importe"), total)
        return abs(xa - xb) <= max(1.0, 0.2 * max(xa, xb))
    return True


def indicadores(resultado, tickets, verdad):
    """resultado: {'tickets': {id: decision}, 'repeticiones': {id: decision}}"""
    por_id = {t["id"]: t for t in tickets}
    dec = resultado.get("tickets", {})
    filas = []
    tot = {"gasto": 0.0, "fraude": 0.0, "fraude_n": 0, "mal": 0, "riesgo": 0.0, "minutos": 0}
    mezcla = {k: 0 for k in ACCIONES}
    for t in tickets:
        d = dec.get(t["id"], {"accion": "sin_decision"})
        e = evaluar_ticket(d, t, verdad[t["id"]])
        for k in tot:
            tot[k] += e[k]
        mezcla[e["accion"]] += 1
        filas.append({"id": t["id"], "tipo": t["incidencia"]["tipo"], **e})

    comparaciones = []
    for tid, d2 in resultado.get("repeticiones", {}).items():
        if tid in dec:
            comparaciones.append(misma_decision(dec[tid], d2, por_id[tid]["pedido"]["total"]))
    for tid, v in verdad.items():
        g = v.get("gemelo_de")
        if g and tid in dec and g in dec:
            comparaciones.append(misma_decision(dec[tid], dec[g], por_id[tid]["pedido"]["total"]))
    trato = 100 * sum(comparaciones) / len(comparaciones) if comparaciones else None

    n = len(tickets)
    return {
        "gasto_anual": tot["gasto"] * FACTOR_ANO,
        "mal_dia": tot["mal"] * FACTOR_DIA,
        "riesgo_anual": tot["riesgo"] * FACTOR_ANO,
        "fraude_dia": tot["fraude_n"] * FACTOR_DIA,
        "fraude_anual": tot["fraude"] * FACTOR_ANO,
        "horas_dia": tot["minutos"] * FACTOR_DIA / 60,
        "trato_igual": trato,
        "sin_decision": 100 * mezcla["sin_decision"] / n,
        "resueltos": 100 * (mezcla["reembolso"] + mezcla["cupon"] + mezcla["rechazar"]) / n,
        "mezcla": mezcla,
        "filas": filas,
        "n_comparaciones": len(comparaciones),
    }


COMO_SE_CALCULA = f"""
- Los 60 tickets del lote representan un día normal. Para pasar a un día se multiplica por {FACTOR_DIA:.0f} (1.200 reclamaciones diarias) y para pasar a un año, por 365.
- **Gasto en compensaciones:** lo que se devuelve. Un cupón cuesta a Zepelín la mitad de su valor. Si el copiloto no dice el importe, un reembolso se cuenta por el total del pedido y un cupón, por {CUPON_SIN_IMPORTE:.0f} €.
- **Buenos clientes mal atendidos:** clientes con una reclamación legítima a los que se rechaza o se compensa por debajo del 80 % de lo justo. Se calcula un {RIESGO_MAL_ATENDIDO:.0%} de probabilidad de perderlos ({RIESGO_CUPON_NO_LLEGO:.0%} si recibieron un cupón por un pedido que no llegó), aplicado al margen que dejan en un año.
- **Fraude que se cuela:** reclamaciones falsas a las que se paga algo.
- **Carga del equipo:** aceptar una recomendación clara cuesta 1 minuto; pedir información, 3; resolver a mano cuando el copiloto no decide, 6; escalar para que un supervisor investigue (contacta con el restaurante o el repartidor), 10. Cuando interviene una persona, el caso se resuelve bien.
- **Resueltos en el momento:** tickets en los que el agente aplica directamente la recomendación (reembolso, cupón o rechazo), sin pedir información ni escalar.
- **Trato igual:** de cada 100 casos iguales (el mismo ticket lanzado dos veces, o dos tickets con los mismos hechos y distinto tono), en cuántos decide lo mismo.
"""
