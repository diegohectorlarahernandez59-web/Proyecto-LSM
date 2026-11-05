import cv2
import mediapipe as mp
from capture.camera import CameraCapture
from core.landmarks import LandmarksExtractor
from core.sign_classifier import SignClassifier

class SignToTextOrchestrator:
    def __init__(self):
        print("Inicializando componentes del núcleo (SignToText)...")
        self.camera = CameraCapture(width=640, height=480, fps=30)
        self.extractor = LandmarksExtractor()
        self.classifier = SignClassifier()
        self.mp_drawing = mp.solutions.drawing_utils
        self.mp_hands = mp.solutions.hands

    def iniciar_traduccion(self):
        print("🎥 Abriendo cámara en vivo...")
        self.camera.iniciar()
        
        with self.mp_hands.Hands(
            model_complexity=0,
            min_detection_confidence=0.7,
            min_tracking_confidence=0.7) as hands:

            print("🟢 Traducción en tiempo real activa. Presiona 'q' para salir.")
            
            while True:
                frame = self.camera.obtener_frame()
                if frame is None:
                    continue

                # Efecto espejo e inversión de color para MediaPipe
                frame = cv2.flip(frame, 1)
                image_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                results = hands.process(image_rgb)

                predicted_sign = "ESPERANDO SEÑA..."
                confidence_text = ""

                if results.multi_hand_landmarks:
                    for hand_landmarks in results.multi_hand_landmarks:
                        # Dibujar landmarks en pantalla
                        self.mp_drawing.draw_landmarks(
                            frame, hand_landmarks, self.mp_hands.HAND_CONNECTIONS)

                        # Extraer coordenadas para el clasificador
                        row = []
                        for landmark in hand_landmarks.landmark:
                            row.extend([landmark.x, landmark.y, landmark.z])

                        # Predicción con el modelo local
                        sign, confidence = self.classifier.predict(row)
                        if sign:
                            predicted_sign = sign
                            confidence_text = f" ({confidence * 100:.1f}%)"

                # Mostrar resultado en pantalla
                cv2.putText(frame, f"Senia: {predicted_sign}{confidence_text}", 
                            (30, 50), cv2.FONT_HERSHEY_SIMPLEX, 0.9, (0, 255, 0), 2, cv2.LINE_AA)

                cv2.imshow('LSM Translator - Core en Vivo', frame)

                if cv2.waitKey(5) & 0xFF == ord('q'):
                    break

        self.detener()

    def detener(self):
        self.camera.detener()
        cv2.destroyAllWindows()
        print("🛑 Sistema detenido correctamente.")

if __name__ == "__main__":
    orchestrator = SignToTextOrchestrator()
    orchestrator.iniciar_traduccion()