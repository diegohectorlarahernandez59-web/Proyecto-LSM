import cv2
import mediapipe as mp
import numpy as np

class LandmarksExtractor:
    def __init__(self):
        self.mp_holistic = mp.solutions.holistic
        self.holistic = self.mp_holistic.Holistic(
            min_detection_confidence=0.5,
            min_tracking_confidence=0.5
        )

    def extract(self, frame):
        """
        Procesa un frame de OpenCV y extrae los landmarks de manos, pose y rostro.
        Retorna un vector plano con todas las coordenadas (x, y, z).
        """
        if frame is None:
            return None

        # Convertir BGR a RGB para MediaPipe
        image_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        image_rgb.flags.writeable = False
        results = self.holistic.process(image_rgb)
        image_rgb.flags.writeable = True

        # Extraer y aplanar landmarks (ej. manos, pose)
        # Si no se detecta mano, se rellenan con ceros para mantener dimensiones fijas
        pose = np.array([[res.x, res.y, res.z, res.visibility] for res in results.pose_landmarks.landmark]).flatten() if results.pose_landmarks else np.zeros(33 * 4)
        left_hand = np.array([[res.x, res.y, res.z] for res in results.left_hand_landmarks.landmark]).flatten() if results.left_hand_landmarks else np.zeros(21 * 3)
        right_hand = np.array([[res.x, res.y, res.z] for res in results.right_hand_landmarks.landmark]).flatten() if results.right_hand_landmarks else np.zeros(21 * 3)

        return np.concatenate([pose, left_hand, right_hand])