# Zepelín · Copiloto de soporte

Dinámica "Diseña tu motor de decisiones" de la asignatura de Toma de Decisiones Empresariales (ISDI, MDA14).
Una sola app de Streamlit que sirve para las 6 versiones del copiloto: cada despliegue elige la suya con el secret `VERSION`.

## Qué hay en el repositorio

| Ruta | Qué es |
| --- | --- |
| `app.py` | La app: pestañas Probar e Informe, y la zona Zepelín (con clave) |
| `zepelin/` | Lógica: tickets, prompts, llamadas a OpenAI, botón mágico y modelo de costes |
| `data/tickets.json` | Los 60 tickets del muestrario (lo que ven los alumnos) |
| `data/verdad.json` | La verdad oculta. El motor nunca la lee; solo la usa el informe |
| `config/*.toml` | Una configuración por versión. Los equipos se rellenan el lunes por la noche |
| `resultados/` | Resultados guardados del botón mágico |
| `herramientas/generar_tickets.py` | Genera los dos JSON de tickets a partir de sus especificaciones |

## Desplegar las 6 apps en Streamlit Cloud

Para cada versión (`base`, `equipo1`, `equipo2`, `equipo3`, `equipo4`, `referencia`):

1. En [share.streamlit.io](https://share.streamlit.io), **Create app** → desde este repositorio, rama `main`. Archivo: `app.py` para la base y `app_equipo1.py` … `app_equipo4.py` o `app_referencia.py` para las demás (Streamlit Cloud no deja desplegar dos apps con el mismo archivo).
2. Elige una URL fácil, por ejemplo `zepelin-base`, `zepelin-equipo1`…
3. En **Advanced settings → Secrets**, pega el contenido de `.streamlit/secrets.toml.example` con los valores reales y la `VERSION` que toque.
4. Deploy.

Cada cambio que se sube a `main` actualiza las 6 apps en uno o dos minutos.

## El lunes por la noche

Pegar las respuestas 2 a 6 del formulario de cada equipo en `config/equipoN.toml` (entre las `'''`), subir el cambio y comprobar que cada app responde.

## Límites de uso

- 40 consultas por sesión y 800 por app y día (configurables en los secrets).
- Entrada máxima de 1.500 caracteres. Solo texto.
- Recomendable: un límite de gasto en la cuenta de OpenAI.
