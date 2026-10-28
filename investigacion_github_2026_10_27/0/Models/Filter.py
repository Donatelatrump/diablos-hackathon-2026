import pandas as pd

# 1. Carga de datos
df = pd.read_parquet('Data/stuff_model_df.parquet')

# 2. Imprimir todas las columnas disponibles
print("\n--- Lista de las 84 Columnas ---")
for i, col in enumerate(df.columns, 1):
    print(f"{i}. {col}")

# 3. Ver tipos de datos y valores nulos
print("\n--- Resumen General ---")
print(df.info())