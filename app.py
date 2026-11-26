
import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import paho.mqtt.client as mqtt
import json
import ssl
import time
import threading
import uuid
import hmac

from collections import deque
from datetime import datetime
from zoneinfo import ZoneInfo

st.set_page_config(
    page_title="AgroRiego | Riego Inteligente",
    page_icon="🌱",
    layout="wide"
)

ZONA = ZoneInfo("America/Santiago")

FOTO = "https://images.unsplash.com/photo-1622206151226-18ca2c9ab4a1?w=1400&q=85"

# ==========================================
# DISEÑO VISUAL
# ==========================================

st.markdown(f"""
<style>

.stApp {{
    background: #F1F5EE;
}}

.block-container {{
    padding-top: 2rem;
    max-width: 1600px;
}}

[data-testid="stSidebar"] {{
    background: #143A27;
}}

[data-testid="stSidebar"] * {{
    color: white !important;
}}

[data-testid="stSidebar"] input {{
    background: white !important;
    color: #173B27 !important;
}}

.hero {{
    background-image:
    linear-gradient(90deg,
    rgba(15,55,30,0.96),
    rgba(25,75,30,0.30)),
    url('{FOTO}');
    background-size: cover;
    background-position: center;
    padding: 32px;
    border-radius: 20px;
    margin-bottom: 18px;
}}

.hero h1 {{
    color: white !important;
    font-size: 34px;
}}

.hero p {{
    color: #FFFFFF;
    font-size: 16px;
}}

.hero-tag {{
    color: #B9E68D;
    font-size: 12px;
    letter-spacing: 2px;
    font-weight: bold;
}}

[data-testid="stMetric"] {{
    background: white;
    border: 1px solid #D6E5CF;
    border-top: 4px solid #559B42;
    padding: 20px;
    border-radius: 16px;
    box-shadow: 0 4px 12px #163D2510;
}}

[data-testid="stMetricValue"] {{
    color: #245A30;
    font-weight: bold;
}}

[data-testid="stMetricLabel"] {{
    color: #34533B;
}}

[data-testid="stVerticalBlockBorderWrapper"] {{
    background: white;
    border-radius: 16px;
}}

.stButton > button {{
    width: 100%;
    border-radius: 10px;
    font-weight: bold;
    min-height: 42px;
}}

.stButton > button[kind="primary"] {{
    background: #31833D;
    color: white;
    border: none;
}}

h1, h2, h3 {{
    color: #20452D;
}}

footer {{
    visibility: hidden;
}}

</style>
""", unsafe_allow_html=True)

# ==========================================
# COMUNICACION MQTT
# ==========================================

class SistemaMQTT:

    def __init__(self):

        self.lock = threading.Lock()
        self.datos = {}
        self.historial = deque(maxlen=30000)
        self.conectado = False
        self.ultima = 0

        self.client = mqtt.Client(
            mqtt.CallbackAPIVersion.VERSION2,
            client_id="AgroRiego-" + uuid.uuid4().hex[:10]
        )

        self.client.username_pw_set(
            st.secrets["mqtt"]["username"],
            st.secrets["mqtt"]["password"]
        )

        self.client.tls_set(
            cert_reqs=ssl.CERT_REQUIRED
        )

        self.client.on_connect = self.on_connect
        self.client.on_disconnect = self.on_disconnect
        self.client.on_message = self.on_message

        self.client.reconnect_delay_set(
            min_delay=1,
            max_delay=30
        )

        self.client.connect_async(
            st.secrets["mqtt"]["host"],
            int(st.secrets["mqtt"]["port"]),
            60
        )

        self.client.loop_start()

    def on_connect(
        self, client, userdata,
        flags, reason_code, properties
    ):

        with self.lock:
            self.conectado = reason_code == 0

        if reason_code == 0:
            client.subscribe("riego/sensores", qos=1)

    def on_disconnect(
        self, client, userdata,
        disconnect_flags, reason_code, properties
    ):

        with self.lock:
            self.conectado = False

    def on_message(self, client, userdata, msg):

        try:

            if msg.retain:
                return

            datos = json.loads(
                msg.payload.decode("utf-8")
            )

            campos = [
                "humedad",
                "temperatura",
                "humedad_ambiental",
                "lluvia",
                "bomba",
                "modo",
                "sensor_valido"
            ]

            if not isinstance(datos, dict):
                return

            if not all(c in datos for c in campos):
                return

            if datos["modo"] not in ["AUTO", "MANUAL"]:
                return

            for campo in [
                "lluvia", "bomba", "sensor_valido"
            ]:
                if not isinstance(datos[campo], bool):
                    return

            datos["humedad"] = float(datos["humedad"])

            if not 0 <= datos["humedad"] <= 100:
                return

            for campo in [
                "temperatura",
                "humedad_ambiental"
            ]:
                if datos[campo] is not None:
                    datos[campo] = float(datos[campo])

            datos["fecha"] = datetime.now(ZONA)

            with self.lock:
                self.datos = datos.copy()
                self.ultima = time.monotonic()
                self.historial.append(datos.copy())

        except (ValueError, TypeError, KeyError):
            pass

    def obtener(self):

        with self.lock:
            return (
                self.datos.copy(),
                list(self.historial),
                self.conectado,
                self.ultima
            )

    def enviar(self, comando):

        datos, _, conectado, ultima = self.obtener()

        if not conectado or ultima == 0:
            return False

        if time.monotonic() - ultima > 15:
            return False

        if comando == "ON":
            if (
                datos.get("modo") != "MANUAL"
                or datos.get("lluvia") is not False
                or datos.get("sensor_valido") is not True
                or datos.get("humedad", 100) >= 70
            ):
                return False

        resultado = self.client.publish(
            "riego/comando",
            comando,
            qos=1,
            retain=False
        )

        return resultado.rc == mqtt.MQTT_ERR_SUCCESS


@st.cache_resource
def iniciar_mqtt():
    return SistemaMQTT()


sistema = None
error_mqtt = False

try:
    sistema = iniciar_mqtt()
except Exception:
    error_mqtt = True

# ==========================================
# MENU LATERAL
# ==========================================

with st.sidebar:

    st.markdown("# 🌱 AgroRiego")
    st.caption("AGRICULTURA DE PRECISIÓN")

    st.divider()

    pagina = st.radio(
        "MENÚ PRINCIPAL",
        [
            "🏠 Inicio",
            "📊 Monitoreo",
            "💧 Control de riego",
            "🕒 Historial",
            "⚙️ Configuración"
        ]
    )

    st.divider()

    st.image(
        FOTO,
        use_container_width=True
    )

    st.caption("Cultivo de lechuga")

    st.markdown("### Acceso de operador")

    clave = st.text_input(
        "Contraseña de control",
        type="password"
    )

    try:

        clave_real = str(
            st.secrets["control"]["password"]
        )

        autorizado = bool(clave_real) and hmac.compare_digest(
            clave.encode("utf-8"),
            clave_real.encode("utf-8")
        )

    except Exception:
        autorizado = False

    if autorizado:
        st.success("Acceso autorizado")
    else:
        st.caption("Modo de visualización")

    st.divider()

    st.markdown("**Proyecto de Título**")
    st.caption("Ingeniería Agrícola")
    st.caption("INACAP Curicó · 2026")

# ==========================================
# ENCABEZADO
# ==========================================

st.markdown("""
<div class="hero">

<div class="hero-tag">
AGRICULTURA DE PRECISIÓN · ESP32 + IoT
</div>

<h1>Sistema de Riego Automatizado</h1>

<p>🥬 Cultivo: Lechuga</p>

<p>Monitoreo en tiempo real, control remoto
y gestión eficiente del recurso hídrico.</p>

</div>
""", unsafe_allow_html=True)

# ==========================================
# FUNCIONES
# ==========================================

def formato(valor, unidad):

    if valor is None:
        return "—"

    try:
        return f"{float(valor):.1f}{unidad}"
    except (ValueError, TypeError):
        return "—"


def enviar(comando):

    if not autorizado:
        st.error("Acceso no autorizado.")
        return

    if sistema is None:
        st.error("MQTT no disponible.")
        return

    if sistema.enviar(comando):
        st.info("Orden enviada. Esperando confirmación.")
    else:
        st.warning("No fue posible enviar la orden.")


def tarjetas(datos):

    c1, c2, c3, c4 = st.columns(4)

    with c1:

        st.metric(
            "🌱 Humedad del suelo",
            formato(
                datos.get("humedad")
                if datos.get("sensor_valido")
                else None,
                " %"
            )
        )

    with c2:

        st.metric(
            "🌡️ Temperatura",
            formato(
                datos.get("temperatura"),
                " °C"
            )
        )

    with c3:

        st.metric(
            "💧 Humedad ambiental",
            formato(
                datos.get("humedad_ambiental"),
                " %"
            )
        )

    with c4:

        lluvia = datos.get("lluvia")

        st.metric(
            "🌧️ Lluvia",
            "Detectada" if lluvia is True
            else "Sin lluvia" if lluvia is False
            else "—"
        )


def grafico(df, campo="humedad"):

    fig = go.Figure()

    if not df.empty:

        valores = df[campo].copy()

        if campo == "humedad":
            valores = valores.where(
                df["sensor_valido"]
            )

        fig.add_trace(go.Scatter(
            x=df["fecha"],
            y=valores,
            mode="lines",
            line=dict(
                color="#368B36",
                width=3
            ),
            fill="tozeroy",
            fillcolor="rgba(80,160,60,0.15)"
        ))

    if campo == "humedad":

        fig.add_hline(
            y=40,
            line_dash="dash",
            line_color="#E3A139"
        )

        fig.add_hline(
            y=70,
            line_dash="dash",
            line_color="#348D3B"
        )

        fig.update_yaxes(
            range=[0, 100],
            title="Índice de humedad (%)"
        )

    elif campo == "temperatura":
        fig.update_yaxes(title="Temperatura (°C)")

    else:
        fig.update_yaxes(
            range=[0, 100],
            title="Humedad ambiental (%)"
        )

    fig.update_layout(
        height=280,
        margin=dict(l=10, r=10, t=15, b=10),
        paper_bgcolor="white",
        plot_bgcolor="#F8FBF6",
        font=dict(color="#34533B"),
        showlegend=False,
        hovermode="x unified"
    )

    st.plotly_chart(
        fig,
        use_container_width=True,
        key="grafico_" + campo
    )


def controles(datos, conectado):

    st.subheader("💧 Control de riego")

    modo = datos.get("modo")

    nombre_modo = {
        "AUTO": "Automático",
        "MANUAL": "Manual"
    }.get(modo, "Sin datos")

    st.write("Modo actual:", nombre_modo)

    c1, c2 = st.columns(2)

    with c1:

        if st.button(
            "🌱 Automático",
            key="auto",
            disabled=not autorizado or not conectado
        ):
            enviar("AUTO")

    with c2:

        if st.button(
            "✋ Manual",
            key="manual",
            disabled=not autorizado or not conectado
        ):
            enviar("MANUAL")

    bloqueo = (
        not autorizado
        or not conectado
        or modo != "MANUAL"
        or datos.get("lluvia") is not False
        or datos.get("sensor_valido") is not True
        or datos.get("humedad", 100) >= 70
    )

    c3, c4 = st.columns(2)

    with c3:

        if st.button(
            "▶ ENCENDER",
            key="on",
            type="primary",
            disabled=bloqueo
        ):
            enviar("ON")

    with c4:

        if st.button(
            "■ APAGAR",
            key="off",
            disabled=not autorizado or not conectado
        ):
            enviar("OFF")

    if not autorizado:
        st.caption(
            "Ingresa tu contraseña en el menú lateral."
        )

    st.caption(
        "Máximo 10 segundos de riego. "
        "Espera de seguridad de 60 segundos."
    )


def estado_bomba(datos, conectado):

    st.subheader("⚙️ Estado de la bomba")

    st.markdown("""
    <div style="text-align:center;
    font-size:65px;padding:12px;">
    💧
    </div>
    """, unsafe_allow_html=True)

    if not conectado:
        st.warning("Estado desconocido")

    elif datos.get("bomba") is True:
        st.success("🟢 Encendida")

    elif datos.get("bomba") is False:
        st.info("⚪ Apagada")

    else:
        st.warning("Sin información")


def recomendacion(datos, conectado):

    st.subheader("🌿 Recomendación del sistema")

    if not conectado:
        st.info("Esperando mediciones reales.")

    elif not datos.get("sensor_valido"):
        st.error("Revisar sensor de humedad.")

    elif datos.get("lluvia"):
        st.warning("Lluvia detectada. No regar.")

    elif datos.get("humedad", 0) < 40:
        st.warning(
            "Suelo seco. Se recomienda activar "
            "el riego según las protecciones."
        )

    elif datos.get("humedad", 0) >= 70:
        st.success(
            "Humedad alta. No se requiere riego."
        )

    else:
        st.success(
            "Humedad dentro del rango configurado."
        )

    st.caption(
        "Recomendación basada en reglas "
        "y umbrales experimentales."
    )


def tabla_lecturas(df, cantidad=10):

    if df.empty:

        st.info("Esperando las primeras mediciones.")

        st.dataframe(
            pd.DataFrame(columns=[
                "Fecha y hora",
                "Humedad suelo",
                "Temperatura",
                "Humedad ambiental",
                "Lluvia"
            ]),
            hide_index=True,
            use_container_width=True
        )

        return

    tabla = df.tail(cantidad).copy()

    tabla["fecha"] = tabla["fecha"].dt.strftime(
        "%d-%m-%Y %H:%M:%S"
    )

    tabla["humedad"] = tabla["humedad"].where(
        tabla["sensor_valido"]
    )

    tabla["lluvia"] = tabla["lluvia"].map({
        True: "Sí",
        False: "No"
    })

    tabla = tabla[[
        "fecha",
        "humedad",
        "temperatura",
        "humedad_ambiental",
        "lluvia"
    ]]

    tabla.columns = [
        "Fecha y hora",
        "Humedad suelo (%)",
        "Temperatura (°C)",
        "Humedad ambiental (%)",
        "Lluvia"
    ]

    st.dataframe(
        tabla.iloc[::-1],
        hide_index=True,
        use_container_width=True
    )

# ==========================================
# PANEL PRINCIPAL
# ==========================================

@st.fragment(run_every=3)
def panel():

    datos = {}
    registros = []
    mqtt_conectado = False
    ultima = 0

    if sistema is not None:

        datos, registros, mqtt_conectado, ultima = (
            sistema.obtener()
        )

    conectado = (
        mqtt_conectado
        and ultima > 0
        and time.monotonic() - ultima <= 15
    )

    if error_mqtt:

        st.warning(
            "Revisar configuración MQTT en Secrets."
        )

    elif conectado:

        st.success("🟢 ESP32 conectado")

        st.caption(
            "Última lectura: "
            + datos["fecha"].strftime("%H:%M:%S")
        )

    elif mqtt_conectado:

        st.info(
            "Servidor MQTT conectado. "
            "Esperando datos del ESP32."
        )

    else:

        st.warning(
            "Esperando conexión con el servidor MQTT."
        )

    if not conectado:
        datos = {}

    df = pd.DataFrame(registros)

    if not df.empty:

        limite = pd.Timestamp.now(
            tz=ZONA
        ) - pd.Timedelta(hours=24)

        df = df[df["fecha"] >= limite]

    # ======================================
    # INICIO
    # ======================================

    if pagina == "🏠 Inicio":

        tarjetas(datos)

        st.write("")

        c1, c2, c3 = st.columns([1.2, 0.9, 1.6])

        with c1:

            with st.container(border=True):
                controles(datos, conectado)

        with c2:

            with st.container(border=True):
                estado_bomba(datos, conectado)

        with c3:

            with st.container(border=True):

                st.subheader("📈 Últimas 24 horas")

                grafico(df)

                if df.empty:
                    st.caption("Sin mediciones todavía.")

        c4, c5 = st.columns([1.4, 1])

        with c4:

            with st.container(border=True):

                st.subheader("📋 Últimas lecturas")

                tabla_lecturas(df, 5)

        with c5:

            with st.container(border=True):

                recomendacion(datos, conectado)

                st.image(
                    FOTO,
                    use_container_width=True
                )

    # ======================================
    # MONITOREO
    # ======================================

    elif pagina == "📊 Monitoreo":

        tarjetas(datos)

        st.subheader("Humedad del suelo")

        grafico(df)

        st.subheader("Temperatura ambiental")

        grafico(df, "temperatura")

        st.subheader("Humedad ambiental")

        grafico(df, "humedad_ambiental")

    # ======================================
    # CONTROL DE RIEGO
    # ======================================

    elif pagina == "💧 Control de riego":

        c1, c2 = st.columns(2)

        with c1:

            with st.container(border=True):
                controles(datos, conectado)

        with c2:

            with st.container(border=True):
                estado_bomba(datos, conectado)

        recomendacion(datos, conectado)

    # ======================================
    # HISTORIAL
    # ======================================

    elif pagina == "🕒 Historial":

        st.subheader("Historial de mediciones")

        grafico(df)

        tabla_lecturas(df, 100)

        if not df.empty:

            st.download_button(
                "📥 Descargar historial CSV",
                df.to_csv(index=False).encode("utf-8-sig"),
                file_name="historial_riego.csv",
                mime="text/csv"
            )

        st.caption(
            "Historial temporal de las últimas 24 horas. "
            "Se pierde al reiniciar el servidor."
        )

    # ======================================
    # CONFIGURACION
    # ======================================

    elif pagina == "⚙️ Configuración":

        st.subheader("Parámetros del sistema")

        c1, c2, c3, c4 = st.columns(4)

        c1.metric("Humedad mínima", "40 %")
        c2.metric("Humedad máxima", "70 %")
        c3.metric("Riego máximo", "10 s")
        c4.metric("Tiempo de espera", "60 s")

        st.subheader("Sensores y conexiones")

        st.table(pd.DataFrame({
            "Componente": [
                "Sensor de humedad del suelo",
                "Sensor de lluvia AO",
                "Sensor de lluvia DO",
                "DHT22",
                "Relé de bomba"
            ],
            "GPIO": [35, 32, 26, 25, 22]
        }))

        st.info(
            "Los parámetros se modifican "
            "desde el código de Arduino."
        )

        st.caption(
            "La humedad del suelo es un índice "
            "relativo calibrado para el prototipo."
        )

# ==========================================
# EJECUTAR TODA LA PLATAFORMA
# ==========================================

panel()

st.divider()

st.caption(
    "🌱 AgroRiego · Ingeniería Agrícola · "
    "INACAP Curicó · 2026"
)
