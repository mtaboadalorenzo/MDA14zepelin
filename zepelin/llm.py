"""Llamadas a OpenAI, con tolerancia a diferencias entre modelos."""
import json
import re

TEMPERATURA_MOTOR = 0.7
MAX_TOKENS_MOTOR = 600
MAX_TOKENS_CLASIFICADOR = 120
TIMEOUT = 30


class ErrorLLM(Exception):
    pass


def _cliente(api_key):
    from openai import OpenAI
    return OpenAI(api_key=api_key, timeout=TIMEOUT, max_retries=1)


def llamar(api_key, modelo, mensajes, temperatura=TEMPERATURA_MOTOR, max_tokens=MAX_TOKENS_MOTOR, json_mode=False):
    from openai import BadRequestError
    cliente = _cliente(api_key)
    kwargs = {"model": modelo, "messages": mensajes, "max_completion_tokens": max_tokens}
    if temperatura is not None:
        kwargs["temperature"] = temperatura
    if json_mode:
        kwargs["response_format"] = {"type": "json_object"}
    for _ in range(3):
        try:
            r = cliente.chat.completions.create(**kwargs)
            texto = (r.choices[0].message.content or "").strip()
            if not texto:
                raise ErrorLLM("El modelo devolvió una respuesta vacía.")
            return texto
        except BadRequestError as e:
            msg = str(e).lower()
            if "temperature" in msg and "temperature" in kwargs:
                kwargs.pop("temperature")
                continue
            if "max_completion_tokens" in msg and "max_completion_tokens" in kwargs:
                kwargs["max_tokens"] = kwargs.pop("max_completion_tokens")
                continue
            if "response_format" in msg and "response_format" in kwargs:
                kwargs.pop("response_format")
                continue
            raise ErrorLLM(str(e)) from e
        except ErrorLLM:
            raise
        except Exception as e:  # red, tiempo de espera, límites de uso
            raise ErrorLLM(str(e)) from e
    raise ErrorLLM("No se pudo completar la llamada.")


def clasificar(api_key, modelo, prompt_clasificador, ficha, respuesta):
    mensajes = [
        {"role": "system", "content": prompt_clasificador},
        {"role": "user", "content": f"FICHA:\n{ficha}\n\nRESPUESTA DEL COPILOTO:\n{respuesta}"},
    ]
    texto = llamar(api_key, modelo, mensajes, temperatura=0, max_tokens=MAX_TOKENS_CLASIFICADOR, json_mode=True)
    return interpretar_clasificacion(texto)


SINONIMOS = {"escalar": "supervisor", "escalado": "supervisor", "pasar_al_supervisor": "supervisor",
             "reembolsar": "reembolso", "reembolso_parcial": "reembolso", "reembolso_total": "reembolso",
             "pedir_informacion": "pedir_info", "pedir_mas_informacion": "pedir_info", "rechazo": "rechazar",
             "sin_decision_clara": "sin_decision"}


def interpretar_clasificacion(texto):
    m = re.search(r"\{.*\}", texto, flags=re.S)
    try:
        d = json.loads(m.group(0) if m else texto)
    except (json.JSONDecodeError, AttributeError):
        return {"accion": "sin_decision", "importe": None}
    accion = str(d.get("accion", "sin_decision")).strip().lower().replace("ó", "o").replace(" ", "_")
    accion = SINONIMOS.get(accion, accion)
    if accion not in {"reembolso", "cupon", "rechazar", "pedir_info", "supervisor", "sin_decision"}:
        accion = "sin_decision"
    importe = d.get("importe")
    try:
        importe = None if importe in (None, "", "null") else float(str(importe).replace(",", "."))
    except ValueError:
        importe = None
    return {"accion": accion, "importe": importe}
