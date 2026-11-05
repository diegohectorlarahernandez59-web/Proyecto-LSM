import streamlit as st
import config as config


st.set_page_config(page_title="", layout = "wide")
st.title("")
st.sidebar.header("Estado del sistema")
if config.GEMINI_API_KEY:
    st.sidebar.success("API de lenguaje conectada")
else:
    st.sidebar.warning("Falta configurar GEMINI_API_KEY en .env")
st.sidebar.info("Modelo Local de Señas a cargar")

modo_activo = st.sidebar.radio("Seleccione el Modo: ", ["Modo Clase","Modo Conservacion"])

if modo_activo == "Modo Clase":
    st.header("Modo Clase")
    st.write("El docente habla, el estudiante lee los subtitulos y ve las señas en el video")
    col1, col2 = st.columns(2)
    with col1:
        st.subheader("Entrada docente (voz)")
        st.button("Iniciar captura de audio")
        st.info("Aqui apareceran los subtitulos en vivo...")
    with col2:
        st.subheader("Estudiante (LSM/Texto)")
        st.button("Tengo una pregunta(Hacer seña)")
        st.info("Aqui se mostrara la camara para reconocer las señas del estudiante")
elif modo_activo == "Modo Conservacion":
    st.header("Modo Conservacion")
    st.write("Alumno con alumno. Cada uno con su propio canal de entrada y salida")
    col1, col2= st.columns(2)
    with col1:
        st.subheader("Canal Alumno 1")
        st.selectbox("Metodo de entrada:",["Voz","Texto","Camara(LSM)"],key="entrada_a1")
        st.text_area("Mensaje recibido:",height=100, key="salida_a1")
    with col2:
        st.subheader("Canal Alumno 2")
        st.selectbox("Metodo de entrada",["Camara (LSM)","Texto","Voz"],key="entrada_a2")
        st.text_area("Mensaje recibido:",height=100, key="salida_a2")

