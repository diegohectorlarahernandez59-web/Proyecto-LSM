import os
import pandas as pd
import numpy as np
from sklearn.ensemble import RandomForestClassifier
import joblib

def entrenar_modelo():
    # Rutas dentro de lsm-translator
    training_folder = "lsm-translator/data/raw/training"
    model_output_path = "lsm-translator/data/models/sign_classifier.pkl"

    if not os.path.exists(training_folder):
        print(f"❌ Error: No se encontró la carpeta de entrenamiento en '{training_folder}'.")
        print("Asegúrate de colocar ahí tus archivos CSV de Google Drive.")
        return

    all_X = []
    all_y = []

    print("📂 Leyendo archivos CSV de entrenamiento...")
    archivos_csv = [f for f in os.listdir(training_folder) if f.endswith('.csv')]
    
    if not archivos_csv:
        print(f"❌ No se encontraron archivos .csv en {training_folder}")
        return

    for file_name in archivos_csv:
        file_path = os.path.join(training_folder, file_name)
        try:
            df = pd.read_csv(file_path)
            
            if df.shape[1] > 1:
                # Las características (X) son todas las columnas de coordenadas
                X_data = df.iloc[:, :-1].values
                
                # Usamos el nombre del archivo (ej. "A_86_Datos.csv" -> "A") como la etiqueta de la seña
                nombre_senia = os.path.splitext(file_name)[0].split('_')[0]
                y_data = np.array([nombre_senia] * len(df))
                
                all_X.append(X_data)
                all_y.append(y_data)
        except Exception as e:
            print(f"⚠️ Error leyendo {file_name}: {e}")

    if all_X:
        X = np.vstack(all_X)
        y = np.concatenate(all_y)

        print(f"🚀 Entrenando el clasificador con {len(X)} muestras...")
        model = RandomForestClassifier(n_estimators=100, random_state=42)
        model.fit(X, y)

        # Guardar el modelo entrenado
        os.makedirs(os.path.dirname(model_output_path), exist_ok=True)
        joblib.dump(model, model_output_path)
        print(f"✅ ¡Modelo entrenado y guardado con éxito en '{model_output_path}'!")
    else:
        print("❌ No se pudieron extraer datos válidos de los archivos CSV.")

if __name__ == "__main__":
    entrenar_modelo()