"""Carga de tickets y verdad oculta, y conversión de un ticket en ficha de texto."""
import json
import re
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent


def cargar_tickets():
    return json.loads((RAIZ / "data" / "tickets.json").read_text(encoding="utf-8"))


def cargar_verdad():
    return json.loads((RAIZ / "data" / "verdad.json").read_text(encoding="utf-8"))


def euros(x):
    """1234.5 -> '1.234,50 €'"""
    s = f"{x:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    return f"{s} €"


def ficha(t):
    c, p, e = t["cliente"], t["pedido"], t["entrega"]
    lineas_prod = []
    for pr in p["productos"]:
        if pr["cantidad"] > 1:
            lineas_prod.append(f"{pr['cantidad']} × {pr['nombre']} ({euros(pr['precio'])} c/u)")
        else:
            lineas_prod.append(f"{pr['nombre']} ({euros(pr['precio'])})")
    lineas_prod.append(f"Envío ({euros(p['envio'])})")
    if p["retraso_min"] is None:
        retraso = "sin dato (no consta la entrega)"
    else:
        retraso = f"{p['retraso_min']} min"
    reclam = "reclamación" if c["reclamaciones_90d"] == 1 else "reclamaciones"
    pedidos = "pedido" if c["pedidos_90d"] == 1 else "pedidos"
    return "\n".join([
        f"Ticket {t['id']}",
        f"Cliente: {c['antiguedad_meses']} meses en Zepelín · {c['pedidos_90d']} {pedidos} y "
        f"{c['reclamaciones_90d']} {reclam} en los últimos 90 días",
        f"Pedido: {p['restaurante']} · " + " · ".join(lineas_prod) + f" · Total: {euros(p['total'])}",
        f"Retraso sobre la hora prometida: {retraso}",
        f"Entrega: {e['tipo']} · GPS confirma la entrega: {'sí' if e['gps_confirma'] else 'no'} · "
        f"Incidencias del repartidor este mes: {e['incidencias_repartidor_mes']}",
        f"Restaurante: quejas este mes: {t['restaurante']['quejas_mes']}",
        f"Incidencia: {t['incidencia']['tipo']}",
        f"Mensaje del cliente: \"{t['incidencia']['mensaje']}\"",
    ])


def etiqueta(t):
    return f"{t['id']} · {t['incidencia']['tipo']} · {t['pedido']['restaurante']} · {euros(t['pedido']['total'])}"


def solo_mensaje(texto):
    """Nivel 0: el prototipo de la consultora solo lee el mensaje del cliente."""
    m = re.search(r"Mensaje del cliente:\s*(.+)", texto, flags=re.S)
    if m:
        return m.group(1).strip().strip('"').strip()
    return texto.strip()


def pide_protocolo_33(texto):
    return re.search(r"protocolo\s*33", texto, flags=re.I) is not None
