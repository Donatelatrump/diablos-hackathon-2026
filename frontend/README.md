# Diablos · React + TypeScript

Frontend Vite/React con CSS adaptable, navegación por URL, formularios controlados, tablas ordenables y paginadas, descargas y estados de carga/error. El contenido conserva el español del dashboard original.

## Ejecutar

Desde la raíz: `python3 src/dashboard_api.py`. En otra terminal: `cd frontend && npm install && npm run dev`. Abre http://127.0.0.1:5173.

`npm run build` verifica TypeScript y genera `dist/`. La API Python también sirve esa compilación en http://127.0.0.1:8000. `npm test` ejecuta las pruebas con Chrome en tamaños de escritorio y móvil.

## Vistas

- **Simulador:** perfiles del bundle, mediciones físicas, contexto, comparación y puntuaciones del pipeline Python existente; resultados marcados como desactualizados al editar el formulario.
- **Comparar estadios:** dos estadios seleccionables, nombres reales y tabla de probabilidades con diferencias en puntos porcentuales. Mantiene las mismas mediciones físicas y marca los resultados como desactualizados al cambiar la selección.
- **Lanzadores:** filtros por temporada y muestra, búsqueda, ficha, repertorio y mapa de movimiento. Sin bundle local utiliza el reporte integral guardado, identificado como una referencia distinta.
- **Confianza:** métricas y tamaño de muestra de las pruebas de temporada, lanzadores nuevos y estadio no visto. Los dos últimos provienen de los reportes por estadios, independientemente del modelo de simulación seleccionado.
- **Ayuda:** interpretación de índices y documentos originales descargables.
- **Histórico v8:** tabla de repertorios con incertidumbre y documentos originales.
- **Escena 3D:** reutiliza el código y los activos originales, incluidas las cámaras y reproducción. El laboratorio de altitud conserva la fórmula educativa de densidad y no cambia las predicciones.

## Datos y modelos

No se incluyen predicciones ficticias. La API descubre los bundles completos `stuff_plus_output_v9_estadios`, `stuff_plus_output_v9_incremental` y `stuff_plus_output_v9`. Las solicitudes de simulación se validan y delegan en `precision_model.infer_dashboard`; los modelos conservan sus verificaciones de hash. No se modificó el entrenamiento ni el cálculo de los índices.

Los CSV/JSON y documentos guardados se pueden consultar sin pandas, CatBoost o Streamlit instalados. La inferencia requiere el entorno Python del proyecto y modelos locales completos. El ejemplo 3D sin modelos usa valores ilustrativos, etiquetados como tales.

La interfaz Streamlit sigue disponible. Sus paneles especializados de investigación (atribuciones SHAP, candidatos experimentales de precisión, variación por juego y simulación histórica v8) no se portaron en esta primera migración; los resultados y documentos históricos sí están disponibles en React. La inferencia real de extremo a extremo debe verificarse al instalar los bundles v9; las pruebas del contrato usan un adaptador simulado y los reportes locales reales.

## Estructura

- `src/App.tsx`: navegación, lanzadores, evidencia, documentación.
- `src/Simulator.tsx`: formulario, comparación y resultados.
- `src/components.tsx`: tablas, recursos HTTP y escena 3D.
- `src/api.ts`: contratos TypeScript y etiquetas.
- `src/style.css`: identidad visual y diseño adaptable.
- `../src/dashboard_api.py`: API HTTP local, reportes y adaptación a inferencia Python.

La API tiene una lista cerrada de tablas/documentos y limita el tamaño de las solicitudes de inferencia. Es un servidor local, no un despliegue público con autenticación.
