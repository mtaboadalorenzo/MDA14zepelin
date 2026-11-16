"""Entrada de la app «equipo2» en Streamlit Cloud, que solo admite una app por archivo.
No contiene lógica: ejecuta app.py. La versión la sigue decidiendo el secret VERSION ("equipo2")."""
import pathlib
import runpy

runpy.run_path(str(pathlib.Path(__file__).with_name("app.py")), run_name="__main__")
