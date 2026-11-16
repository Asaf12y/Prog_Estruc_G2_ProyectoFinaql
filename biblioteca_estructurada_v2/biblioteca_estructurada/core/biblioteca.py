"""Reglas de negocio expresadas mediante funciones y listas/diccionarios."""

from datetime import date, datetime, timedelta
import heapq
import re
import uuid

from core import datos
from core.estructuras import (
    buscar_en_arbol, buscar_lineal, construir_arbol_isbn,
    construir_grafo, estadisticas_grafo, heap_reservas_pendientes,
    normalizar, prestamos_vencidos_heap, recomendar_bfs,
    reservas_por_prioridad,
)


MAX_PRESTAMOS_POR_USUARIO = 3
DIAS_PRESTAMO = 14


def _id(prefijo):
    return prefijo + uuid.uuid4().hex[:10].upper()


def _encontrar(registros, identificador, nombre="Registro"):
    for registro in registros:
        if registro["id"] == identificador:
            return registro
    raise ValueError(f"{nombre} no encontrado.")


def _isbn(texto):
    """Comprueba ISBN-10 (incluido X) e ISBN-13 y sus dígitos de control."""
    if not isinstance(texto, str):
        raise ValueError("El ISBN debe ser texto.")
    isbn = texto.replace("-", "").replace(" ", "").strip().upper()
    if len(isbn) == 10 and re.fullmatch(r"[0-9]{9}[0-9X]", isbn):
        control = 10 if isbn[-1] == "X" else int(isbn[-1])
        if (sum((10 - i) * int(c) for i, c in enumerate(isbn[:9])) + control) % 11 == 0:
            return isbn
    if len(isbn) == 13 and isbn.isascii() and isbn.isdigit():
        if sum((1 if i % 2 == 0 else 3) * int(c) for i, c in enumerate(isbn)) % 10 == 0:
            return isbn
    raise ValueError("ISBN inválido: comprueba que tenga 10 o 13 caracteres y un dígito de control correcto.")


def _texto(formulario, clave, etiqueta, maximo, obligatorio=True, conservar_saltos=False):
    valor = formulario.get(clave, "")
    if not isinstance(valor, str):
        raise ValueError(f"{etiqueta} debe ser texto.")
    valor = valor.strip() if conservar_saltos else " ".join(valor.split())
    if obligatorio and not valor:
        raise ValueError(f"{etiqueta} es obligatorio.")
    if len(valor) > maximo or any(ord(c) < 32 and c not in "\n\r\t" for c in valor):
        raise ValueError(f"{etiqueta} supera los {maximo} caracteres o contiene caracteres inválidos.")
    return valor


def _entero(valor, campo, minimo, maximo):
    if not isinstance(valor, str) or not re.fullmatch(r"[0-9]+", valor.strip()):
        raise ValueError(f"{campo} debe ser un número entero.")
    numero = int(valor.strip())
    if numero < minimo or numero > maximo:
        raise ValueError(f"{campo} debe estar entre {minimo} y {maximo}.")
    return numero


def _campos_libro(formulario):
    """Valida y normaliza un formulario completo antes de modificar el JSON."""
    return {
        "isbn": _isbn(formulario.get("isbn", "")),
        "titulo": _texto(formulario, "titulo", "Título", 120),
        "autor": _texto(formulario, "autor", "Autor", 120),
        "categoria": _texto(formulario, "categoria", "Categoría", 120),
        "anio": _entero(formulario.get("anio", ""), "Año", 1, date.today().year + 1),
        "ejemplares": _entero(formulario.get("ejemplares", ""), "Ejemplares", 0, 10000),
        "descripcion": _texto(formulario, "descripcion", "Descripción", 800, False, True),
    }


def _campos_usuario(formulario):
    nombre = _texto(formulario, "nombre", "Nombre", 120)
    correo = _texto(formulario, "correo", "Correo", 200).lower()
    if not re.fullmatch(r"[^\s@]+@[^\s@.]+(?:\.[^\s@.]+)+", correo) or ".." in correo:
        raise ValueError("Ingresa un correo electrónico válido.")
    return {"nombre": nombre, "correo": correo}


def _libros_ordenados(libros):
    return sorted(libros, key=lambda libro: normalizar(libro["titulo"]))


def _ocupacion_por_libro(base):
    """Calcula todos los ejemplares ocupados con una pasada O(L+P+R)."""
    ocupacion = {libro["id"]: 0 for libro in base["libros"]}
    for prestamo in base["prestamos"]:
        if prestamo["devuelto_en"] is None:
            ocupacion[prestamo["libro_id"]] += 1
    for reserva in base["reservas"]:
        if reserva["estado"] == "lista":
            ocupacion[reserva["libro_id"]] += 1
    return ocupacion


def _ocupados(base, libro_id):
    return _ocupacion_por_libro(base)[libro_id]


def _disponibles(base, libro_id):
    libro = _encontrar(base["libros"], libro_id, "Libro")
    return libro["ejemplares"] - _ocupados(base, libro_id)


def _asignar_reservas(base, libro_id):
    """Heap: entrega ejemplares libres a reservas pendientes más antiguas."""
    monticulo = heap_reservas_pendientes(base["reservas"], libro_id)
    libres = _disponibles(base, libro_id)
    por_id = {reserva["id"]: reserva for reserva in base["reservas"]}
    while libres > 0 and monticulo:
        _, reserva_id = heapq.heappop(monticulo)
        por_id[reserva_id]["estado"] = "lista"
        libres -= 1


def listar_libros(consulta="", categoria=""):
    base = datos.leer()
    libros = base["libros"]
    if categoria:
        libros = [libro for libro in libros if libro["categoria"] == categoria]
    if consulta.strip():
        consulta_isbn = consulta.strip().replace("-", "").replace(" ", "").upper()
        # Solo se construye el BST cuando se consulta un ISBN completo.
        es_isbn = bool(re.fullmatch(r"[0-9]{9}[0-9X]|[0-9]{13}", consulta_isbn))
        exacto = buscar_en_arbol(construir_arbol_isbn(libros), consulta_isbn) if es_isbn else None
        libros = [exacto] if exacto else buscar_lineal(libros, consulta)
    ocupacion = _ocupacion_por_libro(base)
    salida = []
    for libro in _libros_ordenados(libros):
        salida.append({**libro, "disponibles": libro["ejemplares"] - ocupacion[libro["id"]]})
    categorias = sorted(set(item["categoria"] for item in base["libros"]))
    return salida, categorias


def obtener_libro(libro_id):
    base = datos.leer()
    libro = _encontrar(base["libros"], libro_id, "Libro")
    recomendaciones = recomendar_bfs(base["libros"], libro_id)
    reservas = reservas_por_prioridad(base["reservas"], libro_id)
    return {
        **libro,
        "disponibles": _disponibles(base, libro_id),
        "recomendaciones": recomendaciones,
        "reservas_pendientes": len(reservas),
        "prestamos_activos": sum(
            p["libro_id"] == libro_id and p["devuelto_en"] is None
            for p in base["prestamos"]
        ),
    }


def crear_libro(formulario):
    campos = _campos_libro(formulario)

    def operacion(base):
        if buscar_en_arbol(construir_arbol_isbn(base["libros"]), campos["isbn"]):
            raise ValueError("Ya existe un libro registrado con ese ISBN.")
        libro = {"id": _id("LIB"), **campos}
        base["libros"].append(libro)
        return libro["id"]

    return datos.cambiar(operacion)


def editar_libro(libro_id, formulario):
    campos = _campos_libro(formulario)

    def operacion(base):
        libro = _encontrar(base["libros"], libro_id, "Libro")
        if any(b["isbn"] == campos["isbn"] and b["id"] != libro_id for b in base["libros"]):
            raise ValueError("Otro libro ya tiene el ISBN indicado.")
        if campos["ejemplares"] < _ocupados(base, libro_id):
            raise ValueError("No puedes reducir ejemplares por debajo de los prestados o apartados.")
        libro.update(campos)
        _asignar_reservas(base, libro_id)
        return libro_id

    return datos.cambiar(operacion)


def eliminar_libro(libro_id):
    def operacion(base):
        _encontrar(base["libros"], libro_id, "Libro")
        if any(p["libro_id"] == libro_id for p in base["prestamos"]):
            raise ValueError("No se puede eliminar un libro con historial de préstamos.")
        if any(r["libro_id"] == libro_id for r in base["reservas"]):
            raise ValueError("No se puede eliminar un libro con historial de reservas.")
        base["libros"] = [b for b in base["libros"] if b["id"] != libro_id]

    datos.cambiar(operacion)


def listar_usuarios():
    base = datos.leer()
    salida = []
    for usuario in base["usuarios"]:
        activos = sum(
            p["usuario_id"] == usuario["id"] and p["devuelto_en"] is None
            for p in base["prestamos"]
        )
        salida.append({**usuario, "activos": activos})
    return sorted(salida, key=lambda u: normalizar(u["nombre"]))


def crear_usuario(formulario):
    campos = _campos_usuario(formulario)

    def operacion(base):
        if any(u["correo"].casefold() == campos["correo"].casefold() for u in base["usuarios"]):
            raise ValueError("Ya existe un usuario con ese correo.")
        usuario = {"id": _id("USU"), **campos}
        base["usuarios"].append(usuario)
        return usuario["id"]

    return datos.cambiar(operacion)


def obtener_usuario(usuario_id):
    base = datos.leer()
    return dict(_encontrar(base["usuarios"], usuario_id, "Usuario"))


def editar_usuario(usuario_id, formulario):
    campos = _campos_usuario(formulario)

    def operacion(base):
        usuario = _encontrar(base["usuarios"], usuario_id, "Usuario")
        if any(u["id"] != usuario_id and u["correo"].casefold() == campos["correo"].casefold()
               for u in base["usuarios"]):
            raise ValueError("Otro usuario ya tiene ese correo.")
        usuario.update(campos)
        return usuario_id

    return datos.cambiar(operacion)


def eliminar_usuario(usuario_id):
    def operacion(base):
        _encontrar(base["usuarios"], usuario_id, "Usuario")
        if any(p["usuario_id"] == usuario_id for p in base["prestamos"]):
            raise ValueError("No se puede eliminar un usuario con historial de préstamos.")
        if any(r["usuario_id"] == usuario_id for r in base["reservas"]):
            raise ValueError("No se puede eliminar un usuario con historial de reservas.")
        base["usuarios"] = [u for u in base["usuarios"] if u["id"] != usuario_id]

    datos.cambiar(operacion)


def _adjuntar_nombres(base, registros):
    libros = {b["id"]: b for b in base["libros"]}
    usuarios = {u["id"]: u for u in base["usuarios"]}
    return [
        {**registro, "titulo": libros[registro["libro_id"]]["titulo"],
         "usuario": usuarios[registro["usuario_id"]]["nombre"]}
        for registro in registros
    ]


def listar_prestamos(estado="activos"):
    base = datos.leer()
    prestamos = base["prestamos"]
    if estado == "activos":
        prestamos = [p for p in prestamos if p["devuelto_en"] is None]
    elif estado == "devueltos":
        prestamos = [p for p in prestamos if p["devuelto_en"] is not None]
    salida = _adjuntar_nombres(base, prestamos)
    hoy = date.today()
    for prestamo in salida:
        prestamo["dias_atraso"] = (
            max((hoy - date.fromisoformat(prestamo["vence_en"])).days, 0)
            if prestamo["devuelto_en"] is None else 0
        )
    return sorted(salida, key=lambda p: p["prestado_en"], reverse=True)


def crear_prestamo(usuario_id, libro_id):
    def operacion(base):
        _encontrar(base["usuarios"], usuario_id, "Usuario")
        _encontrar(base["libros"], libro_id, "Libro")
        activos = [p for p in base["prestamos"] if p["usuario_id"] == usuario_id and p["devuelto_en"] is None]
        if len(activos) >= MAX_PRESTAMOS_POR_USUARIO:
            raise ValueError("El usuario ya tiene tres préstamos activos.")
        if any(p["libro_id"] == libro_id for p in activos):
            raise ValueError("Este usuario ya tiene prestado ese libro.")
        apartados_usuario = [
            r for r in base["reservas"]
            if r["libro_id"] == libro_id and r["usuario_id"] == usuario_id and r["estado"] == "lista"
        ]
        if not apartados_usuario and _disponibles(base, libro_id) <= 0:
            raise ValueError("No hay ejemplares disponibles. Puedes realizar una reserva.")
        if not apartados_usuario and any(
            r["libro_id"] == libro_id and r["usuario_id"] == usuario_id and r["estado"] == "pendiente"
            for r in base["reservas"]
        ):
            raise ValueError("Tu reserva está pendiente. Espera a que quede lista.")
        if apartados_usuario:
            apartados_usuario[0]["estado"] = "cumplida"
        hoy = date.today()
        prestamo = {
            "id": _id("PRE"), "libro_id": libro_id, "usuario_id": usuario_id,
            "prestado_en": hoy.isoformat(),
            "vence_en": (hoy + timedelta(days=DIAS_PRESTAMO)).isoformat(),
            "devuelto_en": None,
        }
        base["prestamos"].append(prestamo)
        return prestamo["id"]

    return datos.cambiar(operacion)


def devolver_prestamo(prestamo_id):
    def operacion(base):
        prestamo = _encontrar(base["prestamos"], prestamo_id, "Préstamo")
        if prestamo["devuelto_en"] is not None:
            raise ValueError("Este préstamo ya fue devuelto.")
        prestamo["devuelto_en"] = date.today().isoformat()
        _asignar_reservas(base, prestamo["libro_id"])
        return prestamo["libro_id"]

    return datos.cambiar(operacion)


def listar_reservas(estado="todas"):
    base = datos.leer()
    reservas = base["reservas"]
    if estado != "todas":
        reservas = [r for r in reservas if r["estado"] == estado]
    salida = _adjuntar_nombres(base, reservas)
    return sorted(salida, key=lambda r: r["creada_en"], reverse=True)


def crear_reserva(usuario_id, libro_id):
    def operacion(base):
        _encontrar(base["usuarios"], usuario_id, "Usuario")
        _encontrar(base["libros"], libro_id, "Libro")
        if any(
            p["usuario_id"] == usuario_id and p["libro_id"] == libro_id and p["devuelto_en"] is None
            for p in base["prestamos"]
        ):
            raise ValueError("Ya tienes este libro prestado.")
        if any(
            r["usuario_id"] == usuario_id and r["libro_id"] == libro_id and r["estado"] in ("pendiente", "lista")
            for r in base["reservas"]
        ):
            raise ValueError("Ya tienes una reserva activa para este libro.")
        if _disponibles(base, libro_id) > 0:
            raise ValueError("El libro está disponible; realiza un préstamo directamente.")
        reserva = {
            "id": _id("RES"), "libro_id": libro_id, "usuario_id": usuario_id,
            "creada_en": datetime.now().isoformat(timespec="microseconds"),
            "estado": "pendiente",
        }
        base["reservas"].append(reserva)
        return reserva["id"]

    return datos.cambiar(operacion)


def cancelar_reserva(reserva_id):
    def operacion(base):
        reserva = _encontrar(base["reservas"], reserva_id, "Reserva")
        if reserva["estado"] not in ("pendiente", "lista"):
            raise ValueError("Solo puedes cancelar reservas pendientes o listas.")
        libro_id = reserva["libro_id"]
        reserva["estado"] = "cancelada"
        _asignar_reservas(base, libro_id)
        return libro_id

    return datos.cambiar(operacion)


def tablero():
    base = datos.leer()
    activos = [p for p in base["prestamos"] if p["devuelto_en"] is None]
    ocupacion = _ocupacion_por_libro(base)
    vencidos = prestamos_vencidos_heap(base["prestamos"])
    prestamos_por_id = {p["id"]: p for p in base["prestamos"]}
    urgentes = _adjuntar_nombres(base, [prestamos_por_id[id_] for id_, _ in vencidos[:5]])
    for item, (_, dias) in zip(urgentes, vencidos[:5]):
        item["dias_atraso"] = dias
    return {
        "libros": len(base["libros"]),
        "usuarios": len(base["usuarios"]),
        "activos": len(activos),
        "vencidos": len(vencidos),
        "pendientes": sum(r["estado"] == "pendiente" for r in base["reservas"]),
        "disponibles": sum(b["ejemplares"] - ocupacion[b["id"]] for b in base["libros"]),
        "urgentes": urgentes,
        "recientes": _adjuntar_nombres(base, base["prestamos"][-5:][::-1]),
    }


def analisis_estructuras():
    base = datos.leer()
    grafo = construir_grafo(base["libros"])
    estadisticas = estadisticas_grafo(grafo)
    return {
        "n_libros": len(base["libros"]),
        "n_usuarios": len(base["usuarios"]),
        "n_prestamos": len(base["prestamos"]),
        "n_reservas": len(base["reservas"]),
        "n_vertices": estadisticas["vertices"],
        "n_aristas": estadisticas["aristas"],
        "n_vencidos": len(prestamos_vencidos_heap(base["prestamos"])),
        "grafo": [
            {"titulo": libro["titulo"], "conexiones": len(grafo[libro["id"]])}
            for libro in _libros_ordenados(base["libros"])
        ],
    }
