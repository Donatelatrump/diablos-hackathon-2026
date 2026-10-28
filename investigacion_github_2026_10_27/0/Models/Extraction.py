import pandas as pd
import os

# 1. Cargar el dataset
print("Cargando archivo Parquet...")
base_dir = os.path.dirname(os.path.dirname(__file__)) 
file_path = os.path.join(base_dir, 'Data', 'stuff_model_df.parquet')

df = pd.read_parquet(file_path)

# 2. Definir listas de columnas según el diccionario de datos
# Identificadores directos y de agrupación que no deben ser entrenados
id_columns = [
    'PitchUID', 
    'game_anon_id', 
    'pitcher_anon_id', 
    'batter_anon_id', 
    'catcher_anon_id'
]

# Variables marcadas como target_only (Lo que vamos a predecir o resultados de la jugada)
target_columns = [
    'PitchCall', 'KorBB', 'play_result', 'hit_type', 'ExitSpeed', 
    'Angle', 'Direction', 'Distance', 'is_swing', 'is_whiff', 
    'is_contact', 'is_called_strike', 'is_swinging_strike', 
    'is_ball_in_play', 'is_batted', 'is_hit', 'single', 'double', 
    'triple', 'home_run', 'base_on_balls', 'strikeout', 
    'is_hit_by_pitch', 'RunsScored', 'OutsOnPlay', 'swung_outside_strike_zone'
]

location_columns = [    
    'PlateLocHeight', 
    'PlateLocSide', 
    'in_strike_zone', 
    'outside_strike_zone'
]

# 3. Separar los targets del dataset principal (Guardamos 'X' y 'y')
# Guardamos los targets en un DataFrame independiente (útil para la fase de entrenamiento)
df_targets = df[target_columns].copy()

# 4. Limpiar el dataset de entrenamiento (Features)
# Eliminamos los identificadores y los targets del set de características
columns_to_drop = id_columns + target_columns + location_columns
df_features = df.drop(columns=[col for col in columns_to_drop if col in df.columns])

print(f"Dimensión de Features originales: {df.shape}")
print(f"Dimensión de Features limpios (X) para Stuff+: {df_features.shape}")
print(f"Dimensión de Targets (y): {df_targets.shape}")

# 5. Guardar la matriz con filtros
output_features_path = os.path.join(base_dir, 'Data', 'features_clean.parquet')
df_features.to_parquet(output_features_path, index=False)
print(f"Matriz limpia guardada exitosamente en: {output_features_path}")