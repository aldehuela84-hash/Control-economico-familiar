import os
import time
import random
from datetime import datetime
import pandas as pd
import streamlit as st
import sqlalchemy
from sqlalchemy import create_engine, text

st.set_page_config(page_title="Control Económico Familiar v6.1 Cloud", page_icon="💰", layout="wide")

MESES_ORDEN = ["Ene", "Feb", "Mar", "Abril", "Mayo", "Jun", "Jul", "Agos", "Sep", "Oct", "Nov", "Dic"]
MESES_MAPPING_NUM = {1: "Ene", 2: "Feb", 3: "Mar", 4: "Abril", 5: "Mayo", 6: "Jun", 7: "Jul", 8: "Agos", 9: "Sep", 10: "Oct", 11: "Nov", 12: "Dic"}
MESES_NOMBRES = {
    "Ene": "Enero", "Feb": "Febrero", "Mar": "Marzo", "Abril": "Abril",
    "Mayo": "Mayo", "Jun": "Junio", "Jul": "Julio", "Agos": "Agosto",
    "Sep": "Septiembre", "Oct": "Octubre", "Nov": "Noviembre", "Dic": "Diciembre"
}
BLOQUES_ORDEN = ["VIVIENDA", "COMIDA", "COCHES", "NIÑOS", "COMPRAS", "GASTOS PERSONALES", "EXTRAS"]

REGLAS_PREDETERMINADAS = [
    ("MERCADONA", "COMIDA", "Alimentacion", 0.0),
    ("IBERDROLA", "VIVIENDA", "Luz gas, agua", 0.0),
    ("REPSOL", "COCHES", "Combustible", 0.0)
]

# ==========================================
# 🗄️ CONEXIÓN A BASE DE DATOS (Supabase / SQLite)
# ==========================================
def get_db_engine():
    if "DATABASE_URL" in st.secrets:
        db_url = st.secrets["DATABASE_URL"]
    elif "postgres" in st.secrets and "url" in st.secrets["postgres"]:
        db_url = st.secrets["postgres"]["url"]
    else:
        db_url = os.environ.get("DATABASE_URL", "sqlite:///economia_familiar.db")
    
    if db_url.startswith("postgres://"):
        db_url = db_url.replace("postgres://", "postgresql://", 1)
        
    return create_engine(db_url, pool_pre_ping=True)

engine = get_db_engine()
is_postgres = "postgresql" in str(engine.url)

def auto_clasificar(desc):
    d = str(desc).upper()
    if any(x in d for x in ["NOMINA", "NÓMINA", "HABERES", "PENSIÓN", "SALARIO"]): return "INGRESOS", "Nómina Jorge"
    if "BIZUM" in d and ("FAVOR" in d or "RECIBIDO" in d): return "INGRESOS", "Ingreso Bizum"
    if "DEVOLUCION" in d or "RETROCESION" in d or "ABONO" in d: return "INGRESOS", "Devoluciones"
    if any(x in d for x in ["IBERDROLA", "ENDESA", "NATURGY", "REPSOL LUZ", "CURENERGIA", "ENEL", "AGUAS", "CANAL DE ISABEL", "AQUALIA", "GANA ENERGIA"]): return "VIVIENDA", "Luz gas, agua"
    if any(x in d for x in ["HIPOTECA", "PRESTAMO", "ING DIRECT", "CUOTA PRESTAMO"]): return "VIVIENDA", "Hipoteca chalet"
    if any(x in d for x in ["MOVISTAR", "VODAFONE", "ORANGE", "JAZZTEL", "DIGI", "O2", "LOWI", "SIMYO", "PEPEPHONE", "MASMOVIL"]): return "VIVIENDA", "Telf. Internet."
    if any(x in d for x in ["COMUNIDAD", "FINCAS", "ADMINISTRADOR"]): return "VIVIENDA", "Comunidad"
    if any(x in d for x in ["IBI", "AYUNTAMIENTO", "TRIBUTO", "BASURA"]): return "VIVIENDA", "Impuestos"
    if any(x in d for x in ["MERCADONA", "CARREFOUR", "ALCAMPO", "AHORRAMAS", "LIDL", "ALDI", "DIA", "STELAM MARKET", "EROSKI", "ALIMERKA", "CONSUM", "HIPERCOR", "SUPERCOR"]): return "COMIDA", "Alimentacion"
    if any(x in d for x in ["REPSOL", "CEPSA", "PLENOIL", "BALLENOIL", "GALP", "BP", "SHELL", "PETROPRIX", "GREEN GAS", "EASYGAS"]): return "COCHES", "Combustible"
    if any(x in d for x in ["TALLER", "NORAUTO", "MIDAS", "ITV", "RECAMBIOS", "OSCARO", "AUTODOC", "NEUMATICOS"]): return "COCHES", "Mantenimiento"
    if any(x in d for x in ["SEGURO AUTO", "LINEA DIRECTA", "MAPFRE", "MUTUA", "ALLIANZ", "PELAYO", "QUALITAS", "AXA"]) and "VIDA" not in d: return "COCHES", "Seguros"
    if any(x in d for x in ["AMAZON", "ALIEXPRESS", "SHEIN", "ZARA", "PRIMARK", "DECATHLON", "LEROY", "IKEA", "MR DIY", "WALLAPOP", "VINTED", "EL CORTE INGLES", "MEDIA MARKT", "ZALANDO", "MANGO", "STRADIVARIUS", "PULL", "BERSHKA", "H&M"]): return "COMPRAS", "Amazon/Aliexpres"
    if any(x in d for x in ["FARMACIA", "CLINICA", "DENTAL", "DENTISTA", "OPTICA", "CENTRO EVEL", "HOSPITAL", "FISIOTERAPIA"]): return "GASTOS PERSONALES", "Salud"
    if any(x in d for x in ["PSICOLOGO", "TERAPIA"]): return "GASTOS PERSONALES", "Psicologo"
    if any(x in d for x in ["GIMNASIO", "MCFIT", "BASIC FIT", "ALTAFIT", "FITNESS", "SYNERGY", "CROSSFIT"]): return "GASTOS PERSONALES", "Gimanasio"
    if any(x in d for x in ["NETFLIX", "SPOTIFY", "HBO", "DISNEY", "PRIME", "GOOGLE ONE", "APPLE", "YOUTUBE"]): return "GASTOS PERSONALES", "Suscripciones"
    if any(x in d for x in ["RESTAURANTE", "BURGER", "MCDONALDS", "KFC", "TELEPIZZA", "GLOVO", "UBER EATS", "JUST EAT", "VIPS", "FOSTER", "GINOS", "DOMINOS", "GOIKO", "100 MONTADITOS", "CAFETERIA", "BAR "]): return "GASTOS PERSONALES", "Ocio"
    if any(x in d for x in ["RENFE", "METRO", "CONSORCIO", "ALSA", "TAXI", "CABIFY", "UBER", "BOLT", "FREE NOW"]): return "GASTOS PERSONALES", "Abono transporte"
    if any(x in d for x in ["KIWOKO", "TIENDANIMAL", "VETERINARIO"]): return "GASTOS PERSONALES", "Mascotas"
    if any(x in d for x in ["PRIMA SEGURO", "SEGURO DE VIDA", "VIDA CAIXA", "SANTALUCIA", "OCASO"]): return "GASTOS PERSONALES", "Seguro Vida"
    if any(x in d for x in ["COLEGIO", "AMPA", "COMEDOR", "ACADEMIA", "GUARDERIA", "INFANTIL", "JUGUETTOS", "TOYS R US"]): return "NIÑOS", "Extraescolares"
    if "BIZUM" in d: return "EXTRAS", "Bizum Emitido"
    if any(x in d for x in ["COMISION", "MANTENIMIENTO CUENTA", "LIQUIDACION"]): return "EXTRAS", "Imprevistos"
    return None, None

def restaurar_presupuesto_base():
    with engine.begin() as conn:
        conn.execute(text("DELETE FROM movimientos WHERE es_real = 0"))
        
        base_mensual = [
            ("VIVIENDA", "Hipoteca chalet", 700.0), ("VIVIENDA", "Hipoteca piso", 600.0),
            ("VIVIENDA", "Luz gas, agua", 180.0), ("VIVIENDA", "Placas solares", 90.0), ("VIVIENDA", "Telf. Internet.", 100.0),
            ("COMIDA", "Alimentacion", 850.0),
            ("COCHES", "Cupra", 180.0), ("COCHES", "Combustible", 350.0),
            ("NIÑOS", "Gastos peques", 100.0), ("NIÑOS", "Comedor", 130.0), ("NIÑOS", "Extraescolares", 110.0),
            ("COMPRAS", "Amazon/Aliexpres", 120.0),
            ("GASTOS PERSONALES", "Ocio", 400.0), ("GASTOS PERSONALES", "Psicologo", 120.0),
            ("GASTOS PERSONALES", "Gimanasio", 50.0), ("GASTOS PERSONALES", "Seguro Vida", 70.0), ("GASTOS PERSONALES", "Abono transporte", 40.0)
        ]
        
        base_especial = [
            ("VIVIENDA", "Impuestos", 130.0, "Abril"), ("COCHES", "Numeritos", 130.0, "Abril"),
            ("COCHES", "Mantenimiento", 400.0, "Feb"),
            ("EXTRAS", "Cumples / Reyes", 240.0, "Ene"), ("EXTRAS", "Cumples / Reyes", 80.0, "Feb"),
            ("EXTRAS", "Cumples / Reyes", 30.0, "Mar"), ("EXTRAS", "Cumples / Reyes", 80.0, "Abril"),
            ("EXTRAS", "Cumples / Reyes", 30.0, "Mayo")
        ]
        
        registros = []
        for anio in range(2026, 2036):
            for mes in MESES_ORDEN:
                imp_jorge = 4100.0 if mes == "Ene" else 3020.0
                registros.append({"anio": anio, "mes": mes, "bloque": "INGRESOS", "concepto": "Nómina Jorge", "tipo": "INGRESO", "importe": imp_jorge, "es_real": 0, "fecha_exacta": None, "descripcion_original": "Nómina Jorge"})
                registros.append({"anio": anio, "mes": mes, "bloque": "INGRESOS", "concepto": "Nómina Grego", "tipo": "INGRESO", "importe": 1500.0, "es_real": 0, "fecha_exacta": None, "descripcion_original": "Nómina Grego"})
                for b, c, imp in base_mensual:
                    registros.append({"anio": anio, "mes": mes, "bloque": b, "concepto": c, "tipo": "GASTO", "importe": imp, "es_real": 0, "fecha_exacta": None, "descripcion_original": c})
            for b, c, imp, mes in base_especial:
                registros.append({"anio": anio, "mes": mes, "bloque": b, "concepto": c, "tipo": "GASTO", "importe": imp, "es_real": 0, "fecha_exacta": None, "descripcion_original": c})
            
        conn.execute(
            text("INSERT INTO movimientos (anio, mes, bloque, concepto, tipo, importe, es_real, fecha_exacta, descripcion_original) VALUES (:anio, :mes, :bloque, :concepto, :tipo, :importe, :es_real, :fecha_exacta, :descripcion_original)"),
            registros
        )

def init_db():
    with engine.begin() as conn:
        if is_postgres:
            conn.execute(text('''CREATE TABLE IF NOT EXISTS movimientos (id SERIAL PRIMARY KEY, partida_recurrente_id INTEGER, anio INTEGER NOT NULL, mes VARCHAR(10) NOT NULL, bloque VARCHAR(50) NOT NULL, concepto VARCHAR(100) NOT NULL, tipo VARCHAR(20) NOT NULL, importe NUMERIC(10,2) NOT NULL, es_real INTEGER DEFAULT 0, fecha_exacta VARCHAR(20), descripcion_original TEXT)'''))
            conn.execute(text('''CREATE TABLE IF NOT EXISTS meses_cerrados (anio INTEGER NOT NULL, mes VARCHAR(10) NOT NULL, PRIMARY KEY (anio, mes))'''))
            conn.execute(text('''CREATE TABLE IF NOT EXISTS desgloses (id SERIAL PRIMARY KEY, movimiento_id INTEGER NOT NULL, subconcepto VARCHAR(100) NOT NULL, importe NUMERIC(10,2) NOT NULL, fecha VARCHAR(20))'''))
            conn.execute(text('''CREATE TABLE IF NOT EXISTS retiros_ahorro (id SERIAL PRIMARY KEY, anio INTEGER NOT NULL, mes VARCHAR(10) NOT NULL, concepto VARCHAR(100) NOT NULL, importe NUMERIC(10,2) NOT NULL, fecha VARCHAR(20))'''))
            conn.execute(text('''CREATE TABLE IF NOT EXISTS reglas_categorias (id SERIAL PRIMARY KEY, patron VARCHAR(100) NOT NULL, bloque VARCHAR(50) NOT NULL, concepto VARCHAR(100) NOT NULL, importe_exacto NUMERIC(10,2) DEFAULT 0.0)'''))
            conn.execute(text('''CREATE TABLE IF NOT EXISTS configuracion (clave VARCHAR(50) PRIMARY KEY, valor NUMERIC(10,2) NOT NULL)'''))
        else:
            conn.execute(text('''CREATE TABLE IF NOT EXISTS movimientos (id INTEGER PRIMARY KEY AUTOINCREMENT, partida_recurrente_id INTEGER, anio INTEGER NOT NULL, mes TEXT NOT NULL, bloque TEXT NOT NULL, concepto TEXT NOT NULL, tipo TEXT NOT NULL, importe REAL NOT NULL, es_real INTEGER DEFAULT 0, fecha_exacta TEXT, descripcion_original TEXT)'''))
            conn.execute(text('''CREATE TABLE IF NOT EXISTS meses_cerrados (anio INTEGER NOT NULL, mes TEXT NOT NULL, PRIMARY KEY (anio, mes))'''))
            conn.execute(text('''CREATE TABLE IF NOT EXISTS desgloses (id INTEGER PRIMARY KEY AUTOINCREMENT, movimiento_id INTEGER NOT NULL, subconcepto TEXT NOT NULL, importe REAL NOT NULL, fecha TEXT)'''))
            conn.execute(text('''CREATE TABLE IF NOT EXISTS retiros_ahorro (id INTEGER PRIMARY KEY AUTOINCREMENT, anio INTEGER NOT NULL, mes TEXT NOT NULL, concepto TEXT NOT NULL, importe REAL NOT NULL, fecha TEXT)'''))
            conn.execute(text('''CREATE TABLE IF NOT EXISTS reglas_categorias (id INTEGER PRIMARY KEY AUTOINCREMENT, patron TEXT NOT NULL, bloque TEXT NOT NULL, concepto TEXT NOT NULL, importe_exacto REAL DEFAULT 0.0)'''))
            conn.execute(text('''CREATE TABLE IF NOT EXISTS configuracion (clave VARCHAR(50) PRIMARY KEY, valor REAL NOT NULL)'''))

        res = conn.execute(text("SELECT valor FROM configuracion WHERE clave = 'saldo_inicial_sep_2026'")).fetchone()
        if res is None:
            conn.execute(text("INSERT INTO configuracion (clave, valor) VALUES ('saldo_inicial_sep_2026', 3500.0)"))
            
        count = conn.execute(text("SELECT COUNT(*) FROM movimientos WHERE es_real = 0")).fetchone()[0]
        if count == 0:
            restaurar_presupuesto_base()

def limpiar_duplicados_df(df_mov):
    if df_mov.empty: return df_mov
    res = []
    for m in df_mov['mes'].unique():
        sub_m = df_mov[df_mov['mes'] == m]
        
        df_ing = sub_m[sub_m['tipo'] == 'INGRESO']
        for c in df_ing['concepto'].unique():
            df_c = df_ing[df_ing['concepto'] == c]
            if (df_c['es_real'].astype(int) == 1).any(): res.append(df_c[df_c['es_real'].astype(int) == 1])
            else: res.append(df_c)
                
        for b in BLOQUES_ORDEN:
            df_b = sub_m[(sub_m['bloque'] == b) & (sub_m['tipo'] == 'GASTO')]
            if df_b.empty: continue
            if b == "COMIDA":
                if (df_b['es_real'].astype(int) == 1).any(): res.append(df_b[df_b['es_real'].astype(int) == 1])
                else: res.append(df_b)
            else:
                for c in df_b['concepto'].unique():
                    df_c = df_b[df_b['concepto'] == c]
                    if (df_c['es_real'].astype(int) == 1).any(): res.append(df_c[df_c['es_real'].astype(int) == 1])
                    else: res.append(df_c)
                    
    if not res: return df_mov.iloc[0:0]
    return pd.concat(res)

def obtener_metricas_ahorro_completa(anio, saldo_inicial):
    df_m = pd.read_sql_query(text("SELECT anio, mes, bloque, concepto, tipo, importe, es_real FROM movimientos WHERE anio <= :anio"), engine, params={"anio": anio})
    df_r = pd.read_sql_query(text("SELECT * FROM retiros_ahorro WHERE anio <= :anio"), engine, params={"anio": anio})
    
    df_m_limpio = limpiar_duplicados_df(df_m)
    
    data_meses = []
    saldo_acum = saldo_inicial
    
    for a in range(2026, anio + 1):
        for m in MESES_ORDEN:
            sub_m = df_m_limpio[(df_m_limpio['anio'] == a) & (df_m_limpio['mes'] == m)]
            ing = sub_m[sub_m['tipo'] == 'INGRESO']['importe'].sum()
            gas = sub_m[sub_m['tipo'] == 'GASTO']['importe'].sum()
            
            sub_r = df_r[(df_r['anio'] == a) & (df_r['mes'] == m)]
            ret_mes = sub_r['importe'].sum() if not sub_r.empty else 0.0
            
            sobrante = ing - gas
            saldo_acum += (sobrante + ret_mes)
                
            if a == anio:
                data_meses.append({
                    "Mes": m,
                    "Ahorro Generado (Sobrante)": sobrante,
                    "Movimientos Hucha (+/-)": ret_mes,
                    "Saldo Acumulado Hucha": saldo_acum
                })
                
    df_res = pd.DataFrame(data_meses)
    return df_res, saldo_acum

def simular_mes_test(anio, mes):
    mes_idx = MESES_ORDEN.index(mes) + 1
    
    movimientos_ficticios = [
        ("NÓMINA JORGE ALDEHUELA", 3020.00),
        ("BIZUM RECIBIDO PAGO CENA", 45.00),
        ("DEVOLUCION COMPRA AMAZON", 19.99),
        ("RECIBO IBERDROLA", -85.40),
        ("RECIBO MOVISTAR", -100.00),
        ("COMUNIDAD FINCAS", -80.00),
        ("HIPOTECA ING DIRECT", -700.00),
        ("COMPRA MERCADONA", -120.30),
        ("COMPRA MERCADONA", -45.20),
        ("CARREFOUR ALIMENTACION", -110.50),
        ("ALDI SUPERMERCADO", -35.00),
        ("AHORRAMAS COMPRA", -62.10),
        ("REPSOL ESTACION DE SERVICIO", -70.00),
        ("PLENOIL GASOLINERA", -50.00),
        ("TALLERES NORAUTO", -120.00),
        ("AMAZON EU SARL", -34.50),
        ("ALIEXPRESS", -12.90),
        ("DECATHLON COMPRA", -42.99),
        ("ZARA ROPA", -65.00),
        ("NETFLIX SUSCRIPCION", -12.99),
        ("SPOTIFY MUSIC", -9.99),
        ("CUOTA GIMNASIO BASIC FIT", -30.00),
        ("BURGER KING", -22.50),
        ("RESTAURANTE EL CHURRASCO", -55.00),
        ("FARMACIA CONDE", -14.20),
        ("RENFE TICKET", -15.50),
        ("VETERINARIO MASCOTA", -40.00),
        ("BIZUM EMITIDO CUMPLEAÑOS", -20.00),
        ("COLEGIO AMPA", -50.00),
        ("COMEDOR ESCOLAR", -130.00),
        ("TRANSFERENCIA A ALBA", -150.00),
        ("TRANSFERENCIA PISO LUZ", -60.00)
    ]
    
    reglas_df = pd.read_sql_query(text("SELECT patron, bloque, concepto, COALESCE(importe_exacto, 0.0) as importe_exacto FROM reglas_categorias"), engine)
    registros = []
    
    for desc, importe in movimientos_ficticios:
        dia = random.randint(1, 28)
        fecha_exacta = f"{anio}-{mes_idx:02d}-{dia:02d}"
        
        bloque_val, concepto_limpio = "PENDIENTE", desc
        tipo_val = "INGRESO" if importe > 0 else "GASTO"
        imp_abs = abs(importe)
        
        matched = False
        for _, r_rule in reglas_df.iterrows():
            patron_ok = str(r_rule['patron']).upper() in desc.upper()
            imp_rule = float(r_rule['importe_exacto'] or 0.0)
            imp_ok = True if imp_rule == 0.0 else (abs(imp_rule - imp_abs) < 0.01)
            
            if patron_ok and imp_ok:
                bloque_val, concepto_limpio = r_rule['bloque'], r_rule['concepto']
                matched = True
                break
                
        if not matched:
            b_ia, c_ia = auto_clasificar(desc)
            if b_ia and c_ia:
                bloque_val, concepto_limpio = b_ia, c_ia
                
        registros.append({"anio": anio, "mes": mes, "bloque": bloque_val, "concepto": concepto_limpio, "tipo": tipo_val, "importe": imp_abs, "es_real": 1, "fecha_exacta": fecha_exacta, "descripcion_original": desc})
        
    with engine.begin() as conn:
        conn.execute(
            text("INSERT INTO movimientos (anio, mes, bloque, concepto, tipo, importe, es_real, fecha_exacta, descripcion_original) VALUES (:anio, :mes, :bloque, :concepto, :tipo, :importe, :es_real, :fecha_exacta, :descripcion_original)"),
            registros
        )
        conn.execute(
            text("INSERT INTO meses_cerrados (anio, mes) VALUES (:anio, :mes) ON CONFLICT (anio, mes) DO NOTHING"),
            {"anio": anio, "mes": mes}
        )

init_db()

# Estilos CSS
st.markdown("""
<style>
    .block-header-gasto { background-color: #1E293B; color: #F8FAFC; padding: 10px 15px; border-radius: 6px; font-weight: bold; font-size: 16px; margin-top: 15px; margin-bottom: 10px; border-left: 5px solid #3B82F6;}
    .block-header-ingreso { background-color: #064E3B; color: #F8FAFC; padding: 10px 15px; border-radius: 6px; font-weight: bold; font-size: 16px; margin-top: 15px; margin-bottom: 10px; border-left: 5px solid #10B981;}
    .block-header-ahorro { background-color: #4C1D95; color: #F8FAFC; padding: 10px 15px; border-radius: 6px; font-weight: bold; font-size: 16px; margin-top: 15px; margin-bottom: 10px; border-left: 5px solid #8B5CF6;}
    .block-header-pendientes { background-color: #991B1B; color: #F8FAFC; padding: 10px 15px; border-radius: 6px; font-weight: bold; font-size: 16px; margin-top: 25px; margin-bottom: 10px; border-left: 5px solid #F87171;}
    
    button[data-testid="baseButton-primary"], 
    div.stButton > button[kind="primary"],
    div.stButton > button[type="primary"] {
        background-color: #2563EB !important;
        color: #FFFFFF !important;
        font-weight: bold !important;
        border: 2px solid #60A5FA !important;
        box-shadow: 0px 4px 10px rgba(37, 99, 235, 0.6) !important;
    }
</style>
""", unsafe_allow_html=True)

st.title("💰 Control Económico Familiar v6.1 Cloud")

if 'vista_nivel' not in st.session_state: st.session_state.vista_nivel = 'ANUAL'
if 'vista_anterior' not in st.session_state: st.session_state.vista_anterior = 'ANUAL'
if 'mes_seleccionado' not in st.session_state: st.session_state.mes_seleccionado = 'Ene'
if 'detalle_concepto' not in st.session_state: st.session_state.detalle_concepto = None
if 'detalle_bloque' not in st.session_state: st.session_state.detalle_bloque = None
if 'enseñar_id' not in st.session_state: st.session_state.enseñar_id = None

# ==========================================
# 🕹️ PANEL DE NAVEGACIÓN LATERAL
# ==========================================
st.sidebar.header("🕹️ Panel de Navegación")

meses_cerrados_df = pd.read_sql_query(text("SELECT anio, mes FROM meses_cerrados"), engine)
saldo_inicial_db = pd.read_sql_query(text("SELECT valor FROM configuracion WHERE clave = 'saldo_inicial_sep_2026'"), engine).iloc[0]['valor']

anio_sel = st.sidebar.selectbox("Seleccionar Año:", list(range(2026, 2036)), index=0)

st.sidebar.markdown("---")
if st.sidebar.button("📅 Vista Anual (12 Meses)", use_container_width=True):
    st.session_state.vista_nivel = 'ANUAL'
    st.rerun()

st.sidebar.markdown("---")
if st.sidebar.button("🔮 Gestionar Previsiones Base", use_container_width=True):
    st.session_state.vista_anterior = st.session_state.vista_nivel
    st.session_state.vista_nivel = 'GESTION_PREVISIONES'
    st.rerun()

st.sidebar.markdown("---")
st.sidebar.subheader("🏦 Configuración Ahorro")
nuevo_saldo_ini = st.sidebar.number_input("Saldo Inicial Ahorro (Ene 2026):", value=float(saldo_inicial_db), step=100.0)
if nuevo_saldo_ini != saldo_inicial_db:
    with engine.begin() as conn:
        conn.execute(text("UPDATE configuracion SET valor = :val WHERE clave = 'saldo_inicial_sep_2026'"), {"val": nuevo_saldo_ini})
    st.rerun()

st.sidebar.markdown("---")
st.sidebar.subheader("🛠️ Zona de Limpieza Total")

if st.sidebar.button("🧹 Borrar Reglas de IA Manuales"):
    with engine.begin() as conn:
        conn.execute(text("DELETE FROM reglas_categorias"))
        for pat, blq, cpt, imp in REGLAS_PREDETERMINADAS:
            conn.execute(text("INSERT INTO reglas_categorias (patron, bloque, concepto, importe_exacto) VALUES (:pat, :blq, :cpt, :imp)"), {"pat": pat, "blq": blq, "cpt": cpt, "imp": imp})
    st.sidebar.success("Cerebro reseteado.")
    time.sleep(1.5); st.rerun()

if st.sidebar.button("🧨 Borrar SOLO Movimientos de Banco"):
    with engine.begin() as conn:
        conn.execute(text("DELETE FROM movimientos WHERE es_real = 1"))
        conn.execute(text("DELETE FROM meses_cerrados"))
    st.sidebar.success("Banco borrado. Presupuesto intacto.")
    time.sleep(1.5); st.rerun()
    
if st.sidebar.button("🔁 Restaurar Presupuesto Base"):
    restaurar_presupuesto_base()
    st.sidebar.success("¡Presupuesto restaurado en todos los años!")
    time.sleep(1.5); st.rerun()

st.sidebar.markdown("---")
st.sidebar.subheader("🧪 MODO DESARROLLADOR")
if st.sidebar.button("🔴 Ejecutar Test Automático (Simular Mes)", type="primary", use_container_width=True):
    simular_mes_test(anio_sel, st.session_state.mes_seleccionado)
    st.sidebar.success(f"¡Se han inyectado ~30 tickets en {st.session_state.mes_seleccionado} {anio_sel}!")
    time.sleep(1.5)
    st.rerun()

# ==========================================
# VISTA: GESTIÓN DE PREVISIONES BASE
# ==========================================
if st.session_state.vista_nivel == 'GESTION_PREVISIONES':
    st.button("⬅️ Volver", type="primary", on_click=lambda: st.session_state.update(vista_nivel=st.session_state.vista_anterior))
    st.subheader(f"🔮 Gestión Visual de Previsiones - Mes de Referencia: {st.session_state.mes_seleccionado} {anio_sel}")
    st.caption("Estructurado por bloques visuales. Haz clic en un concepto para editar su importe o proyectarlo en el tiempo.")
    
    df_prev = pd.read_sql_query(text("SELECT * FROM movimientos WHERE es_real = 0 AND anio = :anio"), engine, params={"anio": anio_sel})
    
    df_prev_ing = df_prev[(df_prev['mes'] == st.session_state.mes_seleccionado) & (df_prev['tipo'] == 'INGRESO')]
    st.markdown('<div class="block-header-ingreso">💵 BLOQUE: INGRESOS (Previsiones)</div>', unsafe_allow_html=True)
    if not df_prev_ing.empty:
        for _, r in df_prev_ing.iterrows():
            with st.expander(f"🟢 **{r['concepto']}** | Importe actual en {st.session_state.mes_seleccionado}: **{r['importe']:,.2f} €**"):
                with st.form(f"form_edit_prev_{r['id']}"):
                    n_imp = st.number_input("Nuevo importe previsto (€):", value=float(r['importe']), step=10.0)
                    modo_alcance = st.radio("¿A qué meses aplicar este cambio?", [
                        "A) Solo a este mes",
                        "B) Desde este mes en adelante (Hasta Dic)",
                        "C) A todos los 12 meses del año"
                    ])
                    c_act1, c_act2 = st.columns([3, 1])
                    sub_btn = c_act1.form_submit_button("💾 Guardar Cambios")
                    del_btn = c_act2.form_submit_button("🗑️ Eliminar Previsión")
                    
                    if sub_btn:
                        with engine.begin() as conn:
                            if "Solo" in modo_alcance:
                                conn.execute(text("UPDATE movimientos SET importe = :imp WHERE id = :id"), {"imp": n_imp, "id": r['id']})
                            elif "Desde" in modo_alcance:
                                idx_curr = MESES_ORDEN.index(st.session_state.mes_seleccionado)
                                meses_futuros = MESES_ORDEN[idx_curr:]
                                for m in meses_futuros:
                                    conn.execute(text("UPDATE movimientos SET importe = :imp WHERE es_real = 0 AND anio = :anio AND mes = :mes AND concepto = :cpt"), {"imp": n_imp, "anio": anio_sel, "mes": m, "cpt": r['concepto']})
                            else:
                                conn.execute(text("UPDATE movimientos SET importe = :imp WHERE es_real = 0 AND anio = :anio AND concepto = :cpt"), {"imp": n_imp, "anio": anio_sel, "cpt": r['concepto']})
                        st.success("¡Previsión actualizada!"); time.sleep(1); st.rerun()
                    
                    if del_btn:
                        with engine.begin() as conn:
                            conn.execute(text("DELETE FROM movimientos WHERE id = :id"), {"id": r['id']})
                        st.success("Previsión eliminada."); time.sleep(1); st.rerun()
    else: st.info("No hay previsiones de ingresos para este mes.")

    df_prev_gas = df_prev[(df_prev['mes'] == st.session_state.mes_seleccionado) & (df_prev['tipo'] == 'GASTO')]
    for blk in BLOQUES_ORDEN:
        df_b = df_prev_gas[df_prev_gas['bloque'] == blk]
        if not df_b.empty:
            st.markdown(f'<div class="block-header-gasto">📂 BLOQUE: {blk}</div>', unsafe_allow_html=True)
            for _, r in df_b.iterrows():
                with st.expander(f"🟠 **{r['concepto']}** | Importe actual en {st.session_state.mes_seleccionado}: **{r['importe']:,.2f} €**"):
                    with st.form(f"form_edit_prev_{r['id']}"):
                        n_imp = st.number_input("Nuevo importe previsto (€):", value=float(r['importe']), step=10.0)
                        modo_alcance = st.radio("¿A qué meses aplicar este cambio?", [
                            "A) Solo a este mes",
                            "B) Desde este mes en adelante (Hasta Dic)",
                            "C) A todos los 12 meses del año"
                        ], key=f"rad_{r['id']}")
                        c_act1, c_act2 = st.columns([3, 1])
                        sub_btn = c_act1.form_submit_button("💾 Guardar Cambios")
                        del_btn = c_act2.form_submit_button("🗑️ Eliminar Previsión")
                        
                        if sub_btn:
                            with engine.begin() as conn:
                                if "Solo" in modo_alcance:
                                    conn.execute(text("UPDATE movimientos SET importe = :imp WHERE id = :id"), {"imp": n_imp, "id": r['id']})
                                elif "Desde" in modo_alcance:
                                    idx_curr = MESES_ORDEN.index(st.session_state.mes_seleccionado)
                                    meses_futuros = MESES_ORDEN[idx_curr:]
                                    for m in meses_futuros:
                                        conn.execute(text("UPDATE movimientos SET importe = :imp WHERE es_real = 0 AND anio = :anio AND mes = :mes AND concepto = :cpt"), {"imp": n_imp, "anio": anio_sel, "mes": m, "cpt": r['concepto']})
                                else:
                                    conn.execute(text("UPDATE movimientos SET importe = :imp WHERE es_real = 0 AND anio = :anio AND concepto = :cpt"), {"imp": n_imp, "anio": anio_sel, "cpt": r['concepto']})
                            st.success("¡Previsión actualizada!"); time.sleep(1); st.rerun()
                        
                        if del_btn:
                            with engine.begin() as conn:
                                conn.execute(text("DELETE FROM movimientos WHERE id = :id"), {"id": r['id']})
                            st.success("Previsión eliminada."); time.sleep(1); st.rerun()

# ==========================================
# NIVEL 1: VISTA ANUAL
# ==========================================
elif st.session_state.vista_nivel == 'ANUAL':
    
    st.markdown(f"#### 📅 Selección de Mes de Trabajo (Año {anio_sel}):")
    cols_meses = st.columns(12)
    for idx, m in enumerate(MESES_ORDEN):
        es_cerrado = not meses_cerrados_df[(meses_cerrados_df['anio'] == anio_sel) & (meses_cerrados_df['mes'] == m)].empty
        es_activo = (st.session_state.mes_seleccionado == m)
        
        lbl = f"📌 {m.upper()}" if es_activo else (f"🟢 {m}" if es_cerrado else f"{m}")
        tipo_btn = "primary" if es_activo else "secondary"
            
        if cols_meses[idx].button(lbl, key=f"btn_m_anual_top_{m}", type=tipo_btn, use_container_width=True):
            st.session_state.mes_seleccionado = m
            st.session_state.vista_nivel = 'MENSUAL'
            st.rerun()

    st.caption(f"👉 **Mes activo seleccionado:** `{st.session_state.mes_seleccionado}` (resaltado en Azul Cobalto). Haz clic sobre él para entrar en su desglose.")
    st.markdown("---")
    
    df_ahorro_anual, saldo_final_ahorro = obtener_metricas_ahorro_completa(anio_sel, nuevo_saldo_ini)
    
    st.markdown(f'<div class="block-header-ahorro">🏦 CUENTA BANCARIA DE AHORRO – {anio_sel}</div>', unsafe_allow_html=True)
    st.metric(f"🐷 Saldo Acumulado Total en la Hucha (Dic {anio_sel})", f"{saldo_final_ahorro:,.2f} €")
    
    pivot_ahorro = df_ahorro_anual.set_index("Mes").transpose()
    st.dataframe(pivot_ahorro.style.format("{:,.2f} €"), use_container_width=True)
    
    with st.expander("🔻 Registrar Movimiento Extraordinario en la Hucha (Aportación / Retiro)", expanded=False):
        with st.form("form_ahorro_anual"):
            c1_an, c2_an, c3_an, c4_an = st.columns([2, 2, 4, 2])
            m_ret_anual = c1_an.selectbox("Mes:", MESES_ORDEN, index=MESES_ORDEN.index(st.session_state.mes_seleccionado))
            tipo_ahorro_an = c2_an.selectbox("Tipo:", ["Retiro / Gasto Extra (-)", "Aportación / Ingreso Extra (+)"])
            c_ahorro_an = c3_an.text_input("Motivo (Ej: Reparación coche, Mueble):")
            i_ahorro_an = c4_an.number_input("Importe (€):", min_value=0.0, step=10.0)
            f_ahorro_an = st.date_input("Fecha del movimiento:")
            
            if st.form_submit_button("💾 Guardar en la Hucha") and c_ahorro_an and i_ahorro_an > 0:
                imp_final = -i_ahorro_an if "Retiro" in tipo_ahorro_an else i_ahorro_an
                with engine.begin() as conn:
                    conn.execute(text("INSERT INTO retiros_ahorro (anio, mes, concepto, importe, fecha) VALUES (:a, :m, :c, :i, :f)"), {"a": anio_sel, "m": m_ret_anual, "c": c_ahorro_an, "i": imp_final, "f": str(f_ahorro_an)})
                st.success(f"Movimiento registrado en la Hucha ({m_ret_anual} {anio_sel})")
                time.sleep(1); st.rerun()

    df_retiros_anual = pd.read_sql_query(text("SELECT * FROM retiros_ahorro WHERE anio = :anio ORDER BY id ASC"), engine, params={"anio": anio_sel})
    
    if not df_retiros_anual.empty:
        with st.expander("🔍 Ver y Gestionar Movimientos Registrados en la Hucha", expanded=False):
            for _, r_ret in df_retiros_anual.iterrows():
                f_ret = r_ret['fecha'] if ('fecha' in r_ret and pd.notna(r_ret['fecha']) and str(r_ret['fecha']) != "None") else "Sin fecha"
                signo_str = "💸 Retiro" if r_ret['importe'] < 0 else "🟢 Aportación"
                c_r1, c_r2, c_r3, c_r4 = st.columns([2, 4, 3, 1])
                c_r1.write(f"📅 **{r_ret['mes']}** ({f_ret})")
                c_r2.write(f"Motivo: **{r_ret['concepto']}**")
                c_r3.write(f"{signo_str}: **{abs(r_ret['importe']):,.2f} €**")
                if c_r4.button("❌", key=f"del_ret_anual_{r_ret['id']}"):
                    with engine.begin() as conn:
                        conn.execute(text("DELETE FROM retiros_ahorro WHERE id = :id"), {"id": r_ret['id']})
                    st.rerun()
    
    st.markdown("---")
    
    st.markdown(f"### 📊 Resumen Cuenta Operativa – {anio_sel}")
    
    df_mov = pd.read_sql_query(text("SELECT * FROM movimientos WHERE anio = :anio"), engine, params={"anio": anio_sel})
    
    df_mov_limpio = limpiar_duplicados_df(df_mov)
    
    ing_tot = df_mov_limpio[df_mov_limpio['tipo'] == 'INGRESO']['importe'].sum()
    gas_tot = df_mov_limpio[df_mov_limpio['tipo'] == 'GASTO']['importe'].sum()
    
    m1, m2, m3 = st.columns(3)
    m1.metric("Ingresos Anuales Cuenta Corriente", f"{ing_tot:,.2f} €")
    m2.metric("Gastos Ordinarios Cuenta Corriente", f"{gas_tot:,.2f} €")
    m3.metric("Sobrante Operativo Neto", f"{(ing_tot - gas_tot):,.2f} €")

    df_ingresos = df_mov_limpio[df_mov_limpio['tipo'] == 'INGRESO']
    if not df_ingresos.empty:
        st.markdown(f'<div class="block-header-ingreso">💵 BLOQUE: INGRESOS (Brutos)</div>', unsafe_allow_html=True)
        pivot_i = pd.pivot_table(df_ingresos, values='importe', index='concepto', columns='mes', aggfunc='sum', fill_value=0)
        pivot_i = pivot_i[[m for m in MESES_ORDEN if m in pivot_i.columns]]
        pivot_i['TOTAL ANUAL'] = pivot_i.sum(axis=1)
        st.dataframe(pivot_i.style.format("{:,.2f} €"), use_container_width=True)

    df_gastos = df_mov_limpio[df_mov_limpio['tipo'] == 'GASTO']
    for blk in BLOQUES_ORDEN:
        df_b = df_gastos[df_gastos['bloque'] == blk]
        if not df_b.empty:
            st.markdown(f'<div class="block-header-gasto">📂 BLOQUE: {blk}</div>', unsafe_allow_html=True)
            pivot_b = pd.pivot_table(df_b, values='importe', index='concepto', columns='mes', aggfunc='sum', fill_value=0)
            pivot_b = pivot_b[[m for m in MESES_ORDEN if m in pivot_b.columns]]
            pivot_b['TOTAL ANUAL'] = pivot_b.sum(axis=1)
            st.dataframe(pivot_b.style.format("{:,.2f} €"), use_container_width=True)

    st.markdown("---")
    st.markdown("### 🔍 Lupa de Detalles (Descubre qué tickets hay detrás de cada mes)")
    st.caption("Usa esta lupa para ver los gastos reales exactos que componen los números de las tablas de arriba.")
    
    col_lupa1, col_lupa2 = st.columns(2)
    lupa_mes = col_lupa1.selectbox("1. Selecciona el Mes a investigar:", MESES_ORDEN, index=MESES_ORDEN.index(st.session_state.mes_seleccionado))
    
    df_reales_mes = df_mov[(df_mov['mes'] == lupa_mes) & (df_mov['es_real'] == 1)]
    
    if not df_reales_mes.empty:
        lupa_concepto = col_lupa2.selectbox("2. Selecciona el Concepto:", sorted(df_reales_mes['concepto'].unique()))
        df_lupa_show = df_reales_mes[df_reales_mes['concepto'] == lupa_concepto].sort_values(by='fecha_exacta', ascending=False)
        
        st.markdown(f"**Tickets reales encontrados para {lupa_concepto} en {lupa_mes} ({len(df_lupa_show)} movimientos):**")
        for _, row in df_lupa_show.iterrows():
            f_str = row['fecha_exacta'] if pd.notna(row['fecha_exacta']) else "Sin fecha"
            desc = row['descripcion_original'] if pd.notna(row['descripcion_original']) and str(row['descripcion_original']).lower() != "nan" else row['concepto']
            st.write(f"- 📅 {f_str} | _{desc}_ | **{row['importe']:,.2f} €**")
    else:
        col_lupa2.info(f"No hay tickets reales cargados del banco en {lupa_mes} todavía.")

    st.markdown("---")
    df_pendientes = df_mov[(df_mov['bloque'] == 'PENDIENTE') & (df_mov['tipo'] == 'GASTO')]
    if not df_pendientes.empty:
        st.markdown('<div class="block-header-pendientes">❓ PENDIENTES DE CATEGORIZAR (TODO EL AÑO)</div>', unsafe_allow_html=True)
        for _, row in df_pendientes.iterrows():
            c1, c2, c3, c4 = st.columns([2, 5, 2, 2])
            f_str = row['fecha_exacta'] if pd.notna(row['fecha_exacta']) else "Sin fecha"
            desc_orig = row['descripcion_original'] if pd.notna(row['descripcion_original']) else row['concepto']
            c1.write(f"📅 {f_str} **({row['mes']})**")
            c2.write(f"_{desc_orig}_")
            c3.write(f"**{row['importe']:,.2f} €**")
            if c4.button("🧠 Categorizar", key=f"cat_anual_{row['id']}"):
                st.session_state.enseñar_id = row['id']
                st.session_state.vista_anterior = 'ANUAL'
                st.session_state.vista_nivel = 'ENSENAR_REGLA'
                st.rerun()

# ==========================================
# NIVEL 2: VISTA DETALLADA DEL MES
# ==========================================
elif st.session_state.vista_nivel == 'MENSUAL':
    
    cols_nav = st.columns(12)
    for idx, m_nav in enumerate(MESES_ORDEN):
        is_curr = (m_nav == st.session_state.mes_seleccionado)
        lbl_nav = f"📌 {m_nav.upper()}" if is_curr else m_nav
        tipo_nav = "primary" if is_curr else "secondary"
        if cols_nav[idx].button(lbl_nav, key=f"nav_top_mensual_{m_nav}", type=tipo_nav, use_container_width=True):
            st.session_state.mes_seleccionado = m_nav
            st.rerun()
            
    es_cerrado = not pd.read_sql_query(text("SELECT 1 FROM meses_cerrados WHERE anio = :a AND mes = :m"), engine, params={"a": anio_sel, "m": st.session_state.mes_seleccionado}).empty
    reglas_df = pd.read_sql_query(text("SELECT patron, bloque, concepto, COALESCE(importe_exacto, 0.0) as importe_exacto FROM reglas_categorias"), engine)
    
    tag_estado = '🟢 MES CONSOLIDADO' if es_cerrado else '🟠 PREVISIÓN FUTURA'
    nombre_mes = MESES_NOMBRES.get(st.session_state.mes_seleccionado, st.session_state.mes_seleccionado).upper()
    
    st.info(f"📅 **GESTIÓN DE: {nombre_mes} {anio_sel} | {tag_estado}**", icon="ℹ️")
    
    col_back, col_bank = st.columns([2, 3])
    if col_back.button("⬅️ Volver a Vista Anual", type="primary"):
        st.session_state.vista_nivel = 'ANUAL'
        st.rerun()
        
    with col_bank.expander("📥 Importar Extracto Bancario", expanded=False):
        uploaded_bank = st.file_uploader("Subir Excel/CSV:", type=["xlsx", "xls", "csv"])
        if uploaded_bank:
            try:
                if uploaded_bank.name.endswith(".csv"): df_banco = pd.read_csv(uploaded_bank)
                else:
                    df_raw = pd.read_excel(uploaded_bank, header=None)
                    header_row = 0
                    for r_i in range(min(20, len(df_raw))):
                        row_vals = [str(x).upper() for x in df_raw.iloc[r_i].values if pd.notna(x)]
                        if any("IMPORTE" in v or "CANTIDAD" in v for v in row_vals):
                            header_row = r_i
                            break
                    df_banco = pd.read_excel(uploaded_bank, header=header_row)
                
                cols_lower = [str(c).lower().strip() for c in df_banco.columns]
                df_banco.columns = cols_lower
                col_desc = next((c for c in cols_lower if 'descripci' in c or 'concepto' in c or 'detalle' in c), None)
                col_imp = next((c for c in cols_lower if 'importe' in c or 'cantidad' in c), None)
                col_fec = next((c for c in cols_lower if 'fecha' in c or 'f. valor' in c or 'f.valor' in c), None)

                if st.button("🚀 Importar y Conciliar", type="primary") and col_imp and col_desc and col_fec:
                    movs_existentes = pd.read_sql_query(text("SELECT anio, mes, fecha_exacta, importe, descripcion_original FROM movimientos WHERE es_real = 1"), engine)
                    registros = []
                    
                    for _, b_row in df_banco.iterrows():
                        desc_orig = str(b_row[col_desc]) if pd.notna(b_row[col_desc]) else "Gasto"
                        raw_fec = b_row[col_fec]
                        
                        raw_val = str(b_row[col_imp]).replace('€', '').strip()
                        if ',' in raw_val: raw_val = raw_val.replace('.', '').replace(',', '.')
                        try: importe_val = float(raw_val)
                        except: continue
                                
                        if importe_val != 0:
                            a_dest, m_dest, f_str = anio_sel, st.session_state.mes_seleccionado, None
                            
                            if pd.notna(raw_fec):
                                f_dt = None
                                if isinstance(raw_fec, (datetime, pd.Timestamp)): f_dt = pd.to_datetime(raw_fec)
                                else:
                                    f_str_temp = str(raw_fec).strip().split()[0]
                                    if "/" in f_str_temp:
                                        try: f_dt = pd.to_datetime(f_str_temp, format="%d/%m/%Y")
                                        except: f_dt = pd.to_datetime(f_str_temp, dayfirst=True, errors='coerce')
                                    elif "-" in f_str_temp:
                                        try: f_dt = pd.to_datetime(f_str_temp, format="%Y-%m-%d")
                                        except: f_dt = pd.to_datetime(f_str_temp, dayfirst=True, errors='coerce')
                                    else:
                                        f_dt = pd.to_datetime(f_str_temp, dayfirst=True, errors='coerce')
                                        
                                if f_dt and pd.notna(f_dt):
                                    a_dest, m_dest, f_str = f_dt.year, MESES_MAPPING_NUM.get(f_dt.month, m_dest), f_dt.strftime("%Y-%m-%d")
                                    
                            imp_abs = abs(importe_val)
                            es_dup = False
                            
                            if not movs_existentes.empty and f_str:
                                dup_m = movs_existentes[(movs_existentes['anio'] == a_dest) & (movs_existentes['mes'] == m_dest) & (movs_existentes['fecha_exacta'] == f_str) & (abs(movs_existentes['importe'] - imp_abs) < 0.01) & (movs_existentes['descripcion_original'] == desc_orig)]
                                if not dup_m.empty: es_dup = True
                                    
                            if not es_dup:
                                tipo_val = "INGRESO" if importe_val > 0 else "GASTO"
                                bloque_val, concepto_limpio = "PENDIENTE", desc_orig
                                
                                matched = False
                                for _, r_rule in reglas_df.iterrows():
                                    patron_ok = str(r_rule['patron']).upper() in desc_orig.upper()
                                    imp_rule = float(r_rule['importe_exacto'] or 0.0)
                                    imp_ok = True if imp_rule == 0.0 else (abs(imp_rule - imp_abs) < 0.01)
                                    
                                    if patron_ok and imp_ok:
                                        bloque_val, concepto_limpio = r_rule['bloque'], r_rule['concepto']
                                        matched = True
                                        break
                                
                                if not matched:
                                    b_ia, c_ia = auto_clasificar(desc_orig)
                                    if b_ia and c_ia:
                                        bloque_val, concepto_limpio = b_ia, c_ia
                                
                                if tipo_val == "INGRESO" and not matched and not b_ia:
                                    bloque_val = "INGRESOS"
                                        
                                registros.append({"anio": a_dest, "mes": m_dest, "bloque": bloque_val, "concepto": concepto_limpio, "tipo": tipo_val, "importe": imp_abs, "es_real": 1, "fecha_exacta": f_str, "descripcion_original": desc_orig})
                                
                    if registros:
                        with engine.begin() as conn:
                            conn.execute(
                                text("INSERT INTO movimientos (anio, mes, bloque, concepto, tipo, importe, es_real, fecha_exacta, descripcion_original) VALUES (:anio, :mes, :bloque, :concepto, :tipo, :importe, :es_real, :fecha_exacta, :descripcion_original)"),
                                registros
                            )
                            conn.execute(
                                text("INSERT INTO meses_cerrados (anio, mes) VALUES (:anio, :mes) ON CONFLICT (anio, mes) DO NOTHING"),
                                {"anio": anio_sel, "mes": st.session_state.mes_seleccionado}
                            )
                        st.success(f"¡{len(registros)} registros guardados!")
                    else: st.warning("No se importó nada. Todo estaba duplicado.")
                    time.sleep(2)
                    st.rerun()
            except Exception as e: st.error(str(e))
                
    df_mes = pd.read_sql_query(text("SELECT * FROM movimientos WHERE anio = :a AND mes = :m"), engine, params={"a": anio_sel, "m": st.session_state.mes_seleccionado})
    df_retiros_mes = pd.read_sql_query(text("SELECT * FROM retiros_ahorro WHERE anio = :a AND mes = :m"), engine, params={"a": anio_sel, "m": st.session_state.mes_seleccionado})
    
    df_mes_limpio = limpiar_duplicados_df(df_mes)
    
    ing_m = df_mes_limpio[df_mes_limpio['tipo'] == 'INGRESO']['importe'].sum()
    gas_m = df_mes_limpio[df_mes_limpio['tipo'] == 'GASTO']['importe'].sum()
    sobrante_mes = ing_m - gas_m

    df_ahorro_a, _ = obtener_metricas_ahorro_completa(anio_sel, nuevo_saldo_ini)
    saldo_mes_hucha = df_ahorro_a[df_ahorro_a['Mes'] == st.session_state.mes_seleccionado]['Saldo Acumulado Hucha'].values[0]
    
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Ingresos Mes", f"{ing_m:,.2f} €")
    c2.metric("Gastos Mes", f"{gas_m:,.2f} €")
    c3.metric("Sobrante Operativo", f"{sobrante_mes:,.2f} €")
    c4.metric("🐷 Saldo Cuenta Ahorro", f"{saldo_mes_hucha:,.2f} €")
    
    st.markdown("---")
    
    st.markdown('<div class="block-header-ahorro">🐷 EXTRACCIONES Y GASTOS EXTRAORDINARIOS DE LA CUENTA DE AHORRO</div>', unsafe_allow_html=True)
    if not df_retiros_mes.empty:
        for _, r in df_retiros_mes.iterrows():
            f_r_str = r['fecha'] if ('fecha' in r and pd.notna(r['fecha']) and str(r['fecha']) != "None") else "Sin fecha"
            signo_str = "💸 Retiro" if r['importe'] < 0 or "Retiro" in str(r.get('concepto', '')) else "🟢 Aportación"
            ca1, ca2, ca3, ca4 = st.columns([2, 5, 2, 1])
            ca1.write(f"📅 **{f_r_str}**")
            ca2.write(f"Motivo: **{r['concepto']}**")
            ca3.write(f"{signo_str}: **{abs(r['importe']):,.2f} €**")
            if ca4.button("❌", key=f"del_ahorro_{r['id']}"):
                with engine.begin() as conn:
                    conn.execute(text("DELETE FROM retiros_ahorro WHERE id = :id"), {"id": r['id']})
                st.rerun()
                
    with st.expander("🔻 Registrar un Retiro o Gasto Extraordinario de la Hucha"):
        st.info(f"💡 **Saldo disponible actualmente en la Hucha ({st.session_state.mes_seleccionado} {anio_sel}): {saldo_mes_hucha:,.2f} €**")
        with st.form("form_ahorro"):
            c_ahorro = st.text_input("Motivo del retiro (Ej: Reparación coche, Mueble):")
            i_ahorro = st.number_input("Importe a retirar (€):", min_value=0.0)
            f_ahorro = st.date_input("Fecha del gasto extraordinario:")
            if st.form_submit_button("Guardar Retiro") and c_ahorro and i_ahorro > 0:
                with engine.begin() as conn:
                    conn.execute(text("INSERT INTO retiros_ahorro (anio, mes, concepto, importe, fecha) VALUES (:a, :m, :c, :i, :f)"), {"a": anio_sel, "m": st.session_state.mes_seleccionado, "c": c_ahorro, "i": -i_ahorro, "f": str(f_ahorro)})
                st.rerun()
    st.markdown("---")
    
    df_ing = df_mes[df_mes['tipo'] == 'INGRESO']
    if not df_ing.empty:
        st.markdown(f'<div class="block-header-ingreso">💵 BLOQUE: INGRESOS</div>', unsafe_allow_html=True)
        for concepto in df_ing['concepto'].unique():
            df_c = df_ing[df_ing['concepto'] == concepto]
            has_real = (df_c['es_real'].astype(int) == 1).any()
            df_mostrar = df_c[df_c['es_real'].astype(int) == 1] if has_real else df_c
            total_concepto = df_mostrar['importe'].sum()
            num_movs = len(df_mostrar)
            tag = "🟢 REAL" if has_real else "🟠 PREVISIÓN"
            df_mostrar = df_mostrar.sort_values(by='fecha_exacta', ascending=False)
            
            with st.expander(f"{tag} | **{concepto}** | {total_concepto:,.2f} € | *({num_movs} movimientos)*"):
                for _, row in df_mostrar.iterrows():
                    f_str = row['fecha_exacta'] if pd.notna(row['fecha_exacta']) else "Sin fecha"
                    desc = row['descripcion_original'] if pd.notna(row['descripcion_original']) and str(row['descripcion_original']).lower() != "nan" else row['concepto']
                    
                    c_fec, c_desc, c_imp, c_act = st.columns([2, 5, 2, 2])
                    c_fec.write(f"📅 {f_str}"); c_desc.write(f"_{desc}_"); c_imp.write(f"**{row['importe']:,.2f} €**")
                    if c_act.button("✏️ Cambiar", key=f"edit_mov_{row['id']}"):
                        st.session_state.enseñar_id = row['id']
                        st.session_state.vista_anterior = 'MENSUAL'
                        st.session_state.vista_nivel = 'ENSENAR_REGLA'
                        st.rerun()

    for blk in BLOQUES_ORDEN:
        df_b = df_mes[(df_mes['bloque'] == blk) & (df_mes['tipo'] == 'GASTO')]
        if not df_b.empty:
            st.markdown(f'<div class="block-header-gasto">📂 BLOQUE: {blk}</div>', unsafe_allow_html=True)
            
            if blk == "COMIDA":
                has_real = (df_b['es_real'].astype(int) == 1).any()
                df_mostrar = df_b[df_b['es_real'].astype(int) == 1] if has_real else df_b
                total_concepto = df_mostrar['importe'].sum()
                num_movs = len(df_mostrar)
                tag = "🟢 REAL" if has_real else "🟠 PREVISIÓN"
                df_mostrar = df_mostrar.sort_values(by='fecha_exacta', ascending=False)
                
                with st.expander(f"{tag} | **Alimentación (Total del mes)** | {total_concepto:,.2f} € | *({num_movs} movimientos)*"):
                    for _, row in df_mostrar.iterrows():
                        f_str = row['fecha_exacta'] if pd.notna(row['fecha_exacta']) else "Sin fecha"
                        desc = row['descripcion_original'] if pd.notna(row['descripcion_original']) and str(row['descripcion_original']).lower() != "nan" else row['concepto']
                        
                        c_fec, c_desc, c_imp, c_act = st.columns([2, 5, 2, 2])
                        c_fec.write(f"📅 {f_str}"); c_desc.write(f"_{desc}_"); c_imp.write(f"**{row['importe']:,.2f} €**")
                        if c_act.button("✏️ Cambiar", key=f"edit_mov_{row['id']}"):
                            st.session_state.enseñar_id = row['id']
                            st.session_state.vista_anterior = 'MENSUAL'
                            st.session_state.vista_nivel = 'ENSENAR_REGLA'
                            st.rerun()
            else:
                for concepto in df_b['concepto'].unique():
                    df_c = df_b[df_b['concepto'] == concepto]
                    has_real = (df_c['es_real'].astype(int) == 1).any()
                    df_mostrar = df_c[df_c['es_real'].astype(int) == 1] if has_real else df_c
                    total_concepto = df_mostrar['importe'].sum()
                    num_movs = len(df_mostrar)
                    tag = "🟢 REAL" if has_real else "🟠 PREVISIÓN"
                    df_mostrar = df_mostrar.sort_values(by='fecha_exacta', ascending=False)
                    
                    with st.expander(f"{tag} | **{concepto}** | {total_concepto:,.2f} € | *({num_movs} movimientos)*"):
                        for _, row in df_mostrar.iterrows():
                            f_str = row['fecha_exacta'] if pd.notna(row['fecha_exacta']) else "Sin fecha"
                            desc = row['descripcion_original'] if pd.notna(row['descripcion_original']) and str(row['descripcion_original']).lower() != "nan" else row['concepto']
                            
                            c_fec, c_desc, c_imp, c_act = st.columns([2, 5, 2, 2])
                            c_fec.write(f"📅 {f_str}"); c_desc.write(f"_{desc}_"); c_imp.write(f"**{row['importe']:,.2f} €**")
                            if c_act.button("✏️ Cambiar", key=f"edit_mov_{row['id']}"):
                                st.session_state.enseñar_id = row['id']
                                st.session_state.vista_anterior = 'MENSUAL'
                                st.session_state.vista_nivel = 'ENSENAR_REGLA'
                                st.rerun()
                        st.markdown("---")
                        if st.button(f"🔍 Opciones Avanzadas (Añadir Tickets a {concepto})", key=f"btn_det_{blk}_{concepto}"):
                            st.session_state.detalle_concepto = concepto
                            st.session_state.detalle_bloque = blk
                            st.session_state.vista_nivel = 'DETALLE_AGRUPADO'
                            st.rerun()

    df_pendientes = df_mes[(df_mes['bloque'] == 'PENDIENTE')]
    if not df_pendientes.empty:
        st.markdown(f'<div class="block-header-pendientes">❓ PENDIENTES DE CATEGORIZAR ESTE MES</div>', unsafe_allow_html=True)
        for _, row in df_pendientes.iterrows():
            c1, c2, c3, c4 = st.columns([2, 5, 2, 2])
            f_str = row['fecha_exacta'] if pd.notna(row['fecha_exacta']) else "Sin fecha"
            desc_orig = row['descripcion_original'] if pd.notna(row['descripcion_original']) else row['concepto']
            c1.write(f"📅 {f_str}"); c2.write(f"_{desc_orig}_"); c3.write(f"**{row['importe']:,.2f} €**")
            if c4.button("🧠 Categorizar", key=f"cat_mes_{row['id']}"):
                st.session_state.enseñar_id = row['id']
                st.session_state.vista_anterior = 'MENSUAL'
                st.session_state.vista_nivel = 'ENSENAR_REGLA'
                st.rerun()

# ==========================================
# NIVEL 3: ENSEÑAR REGLA Y CORREGIR ERRORES
# ==========================================
elif st.session_state.vista_nivel == 'ENSENAR_REGLA':
    st.button("⬅️ Volver Atrás", type="primary", on_click=lambda: st.session_state.update(vista_nivel=st.session_state.vista_anterior))
    
    mov = pd.read_sql_query(text("SELECT * FROM movimientos WHERE id = :id"), engine, params={"id": st.session_state.enseñar_id}).iloc[0]
    
    desc_orig = mov['descripcion_original'] if pd.notna(mov['descripcion_original']) and str(mov['descripcion_original']).lower() != "nan" else mov['concepto']
    st.subheader(f"🧠 Categorizar / Modificar Movimiento: {desc_orig}")
    st.info(f"Importe actual guardado: **{mov['importe']:,.2f} €** | Fecha: {mov['fecha_exacta']} | Mes: **{mov['mes']} {mov['anio']}**")
    
    tipo_in = st.radio("1. Tipo de movimiento:", ["Dinero que SALE (GASTO)", "Dinero que ENTRA (INGRESO)"], index=0 if mov['tipo']=='GASTO' else 1)
    tipo_val = "GASTO" if "SALE" in tipo_in else "INGRESO"
    
    bloques_disponibles = ["INGRESOS"] + BLOQUES_ORDEN
    idx_bloque = bloques_disponibles.index(mov['bloque']) if mov['bloque'] in bloques_disponibles else (0 if tipo_val == "INGRESO" else 1)
    
    bloque_in = st.selectbox("2. Selecciona Bloque:", bloques_disponibles, index=idx_bloque)
    
    grupos_bd = pd.read_sql_query(text("SELECT DISTINCT concepto FROM movimientos WHERE bloque = :b"), engine, params={"b": bloque_in})['concepto'].tolist()
    diccionario_excel = {
        "VIVIENDA": ["Hipoteca chalet", "Hipoteca piso", "Luz gas, agua", "Placas solares", "Telf. Internet.", "Impuestos", "Comunidad"],
        "COMIDA": ["Alimentacion"],
        "COCHES": ["Cupra", "Combustible", "Numeritos", "Mantenimiento", "Seguros"],
        "NIÑOS": ["Gastos peques", "Comedor", "Extraescolares"],
        "COMPRAS": ["Amazon/Aliexpres", "Ropa", "Hogar"],
        "GASTOS PERSONALES": ["Ocio", "Psicologo", "Gimanasio", "Seguro Vida", "Abono transporte", "Salud", "Mascotas"],
        "EXTRAS": ["Cumples / Reyes", "Imprevistos", "Bizum Emitido"],
        "INGRESOS": ["Nómina Jorge", "Nómina Grego", "Transferencia", "Devolución", "Ingreso Bizum"]
    }
    for concepto_base in diccionario_excel.get(bloque_in, []):
        if concepto_base not in grupos_bd: grupos_bd.append(concepto_base)
        
    idx_grupo = grupos_bd.index(mov['concepto']) + 1 if mov['concepto'] in grupos_bd else 0
    grupo_sel = st.selectbox("3. Selecciona Grupo / Concepto:", ["➕ Crear Nuevo Grupo..."] + grupos_bd, index=idx_grupo)
    concepto_in = st.text_input("Escribe el nombre del grupo:") if grupo_sel == "➕ Crear Nuevo Grupo..." else grupo_sel
    
    nuevo_importe = st.number_input("4. Modificar Importe (€) para este mes (Ej: Paga extra, ajuste):", value=float(mov['importe']), min_value=0.0, step=10.0)
    
    st.markdown("---")
    st.markdown("#### ⚙️ Alcance de la Categorización")
    
    ambito = st.radio("¿Cómo quieres aplicar este cambio?", [
        "A) SOLO ESTE MOVIMIENTO (Modifica únicamente este registro exacto - Ideal para pagas extras)",
        "B) CREAR REGLA PARA EL FUTURO (Categorizará también comercios o transferencias similares)"
    ])
    
    condicion_regla = "SOLO_TEXTO"
    patron = ""
    if "REGLA" in ambito:
        condicion_regla = st.radio("¿Cómo debe detectar la regla los siguientes movimientos?", [
            "1) Solo por Palabra Clave (Ej: MERCADONA, IBERDROLA - Para cualquier importe)",
            f"2) Por Palabra Clave + IMPORTE EXACTO ({nuevo_importe:,.2f} €) - Ideal para transferencias periódicas específicas"
        ])
        patron = st.text_input("Palabra clave a buscar en el extracto del banco:", value=str(desc_orig).split()[0] if desc_orig else "")
    
    if st.button("💾 Guardar Cambios", type="primary"):
        if concepto_in:
            with engine.begin() as conn:
                # Actualización directa forzosa del registro seleccionado
                conn.execute(
                    text("UPDATE movimientos SET bloque = :b, concepto = :c, tipo = :t, importe = :imp WHERE id = :id"),
                    {"b": bloque_in, "c": concepto_in.strip(), "t": tipo_val, "imp": nuevo_importe, "id": mov['id']}
                )
                
                # Procesar reglas si se han seleccionado
                if "REGLA" in ambito and patron and len(patron.strip()) >= 2:
                    imp_exacto_val = float(nuevo_importe) if "EXACTO" in condicion_regla else 0.0
                    conn.execute(
                        text("INSERT INTO reglas_categorias (patron, bloque, concepto, importe_exacto) VALUES (:p, :b, :c, :i)"), 
                        {"p": patron.strip(), "b": bloque_in, "c": concepto_in.strip(), "i": imp_exacto_val}
                    )
                    
                    if imp_exacto_val > 0:
                        conn.execute(text("""
                            UPDATE movimientos 
                            SET bloque = :b, concepto = :c, tipo = :t 
                            WHERE UPPER(descripcion_original) LIKE :pat AND es_real = 1 AND abs(importe - :imp_ex) < 0.01
                        """), {"b": bloque_in, "c": concepto_in.strip(), "t": tipo_val, "pat": f"%{patron.strip().upper()}%", "imp_ex": imp_exacto_val})
                    else:
                        conn.execute(text("""
                            UPDATE movimientos 
                            SET bloque = :b, concepto = :c, tipo = :t 
                            WHERE UPPER(descripcion_original) LIKE :pat AND es_real = 1
                        """), {"b": bloque_in, "c": concepto_in.strip(), "t": tipo_val, "pat": f"%{patron.strip().upper()}%"})
            
            st.success("✅ Cambios aplicados con éxito.")
            time.sleep(0.5)
            st.session_state.vista_nivel = st.session_state.vista_anterior
            st.rerun()
        else:
            st.error("Indica un nombre de grupo válido.")

# ==========================================
# NIVEL 3: DETALLE AGRUPADO Y TICKETS
# ==========================================
elif st.session_state.vista_nivel == 'DETALLE_AGRUPADO':
    st.button("⬅️ Volver al Mes", type="primary", on_click=lambda: st.session_state.update(vista_nivel='MENSUAL'))
    
    df_movs = pd.read_sql_query(text("SELECT * FROM movimientos WHERE anio = :a AND mes = :m AND bloque = :b AND concepto = :c"), engine, params={"a": anio_sel, "m": st.session_state.mes_seleccionado, "b": st.session_state.detalle_bloque, "c": st.session_state.detalle_concepto})
    
    has_real = (df_movs['es_real'].astype(int) == 1).any()
    if has_real: df_movs = df_movs[df_movs['es_real'].astype(int) == 1]
    
    st.subheader(f"🧾 Opciones Avanzadas: {st.session_state.detalle_concepto}")
    st.caption(f"Gasto Total: **{df_movs['importe'].sum():,.2f} €**")
    st.markdown("---")
        
    mov_ids = tuple(df_movs['id'].tolist())
    if mov_ids:
        df_t = pd.read_sql_query(text("SELECT * FROM desgloses WHERE movimiento_id = :mid"), engine, params={"mid": mov_ids[0]})
        
        st.markdown("#### 📝 Añadir Tickets o Sub-Gastos Manuales")
        if not df_t.empty:
            for _, r in df_t.iterrows():
                c1, c2, c3, c4 = st.columns([3, 2, 2, 1])
                c1.write(f"🏷️ {r['subconcepto']}")
                c2.write(f"**{r['importe']:,.2f} €**")
                c3.write(r['fecha'])
                if c4.button("❌", key=f"del_t_{r['id']}"):
                    with engine.begin() as conn:
                        conn.execute(text("DELETE FROM desgloses WHERE id = :id"), {"id": r['id']})
                    st.rerun()
        
        with st.form("f_ticket"):
            s_nom = st.text_input("Detalle Factura / Ticket:")
            s_imp = st.number_input("Importe (€):", min_value=0.0)
            s_fec = st.date_input("Fecha")
            if st.form_submit_button("➕ Añadir Ticket") and s_nom and s_imp > 0:
                with engine.begin() as conn:
                    conn.execute(text("INSERT INTO desgloses (movimiento_id, subconcepto, importe, fecha) VALUES (:mid, :s, :i, :f)"), {"mid": mov_ids[0], "s": s_nom, "i": s_imp, "f": str(s_fec)})
                st.rerun()
