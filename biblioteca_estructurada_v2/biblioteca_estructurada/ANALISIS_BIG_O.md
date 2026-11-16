# Análisis de notación asintótica — BiblioEstructuras

## Variables

- **n**: número de libros / tamaño del archivo o de una colección según el contexto.
- **V**: cantidad de vértices (libros) del grafo.
- **E**: cantidad de aristas (relaciones) del grafo.
- **k**: número de reservas pendientes para un mismo libro.
- **p**: número de préstamos activos o históricos según la operación.
- **r**: número total de reservas.
- **u**: número de usuarios.
- **s**: tamaño del JSON serializado en caracteres o bytes.

## 1. Listas

Los datos del JSON son **listas** de diccionarios. Agregar un libro a una lista es O(1) amortizado. Recorrer una lista para buscar un título o un usuario por identificador es **O(n)** en el peor caso. El filtrado por categoría recorre los libros, **O(n)**.

## 2. Árbol binario de búsqueda balanceado

Se ordena el catálogo por ISBN y se usa el elemento central como raíz, repitiendo el proceso con cada mitad. Ordenar cuesta **O(n log n)** y construir los nodos con las mitades **O(n)**. El costo combinado de construir el índice es **O(n log n)**. La altura del árbol queda en **O(log n)** y buscar un ISBN exacto sobre ese índice es **O(log n)**. **Limitación:** el índice no se mantiene entre peticiones, así que para cada búsqueda el costo total es **O(n log n)**. No se debe afirmar que todo el proceso web cuesta O(log n).

## 3. Grafos + BFS

Cada libro es un vértice y se conectan dos libros si comparten autor y/o categoría. Comparar todos los pares lleva **O(n²)** y el grafo se almacena como diccionario de listas de vecinos. BFS explora cada vértice y cada arista como máximo un número constante de veces: **O(V+E)**. Tras BFS, las recomendaciones halladas se ordenan por distancia, afinidad y título: **O(V log V)** en el peor caso. Además, se reconstruye el grafo por petición (**O(n²)**). Con un catálogo grande conviene reutilizar el grafo y agrupar libros por autor/categoría.

## 4. Montículos (heaps)

Se emplea `heapq` de la biblioteca estándar de Python:

- Filtrar todas las reservas para obtener las k pendientes de un título cuesta **O(r)**.
- `heapq.heapify(elementos)`: construye el heap de k elementos en **O(k)**. Por tanto `heap_reservas_pendientes()` completa cuesta **O(r+k)**.
- `heapq.heappop(heap)`: saca el elemento de mayor prioridad en **O(log k)**.
- Para reservas: prioridad por fecha más antigua, usando tuplas `(creada_en, id)`.
- Para vencimientos: prioridad por *más días de atraso*, usando `(-dias, fecha, id)`.
- Extraer **todas** las reservas de un libro, una por una, cuesta **O(k log k)** tras construir el heap.

## 5. Persistencia JSON

`json.load()` y `json.dump()` procesan todo el contenido, por tanto son **O(s)** en tiempo y memoria en función del tamaño del JSON, no de una sola entidad. Cada modificación escribe de nuevo el archivo completo. La validación de integridad es **O(n+u+p+r)** en promedio, gracias a conjuntos y diccionarios. Es una elección sencilla y defendible para un proyecto académico.

## 6. Optimización adicional: ocupación de ejemplares

En vez de recorrer todos los préstamos y reservas por cada libro de un catálogo, `_ocupacion_por_libro()` realiza una única pasada por libros, préstamos y reservas y acumula los ejemplares ocupados en un diccionario. Esto cuesta **O(n+p+r)** en tiempo y **O(n)** en memoria auxiliar. Luego obtener la disponibilidad de cada título es O(1) promedio. El catálogo aún ordena los libros por título en **O(n log n)**.

`_asignar_reservas()` construye una cola de prioridad y consulta los ejemplares libres una sola vez. Asignar k reservas cuesta **O(n+p+r+k log k)** en tiempo aproximado, incluida la construcción de sus índices.

## 7. Complejidad espacial

- Listas: **O(n)**.
- Árbol BST: **O(n)** nodos, además de la lista ordenada.
- Grafo: **O(V + E)**, con hasta **O(n²)** aristas si todos los libros comparten una categoría.
- Heap: **O(k)**.

## 8. Ejemplos de explicación ante el profesor

**Pregunta:** ¿Por qué no buscas el ISBN con una lista?

**Respuesta:** la lista requiere comparar hasta n registros, O(n). Al construir el BST balanceado, la búsqueda sobre el índice toma O(log n). Sin embargo, reconstruir el árbol antes de cada petición implica O(n log n) en total; es una comparación de costos con y sin índice persistente.

**Pregunta:** ¿Dónde intervienen los grafos?

**Respuesta:** cada libro es un nodo y una arista indica autor/categoría común. BFS descubre libros relacionados y su distancia en la red.

**Pregunta:** ¿Qué problema resuelve un heap?

**Respuesta:** elegir la reserva más antigua o el préstamo más atrasado sin tener que reordenar toda la lista después de cada extracción.

**Pregunta:** ¿Qué pasa al cerrar la app?

**Respuesta:** la información queda en `data/biblioteca.json` y se recupera al iniciarla de nuevo.
