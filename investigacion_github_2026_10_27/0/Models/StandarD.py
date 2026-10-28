import pandas as pd
import numpy as np
import os
from sklearn.pipeline import Pipeline
from sklearn.impute import SimpleImputer
from sklearn.preprocessing import StandardScaler

# 1. Cargar la matriz limpia de Extraction.py (asumiendo que guardaste df_features)
base_dir = os.path.dirname(os.path.dirname(__file__))
file_path = os.path.join(base_dir, 'Data', 'features_clean.parquet')
df = pd.read_parquet(file_path)

# 2. Limpieza de Texto a Números
print("Limpiando variables de texto...")
df['EffectiveVelo'] = pd.to_numeric(df['EffectiveVelo'], errors='coerce')

def convert_tilt_to_degrees(tilt_str):
    if pd.isna(tilt_str) or str(tilt_str).strip() == '':
        return np.nan
    try:
        h, m = map(int, str(tilt_str).split(':'))
        total_minutes = (h % 12) * 60 + m
        return (total_minutes / 720.0) * 360.0
    except:
        return np.nan

df['Tilt_Degrees'] = df['Tilt'].apply(convert_tilt_to_degrees)
df.drop(columns=['Tilt'], inplace=True, errors='ignore')

# 3. Definir las variables de Arsenal (Físicas)
physical_features = [
    # Velocidad
    'RelSpeed', 'EffectiveVelo', 'ZoneSpeed', 'SpeedDrop',
    # Rotación
    'SpinRate', 'SpinAxis', 'Tilt_Degrees',
    # Movimiento
    'VertBreak', 'InducedVertBreak', 'HorzBreak',
    # Punto de liberación
    'RelHeight', 'RelSide', 'Extension',
    # Ángulos
    'VertRelAngle', 'HorzRelAngle', 'VertApprAngle', 'HorzApprAngle'
]

# 4. Construcción del Pipeline de preprocesamiento
physical_pipeline = Pipeline(steps=[
    ('imputer', SimpleImputer(strategy='median')),
    ('scaler', StandardScaler())
])

print("Pipeline de estandarización construido y listo para usarse.")

# 1. El Pipeline 'aprende' la media/mediana y transforma SOLO las 17 variables físicas de entrenamiento
X_train[physical_features] = physical_pipeline.fit_transform(X_train[physical_features])

# 2. El Pipeline aplica esas reglas matemáticas a las 17 variables físicas de prueba
X_test[physical_features] = physical_pipeline.transform(X_test[physical_features])