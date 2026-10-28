# Perfiles y recomendaciones para Harp Helú

Comparación de 2026 con modelos congelados. Referencia: promedio equiponderado de Veracruz, Campeche y Cancún, todos en la categoría sin altitud.
Cada lanzamiento conserva física, ubicación y arsenal. Las diferencias son predictivas, no efectos causales ni transporte aerodinámico.
Se exige soporte de desarrollo: al menos 300 pitches y 10 juegos en Harp y en el grupo de referencia por tipo/mano; intersección de rangos marginales 1-99% de velocidad, IVB, HB y spin. Esto no garantiza soporte multivariado.
Pitches evaluados dentro de ese soporte: 88,852 de 135,604.
Intervalos 95% con 1,000 remuestreos de juegos; condicionados al modelo, sin corregir múltiples comparaciones. Son análisis exploratorios.

## Cómo actuar

1. Comparar candidatos dentro del mismo tipo de lanzamiento y mano; revisar el rango físico y la historia de recta primaria.
2. Si el intervalo del riesgo de jonrón o contacto duro queda por encima de cero, priorizar revisión de ubicación y video antes de aumentar uso.
3. Si el intervalo cruza cero o falta soporte, solicitar más juegos. No etiquetar al pitcher como adaptado o inadaptado.
4. Un diferencial favorable de swing fallido no compensa automáticamente un riesgo mayor de jonrón: revisar ambos resultados.
5. El score combinado conserva delta cero entre estadios. No hay ganadores o perdedores de Pitching+ por altitud demostrados con esta selección.

Advertencia de calibración: en Harp, el modelo estima en promedio 0.695 jonrones por 100 pitches y se observan 0.866 (52 en 6,005). Las pequeñas diferencias favorables del escenario no justifican afirmar menor riesgo real; se necesita validación prospectiva.

## Diferencias observadas en las predicciones

| Tipo / mano | n / juegos | Cambio HR por 100 pitches | IC95% | Lectura |
|---|---:|---:|---:|---|
| Changeup / Left | 3828 / 371 | -0.022 | [-0.024, -0.021] | Riesgo predicho menor: validar con más datos |
| Changeup / Right | 7519 / 447 | -0.019 | [-0.020, -0.019] | Riesgo predicho menor: validar con más datos |
| Curveball / Left | 2023 / 325 | -0.025 | [-0.026, -0.023] | Riesgo predicho menor: validar con más datos |
| Curveball / Right | 6050 / 447 | -0.022 | [-0.023, -0.021] | Riesgo predicho menor: validar con más datos |
| Cutter / Left | 1332 / 241 | -0.021 | [-0.023, -0.019] | Riesgo predicho menor: validar con más datos |
| Cutter / Right | 2886 / 399 | -0.024 | [-0.026, -0.023] | Riesgo predicho menor: validar con más datos |
| Four-Seam / Left | 4491 / 368 | -0.023 | [-0.024, -0.021] | Riesgo predicho menor: validar con más datos |
| Four-Seam / Right | 20174 / 453 | -0.025 | [-0.026, -0.025] | Riesgo predicho menor: validar con más datos |
| Sinker / Left | 3599 / 354 | -0.022 | [-0.023, -0.021] | Riesgo predicho menor: validar con más datos |
| Sinker / Right | 10934 / 447 | -0.024 | [-0.025, -0.023] | Riesgo predicho menor: validar con más datos |
| Slider / Left | 5336 / 402 | -0.025 | [-0.026, -0.024] | Riesgo predicho menor: validar con más datos |
| Slider / Right | 19664 / 453 | -0.028 | [-0.029, -0.027] | Riesgo predicho menor: validar con más datos |
| Splitter / Right | 1016 / 228 | -0.013 | [-0.015, -0.011] | Riesgo predicho menor: validar con más datos |

## Perfil físico de referencia

perfiles_fisicos.csv describe el cuartil central del 10% de mayor Stuff+ físico en calibración, por tipo y mano. Incluye diferenciales contra recta y uso histórico cuando existen.
Son combinaciones observadas para comparar prospectos, no instrucciones para combinar por separado extremos de cada rango. No son un óptimo de contratación ni una ventaja exclusiva de Harp.
Usar video, salud, comando y rol para decidir; los datos anonimizados no permiten resolver esos aspectos.

## Fundamento y límites físicos

La menor densidad del aire motiva examinar movimiento y riesgo de batazo elevado. El cambio real de movimiento requiere mediciones o un modelo físico adicional; no se aplica un porcentaje impuesto.
El diferencial de velocidad y el rodado son hipótesis de interés del reto. Los resultados locales deben contrastarlas; no se recomienda una familia de pitcheos únicamente por esa hipótesis.

Fuentes: convocatoria local, diccionario de datos, protocolo y modelos congelados de esta ejecución.
Marco físico: Alan M. Nathan, Baseball at High Altitude (https://baseball.physics.illinois.edu/Denver.html) y Determining Pitch Movement from PITCHf/x Data (https://baseball.physics.illinois.edu/Movement.pdf). Las magnitudes observadas de este análisis proceden de los datos locales, no de trasladar porcentajes de MLB.
