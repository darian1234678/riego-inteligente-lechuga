import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import paho.mqtt.client as mqtt
import json, ssl, time, threading, hmac, uuid
from collections import deque
from datetime import datetime
from zoneinfo import ZoneInfo

st.set_page_config(page_title='AgroRiego | Lechuga', page_icon='🌱', layout='wide')
TZ = ZoneInfo('America/Santiago')
# Fotografías externas: requieren conexión a Internet.
PHOTO = 'https://images.unsplash.com/photo-1622206151226-18ca2c9ab4a1?auto=format&fit=crop&w=1600&q=85'
st.markdown(f'''<style>
.stApp {{background:#f2f5ef;color:#233b2b;}}
.block-container {{padding-top:2rem;max-width:1500px;}}
[data-testid="stSidebar"] {{background:#153b28;}}
[data-testid="stSidebar"] p,[data-testid="stSidebar"] label,[data-testid="stSidebar"] h1,[data-testid="stSidebar"] h3 {{color:#fff!important;}}
.hero {{background:linear-gradient(90deg,rgba(13,48,29,.97),rgba(20,62,32,.35)),url('{PHOTO}') center 55%/cover,#285c35;padding:42px 30px;border-radius:20px;margin-bottom:20px;min-height:220px;}}
.hero h1 {{color:white!important;margin:8px 0;font-size:36px;}}
.hero p {{color:#e5f5d9;}}
.hero small {{color:#c4e8a3;letter-spacing:2px;}}
[data-testid="stMetric"] {{background:white;border:1px solid #dce7d8;border-top:4px solid #58934a;border-radius:16px;padding:20px;box-shadow:0 3px 12px #173d2010;}}
[data-testid="stMetric"] * {{color:#234c32!important;}}
[data-testid="stVerticalBlockBorderWrapper"] {{background:white;border-radius:16px;}}
.stButton button {{border-radius:10px;min-height:44px;width:100%;}}
.stButton button[kind="primary"] {{background:#367d43;color:white;border:none;}}
</style>''',unsafe_allow_html=True)

class Broker:
    def __init__(self):
        self.lock=threading.Lock()
        self.data={}; self.history=deque(maxlen=30000); self.online=False; self.last=0
        cfg=st.secrets['mqtt']
        self.client=mqtt.Client(mqtt.CallbackAPIVersion.VERSION2,client_id='agro-web-'+uuid.uuid4().hex[:12])
        self.client.username_pw_set(cfg['username'],cfg['password'])
        self.client.tls_set(cert_reqs=ssl.CERT_REQUIRED)
        self.client.on_connect=self.connect
        self.client.on_disconnect=self.disconnect
        self.client.on_message=self.message
        self.client.reconnect_delay_set(1,30)
        self.client.connect_async(cfg['host'],int(cfg['port']),60)
        self.client.loop_start()
    def connect(self,c,u,f,r,p):
        with self.lock: self.online=(r==0)
        if r==0: c.subscribe('riego/sensores',qos=1)
    def disconnect(self,c,u,f,r,p):
        with self.lock: self.online=False; self.last=0
    def message(self,c,u,m):
        try:
            if m.retain: return
            d=json.loads(m.payload.decode())
            if d['modo'] not in ('AUTO','MANUAL'): return
            if any(type(d[k]) is not bool for k in ('lluvia','bomba','sensor_valido')): return
            d['humedad']=float(d['humedad'])
            if not 0<=d['humedad']<=100: return
            for k in ('temperatura','humedad_ambiental'):
                if d[k] is not None: d[k]=float(d[k])
            d['fecha']=datetime.now(TZ)
            with self.lock:
                self.data=d.copy(); self.history.append(d.copy()); self.last=time.monotonic()
        except (ValueError,TypeError,KeyError,AttributeError): pass
    def snapshot(self):
        with self.lock: return self.data.copy(),list(self.history),self.online,self.last
    def send(self,cmd):
        _,_,online,last=self.snapshot()
        if not online or not last or time.monotonic()-last>15: return False
        return self.client.publish('riego/comando',cmd,qos=1,retain=False).rc==mqtt.MQTT_ERR_SUCCESS

@st.cache_resource
def broker(): return Broker()
try:
    b=broker()
    secret=str(st.secrets['control']['password'])
    if not secret: raise ValueError('Clave vacía')
except Exception:
    st.error('Revisa la configuración de Secrets de Streamlit.'); st.stop()

with st.sidebar:
    st.title('🌱 AgroRiego')
    st.caption('AGRICULTURA DE PRECISIÓN')
    page=st.radio('MENÚ PRINCIPAL',['🏠 Panel principal','📊 Historial','💧 Control de riego','⚙️ Configuración'])
    st.divider()
    st.image(PHOTO,caption='Cultivo de lechuga · Imagen referencial',use_container_width=True)
    st.markdown('### Acceso de operador')
    key=st.text_input('Contraseña de control',type='password')
    auth=hmac.compare_digest(key.encode(),secret.encode())
    if auth: st.success('Control autorizado')
    else: st.caption('Solo visualización')
    st.divider()
    st.markdown('**Proyecto de Título**')
    st.caption('Ingeniería Agrícola · INACAP Curicó')

st.markdown('''<div class="hero"><small>AGRICULTURA DE PRECISIÓN · ESP32 + IoT</small><h1>Sistema de Riego Automatizado</h1><p>Monitoreo inteligente del cultivo de lechuga</p><p>🌱 Riego localizado por goteo</p></div>''',unsafe_allow_html=True)

def fmt(v,u): return '—' if v is None else f'{v:.1f}{u}'
