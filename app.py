"""Zepelín · Copiloto de soporte. Una sola app para las 6 versiones (secret VERSION)."""
import json
import random
import threading
import tomllib
from datetime import date, datetime
from pathlib import Path

import pandas as pd
import streamlit as st

from zepelin import costes, datos, llm, prompts, simulacion

RAIZ = Path(__file__).resolve().parent
st.set_page_config(page_title="Zepelín · Copiloto de soporte", page_icon="🎈", layout="wide")


# ---------------------------------------------------------------- configuración
def secreto(clave, defecto=None):
    try:
        return st.secrets[clave]
    except Exception:
        return defecto


VERSION = str(secreto("VERSION", "base")).strip().lower()
MODELO = secreto("OPENAI_MODEL", "gpt-4o-mini")
API_KEY = secreto("OPENAI_API_KEY")
CLAVE_ZONA = secreto("CLAVE_ZEPELIN")
MAX_SESION = int(secreto("MAX_CONSULTAS_SESION", 40))
MAX_DIA = int(secreto("MAX_CONSULTAS_DIA", 800))
MAX_POR_QUE = 3
MAX_CARACTERES = 1500
MAX_REGLA = 300


@st.cache_data
def cargar_datos():
    return datos.cargar_tickets(), datos.cargar_verdad()


def cargar_config(version):
    """Devuelve (config, error). Se lee en cada ejecución (sin caché) para que un cambio subido al repositorio
    se aplique sin reiniciar la app. Un fallo de formato no tumba la app: se avisa y el copiloto queda sin configurar."""
    ruta = RAIZ / "config" / f"{version}.toml"
    try:
        with open(ruta, "rb") as f:
            return tomllib.load(f), None
    except Exception as e:
        return {"nombre": version, "mandato": ""}, f"{type(e).__name__}: {e}"


@st.cache_resource
def compartido():
    """Estado común a todas las sesiones de esta app (dura mientras la app está despierta)."""
    sh = {"lock": threading.Lock(), "publicado": False, "porque": False, "detalle": False, "regla": False, "p33": False,
          "resultados": {}, "archivos": {}, "dia": date.today().isoformat(), "consultas_dia": 0}
    return sh


def sincronizar_resultados():
    """Carga los .json de resultados/ que sean nuevos o hayan cambiado desde la última vez.
    Así un resultado subido al repositorio aparece sin reiniciar la app (y sin apagar los interruptores)."""
    carpeta = RAIZ / "resultados"
    if not carpeta.exists():
        return
    for f in carpeta.glob("*.json"):
        try:
            m = f.stat().st_mtime
            if SH["archivos"].get(f.name) == m:
                continue
            r = json.loads(f.read_text(encoding="utf-8"))
            with SH["lock"]:
                SH["resultados"][r.get("clave", f.stem)] = r
                SH["archivos"][f.name] = m
        except Exception:
            pass


TICKETS, VERDAD = cargar_datos()
POR_ID = {t["id"]: t for t in TICKETS}
CFG, ERROR_CFG = cargar_config(VERSION)
CFG.setdefault("nombre", VERSION)
CFG.setdefault("mandato", "")
SH = compartido()
sincronizar_resultados()
ES_BASE = VERSION == "base"
PROMPT_EQUIPO = None if ES_BASE else prompts.prompt_equipo(CFG)

if SH["dia"] != date.today().isoformat():
    with SH["lock"]:
        SH["dia"], SH["consultas_dia"] = date.today().isoformat(), 0

ss = st.session_state
for k, v in {"consultas": 0, "pruebas": [], "humor_turno": random.randint(2, 4), "n0": 0,
             "ultima": None, "ocupado": False, "pendiente": None, "error": None,
             "admin": False, "sel_prev": None}.items():
    ss.setdefault(k, v)


def system_para(nivel):
    if nivel == "n0":
        return prompts.NIVEL_0
    if nivel == "n1":
        return prompts.NIVEL_1
    return PROMPT_EQUIPO


def claves_boton():
    if ES_BASE:
        return [("base_n0", "n0", "Tal cual"), ("base_n1", "n1", "Con protocolo 33")]
    if VERSION == "referencia":
        return [("referencia", "eq", "Referencia"), ("referencia_2", "eq", "Referencia, 2ª ejecución")]
    return [(VERSION, "eq", f"{CFG['nombre']} · {CFG['mandato']}")]


def columnas_informe():
    if ES_BASE:
        cols = [("Tal cual", "base_n0"), ("Con protocolo 33", "base_n1")]
    elif VERSION == "referencia":
        cols = [("Piloto con protocolo 33", "base_n1"), ("Referencia", "referencia"),
                ("Referencia, 2ª ejecución", "referencia_2")]
    else:
        cols = [("Piloto con protocolo 33", "base_n1"), ("Vuestro copiloto", VERSION)]
    return [(nombre, SH["resultados"][c]) for nombre, c in cols if c in SH["resultados"]]


def quedan_consultas():
    return ss.consultas < MAX_SESION and SH["consultas_dia"] < MAX_DIA


def contar_consulta():
    ss.consultas += 1
    with SH["lock"]:
        SH["consultas_dia"] += 1


# ---------------------------------------------------------------- formato
def num(x, dec=0):
    s = f"{x:,.{dec}f}"
    return s.replace(",", "X").replace(".", ",").replace("X", ".")


def m_eur(x):
    return f"{num(x / 1e6, 1)} M€" if abs(x) >= 1e6 else f"{num(x / 1e3, 0)} mil €"


# ---------------------------------------------------------------- cabecera y barra lateral
etiqueta_version = "Prototipo de la consultora" if ES_BASE else (
    f"{CFG['nombre']} · {CFG['mandato']}" if CFG.get("mandato") else CFG["nombre"])
st.title("🎈 Zepelín · Copiloto de soporte")
c_ver, c_act = st.columns([4, 1])
c_ver.caption(f"Versión: **{etiqueta_version}**")
c_act.button("🔄 Actualizar", key="actualizar", help="Pulsad aquí cuando Miguel diga que hay novedades. No recarguéis la página.")

with st.sidebar:
    st.markdown("### 🎈 Zepelín")
    st.write(f"Consultas que te quedan en esta sesión: **{max(0, MAX_SESION - ss.consultas)}**")
    if SH["consultas_dia"] >= MAX_DIA:
        st.warning("Se ha alcanzado el límite de consultas de hoy para esta app.")

    with st.expander("Zona Zepelín"):
        if not ss.admin:
            clave = st.text_input("Clave", type="password")
            if st.button("Entrar"):
                if CLAVE_ZONA and clave == CLAVE_ZONA:
                    ss.admin = True
                    st.rerun()
                else:
                    st.error("Clave incorrecta.")
        else:
            st.success("Dentro de la zona Zepelín")
            st.toggle("Publicar informe", value=SH["publicado"], key="tg_pub",
                      on_change=lambda: SH.__setitem__("publicado", ss.tg_pub))
            if ES_BASE:
                st.toggle("Anunciar el protocolo 33", value=SH["p33"], key="tg_p33",
                          on_change=lambda: SH.__setitem__("p33", ss.tg_p33))
            st.toggle("Activar «¿Por qué?»", value=SH["porque"], key="tg_pq",
                      on_change=lambda: SH.__setitem__("porque", ss.tg_pq))
            st.toggle("Publicar resultado por ticket", value=SH["detalle"], key="tg_det",
                      on_change=lambda: SH.__setitem__("detalle", ss.tg_det))
            if not ES_BASE:
                st.toggle("Activar «Probar una regla nueva»", value=SH["regla"], key="tg_regla",
                          on_change=lambda: SH.__setitem__("regla", ss.tg_regla))
            st.toggle("Ver verdad oculta (solo tú)", key="ver_verdad")

            st.markdown("**🪄 Botón mágico**")
            for clave_r, nivel, nombre in claves_boton():
                ya = clave_r in SH["resultados"]
                if st.button(f"Lanzar: {nombre}" + (" (otra vez)" if ya else ""), key=f"bm_{clave_r}",
                             disabled=not API_KEY or (nivel == "eq" and not PROMPT_EQUIPO)):
                    barra = st.progress(0.0, text="Lanzando los 60 tickets…")
                    res = simulacion.lanzar(
                        API_KEY, MODELO, system_para(nivel), nivel, clave_r, nombre, TICKETS, VERDAD,
                        progreso=lambda h, n: barra.progress(h / n, text=f"{h} de {n} respuestas"))
                    SH["resultados"][clave_r] = res
                    barra.empty()
                    if res["errores"]:
                        st.warning(f"Hecho, con {res['errores']} respuestas con error (cuentan como sin decisión).")
                    else:
                        st.success("Hecho.")

            for clave_r, r in SH["resultados"].items():
                st.download_button(f"Descargar {clave_r}.json", json.dumps(r, ensure_ascii=False, indent=1),
                                   file_name=f"{clave_r}.json", mime="application/json", key=f"dl_{clave_r}")
            st.caption("Sube los .json descargados a la carpeta resultados/ del repositorio para que no se pierdan si la app se reinicia.")
            subido = st.file_uploader("Cargar un resultado guardado (.json)", type="json")
            if subido is not None:
                try:
                    r = json.loads(subido.getvalue().decode("utf-8"))
                    SH["resultados"][r["clave"]] = r
                    st.success(f"Cargado: {r['clave']}")
                except Exception as e:
                    st.error(f"No se pudo cargar: {e}")
            st.caption(f"Modelo: {MODELO} · Consultas hoy en esta app: {SH['consultas_dia']} de {MAX_DIA}")
            if st.button("Salir de la zona Zepelín"):
                ss.admin = False
                st.rerun()

if not API_KEY:
    st.error("Falta la clave de OpenAI en los secrets de la app (OPENAI_API_KEY).")
if ERROR_CFG:
    st.error("La configuración de esta versión tiene un error de formato. Avisad a Miguel.")
    if ss.admin:
        st.code(f"config/{VERSION}.toml → {ERROR_CFG}")
elif not ES_BASE and not PROMPT_EQUIPO:
    st.warning("Este copiloto todavía no está configurado. Estará listo el martes.")

tab_probar, tab_informe = st.tabs(["Probar", "Informe"])

# ---------------------------------------------------------------- pestaña Probar
with tab_probar:
    if ES_BASE and SH["p33"]:
        st.info(prompts.AVISO_P33)
    if not ES_BASE:
        novedades = []
        if SH["porque"]:
            novedades.append("**«¿Por qué?»:** debajo de cada recomendación podéis preguntarle al copiloto por su decisión, "
                             "hasta 3 veces.")
        if SH["regla"]:
            novedades.append("**«Probar una regla nueva»:** escribid una regla en la caja que hay sobre el botón y volved a pedir "
                             "la recomendación. ¿Arregla el fallo? ¿Rompe otra cosa? Solo vale para probar: no cambia el informe.")
        if novedades:
            st.info("🆕 **Novedades.** Usadlas en las reclamaciones donde vuestro copiloto falla.\n\n- " + "\n- ".join(novedades))
        if PROMPT_EQUIPO and (VERSION != "referencia" or ss.admin):
            with st.expander("Las instrucciones de vuestro copiloto (vuestras respuestas 2 a 6 del formulario)"):
                for k, titulo in prompts.PREGUNTAS:
                    st.markdown(f"**{titulo}**")
                    st.text((CFG.get(k) or "").strip() or "(sin respuesta)")
        with st.expander("Qué puede hacer el agente y cuánto cuesta"):
            st.markdown(prompts.ACCIONES_AGENTE)
    tipos = ["Todos"] + sorted({t["incidencia"]["tipo"] for t in TICKETS})
    c1, c2 = st.columns([1, 3])
    filtro = c1.selectbox("Tipo de incidencia", tipos)
    visibles = [t for t in TICKETS if filtro == "Todos" or t["incidencia"]["tipo"] == filtro]
    NUEVO = "✏️ Escribir o pegar uno nuevo"
    opciones = [datos.etiqueta(t) for t in visibles] + [NUEVO]
    sel = c2.selectbox("Ticket del muestrario", opciones)
    if sel != ss.sel_prev:
        ss.ficha = "" if sel == NUEVO else datos.ficha(POR_ID[sel.split(" · ")[0]])
        ss.sel_prev = sel

    st.text_area("Ficha del ticket (podéis editarla)", key="ficha", height=230, max_chars=MAX_CARACTERES)
    protocolo = ES_BASE and datos.pide_protocolo_33(ss.ficha)
    if protocolo:
        st.info("🔓 Protocolo 33 activado")

    regla_activa = SH["regla"] and not ES_BASE
    if regla_activa:
        st.text_area("🧪 Probar una regla nueva (opcional)", key="regla", height=80, max_chars=MAX_REGLA,
                     placeholder="Por ejemplo: Nunca reembolses más de 40 € sin pasar por el supervisor.",
                     help="Se añade a las instrucciones de vuestro copiloto solo en esta sesión. No cambia el informe.")

    puede = (bool(API_KEY) and quedan_consultas() and bool(ss.ficha.strip())
             and (ES_BASE or bool(PROMPT_EQUIPO)))
    if st.button("Pedir recomendación", type="primary", disabled=not puede or ss.ocupado):
        ss.ocupado, ss.pendiente, ss.error = True, ss.ficha, None
        st.rerun()

    if ss.ocupado and ss.pendiente:
        texto = ss.pendiente
        nivel = ("n1" if datos.pide_protocolo_33(texto) else "n0") if ES_BASE else "eq"
        system = system_para(nivel)
        regla = (ss.get("regla") or "").strip() if regla_activa else ""
        if regla:
            system += prompts.REGLA_NUEVA.format(regla=regla)
        entrada = simulacion.preparar_entrada(nivel, texto)
        try:
            with st.spinner("El copiloto está pensando…"):
                resp = llm.llamar(API_KEY, MODELO, [{"role": "system", "content": system},
                                                    {"role": "user", "content": entrada}])
            if nivel == "n0":
                ss.n0 += 1
                if ss.n0 == ss.humor_turno:
                    resp = f"*{random.choice(prompts.HUMOR)}*\n\n{resp}"
            contar_consulta()
            ss.ultima = {"system": system, "entrada": entrada, "respuesta": resp, "conversacion": [],
                         "nivel": nivel, "regla": regla}
            ss.pruebas.append({"hora": datetime.now().strftime("%H:%M"),
                               "ticket": texto.splitlines()[0][:40] if texto.strip() else "",
                               "nivel": {"n0": "tal cual", "n1": "protocolo 33"}.get(nivel, etiqueta_version),
                               **({"regla nueva": regla} if regla_activa else {}),
                               "respuesta": resp})
        except llm.ErrorLLM as e:
            ss.error = "El copiloto no ha respondido a tiempo. Vuelve a intentarlo (no se ha descontado la consulta)."
            ss.error_detalle = str(e)
        finally:
            ss.ocupado, ss.pendiente = False, None
        st.rerun()

    if ss.error:
        st.error(ss.error)
        if ss.admin and ss.get("error_detalle"):
            st.caption(f"Detalle técnico (solo tú): {ss.error_detalle}")

    if ss.ultima:
        st.markdown("#### Recomendación del copiloto")
        if regla_activa and ss.ultima.get("regla"):
            st.caption(f"🧪 Con la regla nueva: «{ss.ultima['regla']}»")
        with st.container(border=True):
            st.markdown(ss.ultima["respuesta"])

        if SH["porque"]:
            for q, a in ss.ultima["conversacion"]:
                st.markdown(f"**Vosotros:** {q}")
                with st.container(border=True):
                    st.markdown(a)
            usadas = len(ss.ultima["conversacion"])
            if usadas < MAX_POR_QUE:
                pregunta = st.text_input(f"Preguntadle al copiloto por su recomendación ({MAX_POR_QUE - usadas} preguntas)",
                                         key=f"pq_{len(ss.pruebas)}_{usadas}", max_chars=300,
                                         placeholder="¿Por qué recomiendas esto?")
                if st.button("¿Por qué?", disabled=not quedan_consultas() or not pregunta.strip()):
                    mensajes = [{"role": "system", "content": ss.ultima["system"] + prompts.POR_QUE},
                                {"role": "user", "content": ss.ultima["entrada"]},
                                {"role": "assistant", "content": ss.ultima["respuesta"]}]
                    for q, a in ss.ultima["conversacion"]:
                        mensajes += [{"role": "user", "content": q}, {"role": "assistant", "content": a}]
                    mensajes.append({"role": "user", "content": pregunta})
                    try:
                        with st.spinner("Pensando…"):
                            a = llm.llamar(API_KEY, MODELO, mensajes)
                        contar_consulta()
                        ss.ultima["conversacion"].append((pregunta, a))
                    except llm.ErrorLLM:
                        ss.error = "El copiloto no ha respondido a tiempo. Vuelve a intentarlo."
                    st.rerun()
            else:
                st.caption("Ya habéis usado las 3 preguntas para esta recomendación.")

    if ss.pruebas:
        with st.expander(f"Vuestras pruebas ({len(ss.pruebas)})"):
            df = pd.DataFrame(ss.pruebas).fillna("")
            st.dataframe(df, hide_index=True)
            st.download_button("Descargar en CSV", df.to_csv(index=False).encode("utf-8-sig"),
                               file_name="vuestras_pruebas.csv", mime="text/csv")

# ---------------------------------------------------------------- pestaña Informe
INDICADORES = [
    ("Gasto en compensaciones (al año)", "gasto_anual", m_eur, "4,9 M€"),
    ("Buenos clientes mal atendidos (al día)", "mal_dia", lambda x: num(x), "No lo sabemos"),
    ("Valor en riesgo por clientes mal atendidos (al año)", "riesgo_anual", m_eur, "No lo sabemos"),
    ("Fraude que se cuela (al día)", "fraude_dia", lambda x: num(x), "No lo sabemos"),
    ("Fraude que se cuela (al año)", "fraude_anual", m_eur, "No lo sabemos"),
    ("Carga del equipo de soporte (horas al día)", "horas_dia", lambda x: f"{num(x)} h", "120 h"),
    ("Trato igual (% de casos iguales con la misma decisión)", "trato_igual",
     lambda x: "—" if x is None else f"{num(x)} %", "No lo medimos"),
    ("Resueltos en el momento (% de tickets)", "resueltos", lambda x: f"{num(x)} %", "—"),
    ("Sin decisión clara (% de tickets)", "sin_decision", lambda x: f"{num(x)} %", "—"),
]
TARJETAS = [("Gasto al año", "gasto_anual", m_eur, "inverse"),
            ("Mal atendidos al día", "mal_dia", lambda x: num(x), "inverse"),
            ("Fraude al año", "fraude_anual", m_eur, "inverse"),
            ("Horas al día", "horas_dia", lambda x: f"{num(x)} h", "inverse"),
            ("Resueltos al momento", "resueltos", lambda x: f"{num(x)} %", "normal"),
            ("Trato igual", "trato_igual", lambda x: "—" if x is None else f"{num(x)} %", "normal"),
            ("Sin decisión clara", "sin_decision", lambda x: f"{num(x)} %", "inverse")]

with tab_informe:
    cols = columnas_informe()
    if not SH["publicado"] and not ss.admin:
        st.info("Todavía no hay informe. Lo publicaremos en clase: cuando Miguel avise, pulsad «Actualizar» (arriba a la derecha).")
    elif not cols:
        st.info("Aún no se ha lanzado la simulación.")
    else:
        if not SH["publicado"]:
            st.warning("Informe sin publicar: solo lo ves tú.")
        calc = [(n, r, costes.indicadores(r, TICKETS, VERDAD)) for n, r in cols]
        nombre_p, res_p, ind_p = calc[-1]
        ind_ref = calc[-2][2] if len(calc) > 1 else None

        st.subheader(f"Informe: {nombre_p}")
        st.caption(f"Un día normal simulado con los 60 tickets del muestrario · {res_p.get('fecha', '')}")
        tarjetas = st.columns(len(TARJETAS))
        for col, (nombre, k, fmt, color) in zip(tarjetas, TARJETAS):
            v = ind_p[k]
            delta = None
            if ind_ref and v is not None and ind_ref[k] is not None:
                d = v - ind_ref[k]
                unidades = {"trato_igual": f"{num(d)} pp", "sin_decision": f"{num(d)} pp", "resueltos": f"{num(d)} pp",
                            "horas_dia": f"{num(d)} h", "mal_dia": num(d)}
                delta = unidades.get(k, m_eur(d))
            col.metric(nombre, fmt(v), delta, delta_color=color)
        if ind_ref:
            st.caption(f"Las variaciones se comparan con «{calc[-2][0]}».")

        st.markdown("#### Comparativa")
        tabla = {"Indicador": [i[0] for i in INDICADORES], "Hoy sin copiloto": [i[3] for i in INDICADORES]}
        for n, _, ind in calc:
            tabla[n] = [fmt(ind[k]) for _, k, fmt, _ in INDICADORES]
        st.dataframe(pd.DataFrame(tabla), hide_index=True)

        st.markdown("#### Qué decide el copiloto")
        orden = list(costes.ACCIONES.values())
        filas = [{"Versión": n, "Decisión": costes.ACCIONES[a], "Tickets": c}
                 for n, _, ind in calc for a, c in ind["mezcla"].items()]
        try:
            import altair as alt
            graf = alt.Chart(pd.DataFrame(filas)).mark_bar().encode(
                x=alt.X("Decisión:N", sort=orden, title=None, axis=alt.Axis(labelAngle=0)),
                xOffset=alt.XOffset("Versión:N", sort=[n for n, _, _ in calc]),
                y=alt.Y("Tickets:Q", title="Tickets de 60"),
                color=alt.Color("Versión:N", sort=[n for n, _, _ in calc], legend=alt.Legend(orient="top", title=None)),
                tooltip=["Versión", "Decisión", "Tickets"],
            ).properties(height=320)
            st.altair_chart(graf)
        except Exception:
            # Sin gráfico (por ejemplo, si la versión de Python no es compatible con Altair): tabla equivalente
            tabla_mezcla = pd.DataFrame(filas).pivot(index="Decisión", columns="Versión", values="Tickets")
            st.dataframe(tabla_mezcla.reindex(orden)[[n for n, _, _ in calc]])

        st.markdown(f"#### Ticket a ticket: {nombre_p}")
        ver_verdad = ss.admin and ss.get("ver_verdad")
        filas_t = []
        for f in ind_p["filas"]:
            fila = {"Ticket": f["id"], "Tipo": f["tipo"], "Decisión": costes.ACCIONES[f["accion"]],
                    "Importe": datos.euros(f["importe"]) if f["accion"] in ("reembolso", "cupon") else "",
                    "Minutos del equipo": f["minutos"]}
            if SH["detalle"] or ver_verdad:
                fila["Resultado"] = f["resultado"]
            if ver_verdad:
                v = VERDAD[f["id"]]
                fila.update({"Realidad": v["realidad"], "Compensación justa": datos.euros(v["compensacion_justa"]),
                             "Mala suerte": "sí" if v["mala_suerte"] else "",
                             "Qué pasó después": v["que_paso_despues"] or ""})
            filas_t.append(fila)
        df_t = pd.DataFrame(filas_t)
        if "Resultado" in df_t.columns:
            st.caption("**Resultado** dice qué pasó con cada decisión. Filtrad para encontrar dónde falla el copiloto.")
            opciones_r = sorted(df_t["Resultado"].unique())
            elegidos = st.multiselect("Filtrar por resultado", opciones_r, key="filtro_resultado")
            if elegidos:
                df_t = df_t[df_t["Resultado"].isin(elegidos)]
        st.dataframe(df_t, hide_index=True, height=360)

        ver = st.selectbox("Ver la respuesta completa de un ticket", [""] + [f["id"] for f in ind_p["filas"]])
        if ver:
            for n, r, _ in calc:
                d = r["tickets"].get(ver)
                if d:
                    st.markdown(f"**{n}**")
                    with st.container(border=True):
                        st.markdown(d["respuesta"])

        with st.expander("Cómo se calcula"):
            st.markdown(costes.COMO_SE_CALCULA)
