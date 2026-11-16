"""Ejecuta todas las pruebas del proyecto desde un único comando.

Uso: python verificar.py
"""

from pathlib import Path
import subprocess
import sys

RAIZ = Path(__file__).resolve().parent
SUITES = (
    ("Pruebas funcionales", "tests/test_sistema.py", False),
    ("Validaciones e integridad", "tests/test_validaciones.py", False),
    ("Plantillas HTML", "tests/test_plantillas.py", False),
    ("Rutas HTTP Flask", "tests/test_flask.py", True),
)


def ejecutar():
    resultados = []
    for nombre, archivo, opcional in SUITES:
        print(f"\n{'=' * 60}\n{nombre}\n{'=' * 60}", flush=True)
        proceso = subprocess.run([sys.executable, str(RAIZ / archivo)], cwd=RAIZ, check=False)
        if proceso.returncode == 0:
            estado = "APROBADO"
        elif opcional and proceso.returncode == 2:
            estado = "PENDIENTE: instala Flask"
        else:
            estado = "FALLÓ"
        resultados.append((nombre, estado))

    print("\nRESUMEN")
    for nombre, estado in resultados:
        print(f"- {nombre}: {estado}")
    return 1 if any(estado == "FALLÓ" for _, estado in resultados) else 0


if __name__ == "__main__":
    sys.exit(ejecutar())
