
import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import paho.mqtt.client as mqtt
import json
import ssl
import time
import threading
import hmac
import uuid

from datetime import datetime
from zoneinfo import ZoneInfo
from collections import deque

# =====================================================
# CONFIGURACION GENERAL
# =====================================================

st.set_page_config(
    page_title="AgroRiego | Riego Inteligente",
    page_icon="🌱",
    layout="wide"
)

UMBRAL_MIN = 40
UMBRAL_MAX = 70

ZONA = ZoneInfo("America/Santiago")

# =====================================================
# DISEÑO VISUAL
# =====================================================

st.markdown("""
<style>

.stApp {
    background: #F3F6F0;
    color: #23382A;
}

.block-container {
    padding-top: 2rem;
    max-width: 1500px;
}

[data-testid="stSidebar"] {
    background: linear-gradient(
        180deg, #102D20, #1C4930
    );
}

[data-testid="stSidebar"] * {
    color: #FFFFFF !important;
}

[data-testid="stSidebar"] input {
    color: #172D20 !important;
    background: #FFFFFF !important;
}

.hero {
    background: linear-gradient(
        110deg, #143C26, #367344, #78A84B
    );
    padding: 38px;
    border-radius: 22px;
    margin-bottom: 25px;
    box-shadow: 0 5px 18px #163D2520;
}

.hero h1 {
    color: white !important;
    font-size: 36px;
    margin: 0;
}

.hero p {
    color: #E5F4DA;
    font-size: 16px;
    margin-top: 12px;
}

.hero-tag {
    color: #C7EE9B;
    font-size: 12px;
    font-weight: bold;
    letter-spacing: 2px;
}

[data-testid="stMetric"] {
    background: white;
    padding: 23px;
    border-radius: 16px;
    border: 1px solid #DCE7D8;
    border-top: 4px solid #55963E;
    box-shadow: 0 4px 12px #153C2010;
}

[data-testid="stMetricLabel"] {
    color: #607565;
}

[data-testid="stMetricValue"] {
    color: #204A2B;
    font-weight: bold;
}

[data-testid="stVerticalBlockBorderWrapper"] {
    background: white;
    border-radius: 18px;
}

h1, h2, h3 {
    color: #20452D;
}

.stButton > button {
    border-radius: 10px;
    min-height: 45px;
    font-weight: bold;
    width: 100%;
}

.stButton > button[kind="primary"] {
    background: #367D43;
    color: white;
    border: none;
}

.status-box {
    background: white;
    border: 1px solid #DCE7D8;
    padding: 18px;
    border-radius: 14px;
    margin-bottom: 15px;
}

footer {
    visibility: hidden;
}

</style>
""", unsafe_allow_html=True)

# =====================================================
# CONEXION MQTT CON EMQX
# =====================================================

class SistemaMQTT:

    def __init__(self):

        self.lock = threading.Lock()
        self.datos = {}
        self.historial = deque(maxlen=30000)
        self.conectado = False
        self.ultima_lectura = 0

        self.client = mqtt.Client(
            mqtt.CallbackAPIVersion.VERSION2,
            client_id="web-riego-" + uuid.uuid4().hex[:10]
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

            humedad = float(datos["humedad"])

            if not 0 <= humedad <= 100:
                return

            datos["humedad"] = humedad

            for campo in [
                "temperatura", "humedad_ambiental"
            ]:
                if datos[campo] is not None:
                    datos[campo] = float(datos[campo])

            datos["fecha"] = datetime.now(ZONA)

            with self.lock:
                self.datos = datos.copy()
                self.ultima_lectura = time.monotonic()
                self.historial.append(datos.copy())

        except (ValueError, TypeError, KeyError):
            pass

    def obtener(self):

        with self.lock:
            return (
                self.datos.copy(),
                list(self.historial),
                self.conectado,
                self.ultima_lectura
            )

    def enviar(self, comando):

        datos, _, conectado, ultima = self.obtener()

        if not conectado:
            return False

        if time.monotonic() - ultima > 15:
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


try:
    sistema = iniciar_mqtt()

except Exception:
    st.error(
        "No se pudo iniciar MQTT. "
        "Revisa los Secrets de Streamlit."
    )
    st.stop()

# =====================================================
# MENU LATERAL
# =====================================================

with st.sidebar:

    st.markdown("# 🌱 AgroRiego")

    st.caption("AGRICULTURA INTELIGENTE")

    st.divider()

    pagina = st.radio(
        "MENÚ PRINCIPAL",
        [
            "🏠 Panel principal",
            "📊 Historial",
            "💧 Control de riego",
            "⚙️ Configuración"
        ]
    )

    st.divider()

    st.markdown("### Cultivo")

    st.markdown("🥬 Lechuga")
    st.markdown("💧 Riego por goteo")
    st.markdown("📡 Tecnología ESP32 + IoT")

    st.divider()

    st.markdown("### Acceso de operador")

    clave = st.text_input(
        "Contraseña de control",
        type="password"
    )

    autorizado = hmac.compare_digest(
        clave.encode("utf-8"),
        str(st.secrets["control"]["password"]).encode("utf-8")
    )

    if autorizado:
        st.success("Control autorizado")
    else:
        st.caption("Modo de visualización")

    st.divider()

    st.markdown("**Proyecto de Título**")
    st.caption("Ingeniería Agrícola")
    st.caption("INACAP · Curicó · 2026")

# =====================================================
# FUNCIONES VISUALES
# =====================================================

def formato(valor, unidad):

    if valor is None:
        return "—"

    try:
        return f"{float(valor):.1f}{unidad}"
    except (ValueError, TypeError):
        return "—"


def enviar_comando(comando):

    if not autorizado:
        st.error("Acceso no autorizado.")
        return

    if sistema.enviar(comando):
        st.info(
            "Orden enviada. Esperando confirmación "
            "del ESP32."
        )
    else:
        st.error("No fue posible enviar la orden.")


def grafico_humedad(df):

    fig = go.Figure()

    if not df.empty:
        fig.add_trace(go.Scatter(
            x=df["fecha"],
            y=df["humedad"],
            mode="lines",
            name="Humedad del suelo",
            line=dict(color="#438C42", width=3),
            fill="tozeroy",
            fillcolor="rgba(67,140,66,0.13)"
        ))

    fig.add_hline(
        y=40,
        line_dash="dash",
        line_color="#E5A13C",
        annotation_text="Inicio de riego: 40%"
    )

    fig.add_hline(
        y=70,
        line_dash="dash",
        line_color="#388E3C",
        annotation_text="Detención: 70%"
    )

    fig.update_layout(
        height=330,
        margin=dict(l=15, r=15, t=30, b=15),
        paper_bgcolor="white",
        plot_bgcolor="#F8FBF6",
        font=dict(color="#385440"),
        yaxis=dict(
            range=[0, 100],
            title="Humedad relativa (%)"
        ),
        xaxis_title="Hora",
        hovermode="x unified",
        showlegend=False
    )

    st.plotly_chart(
        fig,
        use_container_width=True
    )


def controles(datos, en_linea):

    st.subheader("💧 Control de riego")

    if not en_linea:
        st.warning("Esperando conexión del ESP32.")

    modo = datos.get("modo")
    bomba = datos.get("bomba")

    st.write(
        "Modo actual:",
        {"AUTO": "Automático",
         "MANUAL": "Manual"}.get(modo, "Sin datos")
    )

    c1, c2 = st.columns(2)

    with c1:
        if st.button(
            "🌱 Automático",
            key="auto",
            disabled=not autorizado or not en_linea
        ):
            enviar_comando("AUTO")

    with c2:
        if st.button(
            "✋ Manual",
            key="manual",
            disabled=not autorizado or not en_linea
        ):
            enviar_comando("MANUAL")

    st.divider()

    if not en_linea or bomba is None:
        st.warning("Estado de bomba desconocido")
    elif bomba:
        st.success("🟢 BOMBA ENCENDIDA")
    else:
        st.info("⚪ BOMBA APAGADA")

    bloquear_on = (
        not autorizado
        or not en_linea
        or modo != "MANUAL"
        or datos.get("lluvia") is not False
        or datos.get("sensor_valido") is not True
        or datos.get("humedad", 100) >= 70
    )

    c3, c4 = st.columns(2)

    with c3:
        if st.button(
            "▶ ENCENDER",
            type="primary",
            key="on",
            disabled=bloquear_on
        ):
            enviar_comando("ON")

    with c4:
        if st.button(
            "■ APAGAR",
            key="off",
            disabled=not autorizado or not en_linea
        ):
            enviar_comando("OFF")

    st.caption(
        "Protecciones previstas: lluvia, "
        "humedad alta, máximo 10 segundos "
        "y espera de 60 segundos."
    )

# =====================================================
# ENCABEZADO PRINCIPAL
# =====================================================

st.markdown("""
<div class="hero">
    <div class="hero-tag">
        AGRICULTURA DE PRECISIÓN · IoT
    </div>
    <h1>🌱 Sistema de Riego Automatizado</h1>
    <p>
        Monitoreo inteligente del cultivo de lechuga
        y gestión eficiente del recurso hídrico.
    </p>
</div>
""", unsafe_allow_html=True)

# =====================================================
# PANEL CON ACTUALIZACION AUTOMATICA
# =====================================================

@st.fragment(run_every=3)
def panel():

    datos, registros, conectado, ultima = sistema.obtener()

    en_linea = (
        conectado
        and ultima > 0
        and time.monotonic() - ultima <= 15
    )

    if conectado:
        st.caption("🟢 Servidor MQTT conectado")
    else:
        st.caption("🔴 Servidor MQTT desconectado")

    if en_linea:
        st.success("🟢 ESP32 EN LÍNEA")
        st.caption(
            "Última actualización: "
            + datos["fecha"].strftime("%H:%M:%S")
        )
    else:
        st.warning(
            "ESP32 sin datos recientes. "
            "Esperando mediciones reales."
        )

    if not en_linea:
        datos = {}

    df = pd.DataFrame(registros)

    if not df.empty:
        limite = pd.Timestamp.now(
            tz=ZONA
        ) - pd.Timedelta(hours=24)

        df = df[df["fecha"] >= limite]

    # PANEL PRINCIPAL

    if pagina == "🏠 Panel principal":

        c1, c2, c3, c4 = st.columns(4)

        with c1:
            st.metric(
                "🌱 Humedad del suelo",
                formato(
                    datos.get("humedad")
                    if datos.get("sensor_valido")
                    else None,
                    "%"
                )
            )

        with c2:
            st.metric(
                "🌡️ Temperatura",
                formato(datos.get("temperatura"), " °C")
            )

        with c3:
            st.metric(
                "💧 Humedad ambiental",
                formato(
                    datos.get("humedad_ambiental"),
                    "%"
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

        st.write("")

        izquierda, derecha = st.columns([2, 1])

        with izquierda:

            with st.container(border=True):

                st.subheader(
                    "📈 Evolución de humedad del suelo"
                )

                st.caption(
                    "Mediciones reales · Últimas 24 horas"
                )

                grafico_humedad(df)

                if df.empty:
                    st.info(
                        "El historial comenzará cuando "
                        "el ESP32 envíe sus mediciones."
                    )

        with derecha:
            with st.container(border=True):
                controles(datos, en_linea)

        st.subheader("🌿 Recomendación del sistema")

        if not en_linea:
            st.info("Esperando información del cultivo.")

        elif not datos.get("sensor_valido"):
            st.error("Revisar sensor de humedad.")

        elif datos.get("lluvia"):
            st.warning(
                "Lluvia detectada. Mantener riego detenido."
            )

        elif datos.get("humedad", 0) < 40:
            st.warning(
                "Suelo seco. Se recomienda riego "
                "según las protecciones del sistema."
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
            "Recomendación basada en reglas y "
            "umbrales experimentales."
        )

    # HISTORIAL

    elif pagina == "📊 Historial":

        st.subheader("Historial de mediciones")

        grafico_humedad(df)

        if not df.empty:

            fig = go.Figure()

            fig.add_trace(go.Scatter(
                x=df["fecha"],
                y=df["temperatura"],
                name="Temperatura ambiental",
                line=dict(color="#E89538", width=3)
            ))

            fig.update_layout(
                height=300,
                yaxis_title="Temperatura (°C)",
                paper_bgcolor="white",
                plot_bgcolor="#F8FBF6"
            )

            st.plotly_chart(
                fig,
                use_container_width=True
            )

            tabla = df.copy()

            tabla["fecha"] = tabla["fecha"].dt.strftime(
                "%d-%m-%Y %H:%M:%S"
            )

            tabla = tabla.rename(columns={
                "fecha": "Fecha",
                "humedad": "Humedad suelo (%)",
                "temperatura": "Temperatura (°C)",
                "humedad_ambiental": "Humedad ambiental (%)",
                "lluvia": "Lluvia",
                "bomba": "Bomba",
                "modo": "Modo",
                "sensor_valido": "Sensor válido"
            })

            st.dataframe(
                tabla.tail(100).iloc[::-1],
                use_container_width=True,
                hide_index=True
            )

            st.download_button(
                "📥 Descargar mediciones CSV",
                tabla.to_csv(index=False).encode("utf-8-sig"),
                file_name="historial_riego.csv",
                mime="text/csv"
            )

        else:
            st.info("Todavía no existen mediciones.")

        st.caption(
            "Historial temporal en memoria. "
            "Descárgalo antes de reiniciar la aplicación."
        )

    # CONTROL

    elif pagina == "💧 Control de riego":

        with st.container(border=True):
            controles(datos, en_linea)

    # CONFIGURACION

    elif pagina == "⚙️ Configuración":

        st.subheader("Parámetros del prototipo")

        c1, c2 = st.columns(2)

        with c1:
            st.metric("Humedad mínima", "40%")
            st.metric("Duración máxima", "10 s")

        with c2:
            st.metric("Humedad máxima", "70%")
            st.metric("Espera entre riegos", "60 s")

        st.markdown("### Sensores instalados")

        st.table(pd.DataFrame({
            "Componente": [
                "Humedad del suelo",
                "Sensor de lluvia AO",
                "Sensor de lluvia DO",
                "DHT22",
                "Relé"
            ],
            "GPIO": [35, 32, 26, 25, 22]
        }))

        st.info(
            "Los parámetros se configuran "
            "en el programa del ESP32."
        )

        st.caption(
            "La humedad del suelo corresponde "
            "a un índice relativo calibrado."
        )


panel()

st.divider()

st.caption(
    "🌱 AgroRiego · Proyecto de Título · "
    "Ingeniería Agrícola · INACAP Curicó 2026"
)
