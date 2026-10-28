import pandas as pd
import os

# 1. Cargar el dataset
print("Cargando archivo Parquet...")
base_dir = os.path.dirname(os.path.dirname(__file__)) 
file_path = os.path.join(base_dir, 'Data', 'stuff_model_df.parquet')

df = pd.read_parquet(file_path)