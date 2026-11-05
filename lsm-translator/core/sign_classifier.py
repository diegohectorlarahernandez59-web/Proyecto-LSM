import os
import numpy as np
import joblib

class SignClassifier:
    def __init__(self, model_path="lsm-translator/data/models/sign_classifier.pkl"):
        self.model_path = model_path
        self.model = self._load_model()

    def _load_model(self):
        if os.path.exists(self.model_path):
            try:
                return joblib.load(self.model_path)
            except Exception as e:
                print(f"Error al cargar el modelo local: {e}")
        return None

    def predict(self, sequence_landmarks):
        if self.model is None:
            return "ESPERANDO MODELO", 0.0

        try:
            input_data = np.array(sequence_landmarks).reshape(1, -1)
            prediction = self.model.predict(input_data)
            probabilities = self.model.predict_proba(input_data)
            confidence = np.max(probabilities)
            return str(prediction[0]), float(confidence)
        except Exception as e:
            print(f"Error en predicción: {e}")
            return None, 0.0