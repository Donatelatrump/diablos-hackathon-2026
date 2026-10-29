# Código fuente

Los módulos conservan sus nombres para mantener la compatibilidad con los modelos históricos.

| Prefijo | Responsabilidad |
| --- | --- |
| `dashboard_` | Pantallas, navegación y componentes del dashboard |
| `entrenar_`, `precision_`, `coherent_events` | Entrenamiento e inferencia |
| `analizar_`, `analisis_`, `auditar_`, `probar_` | Experimentos y análisis |
| `reportar_`, `generar_`, `exportar_` | Reportes y entregables |
| `verificar_`, `validar_` | Validación de modelos y paquetes |
| `actualizar_`, `clasificar_`, `completar_` | Preparación y mantenimiento de datos |

Desde la raíz del repositorio:

```bash
python -m streamlit run app.py
python src/entrenar_stuff_plus_v9.py --help
```

Los modelos, datos y reportes se resuelven desde la raíz del proyecto, independientemente de la ubicación de estos módulos.
