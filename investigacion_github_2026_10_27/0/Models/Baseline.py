import pandas as pd
import os

# 1. Configurar la ruta relativa segura y cargar el dataset

print("Cargando archivo Parquet...")
base_dir = os.path.dirname(os.path.dirname(__file__)) 
file_path = os.path.join(base_dir, 'Data', 'stuff_model_df.parquet')

df = pd.read_parquet(file_path)

# 2. Aislamiento Temporal (Media Entrada)
half_inning_cols = ['game_anon_id', 'Inning', 'Top/Bottom']

# 3. Cálculo de RRI (Runs Rest of Inning)
df['Runs_Rest_Of_Inning'] = df.groupby(half_inning_cols)['RunsScored'].transform(lambda x: x[::-1].cumsum()[::-1])

# 4. Generación del Baseline (xRunValue por Conteo)
baseline_xRunValue = df.groupby('count')['Runs_Rest_Of_Inning'].mean().reset_index()
baseline_xRunValue.rename(columns={'Runs_Rest_Of_Inning': 'xRunValue'}, inplace=True)

# 5. Exportación del Entregable
output_path = os.path.join(base_dir, 'Data', 'baseline_xRunValue.csv')
baseline_xRunValue.to_csv(output_path, index=False)

print("Baseline de xRunValue calculado y guardado")
print(baseline_xRunValue.to_string(index=False))
