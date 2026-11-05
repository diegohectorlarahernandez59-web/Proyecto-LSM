import joblib
import os
import streamlit as st
import config as config

st.set_page_config(page_title="Traductor LSM Híbrido", layout="wide")

# Función optimizada para cargar el modelo local de señas usando joblib
@st.cache_resource
def cargar_modelo_señas():
    ruta_modelo = "lsm-translator/data/models/sign_classifier.pkl"
    # Por si se ejecuta directamente desde la carpeta interna
    if not os.path.exists(ruta_modelo):
        ruta_modelo = "data/models/sign_classifier.pkl"
        
    if os.path.exists(ruta_modelo):
        try:
            modelo = joblib.load(ruta_modelo)
            return modelo
        except Exception as e:
            return None
    return None

# 1. Variables de estado del sistema
if "duda_activa" not in st.session_state:
    st.session_state.duda_activa = False

if "subtitulos_lsm" not in st.session_state:
    st.session_state.subtitulos_lsm = "Esperando detección de señas..."

if "mostrar_subtitulos" not in st.session_state:
    st.session_state.mostrar_subtitulos = False

if "subtitulos_oyente" not in st.session_state:
    st.session_state.subtitulos_oyente = "Esperando entrada de audio/texto..."

# Estados de transmisión síncrona en tiempo real
if "camara_sordo_activa" not in st.session_state:
    st.session_state.camara_sordo_activa = False

if "mic_oyente_activo" not in st.session_state:
    st.session_state.mic_oyente_activo = False

# 2. Barra lateral
rol = st.sidebar.radio("Perfil de usuario: ", ["Profesor", "Estudiante"])
st.sidebar.markdown("---")

st.sidebar.header("Estado del sistema")
if config.GEMINI_API_KEY:
    st.sidebar.success("API de lenguaje conectada")
else:
    st.sidebar.warning("Falta configurar GEMINI_API_KEY en .env")

# Validación visual del modelo local en la barra lateral
modelo_señas = cargar_modelo_señas()
if modelo_señas is not None:
    st.sidebar.success("Modelo Local de Señas cargado")
else:
    st.sidebar.error("Error al cargar el modelo .pkl")

# 3. Vista Profesor
if rol == "Profesor":
    st.title("Panel del Profesor")

    def atender_duda():
        st.session_state.duda_activa = False
        st.session_state.mostrar_subtitulos = True
        st.toast("Duda atendida y canal de subtítulos activado.")

    if st.session_state.duda_activa:
        st.error("¡ATENCIÓN! Una persona sorda ha levantado la mano / enviado una duda.")
        st.button(
            "Atender duda y abrir subtítulos",
            type="primary",
            on_click=atender_duda
        )
    else:
        st.info("Sin notificaciones pendientes.")

    st.markdown("---")

    col_titulo, col_btn = st.columns([3, 1])
    with col_titulo:
        st.subheader("Visor de Subtítulos en Vivo (Traducción LSM ➔ Texto)")
    with col_btn:
        texto_boton = "Ocultar Subtítulos" if st.session_state.mostrar_subtitulos else "Abrir Subtítulos"
        if st.button(texto_boton):
            st.session_state.mostrar_subtitulos = not st.session_state.mostrar_subtitulos

    if st.session_state.mostrar_subtitulos:
        st.success("Transmisión en tiempo real ACTIVADA")
        st.text_area(
            label="Subtítulos en directo:",
            value=st.session_state.subtitulos_lsm,
            height=150,
            disabled=True
        )
    else:
        st.warning("Transmisión pausada. Atiende una duda o activa los subtítulos para ver el canal en directo.")

# 4. Vista Estudiante
elif rol == "Estudiante":
    st.title("Panel de Estudiante")
    modo = st.radio(
        "Seleccione modalidad:",
        ["Modo conversación", "Modo Duda o Comentario"],
        horizontal=True
    )
    st.markdown("---")

    if modo == "Modo conversación":
        st.subheader("Conversación Síncrona en Tiempo Real")
        col_oyente, col_sordo = st.columns(2)

        with col_oyente:
            st.markdown("### Persona Oyente")

            canal_oyente = st.radio(
                "Canal de entrada:",
                ["Audio (Voz en vivo)", "Escrito (Texto directo)"],
                horizontal=True,
                key="canal_oyente_radio"
            )

            if canal_oyente == "Audio (Voz en vivo)":
                st.session_state.mic_oyente_activo = st.toggle(
                    "🔴 / 🟢 Activar Micrófono (Captura Continua)",
                    value=st.session_state.mic_oyente_activo
                )

                if st.session_state.mic_oyente_activo:
                    st.success("Micrófono ACTIVADO - Procesando voz a texto de forma continua...")
                    st.session_state.subtitulos_oyente = "Transcripción síncrona: 'Hola, ¿tienen alguna duda con este tema?'"
                else:
                    st.warning("🔇 Micrófono DESACTIVADO")

            elif canal_oyente == "Escrito (Texto directo)":
                st.session_state.mic_oyente_activo = False
                texto_ingresado = st.text_input("Escribe tu mensaje en tiempo real:", key="txt_oyente_live")
                if texto_ingresado:
                    st.session_state.subtitulos_oyente = texto_ingresado

            st.markdown("#### Subtítulos Recibidos (LSM ➔ Texto en Vivo)")
            st.text_area(
                label="Traducción continua de las señas:",
                value=st.session_state.subtitulos_lsm,
                height=100,
                disabled=True,
                key="sub_lsm_recibidos_oyente"
            )

        with col_sordo:
            st.markdown("### Estudiante")

            st.session_state.camara_sordo_activa = st.toggle(
                "📷 / 🟢 Activar Cámara (Traducción LSM en Vivo)",
                value=st.session_state.camara_sordo_activa
            )

            if st.session_state.camara_sordo_activa:
                st.success("🟢 Cámara ACTIVADA - Modelo de señas clasificando en tiempo real...")

                with st.container(border=True):
                    st.caption("Transmisión de Video en Vivo (Feed del modelo)")
                    st.info("Simulación: Detectando puntos clave (Hand Landmarks / MediaPipe) y clasificando señas...")
                    st.session_state.subtitulos_lsm = "Traducción en vivo: 'Todo claro profesor, podemos continuar.'"
            else:
                st.warning("Cámara DESACTIVADA")

            st.markdown("#### Animaciones LSM Generadas en Vivo")
            with st.container(border=True):
                if st.session_state.mic_oyente_activo or st.session_state.subtitulos_oyente:
                    st.success(f"Renderizando secuencia LSM para: '{st.session_state.subtitulos_oyente}'")
                else:
                    st.info("Esperando que la persona oyente active su audio o texto...")

    elif modo == "Modo Duda o Comentario":
        st.subheader("Notificación y Transmisión de Duda")

        col_btn, col_cam = st.columns([1, 2])

        with col_btn:
            st.write("Presiona para enviar la alerta al profesor:")
            if st.button("Enviar Notificación al Profesor", type="primary"):
                st.session_state.duda_activa = True
                st.toast("Notificación enviada al profesor.")

        with col_cam:
            st.markdown("### Cámara de Duda (LSM)")

            camara_duda_activa = st.toggle("Activar Transmisión de Duda")

            if camara_duda_activa:
                st.success("Transmitiendo señas en tiempo real hacia la pantalla del profesor...")
                st.session_state.subtitulos_lsm = "Traducción de duda: '¿Puede repetir la última diapositiva?'"
            else:
                st.info("Activa el interruptor para comenzar a transmitir tu duda en señas.")