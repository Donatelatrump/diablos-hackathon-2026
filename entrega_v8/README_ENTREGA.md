# Entrega v8

Documento técnico vigente: DOCUMENTO_TECNICO_V8.pdf. Recomendaciones: RECOMENDACIONES_V8.md. Los documentos antiguos v3/v4 no forman parte del paquete.

## Reproducir localmente

Instalar `requirements-entrega.txt`. Con el dataset autorizado y los artefactos locales v8 disponibles, ejecutar `validar_pitchers_v8.py`, `analisis_operativo_v8.py`, `explicar_casos_v8.py`, `generar_paquete_v8.py` y `verificar_entrega_v8.py`. La auditoría exige una salida nueva y no sobrescribe un protocolo iniciado. Ejecutar `python -m streamlit run dashboard_stuff_plus.py` desde la raíz.

El ZIP contiene scores derivados por lanzamiento (solo IDs anónimos y predicciones), agregados, código y documentación. Para entrenamiento desde cero se necesitan el dataset de la organización y los artefactos parentales generados por la cadena v5-v8. No incluye mediciones/outcomes originales ni modelos binarios. El dashboard completo funciona en el workspace local con esos modelos. Los scores completos se conservan localmente en `stuff_plus_output_v8/scores_pitch_v8.parquet`.

Las cinco mejoras están implementadas: auditoría de pitchers, análisis de entorno, interfaz operativa, tres casos y documentación. Comparación nominal de Harp Helú y park holdout permanecen limitados por datos faltantes. No hay efecto causal confirmado ni benchmark futuro intacto.

## Antes de enviar

Completar nombres, correos y elegibilidad del equipo; confirmar la modalidad de acceso a modelos y scores detallados con la organización. No se envía correo automáticamente. La fecha publicada consultada es 22/10/2026.

## Actualización del dashboard (20/10/2026)

El simulador expone nueve probabilidades, riesgos y una explicación SHAP local comprobada. Incluye diferencias por categoría, baseline por conteo y scores descargables. La pestaña Estadios y altitudes compara referencias geográficas con fuentes; no infiere estadio desde una categoría. Consultar ESTADIOS_Y_ALTITUDES.md y AUDITORIA_ESTADIOS.json. Ejecutar `python estadios_v8.py` antes de regenerar el paquete para actualizar cobertura. El mapeo por juego necesita evidencia externa explícita.
