import streamlit as st
import config as config


st.set_page_config(page_title="", layout = "wide")
st.title("")


if "duda_activa" not in st.session_state:
    st.session_state.duda_activa = False
if "subtitulo_lsm" not in st.session_state:
    st.session_state.subtitulos_lsm = "Esperando traduccion de señas..."

rol = st.sidebar.radio("Perfil de usuario: ",["Profesor","Persona Estudiante"])
st.sidebar.markdown("---")


st.sidebar.header("Estado del sistema")
if config.GEMINI_API_KEY:
    st.sidebar.success("API de lenguaje conectada")
else:
    st.sidebar.warning("Falta configurar GEMINI_API_KEY en .env")
st.sidebar.info("Modelo Local de Señas a cargar")


if rol == "Profesor":
    st.title("Panel del Profesor")

    # Función callback que limpia la duda ANTES de redibujar la pantalla
    def limpiar_duda():
        st.session_state.duda_activa = False
        st.toast("Duda marcada como atendida.")


    # Notificación de duda entrante
    if st.session_state.duda_activa:
        st.error("ATENCIÓN! Una persona sorda ha levantado la mano / enviado una duda.")
        st.button(
            "Atender duda y abrir subtítulos",
            type="primary",
            on_click=limpiar_duda  # <--- Asignamos el callback aquí
        )
    else:
        st.info("Sin notificaciones pendientes.")

    st.markdown("---")

    # Apertura de Subtítulos recibidos de la Persona Sorda
    st.subheader("Visor de Subtítulos (Traducción LSM ➔ Texto)")
    st.caption("Aquí se muestran en tiempo real las señas traducidas del estudiante.")

    st.text_area(
        label="Subtítulos en vivo:",
        value=st.session_state.subtitulos_lsm,
        height=150,
        disabled=True
    )

elif rol == "Persona Estudiante":
    st.title("Panel de Estudiante ")
    modo = st.radio("Seleccione modalidad:",
                    ["Modo conversacion","Modo Duda o Comentario"],
                    horizontal = True
                    )
    st.markdown("---")
    if modo == "Modo conversacion":
        st.subheader("Vista Duo de conversacion")
        col1, col2 = st.columns(2)

        with col1:
            st.markdown(" Tu Salida (LSM / Texto)")
            st.text_area("Señas detectadas o texto a enviar:", height=120)
            if st.button("Enviar respuesta"):
                st.toast("Mensaje enviado a la conversación.")
        with col2:
            with col2:
                st.markdown("Entrada (Voz del Profesor traducida)")
                st.info("El profesor dice: 'Bienvenidos a la clase, abran su proyecto en la página 10.'")

    elif modo == "Modo Duda o Comentario":
        st.subheader("Envío de Duda en LSM al Profesor")

        col_btn, col_cam = st.columns([1, 2])

        with col_btn:
            st.write("Presiona el botón para notificar al profesor que tienes una duda:")
            if st.button("Enviar Notificación al Profesor", type="primary"):
                st.session_state.duda_activa = True
                st.success("¡Notificación enviada al profesor!")

        with col_cam:
            st.markdown("Cámara de Captura LSM")
            st.caption("La cámara procesará tus señas para enviarlas como subtítulo a la pantalla del profesor.")

            # Entrada de cámara nativa de Streamlit para pruebas directas
            imagen_cam = st.camera_input("Capturar seña para traducción")

            if imagen_cam:
                # Simulación de actualización de subtítulos traduciendo LSM
                st.session_state.subtitulos_lsm = "Traducción detectada: 'Tengo una duda sobre la tarea'"
                st.success("Seña procesada y enviada a la pantalla del profesor.")






