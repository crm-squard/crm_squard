import numpy as np
import pandas as pd

file_name = 'data/clean_final_data.csv'
df = pd.read_csv(file_name)
unique_list = df['ProductName'].unique().tolist()
print(unique_list)