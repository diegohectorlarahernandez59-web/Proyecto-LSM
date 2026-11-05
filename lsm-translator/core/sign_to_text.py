from core.landmarks import LandmarksExtractor
from core.sign_classifier import SignClassifier

class SignToText:
    def __init__(self):
        self.extractor = LandmarksExtractor()
        self.classifier = SignClassifier()

    def process_window(self, frame_buffer):
        """
        Procesa una ventana completa de frames de video:
        1. Extrae landmarks de cada frame.
        2. Ejecuta el clasificador local.
        3. Retorna la glosa detectada.
        """
        if not frame_buffer:
            return None

        sequence_landmarks = []
        for frame in frame_buffer:
            landmarks = self.extractor.extract(frame)
            if landmarks is not None:
                sequence_landmarks.append(landmarks)

        if len(sequence_landmarks) == 0:
            return None

        # Clasificar la secuencia temporal obtenida
        gloss, confidence = self.classifier.predict(sequence_landmarks)
        
        return {"gloss": gloss, "confidence": confidence}