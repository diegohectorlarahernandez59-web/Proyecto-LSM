import time
from modes.classroom import ClassroomMode

print("=== INICIANDO PRUEBA AISLADA DE MODO CLASE ===")

# Instanciar el modo clase que programaste
clase = ClassroomMode()

try:
    # 1. Iniciar los flujos (enciende la cámara y el micrófono)
    clase.iniciar_clase()
    print("¡Cámara y micrófono iniciados correctamente!")

    print("Capturando datos en tiempo real por 5 segundos...")
    start_time = time.time()

    # 2. Simular un ciclo de ejecución de la aplicación
    while time.time() - start_time < 5:
        frame, audio_block = clase.procesar_ciclo()
        
        if frame is not None:
            print(f"✔️ [CÁMARA] Frame recibido - Dimensiones: {frame.shape}")
        else:
            print("⚠️ [CÁMARA] No hay frame disponible aún.")
            
        if audio_block is not None:
            print(f"✔️ [AUDIO] Bloque de audio recibido - Tamaño: {audio_block.shape}")
        else:
            print("⚠️ [AUDIO] Silencio o esperando bloque de audio...")
            
        time.sleep(0.5) # Pausa breve para la prueba

except Exception as e:
    print(f"❌ Error durante la prueba: {e}")

finally:
    # 3. Detener todo limpiamente al terminar
    clase.detener_clase()
    print("=== PRUEBA FINALIZADA ===")