# Entrega T04

Se reemplazaron las órdenes por prioridades ordenadas, con las cuatro dimensiones ponderadas y evidencia asignada al nodo más cercano dentro de 500 metros. Se conserva el cálculo original y se identifica el origen de los incidentes; se eliminó la consola Streamlit y sus dependencias. El nivel usa el umbral existente de 0,65: crítico o no crítico.

Se actualizaron las pruebas del contrato, API y auditoría; se verifica la suma de aportes con tolerancia de redondeo y la asignación de evidencia cercana, lejana y simulada. No se ajustó ninguna prueba de texto del Analista.

Verificación: ` .venv/Scripts/python.exe -m pytest -q tests` (6 pruebas aprobadas) y ` .venv/Scripts/python.exe -c "import api"` (correcto). El grep solicitado devuelve dos coincidencias de «Movilidad» en api.py, porque el patrón `movil` coincide con esa palabra; no son referencias a despacho.

Pendiente: la limpieza integral de los textos y respuestas preexistentes del Analista corresponde a T05; la interfaz y los valores de los endpoints y corredor reservados quedan para T06 y T11. La variación conserva la unidad porcentual del motor existente.
