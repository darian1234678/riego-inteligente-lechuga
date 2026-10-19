"""
==========================================================================
 SISTEMA DE RIEGO AUTOMATIZADO CON IA - Página web de monitoreo
 Proyecto de Título - Ingeniería Agrícola
 (Versión con diseño más colorido)
==========================================================================

CÓMO USAR ESTE ARCHIVO:
1. Reemplaza tu app.py actual (local y en GitHub) por este
2. Streamlit Cloud actualiza tu página publicada automáticamente

CUANDO TENGAS TU ESP32 FUNCIONANDO:
Busca la sección "ZONA A REEMPLAZAR" más abajo.
==========================================================================
"""

import streamlit as st
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import plotly.graph_objects as go

st.set_page_config(
    page_title="Riego Inteligente - Lechuga",
    page_icon="🌱",
    layout="wide"
)

# --------------------------------------------------------------------
# ESTILO VISUAL - Mucho más color, menos blanco
# --------------------------------------------------------------------
st.markdown("""
<style>
    .stApp {
        background: linear-gradient(180deg, #EAF3E3 0%, #F6F9F1 100%);
    }

    .block-container {
        padding-top: 1.5rem;
    }

    /* Encabezado tipo banner grande */
    .agro-header {
        background: linear-gradient(135deg, #1B5E20 0%, #4E8C2F 60%, #8BC34A 100%);
        padding: 2.4rem 2.4rem;
        border-radius: 20px;
        color: white;
        margin-bottom: 1.5rem;
        box-shadow: 0 6px 18px rgba(27, 94, 32, 0.25);
    }
    .agro-header h1 {
        color: white;
        margin: 0;
        font-size: 2.3rem;
    }
    .agro-header p {
        color: #E8F5E9;
        margin: 0.4rem 0 0 0;
        font-size: 1.05rem;
    }

    /* Tarjetas de métricas con fondo de color */
    div[data-testid="stMetric"] {
        background: linear-gradient(160deg, #FFFFFF 0%, #EAF6E3 100%);
        border: 1px solid #C6E2B5;
        border-left: 6px solid #4E8C2F;
        border-radius: 14px;
        padding: 1.1rem 1.3rem;
        box-shadow: 0 3px 10px rgba(46, 125, 50, 0.12);
    }
    div[data-testid="stMetricLabel"] {
        color: #3B5A32;
        font-weight: 600;
    }
    div[data-testid="stMetricValue"] {
        color: #1B5E20;
    }

    /* Caja de recomendación con más color */
    .rec-box {
        border-radius: 16px;
        padding: 1.5rem 1.8rem;
        margin: 0.5rem 0 1.8rem 0;
        border: 2px solid;
    }
    .rec-ok {
        background: linear-gradient(135deg, #DCF0D0 0%, #C3E6B0 100%);
        border-color: #7CB342;
        color: #1B5E20;
    }
    .rec-warn {
        background: linear-gradient(135deg, #FFF3C4 0%, #FFE082 100%);
        border-color: #F9A825;
        color: #8D5A00;
    }
    .rec-alert {
        background: linear-gradient(135deg, #FFD5D5 0%, #FFAFAF 100%);
        border-color: #E53935;
        color: #8B0000;
    }
    .rec-box h3 {
        margin: 0 0 0.3rem 0;
    }
    .rec-box p {
        margin: 0;
    }

    /* Secciones con tarjeta de fondo */
    .section-card {
        background-color: #FFFFFF;
        border-radius: 16px;
        padding: 1.5rem 1.7rem 0.8rem 1.7rem;
        margin-bottom: 1.5rem;
        border: 1px solid #D7E8C8;
        box-shadow: 0 3px 10px rgba(46, 125, 50, 0.06);
    }

    h2, h3 {
        color: #1B5E20;
    }

    div[data-testid="stAlert"] {
        border-radius: 12px;
        background-color: #FFF9E6;
        border: 1px solid #FFE082;
    }

    /* Expander */
    div[data-testid="stExpander"] {
        background-color: white;
        border-radius: 12px;
        border: 1px solid #D7E8C8;
    }

    footer {visibility: hidden;}
</style>
""", unsafe_allow_html=True)

UMBRAL_HUMEDAD = 40
HUMEDAD_MAX_OK = 70
DURACION_RIEGO_SEG = 12


# ======================================================================
# ZONA A REEMPLAZAR CUANDO TENGAS DATOS REALES DE THINGSPEAK
# ======================================================================
def obtener_datos_simulados():
    np.random.seed(42)
    ahora = datetime.now()
    fechas = [ahora - timedelta(minutes=30 * i) for i in range(7 * 48)]
    fechas.reverse()

    humedad, temperatura, riego_activado = [], [], []
    nivel = 65.0
    for f in fechas:
        nivel -= np.random.uniform(0.3, 0.9)
        regó = False
        if nivel < UMBRAL_HUMEDAD:
            nivel += np.random.uniform(20, 30)
            regó = True
        nivel = np.clip(nivel, 15, 85)
        humedad.append(round(nivel, 1))
        riego_activado.append(regó)

        hora = f.hour + f.minute / 60
        temp_base = 18 + 6 * np.sin((hora - 6) / 24 * 2 * np.pi)
        temperatura.append(round(temp_base + np.random.uniform(-1, 1), 1))

    return pd.DataFrame({
        "fecha": fechas, "humedad": humedad,
        "temperatura": temperatura, "riego_activado": riego_activado,
    })
# ======================================================================
# FIN DE LA ZONA A REEMPLAZAR
# ======================================================================


def generar_recomendacion(humedad_actual):
    if humedad_actual < UMBRAL_HUMEDAD:
        return "alert", "🔴 Regar ahora", "El nivel de humedad está bajo el umbral óptimo (40%)."
    elif humedad_actual > HUMEDAD_MAX_OK:
        return "warn", "🟡 No regar", "El suelo está muy húmedo, evitar encharcamiento."
    else:
        return "ok", "🟢 Nivel óptimo", "La humedad está dentro del rango ideal, no es necesario regar."


df = obtener_datos_simulados()
ultimo = df.iloc[-1]

st.markdown("""
<div class="agro-header">
    <h1>🌱 Sistema de riego inteligente</h1>
    <p>Monitoreo remoto y recomendación de riego asistida por inteligencia artificial · Cultivo: lechuga</p>
</div>
""", unsafe_allow_html=True)

st.info(
    "📌 Estás viendo datos **simulados** para probar la página. "
    "Cuando el ESP32 esté enviando datos reales a ThingSpeak, "
    "se reemplazan automáticamente por los datos verdaderos del cultivo.",
    icon="ℹ️"
)

col1, col2, col3, col4 = st.columns(4)
with col1:
    st.metric("💧 Humedad de suelo", f"{ultimo['humedad']}%")
with col2:
    st.metric("🌡️ Temperatura ambiente", f"{ultimo['temperatura']}°C")
with col3:
    riegos_hoy = df[df["fecha"] >= (datetime.now() - timedelta(days=1))]["riego_activado"].sum()
    st.metric("🚿 Riegos últimas 24h", int(riegos_hoy))
with col4:
    agua_estimada = riegos_hoy * DURACION_RIEGO_SEG * 0.05
    st.metric("🪣 Agua usada 24h", f"{agua_estimada:.2f} L")

st.subheader("Recomendación del sistema")
tipo, estado, detalle = generar_recomendacion(ultimo["humedad"])
st.markdown(f"""
<div class="rec-box rec-{tipo}">
    <h3>{estado}</h3>
    <p>{detalle}</p>
</div>
""", unsafe_allow_html=True)

st.markdown('<div class="section-card">', unsafe_allow_html=True)
st.subheader("🌾 Historial de humedad del suelo")

fig = go.Figure()
fig.add_trace(go.Scatter(
    x=df["fecha"], y=df["humedad"], mode="lines", name="Humedad (%)",
    line=dict(color="#2E7D32", width=3),
    fill="tozeroy", fillcolor="rgba(46, 125, 50, 0.15)"
))
fig.add_hline(y=UMBRAL_HUMEDAD, line_dash="dash", line_color="#C62828",
              annotation_text="Umbral de riego (40%)")
fig.add_hline(y=HUMEDAD_MAX_OK, line_dash="dash", line_color="#F9A825",
              annotation_text="Límite superior (70%)")

riegos = df[df["riego_activado"]]
fig.add_trace(go.Scatter(
    x=riegos["fecha"], y=riegos["humedad"], mode="markers", name="Riego activado",
    marker=dict(color="#1565C0", size=9, symbol="triangle-up")
))
fig.update_layout(
    xaxis_title="Fecha", yaxis_title="Humedad de suelo (%)",
    hovermode="x unified", height=420,
    margin=dict(l=10, r=10, t=30, b=10),
    plot_bgcolor="#FBFDF8", paper_bgcolor="rgba(0,0,0,0)",
    legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
)
st.plotly_chart(fig, width="stretch")
st.markdown('</div>', unsafe_allow_html=True)

st.markdown('<div class="section-card">', unsafe_allow_html=True)
st.subheader("🌡️ Historial de temperatura ambiente")
fig2 = go.Figure()
fig2.add_trace(go.Scatter(
    x=df["fecha"], y=df["temperatura"], mode="lines", name="Temperatura (°C)",
    line=dict(color="#EF6C00", width=3),
    fill="tozeroy", fillcolor="rgba(239, 108, 0, 0.15)"
))
fig2.update_layout(
    xaxis_title="Fecha", yaxis_title="Temperatura (°C)", height=350,
    margin=dict(l=10, r=10, t=30, b=10),
    plot_bgcolor="#FBFDF8", paper_bgcolor="rgba(0,0,0,0)",
)
st.plotly_chart(fig2, width="stretch")

with st.expander("📋 Ver tabla de datos (últimos 20 registros)"):
    tabla = df.tail(20).copy()
    tabla["fecha"] = tabla["fecha"].dt.strftime("%d-%m-%Y %H:%M")
    tabla["riego_activado"] = tabla["riego_activado"].map({True: "Sí", False: "No"})
    st.dataframe(tabla, width="stretch", hide_index=True)
st.markdown('</div>', unsafe_allow_html=True)

# CONTROL DE BOMBA DE AGUA

st.subheader("💧 Control de bomba de agua")

st.warning("Modo de prueba: todavía no controla la bomba real.")

if "bomba_encendida" not in st.session_state:
    st.session_state.bomba_encendida = False

col1, col2 = st.columns(2)

with col1:
    if st.button("🟢 ENCENDER BOMBA"):
        st.session_state.bomba_encendida = True

with col2:
    if st.button("🔴 APAGAR BOMBA"):
        st.session_state.bomba_encendida = False

if st.session_state.bomba_encendida:
    st.success("💧 Bomba encendida (simulación)")
else:
    st.info("⛔ Bomba apagada (simulación)")

st.divider()
st.caption("🌱 Sistema de riego automatizado con monitoreo remoto y recomendación asistida por IA — Proyecto de Título, Ingeniería Agrícola.")
