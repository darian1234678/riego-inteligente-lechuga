"""
==========================================================================
 SISTEMA DE RIEGO AUTOMATIZADO CON IA - Página web de monitoreo
 Proyecto de Título - Ingeniería Agrícola
==========================================================================

CÓMO USAR ESTE ARCHIVO:
1. Guarda este archivo en una carpeta (ej: Escritorio/proyecto_riego/app.py)
2. Abre la terminal (cmd) en esa carpeta
3. Escribe: streamlit run app.py
4. Se abrirá tu navegador automáticamente con la página funcionando

POR AHORA usa DATOS SIMULADOS (inventados por el computador) para que
puedas ver cómo se va a ver tu página ANTES de tener el sensor real.

CUANDO TENGAS TU ESP32 FUNCIONANDO:
Busca la sección "ZONA A REEMPLAZAR" más abajo. Ahí es donde vas a
cambiar los datos simulados por los datos reales que vengan de ThingSpeak.
Todo lo demás del código (gráficos, diseño, recomendación) sigue igual.
==========================================================================
"""

import streamlit as st
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import plotly.graph_objects as go

# --------------------------------------------------------------------
# CONFIGURACIÓN DE LA PÁGINA (título de la pestaña, ícono, ancho)
# --------------------------------------------------------------------
st.set_page_config(
    page_title="Riego Inteligente - Lechuga",
    page_icon="🌱",
    layout="wide"
)

# --------------------------------------------------------------------
# UMBRAL DE RIEGO (la "regla fija" que definimos juntos)
# Cámbialo aquí si después decides otro número al calibrar tu sensor.
# --------------------------------------------------------------------
UMBRAL_HUMEDAD = 40      # % bajo el cual se activa el riego
HUMEDAD_MAX_OK = 70      # % sobre el cual se evita regar (no encharcar)
DURACION_RIEGO_SEG = 12  # segundos que riega cada vez que se activa


# ======================================================================
# ZONA A REEMPLAZAR CUANDO TENGAS DATOS REALES DE THINGSPEAK
# ======================================================================
# Por ahora esta función INVENTA datos parecidos a los que dará tu
# sensor real, para que puedas probar toda la página sin hardware.
#
# Cuando tengas tu ESP32 funcionando y subiendo datos a ThingSpeak,
# esta función se reemplaza por una que pida los datos reales con
# la librería "requests" a la API de ThingSpeak. Yo te ayudo con
# ese cambio cuando llegue el momento - la estructura de abajo
# (un DataFrame con columnas fecha, humedad, temperatura) se mantiene
# igual, así el resto del código no se toca.
def obtener_datos_simulados():
    """Genera datos falsos de los últimos 7 días, cada 30 minutos,
    simulando el ciclo de secado y riego de una lechuga."""
    np.random.seed(42)
    ahora = datetime.now()
    fechas = [ahora - timedelta(minutes=30 * i) for i in range(7 * 48)]
    fechas.reverse()

    humedad = []
    temperatura = []
    riego_activado = []

    nivel = 65.0  # empieza en un nivel húmedo
    for i, f in enumerate(fechas):
        # la humedad baja de a poco con el tiempo (la planta consume agua)
        nivel -= np.random.uniform(0.3, 0.9)

        # si baja del umbral, "se riega" y sube de nuevo
        regó = False
        if nivel < UMBRAL_HUMEDAD:
            nivel += np.random.uniform(20, 30)
            regó = True

        nivel = np.clip(nivel, 15, 85)
        humedad.append(round(nivel, 1))
        riego_activado.append(regó)

        # temperatura simulada con ciclo día/noche
        hora = f.hour + f.minute / 60
        temp_base = 18 + 6 * np.sin((hora - 6) / 24 * 2 * np.pi)
        temperatura.append(round(temp_base + np.random.uniform(-1, 1), 1))

    df = pd.DataFrame({
        "fecha": fechas,
        "humedad": humedad,
        "temperatura": temperatura,
        "riego_activado": riego_activado,
    })
    return df
# ======================================================================
# FIN DE LA ZONA A REEMPLAZAR
# ======================================================================


def generar_recomendacion(humedad_actual):
    """Regla simple de recomendación (después esto lo reemplaza tu
    modelo de IA entrenado con los datos reales)."""
    if humedad_actual < UMBRAL_HUMEDAD:
        return "🔴 Regar ahora", "El nivel de humedad está bajo el umbral óptimo."
    elif humedad_actual > HUMEDAD_MAX_OK:
        return "🟡 No regar", "El suelo está muy húmedo, evitar encharcamiento."
    else:
        return "🟢 Nivel óptimo", "No es necesario regar por ahora."


# --------------------------------------------------------------------
# CARGA DE DATOS
# --------------------------------------------------------------------
df = obtener_datos_simulados()
ultimo = df.iloc[-1]

# --------------------------------------------------------------------
# ENCABEZADO
# --------------------------------------------------------------------
st.title("🌱 Sistema de riego inteligente")
st.caption("Proyecto de Título — Monitoreo con datos simulados (demo previa al hardware)")

st.info(
    "📌 Estás viendo datos **simulados** para probar la página. "
    "Cuando el ESP32 esté enviando datos reales a ThingSpeak, "
    "se reemplazan automáticamente por los datos verdaderos del cultivo.",
    icon="ℹ️"
)

# --------------------------------------------------------------------
# INDICADORES PRINCIPALES (las tarjetas de arriba)
# --------------------------------------------------------------------
col1, col2, col3, col4 = st.columns(4)

with col1:
    st.metric("Humedad de suelo actual", f"{ultimo['humedad']}%")

with col2:
    st.metric("Temperatura ambiente", f"{ultimo['temperatura']}°C")

with col3:
    riegos_hoy = df[df["fecha"] >= (datetime.now() - timedelta(days=1))]["riego_activado"].sum()
    st.metric("Riegos en las últimas 24h", int(riegos_hoy))

with col4:
    agua_estimada = riegos_hoy * DURACION_RIEGO_SEG * 0.05  # litros aprox por riego
    st.metric("Agua usada (últimas 24h)", f"{agua_estimada:.2f} L")

# --------------------------------------------------------------------
# RECOMENDACIÓN ACTUAL
# --------------------------------------------------------------------
st.subheader("Recomendación del sistema")
estado, detalle = generar_recomendacion(ultimo["humedad"])
st.markdown(f"### {estado}")
st.write(detalle)

# --------------------------------------------------------------------
# GRÁFICO DE HUMEDAD EN EL TIEMPO
# --------------------------------------------------------------------
st.subheader("Historial de humedad del suelo")

fig = go.Figure()
fig.add_trace(go.Scatter(
    x=df["fecha"], y=df["humedad"],
    mode="lines", name="Humedad (%)",
    line=dict(color="#2E7D32", width=2)
))

# líneas de referencia del umbral
fig.add_hline(y=UMBRAL_HUMEDAD, line_dash="dash", line_color="red",
              annotation_text="Umbral de riego (40%)")
fig.add_hline(y=HUMEDAD_MAX_OK, line_dash="dash", line_color="orange",
              annotation_text="Límite superior (70%)")

# marcar los momentos en que se regó
riegos = df[df["riego_activado"]]
fig.add_trace(go.Scatter(
    x=riegos["fecha"], y=riegos["humedad"],
    mode="markers", name="Riego activado",
    marker=dict(color="#1565C0", size=7, symbol="triangle-up")
))

fig.update_layout(
    xaxis_title="Fecha",
    yaxis_title="Humedad de suelo (%)",
    hovermode="x unified",
    height=420,
    margin=dict(l=10, r=10, t=30, b=10),
)
st.plotly_chart(fig, use_container_width=True)

# --------------------------------------------------------------------
# GRÁFICO DE TEMPERATURA
# --------------------------------------------------------------------
st.subheader("Historial de temperatura ambiente")

fig2 = go.Figure()
fig2.add_trace(go.Scatter(
    x=df["fecha"], y=df["temperatura"],
    mode="lines", name="Temperatura (°C)",
    line=dict(color="#EF6C00", width=2)
))
fig2.update_layout(
    xaxis_title="Fecha",
    yaxis_title="Temperatura (°C)",
    height=350,
    margin=dict(l=10, r=10, t=30, b=10),
)
st.plotly_chart(fig2, use_container_width=True)

# --------------------------------------------------------------------
# TABLA CON LOS ÚLTIMOS REGISTROS
# --------------------------------------------------------------------
with st.expander("Ver tabla de datos (últimos 20 registros)"):
    tabla = df.tail(20).copy()
    tabla["fecha"] = tabla["fecha"].dt.strftime("%d-%m-%Y %H:%M")
    tabla["riego_activado"] = tabla["riego_activado"].map({True: "Sí", False: "No"})
    st.dataframe(tabla, use_container_width=True, hide_index=True)

# --------------------------------------------------------------------
# PIE DE PÁGINA
# --------------------------------------------------------------------
st.divider()
st.caption("Sistema de riego automatizado con monitoreo remoto y recomendación asistida por IA — Proyecto de Título, Ingeniería Agrícola.")
