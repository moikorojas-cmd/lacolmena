import streamlit as st
import sqlite3
import math
from datetime import datetime, date, timedelta
import pandas as pd
import os
import smtplib
import re
import random
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.application import MIMEApplication
import urllib.parse
import streamlit.components.v1 as components
import altair as alt

try:
    from fpdf import FPDF
except ImportError:
    st.error("Falta instalar FPDF. Agrega 'fpdf' a tu archivo requirements.txt")

# =============================================================================
# 1. CONFIGURACIÓN INICIAL, BASE DE DATOS Y DISEÑO (CSS)
# =============================================================================
st.set_page_config(page_title="Banquito La Colmena", page_icon="🐝", layout="wide", initial_sidebar_state="collapsed")

# Función para decimales con PUNTO y miles con COMA (Ej: 1,234.56)
def f_m(valor):
    if valor is None: return "0.00"
    return "{:,.2f}".format(float(valor))

# Diseño Gráfico Profesional, Amplio, Mayúsculas y Footer Fijo
st.markdown("""
    <style>
    /* Ocultar barra lateral y botón de menú permanentemente */
    [data-testid="collapsedControl"] { display: none !important; }
    [data-testid="stSidebar"] { display: none !important; }
    
    /* 🛠️ FIX: FORZAR SCROLL PARA EVITAR SALTOS EN EL MENÚ */
    [data-testid="stAppViewContainer"] { overflow-y: scroll !important; }
    
    .stApp { background: linear-gradient(135deg, #fcfaf5 0%, #f0f4fd 100%); }
    .block-container { padding-top: 2rem; padding-bottom: 80px !important; max-width: 95% !important;}
    h1, h2, h3, h4, h5, h6 { color: #1e3a8a !important; font-weight: 800 !important; font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif !important; text-transform: uppercase !important; letter-spacing: 0.5px; }
    h1 { font-size: 2.4rem !important; } h2 { font-size: 1.8rem !important; } h3 { font-size: 1.5rem !important; }
    .stMetric { background-color: #ffffff; padding: 20px; border-radius: 12px; border: 1px solid #e2e8f0; box-shadow: 0 4px 6px rgba(0,0,0,0.05); }
    div[data-testid="stTabs"] button { font-size: 18px !important; font-weight: 800 !important; color: #64748b; text-transform: uppercase !important; padding: 15px 25px !important; }
    div[data-testid="stTabs"] button[aria-selected="true"] { color: #2563eb; border-bottom-color: #2563eb; }
    
    /* Menús (Radios) ESTILO TARJETAS Y CENTRADOS PARA EVITAR SALTOS */
    div[role="radiogroup"] { gap: 15px; flex-wrap: wrap; justify-content: center; }
    div[role="radiogroup"] > label { padding: 15px 25px !important; background-color: #ffffff; border: 2px solid #cbd5e1; border-radius: 12px; cursor: pointer; transition: all 0.3s ease; box-shadow: 0 4px 6px rgba(0,0,0,0.05); }
    div[role="radiogroup"] > label:hover { border-color: #2563eb; background-color: #f8fafc; transform: translateY(-3px); box-shadow: 0 6px 12px rgba(0,0,0,0.1); }
    div[role="radiogroup"] > label[data-checked="true"] { border-color: #2563eb; background-color: #eff6ff; box-shadow: 0 4px 10px rgba(37,99,235,0.2); }
    .stRadio p { font-size: 16px !important; font-weight: 800 !important; text-transform: uppercase !important; color: #1e3a8a; margin: 0; }
    
    .stButton>button { border-radius: 8px; font-weight: 700 !important; font-size: 16px !important; text-transform: uppercase !important; transition: all 0.2s ease-in-out; border: 1px solid #e2e8f0; box-shadow: 0 2px 4px rgba(0,0,0,0.05); }
    .stButton>button:hover { transform: translateY(-2px); box-shadow: 0 4px 6px rgba(0,0,0,0.1); border-color: #fbbf24; color: #b45309; }
    div[data-testid="stExpander"] { border-radius: 12px; border: 1px solid #e2e8f0; box-shadow: 0 2px 4px rgba(0,0,0,0.02); background-color: #ffffff;}
    .stAlert { border-radius: 10px; }
    .fixed-footer { position: fixed; bottom: 0; left: 0; width: 100%; background-color: #e2e8f0; color: #334155; text-align: center; padding: 12px 0; font-size: 15px; font-weight: 800; border-top: 3px solid #cbd5e1; z-index: 99999; box-shadow: 0 -2px 10px rgba(0,0,0,0.05); }
    </style>
    <div class="fixed-footer">Banquito La Colmena V 1.0 / Ing. Juan Moisés Rojas De La Torre / CIP: 273739.</div>
""", unsafe_allow_html=True)

def inicializar_db():
    with sqlite3.connect("banquito.db") as conn:
        c = conn.cursor()
        c.execute('''CREATE TABLE IF NOT EXISTS usuarios (id INTEGER PRIMARY KEY AUTOINCREMENT, nombre TEXT, usuario TEXT UNIQUE, password TEXT, rol TEXT)''')
        c.execute('''CREATE TABLE IF NOT EXISTS cuentas (id INTEGER PRIMARY KEY AUTOINCREMENT, id_usuario INTEGER, saldo REAL DEFAULT 0.0, FOREIGN KEY(id_usuario) REFERENCES usuarios(id))''')
        c.execute('''CREATE TABLE IF NOT EXISTS movimientos (id INTEGER PRIMARY KEY AUTOINCREMENT, id_usuario INTEGER, tipo TEXT, monto REAL, fecha TIMESTAMP DEFAULT CURRENT_TIMESTAMP)''')
        c.execute('''CREATE TABLE IF NOT EXISTS configuracion (clave TEXT PRIMARY KEY, valor TEXT)''')
        c.execute('''CREATE TABLE IF NOT EXISTS socios (id INTEGER PRIMARY KEY AUTOINCREMENT, dni TEXT UNIQUE NOT NULL, nombres TEXT NOT NULL, apellidos TEXT, telefono TEXT, direccion TEXT, correo TEXT, sexo TEXT, fecha_nacimiento TEXT, fecha_ingreso TEXT, es_fundador INTEGER DEFAULT 0, acciones INTEGER DEFAULT 0)''')
        c.execute('''CREATE TABLE IF NOT EXISTS prestamos (id INTEGER PRIMARY KEY AUTOINCREMENT, dni_socio TEXT, monto_original REAL, saldo_actual REAL, fecha_inicio TEXT, estado TEXT DEFAULT 'ACTIVO', accion_asociada INTEGER DEFAULT 1)''')
        c.execute('''CREATE TABLE IF NOT EXISTS tramites (id INTEGER PRIMARY KEY AUTOINCREMENT, dni_socio TEXT, tipo TEXT, detalle TEXT, estado TEXT, fecha TEXT, respuesta TEXT)''')
        c.execute('''CREATE TABLE IF NOT EXISTS comunicados (id INTEGER PRIMARY KEY AUTOINCREMENT, mensaje TEXT, fecha TEXT)''')
        c.execute('''CREATE TABLE IF NOT EXISTS asistencia (id INTEGER PRIMARY KEY AUTOINCREMENT, dni_socio TEXT, fecha_asamblea TEXT, estado TEXT)''')
        c.execute('''CREATE TABLE IF NOT EXISTS votaciones (id INTEGER PRIMARY KEY AUTOINCREMENT, pregunta TEXT, opciones TEXT, estado TEXT DEFAULT 'ABIERTA', fecha_creacion TEXT)''')
        c.execute('''CREATE TABLE IF NOT EXISTS votos (id INTEGER PRIMARY KEY AUTOINCREMENT, id_votacion INTEGER, dni_socio TEXT, opcion TEXT, peso INTEGER DEFAULT 1)''')
        
        for query in [
            '''ALTER TABLE socios ADD COLUMN fecha_nacimiento TEXT''',
            '''ALTER TABLE tramites ADD COLUMN respuesta TEXT''',
            '''ALTER TABLE prestamos ADD COLUMN conteo_minimos INTEGER DEFAULT 0''',
            '''ALTER TABLE socios ADD COLUMN password TEXT'''
        ]:
            try: c.execute(query)
            except: pass
        
        c.execute('''CREATE TABLE IF NOT EXISTS cumpleanos_pagos (id INTEGER PRIMARY KEY AUTOINCREMENT, anio INTEGER, mes INTEGER, dni_cumpleanero TEXT, dni_aportante TEXT, monto REAL, fecha_pago TEXT)''')
        c.execute('''CREATE TABLE IF NOT EXISTS solicitudes_prestamo (id INTEGER PRIMARY KEY AUTOINCREMENT, dni_socio TEXT, accion INTEGER, monto REAL, fecha TEXT, estado TEXT DEFAULT 'PENDIENTE')''')
        c.execute('''CREATE TABLE IF NOT EXISTS historial_anulaciones (id INTEGER PRIMARY KEY AUTOINCREMENT, fecha TEXT, detalle TEXT, autorizador TEXT)''')

        try:
            hoy_str = datetime.now().strftime("%Y-%m-%d")
            configs = [
                ("fecha_fundacion", hoy_str), ("monto_minimo_capital", "50.0"), ("cuota_inscripcion", "20.0"),
                ("interes_prestamo", "1.5"), ("aporte_mensual", "100.0"), ("presidente", "No asignado"),
                ("correo_presidente", ""), ("tesorero", "No asignado"), ("secretario", "No asignado"),
                ("password_presidente", "123456"), ("proxima_reunion", "2000-01-01"), ("proxima_reunion_hora", "16:00"),
                ("jugar_cumpleanos", "SI"), ("cuota_cumpleanos", "50.0"), ("tope_prestamo_activo", "SI"),
                ("tope_prestamo_monto", "3000.0"), ("amort_porcentaje_activo", "SI"), ("amort_porcentaje_valor", "2.0"),
                ("mes_limite_minimos", "9")
            ]
            for clave, valor in configs:
                c.execute("INSERT OR IGNORE INTO configuracion (clave, valor) VALUES (?, ?)", (clave, valor))

            c.execute("INSERT OR IGNORE INTO usuarios (id, nombre, usuario, password, rol) VALUES (1, 'Administrador Principal', 'admin', 'admin123', 'superadmin')")
            c.execute("INSERT OR IGNORE INTO cuentas (id_usuario, saldo) VALUES (1, 0.0)")
        except: pass
        conn.commit()

inicializar_db()

# =============================================================================
# 2. FUNCIONES NÚCLEO (DB, CORREOS, UTILIDADES)
# =============================================================================
def db_query(query, params=(), fetch=True):
    with sqlite3.connect("banquito.db") as conn:
        c = conn.cursor()
        c.execute(query, params)
        if fetch: return c.fetchall()
        conn.commit()
        return c.lastrowid

def get_config(clave, default, tipo=float):
    res = db_query("SELECT valor FROM configuracion WHERE clave=?", (clave,))
    return tipo(res[0][0]) if res else tipo(default)

# -- FUNCIÓN MAESTRA DE CORREOS --
def enviar_correo_generico(destinatario, asunto, cuerpo, pdf_bytes=None, pdf_nombre=None):
    if not destinatario or str(destinatario).strip() == "":
        return False, "ℹ️ Socio sin correo registrado."
    try:
        REMITENTE = "lacolmenabanco@gmail.com"
        PASSWORD = "fvux bnfk qbzv brad"
        msg = MIMEMultipart()
        msg['Subject'] = asunto
        msg['From'] = f"Banquito La Colmena <{REMITENTE}>"
        msg['To'] = destinatario
        msg.attach(MIMEText(cuerpo, 'plain', 'utf-8'))
        
        if pdf_bytes and pdf_nombre:
            adj = MIMEApplication(pdf_bytes, _subtype="pdf")
            adj.add_header('Content-Disposition', 'attachment', filename=pdf_nombre)
            msg.attach(adj)
            
        server = smtplib.SMTP('smtp.gmail.com', 587)
        server.starttls()
        server.login(REMITENTE, PASSWORD)
        server.send_message(msg)
        server.quit()
        return True, "✅ Correo enviado con éxito."
    except Exception as e:
        return False, f"⚠️ Fallo el envío de correo: {e}"

def enviar_alerta_correo(usuario_intruso):
    correo_presi = get_config("correo_presidente", "", str)
    st.toast(f"📧 ALERTA ENVIADA AL CORREO DEL PRESIDENTE: Intento de acceso a la bóveda.", icon="🚨")
    if correo_presi:
        cuerpo = f"🚨 ALERTA DE SEGURIDAD 🚨\n\nEl usuario '{usuario_intruso}' acaba de intentar acceder a la bóveda del sistema fuera de la fecha agendada.\n\nFecha y Hora del intento: {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}"
        enviar_correo_generico(correo_presi, "🚨 ALERTA DE SEGURIDAD - Banquito La Colmena", cuerpo)

def format_fecha(fecha_str):
    if not fecha_str: return ""
    try:
        if len(fecha_str) > 10:
            return datetime.strptime(fecha_str, "%Y-%m-%d %H:%M:%S").strftime("%d/%m/%Y %H:%M:%S")
        else:
            return datetime.strptime(fecha_str[:10], "%Y-%m-%d").strftime("%d/%m/%Y")
    except: return fecha_str

def format_movimiento(texto):
    if not texto: return ""
    texto_out = str(texto)
    numeros = set(re.findall(r'\b\d+\b', texto_out))
    for d in numeros:
        if len(d) >= 8:
            soc = db_query("SELECT nombres, apellidos FROM socios WHERE dni=?", (d,))
            if soc:
                nom = soc[0][0].split()[0] if soc[0][0] else ""
                ape = soc[0][1].split()[0] if soc[0][1] else ""
                texto_out = re.sub(rf'\b{d}\b', f"{nom} {ape}".strip(), texto_out)
    return texto_out

def truncar_a_un_decimal(numero):
    return math.floor(numero * 10) / 10.0

def calcular_nivelacion_por_accion():
    socios_data = db_query("SELECT dni, acciones FROM socios WHERE acciones > 0")
    max_cap_por_accion = 0.0
    socio_max_dni = None
    if not socios_data: return 0.0, 0.0
        
    for s_dni, s_acc in socios_data:
        ap_socio = db_query("SELECT SUM(monto) FROM movimientos WHERE tipo LIKE '%Aporte%' AND tipo LIKE ?", (f"%{s_dni}%",))[0][0] or 0.0
        cap_actual_accion = float(ap_socio) / float(s_acc)
        if cap_actual_accion > max_cap_por_accion:
            max_cap_por_accion = cap_actual_accion
            socio_max_dni = s_dni
            
    int_global = 0.0
    int_por_accion = 0.0
    if socio_max_dni:
        movs = db_query("SELECT fecha, monto FROM movimientos WHERE tipo LIKE '%Aporte%' AND tipo LIKE ?", (f"%{socio_max_dni}%",))
        aportes_mes = {}
        for f, m in movs:
            mes = f[:7]
            aportes_mes[mes] = aportes_mes.get(mes, 0.0) + float(m)
        
        tasa = get_config("interes_prestamo", 0.0) / 100.0
        mes_actual = datetime.now().strftime("%Y-%m")
        cap_global = 0.0
        for mes in sorted(aportes_mes.keys()):
            cap_global += aportes_mes[mes]
            if mes < mes_actual: int_global += cap_global * tasa
                
        acc_modelo = db_query("SELECT acciones FROM socios WHERE dni=?", (socio_max_dni,))[0][0]
        int_por_accion = int_global / float(acc_modelo)
    return float(max_cap_por_accion), float(int_por_accion)

def obtener_estado_cumpleanos():
    anio_act, mes_act = datetime.now().year, datetime.now().month
    meses_nom = ["Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio", "Julio", "Agosto", "Septiembre", "Octubre", "Noviembre", "Diciembre"]
    socios_c = db_query("SELECT dni, nombres, apellidos, fecha_nacimiento FROM socios WHERE acciones > 0")
    lista_cumples = []
    
    for s_dni, s_nom, s_ape, fnac in socios_c:
        if fnac:
            try:
                dt_nac = datetime.strptime(fnac, "%Y-%m-%d")
                nombre_fmt = f"{s_nom.split()[0]} {s_ape.split()[0]}"
                estado, fecha_entrega = "PENDIENTE", "---"
                entrega_bd = db_query("SELECT fecha FROM movimientos WHERE tipo LIKE ? AND monto < 0", (f"Entrega de Pozo Cumpleaños - {nombre_fmt} ({anio_act})%",))
                
                if entrega_bd:
                    estado, fecha_entrega = "ENTREGADO", format_fecha(entrega_bd[0][0])
                elif dt_nac.month == mes_act:
                    estado = "EN RECAUDACIÓN"
                    
                lista_cumples.append({
                    "Mes_Num": dt_nac.month, "Día": dt_nac.day, "Mes": meses_nom[dt_nac.month - 1],
                    "Socio": nombre_fmt, "DNI": s_dni, "Estado": estado, "Fecha de Entrega": fecha_entrega
                })
            except: pass
    lista_cumples.sort(key=lambda x: (x["Mes_Num"], x["Día"]))
    return lista_cumples

# =============================================================================
# 3. LÓGICA DE PDFS
# =============================================================================
def generar_pdf_historial_caja(movimientos_fmt, f_ini, f_fin, dni_filtro):
    pdf = FPDF(); pdf.add_page(); pdf.set_font("Courier", 'B', 14)
    pdf.cell(0, 10, "BANQUITO LA COLMENA - REPORTE DE CAJA", ln=True, align='C'); pdf.set_font("Courier", size=10)
    pdf.cell(0, 6, f"Rango de fechas: {format_fecha(str(f_ini))} al {format_fecha(str(f_fin))}", ln=True)
    if dni_filtro: pdf.cell(0, 6, f"Filtro aplicado (DNI/Nombre): {dni_filtro}", ln=True)
    pdf.cell(0, 6, f"Fecha de reporte: {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}", ln=True); pdf.ln(5)
    
    pdf.set_font("Courier", 'B', 9); pdf.cell(35, 6, "FECHA", border=1, align='C'); pdf.cell(125, 6, "DETALLE DE OPERACION", border=1, align='C'); pdf.cell(30, 6, "MONTO (S/)", border=1, align='C'); pdf.ln()
    
    pdf.set_font("Courier", '', 8); t_ing, t_egr = 0.0, 0.0
    for f, d, m in movimientos_fmt:
        d_clean = d.encode('latin-1', 'ignore').decode('latin-1')
        if len(d_clean) > 65: d_clean = d_clean[:62] + "..."
        pdf.cell(35, 6, f, border=1); pdf.cell(125, 6, d_clean, border=1); pdf.cell(30, 6, f"{m:.2f}", border=1, align='R'); pdf.ln()
        if m > 0: t_ing += m 
        else: t_egr += abs(m)
            
    pdf.ln(5); pdf.set_font("Courier", 'B', 10); pdf.cell(0, 6, f"TOTAL INGRESOS: S/ {t_ing:.2f}", ln=True); pdf.cell(0, 6, f"TOTAL EGRESOS:  S/ {t_egr:.2f}", ln=True)
    pdf.cell(0, 6, f"BALANCE NETO:   S/ {t_ing - t_egr:.2f}", ln=True)
    f_n = f"Caja_Temp.pdf"; pdf.output(f_n)
    with open(f_n, "rb") as fi: b = fi.read()
    os.remove(f_n)
    return b

def generar_pdf_estado_cuenta(nombre_completo, dni, acc_num, f_inicio=None, f_fin=None):
    tasa, m_min = get_config("interes_prestamo", 0.0) / 100.0, get_config("monto_minimo_capital", 50.0)
    res_p = db_query("SELECT saldo_actual FROM prestamos WHERE dni_socio=? AND accion_asociada=? AND estado='ACTIVO'", (dni, acc_num))
    saldo_hoy = res_p[0][0] if res_p else 0.0
    filtro = f"%{dni}%(Acción {acc_num})%"
    
    if f_inicio and f_fin:
        movs = db_query("SELECT fecha, tipo, monto FROM movimientos WHERE tipo LIKE ? AND date(fecha) >= ? AND date(fecha) <= ? ORDER BY fecha ASC", (filtro, f_inicio, f_fin))
        rango_str = f"Rango: {format_fecha(str(f_inicio))} al {format_fecha(str(f_fin))}"
    else:
        movs = db_query("SELECT fecha, tipo, monto FROM movimientos WHERE tipo LIKE ? ORDER BY fecha ASC", (filtro,))
        rango_str = "Rango: Histórico Completo"
        
    pdf = FPDF(); pdf.add_page(); pdf.set_font("Courier", size=9)
    header = f"ESTADO DE CUENTA DETALLADO - ACCIÓN {acc_num}\nBANQUITO LA COLMENA 🐝\n" + "="*85 + "\n"
    header += f"Socio: {nombre_completo}\nDNI  : {dni}\n{rango_str}\nFecha de reporte: {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}\n" + "="*85 + "\n\n"
    header += "⏪ PARTE 1: HISTORIAL DE MOVIMIENTOS\n" + "-"*85 + "\n"
    header += f"{'FECHA':<10} | {'DETALLE':<20} | {'CAPITAL':<9} | {'INTERES':<9} | {'CUOTA':<9} | {'SALDO CAP.'}\n" + "-"*85 + "\n"
    
    reporte_texto, saldo_acumulado, historial_agrupado = header, 0.0, {}
    
    for m in movs:
        f, t, mon = m[0], m[1], m[2]; f_dia = f[:10] 
        if "Préstamo" in t:
            key = f"{f_dia}_2_DESEMBOLSO"
            if key not in historial_agrupado: historial_agrupado[key] = {'fecha': f_dia, 'cap': 0.0, 'int': 0.0, 'tipo': 'DESEMBOLSO'}
            historial_agrupado[key]['cap'] += abs(mon)
        else:
            key = f"{f_dia}_1_PAGO"
            if key not in historial_agrupado: historial_agrupado[key] = {'fecha': f_dia, 'cap': 0.0, 'int': 0.0, 'tipo': 'PAGO'}
            if "Interés" in t: historial_agrupado[key]['int'] += abs(mon)
            elif "Pago Cuota" in t: historial_agrupado[key]['cap'] += abs(mon)
        
    for key in sorted(historial_agrupado.keys()):
        d_mov = historial_agrupado[key]
        f_display = format_fecha(d_mov['fecha'])
        if d_mov['tipo'] == 'DESEMBOLSO':
            saldo_acumulado += d_mov['cap']
            reporte_texto += f"{f_display:<10} | {'NUEVO PRÉSTAMO':<20} | {d_mov['cap']:>9.2f} | {'0.00':>9} | {d_mov['cap']:>9.2f} | {saldo_acumulado:>10.2f}\n"
        elif d_mov['tipo'] == 'PAGO':
            if d_mov['cap'] > 0 or d_mov['int'] > 0:
                saldo_acumulado -= d_mov['cap']
                if saldo_acumulado < 0.01: saldo_acumulado = 0.0
                reporte_texto += f"{f_display:<10} | {'PAGO CUOTA':<20} | {d_mov['cap']:>9.2f} | {d_mov['int']:>9.2f} | {d_mov['cap']+d_mov['int']:>9.2f} | {saldo_acumulado:>10.2f} C\n"
            
    reporte_texto += "\n\n⏩ PARTE 2: PROYECCIÓN DE PAGOS PENDIENTES (CRONOGRAMA ACTUALIZADO)\n" + "-"*85 + "\n"
    reporte_texto += f"{'NRO CUOTA':<10} | {'MES Y AÑO':<20} | {'CAPITAL':<9} | {'INTERES':<9} | {'CUOTA':<9} | {'SALDO CAP.'}\n" + "-"*85 + "\n"
    sp, mes, anio, total_proyectado = saldo_hoy, datetime.now().month, datetime.now().year, 0.0
    
    amort_pct_act, amort_pct_val = get_config("amort_porcentaje_activo", "NO", str), get_config("amort_porcentaje_valor", 0.0) / 100.0
    res_orig = db_query("SELECT monto_original FROM prestamos WHERE dni_socio=? AND accion_asociada=? AND estado='ACTIVO'", (dni, acc_num))
    d_orig = res_orig[0][0] if res_orig else 0.0
    meses_nombres = ["Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio", "Julio", "Agosto", "Septiembre", "Octubre", "Noviembre", "Diciembre"]
    num_c = 1
    
    while sp > 0.01:
        mes = mes + 1 if mes < 12 else 1
        if mes == 1: anio += 1
        
        if amort_pct_act == "SI":
            m_pct = float(math.ceil(d_orig * amort_pct_val))
            if m_pct < m_min: m_pct = float(m_min)
            am = min(m_pct, sp)
        else: am = min(m_min, sp)
            
        i = float(math.ceil(sp * tasa)); cuo = am + i; sp -= am; total_proyectado += cuo
        reporte_texto += f"Cuota {num_c:<4} | {meses_nombres[mes-1]} {anio:<13} | {am:>9.2f} | {i:>9.2f} | {cuo:>9.2f} | {max(0.0, sp):>10.2f}\n"
        num_c += 1
        
    reporte_texto += "-"*85 + "\n" + f"Saldo actual de capital: S/ {saldo_hoy:.2f}\nTotal estimado para liquidar deuda: S/ {total_proyectado:.2f}\n" + "="*85 + "\n"
    for line in reporte_texto.split('\n'): pdf.cell(0, 5, txt=line.encode('latin-1','ignore').decode('latin-1'), ln=True)
    f_n = f"R_{dni}_{acc_num}.pdf"; pdf.output(f_n)
    with open(f_n, "rb") as f: b = f.read()
    os.remove(f_n); return b

def generar_pdf_desembolso(nom_soc, d, n_a, m_prestado, m_proy, tot_i, cuotas, fh, tasa, incluir_contrato=True):
    nom_presi, nom_teso, nom_secri, anio_actual = get_config("presidente", "No asignado", str), get_config("tesorero", "No asignado", str), get_config("secretario", "No asignado", str), datetime.now().year
    pdf = FPDF(); fh_fmt = format_fecha(fh)
    
    pdf.add_page(); pdf.set_font("Courier", 'B', 14); pdf.cell(0, 10, "BANQUITO LA COLMENA - VOUCHER DE DESEMBOLSO", ln=True, align='C')
    pdf.set_font("Courier", size=12); pdf.ln(5)
    texto_v = f"Fecha: {fh_fmt}\nSocio: {nom_soc}\nDNI:   {d} | Accion Vinculada: {n_a}\n" + "-"*50 + f"\nMONTO DESEMBOLSADO EN EFECTIVO : S/ {m_prestado:.2f}\n" + "-"*50 + "\n\n\n     ____________________________\n          FIRMA DEL SOCIO\n"
    for l in texto_v.split('\n'): pdf.cell(0, 6, txt=l.encode('latin-1','ignore').decode('latin-1'), ln=True)
        
    pdf.add_page(); pdf.set_font("Courier", 'B', 14); pdf.cell(0, 10, "CRONOGRAMA DE PRESTAMO", ln=True, align='C'); pdf.set_font("Courier", size=10); pdf.ln(5)
    tc = f"Socio: {nom_soc}\nDNI: {d} | Accion: {n_a}\nFecha de Emision: {fh_fmt}\nDeuda Total Capital: S/ {m_proy:.2f} | Int. Proyectado: S/ {tot_i:.2f} | Total a Pagar: S/ {m_proy+tot_i:.2f}\n--------------------------------------------------------------------------\n{'NRO CUOTA':<10} | {'MES Y AÑO':<17} | {'CAPITAL':<9} | {'INTERES':<9} | {'CUOTA':<9} | {'SALDO CAP.'}\n--------------------------------------------------------------------------\n"
    saldo = m_proy
    for c in cuotas: 
        n_cuota, mes_anio, cap, interes, cuota = c[0], c[1], c[2], c[3], c[4]
        saldo -= cap; tc += f"{n_cuota:<10} | {mes_anio:<17} | {cap:>9.2f} | {interes:>9.2f} | {cuota:>9.2f} | {max(0.0, saldo):>10.2f}\n"
    for l in tc.split('\n'): pdf.cell(0, 5, txt=l.encode('latin-1','ignore').decode('latin-1'), ln=True)
        
    if incluir_contrato:
        pdf.add_page(); pdf.set_font("Arial", 'B', 14); pdf.cell(0, 10, "CONTRATO PRIVADO DE PRÉSTAMO DE DINERO", ln=True, align='C'); pdf.ln(5)
        pdf.set_font("Arial", '', 11)
        intro = f"Conste por el presente documento privado de préstamo de dinero que celebran, de una parte, la Junta Directiva del periodo {anio_actual} del BANQUITO LA COLMENA, debidamente representada por su Presidente(a): {nom_presi}, Tesorero(a): {nom_teso} y Secretario(a): {nom_secri}, a quienes en adelante se les denominará EL PRESTAMISTA; y de la otra parte, el/la socio(a) {nom_soc}, identificado(a) con DNI Nro. {d}, a quien en adelante se le denominará EL PRESTATARIO; quienes convienen en celebrar el presente contrato bajo los terms y condiciones contenidos en las siguientes cláusulas:"
        pdf.multi_cell(0, 6, txt=intro.encode('latin-1','ignore').decode('latin-1'), align='J'); pdf.ln(5)
        
        pdf.set_font("Arial", 'B', 11); pdf.cell(0, 6, "PRIMERA: DEL PRÉSTAMO Y LA DEUDA TOTAL", ln=True, align='L'); pdf.set_font("Arial", '', 11)
        clausula_1 = f"EL PRESTAMISTA otorga a EL PRESTATARIO un nuevo desembolso en efectivo por la suma de S/ {m_prestado:.2f}. " + (f"Sumado al saldo deudor anterior, la DEUDA TOTAL ACTUALIZADA asciende a la suma de S/ {m_proy:.2f}, " if m_proy > m_prestado else f"La DEUDA TOTAL ACTUALIZADA asciende a la suma de S/ {m_proy:.2f}, ") + f"vinculada a la Acción Nro. {n_a}."
        pdf.multi_cell(0, 6, txt=clausula_1.encode('latin-1','ignore').decode('latin-1'), align='J'); pdf.ln(4)
        
        pdf.set_font("Arial", 'B', 11); pdf.cell(0, 6, "SEGUNDA: DE LOS INTERESES", ln=True, align='L'); pdf.set_font("Arial", '', 11)
        pdf.multi_cell(0, 6, txt=f"El capital total prestado devengará un interés compensatorio mensual del {tasa * 100:.1f}%.".encode('latin-1','ignore').decode('latin-1'), align='J'); pdf.ln(4)
        
        pdf.set_font("Arial", 'B', 11); pdf.cell(0, 6, "TERCERA: DE LA DEVOLUCIÓN", ln=True, align='L'); pdf.set_font("Arial", '', 11)
        pdf.multi_cell(0, 6, txt="EL PRESTATARIO se obliga y compromete a devolver el capital total prestado más los intereses generados mediante pagos mensuales y continuos los días de asamblea estipulados de cada mes, cumpliendo estrictamente con la amortización mínima obligatoria pactada en asamblea general.".encode('latin-1','ignore').decode('latin-1'), align='J'); pdf.ln(4)
        
        pdf.set_font("Arial", 'B', 11); pdf.cell(0, 6, "CUARTA: DEL INCUMPLIMIENTO", ln=True, align='L'); pdf.set_font("Arial", '', 11)
        pdf.multi_cell(0, 6, txt="En caso de demora, morosidad o incumplimiento en el pago de las cuotas, EL PRESTATARIO acepta y autoriza someterse a las multas, sanciones o al descuento directo y automático de sus ahorros (capitalización) depositados en EL BANQUITO, conforme al reglamento interno vigente.".encode('latin-1','ignore').decode('latin-1'), align='J'); pdf.ln(8)
        
        try: f_dt = datetime.strptime(fh[:10], "%Y-%m-%d"); meses = ["enero", "febrero", "marzo", "abril", "mayo", "junio", "julio", "agosto", "septiembre", "octubre", "noviembre", "diciembre"]; fecha_texto = f"{f_dt.day} de {meses[f_dt.month - 1]} de {f_dt.year}"
        except: fecha_texto = format_fecha(fh[:10])
            
        pdf.multi_cell(0, 6, txt=f"Suscrito y firmado en señal de estricta conformidad, el día {fecha_texto}.".encode('latin-1','ignore').decode('latin-1'), align='J'); pdf.ln(20)
        firmas = "_____________________________                  _____________________________\nEL PRESTATARIO                               POR EL PRESTAMISTA\n" + f"DNI: {d:<15}                        (Junta Directiva {anio_actual})"
        pdf.multi_cell(0, 5, txt=firmas.encode('latin-1','ignore').decode('latin-1'), align='C')
        
    f_n = f"D_{d}.pdf"; pdf.output(f_n)
    with open(f_n, "rb") as f: b = f.read()
    os.remove(f_n); return b

def generar_pdf_voucher(t, d):
    pdf = FPDF(); pdf.add_page(); pdf.set_font("Courier", size=12)
    for l in t.replace("🐝", "").split('\n'): pdf.cell(0, 6, txt=l.encode('latin-1','ignore').decode('latin-1'), ln=True)
    f = f"V_{d}.pdf"; pdf.output(f)
    with open(f, "rb") as fi: b = fi.read()
    os.remove(f); return b

def generar_pdf_constancia(tipo, socio_nom, dni):
    pdf = FPDF(); pdf.add_page(); pdf.set_font("Arial", 'B', 16); pdf.cell(0, 15, "BANQUITO LA COLMENA", ln=True, align='C')
    pdf.set_font("Arial", 'B', 12); pdf.cell(0, 10, f"CONSTANCIA DE {tipo.upper()}", ln=True, align='C'); pdf.ln(10)
    pdf.set_font("Arial", '', 12); fecha_hoy = datetime.now().strftime("%d de %B de %Y")
    
    if tipo == "Socio Activo": texto = f"La Junta Directiva del Banquito La Colmena hace constar que el Sr(a). {socio_nom.upper()}, identificado con DNI {dni}, se encuentra registrado como SOCIO ACTIVO de nuestra institucion, cumpliendo con sus aportaciones a la fecha.\n\nSe expide el presente documento a solicitud del interesado para los fines que considere convenientes."
    else: texto = f"La Junta Directiva del Banquito La Colmena certifica que el Sr(a). {socio_nom.upper()}, con DNI {dni}, NO MANTIENE DEUDAS PENDIENTES por concepto de prestamos en ninguna de sus acciones a la fecha de hoy.\n\nSe extiende la presente constancia para acreditar su solvencia interna dentro de la organizacion."
        
    pdf.multi_cell(0, 8, txt=texto.encode('latin-1','ignore').decode('latin-1'), align='J'); pdf.ln(30)
    pdf.cell(0, 10, "__________________________", ln=True, align='C'); pdf.cell(0, 5, "Secretaria / Junta Directiva", ln=True, align='C'); pdf.cell(0, 5, f"Fecha: {fecha_hoy}", ln=True, align='C')
    f = f"C_{dni}.pdf"; pdf.output(f)
    with open(f, "rb") as fi: b = fi.read()
    os.remove(f); return b

def generar_pdf_acta_cierre(anio):
    nom_presi, nom_teso, nom_secri = get_config("presidente", "No asignado", str), get_config("tesorero", "No asignado", str), get_config("secretario", "No asignado", str)
    movs_dir = db_query("SELECT tipo, monto FROM movimientos WHERE tipo LIKE ? AND monto < 0", (f"Pago Directiva {anio}%",))
    movs_soc = db_query("SELECT tipo, monto FROM movimientos WHERE tipo LIKE ? AND monto < 0", (f"Pago Utilidades {anio}%",))
    movs_cc = db_query("SELECT monto FROM movimientos WHERE tipo = ?", (f"Ingreso Caja Chica - Sobrante Utilidades {anio}",))
    sobrante_cc = sum([float(m[0]) for m in movs_cc]) if movs_cc else 0.0
    
    pdf = FPDF(); pdf.add_page(); pdf.set_font("Arial", 'B', 14); pdf.cell(0, 10, f"ACTA DE CIERRE Y REPARTO DE UTILIDADES - AÑO {anio}", ln=True, align='C'); pdf.ln(5)
    pdf.set_font("Arial", '', 11)
    intro = f"En la presente asamblea general de cierre del año {anio}, la Junta Directiva del BANQUITO LA COLMENA, conformada por su Presidente(a): {nom_presi}, Tesorero(a): {nom_teso} y Secretario(a): {nom_secri}, deja constancia de la distribution de las utilidades generadas por los intereses de los préstamos durante el periodo correspondiente."
    pdf.multi_cell(0, 6, txt=intro.encode('latin-1','ignore').decode('latin-1'), align='J'); pdf.ln(5)
    
    pdf.set_font("Arial", 'B', 11); pdf.cell(0, 6, "1. PAGO A LA JUNTA DIRECTIVA (3%)", ln=True); pdf.set_font("Arial", '', 11); tot_dir = 0.0
    if movs_dir:
        for t, m in movs_dir:
            tot_dir += abs(m); detalle = format_movimiento(t).split(" - ")[1] if " - " in format_movimiento(t) else format_movimiento(t)
            pdf.cell(0, 6, f" - {detalle}: S/ {abs(m):.2f}".encode('latin-1','ignore').decode('latin-1'), ln=True)
    else: pdf.cell(0, 6, " - No se registraron pagos a la directiva.", ln=True)
    pdf.ln(3)
    
    pdf.set_font("Arial", 'B', 11); pdf.cell(0, 6, "2. REPARTO A SOCIOS (97% + Excedentes)", ln=True); pdf.set_font("Arial", '', 11); tot_soc = 0.0
    if movs_soc:
        for t, m in movs_soc:
            tot_soc += abs(m); detalle = format_movimiento(t).split(" - ")[1] if " - " in format_movimiento(t) else format_movimiento(t)
            pdf.cell(0, 6, f" - Socio: {detalle}: S/ {abs(m):.2f}".encode('latin-1','ignore').decode('latin-1'), ln=True)
    else: pdf.cell(0, 6, " - No se registraron pagos a socios.", ln=True)
    pdf.ln(3)
    
    pdf.set_font("Arial", 'B', 11); pdf.cell(0, 6, "3. SOBRANTE A CAJA CHICA", ln=True); pdf.set_font("Arial", '', 11)
    pdf.cell(0, 6, f" - Excedente depositado a Caja Chica: S/ {sobrante_cc:.2f}", ln=True); pdf.ln(8)
    
    pdf.set_font("Arial", 'B', 11); pdf.cell(0, 6, "RESUMEN TOTAL REPARTIDO:", ln=True); pdf.set_font("Arial", '', 11)
    pdf.cell(0, 6, f"Total Directiva : S/ {tot_dir:.2f}", ln=True); pdf.cell(0, 6, f"Total Socios    : S/ {tot_soc:.2f}", ln=True); pdf.cell(0, 6, f"Total Caja Chica: S/ {sobrante_cc:.2f}", ln=True); pdf.cell(0, 6, f"GRAN TOTAL      : S/ {tot_dir + tot_soc + sobrante_cc:.2f}", ln=True); pdf.ln(20)
    
    firmas = "_____________________________                  _____________________________\nPRESIDENTE(A)                                 TESORERO(A)\n"
    pdf.multi_cell(0, 5, txt=firmas.encode('latin-1','ignore').decode('latin-1'), align='C')
    f_n = f"Acta_Cierre_{anio}.pdf"; pdf.output(f_n)
    with open(f_n, "rb") as f: b = f.read()
    os.remove(f_n); return b

# =============================================================================
# 4. FUNCIONES DE ESTADO Y UI COMPARTIDA
# =============================================================================
def limpiar_formularios_socio():
    claves = ['ce_pdf_bytes', 'ce_msg_correo', 'ce_done', 'ns_pdf_bytes', 'ns_msg_correo', 'ns_done', 'update_success_sec']
    for clave in claves:
        if clave in st.session_state: del st.session_state[clave]

def limpiar_formularios_pago():
    claves = ['pu_tot', 'pu_det_ap', 'pu_tot_ap', 'pu_det_pr', 'pu_tot_cap', 'pu_tot_int', 'pu_show_voucher', 'pu_done', 'pu_pdf_bytes', 'pu_msg_correo', 'pu_needs_auth', 'pu_auth_success', 'pres_done', 'pres_pdf', 'pres_dni', 'pres_msg_correo']
    for clave in claves:
        if clave in st.session_state: del st.session_state[clave]

def update_monto_inline(sol_id, input_key):
    db_query("UPDATE solicitudes_prestamo SET monto=? WHERE id=?", (st.session_state[input_key], sol_id), fetch=False)

def render_top_header():
    col_head1, col_head2 = st.columns([5, 1])
    nombre = st.session_state.usuario_nombre if st.session_state.usuario_id else st.session_state.socio_nombre
    rol = st.session_state.usuario_rol.upper() if st.session_state.usuario_id else "SOCIO"
    col_head1.markdown(f"<h2 style='margin-bottom: 0px;'>🐝 BIENVENIDO(A), {nombre}</h2>", unsafe_allow_html=True)
    col_head1.markdown(f"**PERFIL:** {rol}")
    if col_head2.button("🚪 CERRAR SESIÓN", use_container_width=True, type="primary"):
        st.session_state.usuario_id = st.session_state.usuario_rol = st.session_state.usuario_nombre = None
        st.session_state.socio_logged_in = st.session_state.socio_dni = st.session_state.socio_nombre = False
        st.session_state.vista = 'login'
        st.rerun()
    st.divider()

# --- MÓDULOS DE UI COMPARTIDOS ---
def ui_panel_control():
    st.subheader("📊 DASHBOARD ANALÍTICO GLOBAL")
    s_tot = float(db_query("SELECT SUM(monto) FROM movimientos")[0][0] or 0.0)
    i_cc = db_query("SELECT SUM(monto) FROM movimientos WHERE tipo LIKE 'Ingreso Caja Chica%' OR tipo = 'Depósito Caja'")[0][0] or 0.0
    e_cc = abs(db_query("SELECT SUM(monto) FROM movimientos WHERE tipo LIKE 'Egreso Caja Chica%' OR tipo = 'Retiro Caja'")[0][0] or 0.0)
    f_cc = i_cc - e_cc
    c_prin = s_tot - f_cc
    
    prestado_bd = db_query("SELECT SUM(saldo_actual) FROM prestamos WHERE estado='ACTIVO'")
    dinero_prestado = float(prestado_bd[0][0]) if prestado_bd and prestado_bd[0][0] else 0.0
    patrimonio_total = c_prin + f_cc + dinero_prestado
    
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("CAJA PRINCIPAL (FÍSICO)", f"S/ {f_m(c_prin)}")
    c2.metric("DINERO EN LA CALLE", f"S/ {f_m(dinero_prestado)}")
    c3.metric("CAJA CHICA", f"S/ {f_m(f_cc)}")
    c4.metric("PATRIMONIO TOTAL", f"S/ {f_m(patrimonio_total)}")
    
    st.divider()
    col_chart1, col_chart2 = st.columns(2)
    with col_chart1:
        st.write("#### 🥧 DISTRIBUCIÓN DEL PORTAFOLIO")
        if patrimonio_total > 0:
            source = pd.DataFrame({"Categoría": ["Efectivo Caja Principal", "Dinero Prestado", "Caja Chica"], "Monto": [c_prin, dinero_prestado, f_cc]})
            base = alt.Chart(source).encode(theta=alt.Theta("Monto:Q", stack=True), color=alt.Color("Categoría:N", scale=alt.Scale(scheme='set2'), legend=alt.Legend(title="Fondo")), tooltip=["Categoría", "Monto"])
            st.altair_chart(base.mark_arc(innerRadius=50, outerRadius=120), use_container_width=True)
        else: st.info("No hay fondos registrados en el sistema.")
            
    with col_chart2:
        st.write("#### 📈 CRECIMIENTO DE APORTES (HISTÓRICO)")
        movs_aportes = db_query("SELECT fecha, monto FROM movimientos WHERE tipo LIKE '%Aporte%'")
        if movs_aportes:
            df_ap = pd.DataFrame(movs_aportes, columns=["fecha", "monto"])
            df_ap['fecha'] = pd.to_datetime(df_ap['fecha'])
            df_ap['Mes'] = df_ap['fecha'].dt.strftime('%Y-%m')
            st.bar_chart(df_ap.groupby('Mes')['monto'].sum().reset_index().set_index('Mes'), color="#2563eb")
        else: st.info("No hay aportes registrados en el sistema.")

def ui_votaciones_admin():
    st.subheader("🗳️ GESTIÓN DE VOTACIONES (URNA VIRTUAL)")
    t_v1, t_v2 = st.tabs(["➕ CREAR NUEVA CONSULTA", "📊 RESULTADOS Y CIERRE"])
    with t_v1:
        st.write("Crea una consulta para que los socios voten desde su celular. El voto es estrictamente 1 por persona.")
        v_preg = st.text_input("Pregunta a consultar a los socios:", placeholder="Ej: ¿Subimos la cuota de inscripción a S/ 50.00?")
        v_ops = st.text_input("Opciones de respuesta separadas por coma:", value="SÍ, NO, ABSTENCIÓN")
        if st.button("🚀 PUBLICAR VOTACIÓN", type="primary"):
            if v_preg and v_ops:
                db_query("INSERT INTO votaciones (pregunta, opciones, fecha_creacion) VALUES (?,?,?)", (v_preg, v_ops, datetime.now().strftime("%Y-%m-%d %H:%M:%S")), fetch=False)
                st.success("Votación creada y publicada con éxito. Los socios ya pueden votar.")
            else: st.warning("Completa la pregunta y las opciones.")
                
    with t_v2:
        st.write("Cierra las urnas y revisa los resultados finales.")
        vot_abiertas = db_query("SELECT id, pregunta, fecha_creacion FROM votaciones WHERE estado='ABIERTA' ORDER BY id DESC")
        if vot_abiertas:
            for v_id, preg, f_crea in vot_abiertas:
                with st.container(border=True):
                    st.write(f"**{preg}** (Creada el {f_crea})")
                    resultados = db_query("SELECT opcion, COUNT(*) as votos FROM votos WHERE id_votacion=? GROUP BY opcion", (v_id,))
                    if resultados: st.bar_chart(pd.DataFrame(resultados, columns=["Opción", "Votos (1 x Socio)"]).set_index("Opción"), color="#2563eb")
                    else: st.info("Aún no hay votos registrados.")
                    if st.button("🔒 CERRAR URNA PARA ESTA CONSULTA", key=f"cierra_{v_id}"):
                        db_query("UPDATE votaciones SET estado='CERRADA' WHERE id=?", (v_id,), fetch=False)
                        st.rerun()
        else: st.info("No hay votaciones activas en este momento.")

def ui_cumpleanos_admin(es_tesorero=False):
    if not es_tesorero:
        with st.expander("📅 VER CALENDARIO ANUAL DE CUMPLEAÑOS Y ENTREGAS", expanded=False):
            lista_c = obtener_estado_cumpleanos()
            if lista_c:
                df_c = pd.DataFrame(lista_c)
                def highlight_estado(val):
                    if val == 'ENTREGADO': return 'color: green; font-weight: bold'
                    elif val == 'EN RECAUDACIÓN': return 'color: orange; font-weight: bold'
                    return 'color: gray'
                st.dataframe(df_c.style.map(highlight_estado, subset=['Estado']), use_container_width=True)
            else: st.info("No hay fechas registradas.")
        return

    st.subheader("🎂 Gestión del Juego de Cumpleaños")
    with st.expander("📅 VER CALENDARIO ANUAL DE CUMPLEAÑOS Y ENTREGAS", expanded=False):
        lista_c = obtener_estado_cumpleanos()
        if lista_c:
            df_c = pd.DataFrame(lista_c)
            def highlight_estado(val):
                if val == 'ENTREGADO': return 'color: green; font-weight: bold'
                elif val == 'EN RECAUDACIÓN': return 'color: orange; font-weight: bold'
                return 'color: gray'
            st.dataframe(df_c.style.map(highlight_estado, subset=['Estado']), use_container_width=True)
        else: st.info("No hay fechas registradas.")
            
    st.divider()
    anio_act, mes_act = datetime.now().year, datetime.now().month
    meses_nom = ["Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio", "Julio", "Agosto", "Septiembre", "Octubre", "Noviembre", "Diciembre"]
    
    cumpleaneros = db_query("SELECT dni, nombres, apellidos, fecha_nacimiento FROM socios WHERE acciones > 0")
    cumplen_este_mes = []
    for d, n, a, fnac in cumpleaneros:
        if fnac:
            try:
                dt_nac = datetime.strptime(fnac, "%Y-%m-%d")
                if dt_nac.month == mes_act: cumplen_este_mes.append({"dni": d, "nom": f"{n.split()[0]} {a.split()[0]}", "dia": dt_nac.day})
            except: pass
    
    cuota_c = get_config("cuota_cumpleanos", 0.0)
    if cumplen_este_mes:
        st.success(f"Este mes de **{meses_nom[mes_act-1]}** estamos festejando a:")
        for c in cumplen_este_mes: st.write(f"- 🎈 **{c['nom']}** (Día {c['dia']})")
        st.divider()
        t1, t2 = st.tabs(["💰 COBRAR CUOTAS A SOCIOS", "🎁 ENTREGAR POZO AL CUMPLEAÑERO"])
        
        with t1:
            st.write(f"**Cuota acordada por socio:** S/ {f_m(cuota_c)}")
            soc_pagadores = db_query("SELECT dni, nombres, apellidos FROM socios WHERE acciones > 0 ORDER BY nombres ASC")
            dni_festejado = st.selectbox("¿Para el cumpleaños de quién están aportando?", [c['nom'] for c in cumplen_este_mes])
            dni_f_real = next(c['dni'] for c in cumplen_este_mes if c['nom'] == dni_festejado)
            
            st.write("Marque a los socios que están pagando su cuota en este momento:")
            socios_a_pagar = []
            for s_p in soc_pagadores:
                if s_p[0] == dni_f_real: continue
                ya_pago = db_query("SELECT id FROM cumpleanos_pagos WHERE anio=? AND mes=? AND dni_cumpleanero=? AND dni_aportante=?", (anio_act, mes_act, dni_f_real, s_p[0]))
                nombre_pagador = f"{s_p[1].split()[0]} {s_p[2].split()[0]}"
                if ya_pago: st.write(f"✅ {nombre_pagador} (Ya pagó)")
                else:
                    if st.checkbox(f"Cobrar a: {nombre_pagador}"): socios_a_pagar.append(s_p[0])
            
            if st.button("💾 REGISTRAR PAGO DE CUOTAS", type="primary"):
                if socios_a_pagar:
                    monto_ingreso_total = len(socios_a_pagar) * cuota_c
                    fh = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    db_query("UPDATE cuentas SET saldo = saldo + ? WHERE id_usuario=1", (monto_ingreso_total,), fetch=False)
                    for sp_dni in socios_a_pagar: db_query("INSERT INTO cumpleanos_pagos (anio, mes, dni_cumpleanero, dni_aportante, monto, fecha_pago) VALUES (?,?,?,?,?,?)", (anio_act, mes_act, dni_f_real, sp_dni, cuota_c, fh), fetch=False)
                    db_query("INSERT INTO movimientos (id_usuario, tipo, monto, fecha) VALUES (1, ?, ?, ?)", (f"Ingreso Recaudación Cumpleaños - Para {dni_festejado}", monto_ingreso_total, fh), fetch=False)
                    st.success(f"Se registraron {len(socios_a_pagar)} pagos exitosamente. El dinero ingresó a la Caja Principal.")
                    st.rerun()
                else: st.warning("No seleccionaste a ningún socio para cobrarle.")
                    
        with t2:
            st.write("Entregar el dinero recaudado al cumpleañero.")
            dni_festejado_pago = st.selectbox("Seleccione al cumpleañero a pagar:", [c['nom'] for c in cumplen_este_mes], key="sel_pagar")
            dni_f_real_pago = next(c['dni'] for c in cumplen_este_mes if c['nom'] == dni_festejado_pago)
            recaudado = db_query("SELECT SUM(monto) FROM cumpleanos_pagos WHERE anio=? AND mes=? AND dni_cumpleanero=?", (anio_act, mes_act, dni_f_real_pago))[0][0] or 0.0
            st.metric(f"Total Recaudado para {dni_festejado_pago}", f"S/ {f_m(recaudado)}")
            ya_se_le_entrego = db_query("SELECT id FROM movimientos WHERE tipo = ? AND monto < 0", (f"Entrega de Pozo Cumpleaños - {dni_festejado_pago} ({anio_act})",))
            
            if ya_se_le_entrego: st.success("✅ El pozo ya fue entregado a este cumpleañero.")
            elif recaudado > 0:
                if st.button(f"🎁 ENTREGAR POZO (S/ {f_m(recaudado)}) A {dni_festejado_pago}", type="primary"):
                    fh = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    db_query("UPDATE cuentas SET saldo = saldo - ? WHERE id_usuario=1", (recaudado,), fetch=False)
                    db_query("INSERT INTO movimientos (id_usuario, tipo, monto, fecha) VALUES (1, ?, ?, ?)", (f"Entrega de Pozo Cumpleaños - {dni_festejado_pago} ({anio_act})", -recaudado, fh), fetch=False)
                    st.success("¡Dinero entregado y descontado de la Caja Principal!")
                    st.rerun()
            else: st.info("Aún no se ha recaudado dinero para este cumpleañero.")
    else: st.info(f"Este mes de **{meses_nom[mes_act-1]}** no hay cumpleaños programados en el padrón de socios activos.")

def ui_registro_nuevo_socio():
    if st.session_state.get('ns_done', False):
        st.success("🎉 ¡Socio nuevo registrado y pago ingresado en la Caja exitosamente!")
        st.info(st.session_state.ns_msg_correo)
        st.download_button("🖨️ DESCARGAR VOUCHER (IMPRIMIR Y FIRMAR)", data=st.session_state.ns_pdf_bytes, file_name=f"Voucher_Ingreso.pdf", mime="application/pdf", type="primary")
        if st.button("FINALIZAR Y LIMPIAR FORMULARIO"):
            limpiar_formularios_socio(); st.rerun()
    else:
        rdni = st.text_input("DNI*", on_change=limpiar_formularios_socio)
        rnom = st.text_input("Nombres*")
        rape = st.text_input("Apellidos")
        rtel = st.text_input("Teléfono")
        rdir = st.text_input("Dirección")
        rcor = st.text_input("Correo")
        rsex = st.selectbox("Sexo", ["Masculino", "Femenino"])
        rnac = st.date_input("Fecha de Nacimiento", value=date(1990, 1, 1), min_value=date(1900, 1, 1), max_value=date.today())
        racc = st.number_input("Acciones a Iniciar", 1, 4, 1)
        
        st.divider()
        st.write("El sistema calcula automáticamente la nivelación correspondiente al día de hoy:")
        c_hist, i_hist = calcular_nivelacion_por_accion()
        ins_b = get_config("cuota_inscripcion", 0.0)
        t_cap = c_hist * racc
        t_int = math.ceil(i_hist) * racc
        t_ins = ins_b * racc
        t_tot = t_cap + t_int + t_ins
        
        st.markdown("### 📄 Desglose del Pago de Ingreso")
        st.write(f"- **Aportes (Capital de Nivelación):** S/ {f_m(t_cap)}\n- **Inscripción ({racc} acc):** S/ {f_m(t_ins)}\n- **Interés de Nivelación:** S/ {f_m(t_int)}")
        st.info(f"**TOTAL A PAGAR E INGRESAR A CAJA:** S/ {f_m(t_tot)}")
        
        if st.button("💸 REGISTRAR SOCIO Y PAGAR", type="primary"):
            if not rdni or not rnom: st.warning("DNI y Nombres son obligatorios.")
            else:
                if db_query("SELECT id FROM socios WHERE dni=?", (rdni,)): st.error("Error: Este DNI ya está registrado.")
                else:
                    db_query("INSERT INTO socios (dni, nombres, apellidos, telefono, direccion, correo, sexo, fecha_nacimiento, acciones, fecha_ingreso) VALUES (?,?,?,?,?,?,?,?,?,?)", (rdni, rnom, rape, rtel, rdir, rcor, rsex, str(rnac), racc, datetime.now().strftime("%Y-%m-%d")), fetch=False)
                    db_query("UPDATE cuentas SET saldo = saldo + ? WHERE id_usuario=1", (t_tot,), fetch=False)
                    fh = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    nombre_fmt = f"{rnom.split()[0]} {rape.split()[0]}"
                    
                    if t_cap>0: db_query("INSERT INTO movimientos (id_usuario, tipo, monto, fecha) VALUES (1, ?, ?, ?)", (f"Aporte Inicial - {nombre_fmt} ({racc} acc)", t_cap, fh), fetch=False)
                    if t_int>0: db_query("INSERT INTO movimientos (id_usuario, tipo, monto, fecha) VALUES (1, ?, ?, ?)", (f"Interés Inicial - {nombre_fmt} ({racc} acc)", t_int, fh), fetch=False)
                    if t_ins>0: db_query("INSERT INTO movimientos (id_usuario, tipo, monto, fecha) VALUES (1, ?, ?, ?)", (f"Derecho Inscripción - {nombre_fmt} ({racc} acc)", t_ins, fh), fetch=False)
                    
                    txt_ns = f"======================================\n      BANQUITO LA COLMENA\n     INGRESO DE NUEVO SOCIO\n======================================\nFecha: {format_fecha(fh)}\nSocio: {rnom} {rape}\nDNI:   {rdni}\n--------------------------------------\n"
                    txt_ns += f"Acciones Iniciales : {racc}\nAportes Nivelacion : S/ {f_m(t_cap)}\nInteres Nivelacion : S/ {f_m(t_int)}\nInscripcion        : S/ {f_m(t_ins)}\n--------------------------------------\nTOTAL INGRESADO    : S/ {f_m(t_tot)}\n======================================\n\n\n     ____________________________\n          FIRMA DEL SOCIO\n"
                    pdf_bytes = generar_pdf_voucher(txt_ns, rdni)
                    st.session_state.ns_pdf_bytes = pdf_bytes
                    
                    cuerpo = f"Estimado/a {rnom} {rape},\n\n¡Bienvenido/a al Banquito La Colmena!\nAdjuntamos su comprobante de ingreso.\n\nAtentamente,\nLa Junta Directiva."
                    exito, st.session_state.ns_msg_correo = enviar_correo_generico(rcor, "Bienvenido al Banquito - Voucher de Ingreso", cuerpo, pdf_bytes, f"Voucher_Ingreso_{rdni}.pdf")
                    st.session_state.ns_done = True
                    st.rerun()

# =============================================================================
# 5. GESTIÓN DE SESIONES Y BÓVEDA DE TIEMPO
# =============================================================================
if 'usuario_id' not in st.session_state:
    st.session_state.update({'usuario_id': None, 'usuario_rol': None, 'usuario_nombre': None, 'vista': 'login', 'tesorero_bloqueado': False, 'tesorero_id_temp': None, 'last_menu_t': None})
if 'socio_logged_in' not in st.session_state:
    st.session_state.update({'socio_logged_in': False, 'socio_dni': None, 'socio_nombre': None})

# =============================================================================
# 6. VISTAS DEL SISTEMA
# =============================================================================

# -----------------------------------------------------------------------------
# VISTA LOGIN
# -----------------------------------------------------------------------------
if not st.session_state.usuario_id and not st.session_state.socio_logged_in:
    if st.session_state.tesorero_bloqueado:
        st.markdown("<br><br>", unsafe_allow_html=True); col_bloq1, col_bloq2, col_bloq3 = st.columns([1,2,1])
        with col_bloq2:
            with st.form("form_desbloqueo_boveda"):
                st.error("🛑 ACCESO A BÓVEDA DENEGADO")
                st.write("El sistema detectó que **hoy no es la fecha agendada** para la asamblea/reunión financiera.")
                st.warning("🚨 Se ha enviado una alerta al CORREO del Presidente notificando este intento.")
                auth_p = st.text_input("Clave del Presidente para autorizar apertura extraordinaria:", type="password")
                components.html("<script>const inputs = window.parent.document.querySelectorAll('input[type=\"password\"]'); if(inputs.length > 0) inputs[0].focus();</script>", height=0)
                c_b1, c_b2 = st.columns(2)
                if c_b1.form_submit_button("🔓 DESBLOQUEAR", type="primary", use_container_width=True):
                    if auth_p == get_config("password_presidente", "123456", str):
                        st.session_state.usuario_id, st.session_state.usuario_rol, st.session_state.usuario_nombre = st.session_state.tesorero_id_temp
                        st.session_state.vista, st.session_state.tesorero_bloqueado = st.session_state.tesorero_id_temp[1], False
                        st.success("✅ Acceso autorizado por Presidencia."); st.rerun()
                    else: st.error("❌ Clave incorrecta.")
                if c_b2.form_submit_button("CANCELAR", use_container_width=True):
                    st.session_state.tesorero_bloqueado = False; st.rerun()
    else:
        st.markdown("<br><br>", unsafe_allow_html=True); col_log1, col_log2, col_log3 = st.columns([1, 2, 1])
        with col_log2:
            st.markdown("<h1 style='text-align: center; color: #b45309;'>🐝 BANQUITO LA COLMENA</h1><p style='text-align: center; color: #64748b; font-size: 1.2rem; font-weight: 700; text-transform: uppercase;'>Portal Integrado de Socios y Directiva</p>", unsafe_allow_html=True)
            t_acc, t_rec = st.tabs(["🔐 INGRESAR", "🆘 RECUPERAR CLAVE"])
            with t_acc:
                with st.form("main_login_form"):
                    input_user = st.text_input("USUARIO INSTITUCIONAL O DNI DE SOCIO:", placeholder="Ej: tesorero o 44556677")
                    input_pass = st.text_input("CONTRASEÑA:", type="password")
                    if st.form_submit_button("INGRESAR AL SISTEMA", type="primary", use_container_width=True):
                        res_dir = db_query("SELECT id, nombre, rol FROM usuarios WHERE usuario=? AND password=?", (input_user, input_pass))
                        if res_dir:
                            u_id, u_nom, u_rol = res_dir[0]
                            if u_rol == 'tesorero' and get_config("proxima_reunion", "2000-01-01", str) != datetime.now().strftime("%Y-%m-%d"):
                                st.session_state.tesorero_bloqueado, st.session_state.tesorero_id_temp = True, (u_id, u_rol, u_nom)
                                enviar_alerta_correo(u_nom); st.rerun()
                            else:
                                st.session_state.update({'usuario_id': u_id, 'usuario_rol': u_rol, 'usuario_nombre': u_nom, 'vista': u_rol}); st.rerun()
                        else:
                            res_soc = db_query("SELECT nombres, apellidos, password FROM socios WHERE dni=?", (input_user,))
                            if res_soc:
                                if not res_soc[0][2]: st.warning("Aún no has creado una contraseña. Ve a la pestaña 'Recuperar Clave'.")
                                elif res_soc[0][2] == input_pass:
                                    st.session_state.update({'socio_logged_in': True, 'socio_dni': input_user, 'socio_nombre': f"{res_soc[0][0]} {res_soc[0][1]}", 'vista': 'socio'}); st.rerun()
                                else: st.error("❌ Contraseña incorrecta.")
                            else: st.error("❌ Usuario o DNI no encontrado.")
            with t_rec:
                if 'pwd_step' not in st.session_state: st.session_state.pwd_step = 1
                if st.session_state.pwd_step == 1:
                    st.write("Te enviaremos un código secreto a tu correo registrado.")
                    with st.form("form_req_code"):
                        r_dni = st.text_input("DNI:")
                        r_nac = st.date_input("Fecha de Nacimiento:", value=date(1990,1,1), min_value=date(1900,1,1), max_value=date.today())
                        if st.form_submit_button("ENVIAR CÓDIGO", type="primary", use_container_width=True):
                            s = db_query("SELECT fecha_nacimiento, password, correo, nombres FROM socios WHERE dni=?", (r_dni,))
                            if s:
                                db_nac, db_pwd, db_cor, db_nom = s[0]
                                if str(r_nac) != db_nac: st.error("La fecha de nacimiento no coincide.")
                                elif not db_cor or db_cor.strip() == "": st.error("No tienes un correo electrónico registrado. Habla con la directiva.")
                                else:
                                    codigo = str(random.randint(100000, 999999))
                                    st.session_state.update({'pwd_code': codigo, 'pwd_dni': r_dni})
                                    cuerpo = f"Hola {db_nom},\n\nTu código es: {codigo}\n\nIngrésalo en la plataforma para continuar."
                                    exito, msg = enviar_correo_generico(db_cor, "Código de Verificación - Banquito La Colmena", cuerpo)
                                    if exito:
                                        st.session_state.pwd_step = 2; st.rerun()
                                    else: st.error(msg)
                            else: st.error("Socio no encontrado.")
                elif st.session_state.pwd_step == 2:
                    st.success("Código enviado a tu correo.")
                    with st.form("form_set_pwd_new"):
                        codigo_in = st.text_input("Código de Verificación (6 dígitos):")
                        r_pwd1, r_pwd2 = st.text_input("Nueva Contraseña:", type="password"), st.text_input("Confirmar Nueva Contraseña:", type="password")
                        c1, c2 = st.columns(2)
                        btn_crear, btn_cancelar = c1.form_submit_button("GUARDAR CONTRASEÑA", type="primary", use_container_width=True), c2.form_submit_button("CANCELAR", use_container_width=True)
                        if btn_cancelar: st.session_state.pwd_step = 1; st.rerun()
                        if btn_crear:
                            if codigo_in != st.session_state.pwd_code: st.error("El código es incorrecto.")
                            elif len(r_pwd1) < 4: st.warning("La contraseña debe tener al menos 4 caracteres.")
                            elif r_pwd1 != r_pwd2: st.error("Las contraseñas no coinciden.")
                            else:
                                db_query("UPDATE socios SET password=? WHERE dni=?", (r_pwd1, st.session_state.pwd_dni), fetch=False)
                                st.session_state.pwd_step = 1; st.success("✅ Contraseña guardada. Ya puedes iniciar sesión.")

# -----------------------------------------------------------------------------
# VISTA: SOCIO
# -----------------------------------------------------------------------------
elif st.session_state.socio_logged_in:
    render_top_header()
    s_dni = st.session_state.socio_dni
    soc_data = db_query("SELECT nombres, apellidos, acciones FROM socios WHERE dni=?", (s_dni,))
    if not soc_data: st.session_state.socio_logged_in = False; st.rerun()
    acc_socio = soc_data[0][2]
    
    st.write(f"**ACCIONES ACTIVAS:** {acc_socio}")
    
    f_reu_dt = datetime.strptime(get_config("proxima_reunion", "2000-01-01", str), "%Y-%m-%d").date() if get_config("proxima_reunion", "2000-01-01", str) != "2000-01-01" else date(2000, 1, 1)
    if f_reu_dt > date(2000, 1, 1) and date.today() <= f_reu_dt:
        h_format = get_config("proxima_reunion_hora", "16:00", str)
        try: h_format = datetime.strptime(h_format, '%H:%M').strftime('%I:%M %p')
        except: pass
        st.warning(f"📅 **PRÓXIMA REUNIÓN CONFIRMADA:** EL DÍA **{f_reu_dt.strftime('%d/%m/%Y')}** A LAS **{h_format}**.")

    a_pagar_cumple, cuota_c = 0.0, get_config("cuota_cumpleanos", 0.0)
    if get_config("jugar_cumpleanos", "SI", str) == "SI":
        mes_actual, dia_actual = datetime.now().month, datetime.now().day
        cumpleaneros = db_query("SELECT dni, nombres, apellidos, fecha_nacimiento FROM socios WHERE acciones > 0")
        cumplen_este_mes_alerta = [{"dni": d, "nom": f"{n.split()[0]} {a.split()[0]}", "dia": datetime.strptime(fnac, "%Y-%m-%d").day} for d, n, a, fnac in cumpleaneros if fnac and datetime.strptime(fnac, "%Y-%m-%d").month == mes_actual and dia_actual <= datetime.strptime(fnac, "%Y-%m-%d").day + 1]
        
        if cumplen_este_mes_alerta:
            cumplen_este_mes_alerta.sort(key=lambda x: x["dia"])
            nombres_cumple = ", ".join([f"{c['nom']} (Día {c['dia']})" for c in cumplen_este_mes_alerta])
            a_pagar_cumple = sum([cuota_c for c in cumplen_este_mes_alerta if c["dni"] != s_dni])
            st.success(f"🎉 **¡ESTAMOS DE FIESTA!** FESTEJANDO A: **{nombres_cumple}**. \n\n💡 **TU CUOTA DE CUMPLEAÑOS A PAGAR ES:** S/ {f_m(a_pagar_cumple)}." if a_pagar_cumple > 0 else f"🎉 **¡ESTAMOS DE FIESTA!** FESTEJANDO A: **{nombres_cumple}**. (¡ES TU CELEBRACIÓN, TÚ NO APORTAS!)")
        ui_cumpleanos_admin(es_tesorero=False) # Solo pinta la tablita de fechas
                
    coms = db_query("SELECT mensaje, fecha FROM comunicados WHERE mensaje NOT LIKE '%anulación%' AND mensaje NOT LIKE '%anuló%' ORDER BY id DESC")
    if coms:
        with st.expander("📢 HISTORIAL DE COMUNICADOS (MURO DE AVISOS)", expanded=False):
            for msg, f_msg in coms: st.write(f"🕒 **{format_fecha(f_msg)}**\n📝 {msg}"); st.divider()
    
    menu_s = st.radio("MENÚ DEL SOCIO:", ["📊 RESUMEN Y PRÉSTAMOS", "📅 HISTORIAL DE PAGOS", "📥 MESA DE PARTES", "🤝 SIM. DE PRÉSTAMOS", "📈 SIM. DE INVERSIÓN", "🗳️ VOTO VIRTUAL"], horizontal=True)
    
    if menu_s == "📊 RESUMEN Y PRÉSTAMOS":
        tot_ah = db_query("SELECT SUM(monto) FROM movimientos WHERE tipo LIKE '%Aporte%' AND tipo LIKE ?", (f"%{s_dni}%",))[0][0] or 0.0
        total_prestamos_prox = 0.0
        tasa, amort_pct_act, amort_pct_val, m_min_fijo = get_config("interes_prestamo", 0.0)/100.0, get_config("amort_porcentaje_activo", "NO", str), get_config("amort_porcentaje_valor", 0.0)/100.0, get_config("monto_minimo_capital", 0.0)
        
        deudas = db_query("SELECT id, accion_asociada, saldo_actual, monto_original, conteo_minimos FROM prestamos WHERE dni_socio=? AND estado='ACTIVO'", (s_dni,))
        if deudas:
            for d in deudas:
                d_saldo, d_orig, d_conteo = d[2], d[3], d[4]
                min_req = min(float(math.ceil(d_orig * amort_pct_val)), d_saldo) if amort_pct_act == "SI" and (d_conteo >= 3 or datetime.now().month > int(get_config("mes_limite_minimos", 12))) else min(m_min_fijo, d_saldo)
                total_prestamos_prox += (min_req + float(math.ceil(d_saldo * tasa)))
                
        cm1, cm2, cm3 = st.columns(3)
        cm1.metric("Aportes Totales Ahorrados", f"S/ {f_m(tot_ah)}")
        cm2.metric("Aporte Promedio x Acción", f"S/ {f_m(tot_ah / acc_socio if acc_socio > 0 else 0.0)}")
        cm3.metric("Monto a Pagar Próx. Reunión", f"S/ {f_m((acc_socio * get_config('aporte_mensual', 0.0)) + total_prestamos_prox + a_pagar_cumple)}", help="Incluye aportes obligatorios, amortización mínima a capital, intereses y cuotas de cumpleaños si aplican.")
        
        st.divider(); st.subheader("💳 MIS PRÉSTAMOS ACTIVOS")
        if deudas:
            for d in deudas:
                st.warning(f"**Préstamo en Acción {d[1]}** | Saldo Capital Restante: **S/ {f_m(d[2])}**")
                st.download_button(label=f"📄 DESCARGAR CRONOGRAMA ACTUALIZADO (ACCIÓN {d[1]})", data=generar_pdf_estado_cuenta(st.session_state.socio_nombre, s_dni, d[1]), file_name=f"Cronograma_Actualizado_Acc{d[1]}.pdf", mime="application/pdf", key=f"btn_dl_{d[0]}")
        else: st.success("No tienes deudas activas en este momento.")
            
    elif menu_s == "📅 HISTORIAL DE PAGOS":
        st.subheader("📅 HISTORIAL DE PAGOS Y APORTES")
        cf1, cf2 = st.columns(2); f_ini, f_fin = cf1.date_input("Desde:", value=date(date.today().year, 1, 1)), cf2.date_input("Hasta:", value=date.today())
        if st.button("BUSCAR MOVIMIENTOS", type="primary"):
            nom_fmt = f"{soc_data[0][0].split()[0]} {soc_data[0][1].split()[0] if soc_data[0][1] else ''}".strip()
            historial_soc = db_query("SELECT fecha, tipo, monto FROM movimientos WHERE (tipo LIKE ? OR tipo LIKE ?) AND date(fecha) >= ? AND date(fecha) <= ? ORDER BY fecha DESC", (f"%{s_dni}%", f"%{nom_fmt}%", str(f_ini), str(f_fin)))
            if historial_soc:
                df_h = pd.DataFrame(historial_soc, columns=["Fecha y Hora", "Detalle de Operación", "Monto"])
                df_h["Fecha y Hora"], df_h["Detalle de Operación"], df_h["Monto"] = df_h["Fecha y Hora"].apply(format_fecha), df_h["Detalle de Operación"].apply(format_movimiento), df_h["Monto"].apply(lambda x: f"S/ {f_m(x)}")
                st.dataframe(df_h, use_container_width=True)
            else: st.info("No se encontraron pagos ni aportes en este rango de fechas.")
                
    elif menu_s == "📥 MESA DE PARTES":
        st.subheader("📥 MIS TRÁMITES (MESA DE PARTES)")
        mis_tramites = db_query("SELECT fecha, tipo, estado, respuesta FROM tramites WHERE dni_socio=? ORDER BY id DESC", (s_dni,))
        if mis_tramites:
            df_mt = pd.DataFrame(mis_tramites, columns=["Fecha", "Tipo de Trámite", "Estado Actual", "Respuesta/Resolución"])
            df_mt["Fecha"] = df_mt["Fecha"].apply(format_fecha); st.dataframe(df_mt, use_container_width=True)
        else: st.info("No tienes trámites ni solicitudes en curso.")

    elif menu_s == "🤝 SIM. DE PRÉSTAMOS":
        st.subheader("🤝 SIMULADOR DE PRÉSTAMOS")
        tasa_sim, m_min_sim, amort_pct_act_sim, amort_pct_val_sim, tope_act_sim, tope_monto_sim = get_config("interes_prestamo", 0.0)/100.0, get_config("monto_minimo_capital", 50.0), get_config("amort_porcentaje_activo", "NO", str), get_config("amort_porcentaje_valor", 0.0)/100.0, get_config("tope_prestamo_activo", "NO", str), get_config("tope_prestamo_monto", 0.0)
        dict_deudas = {d[0]: {'saldo': d[1], 'orig': d[2]} for d in db_query("SELECT accion_asociada, saldo_actual, monto_original FROM prestamos WHERE dni_socio=? AND estado='ACTIVO'", (s_dni,))}
        
        c_s1, c_s2 = st.columns(2)
        acc_sim = c_s1.selectbox("Selecciona la Acción a simular:", [i for i in range(1, acc_socio + 1)])
        saldo_act_sim = dict_deudas[acc_sim]['saldo'] if acc_sim in dict_deudas else 0.0
        c_s2.info(f"💳 Deuda actual en esta Acción: **S/ {f_m(saldo_act_sim)}**")
        
        disp_sim = max(0.0, tope_monto_sim - saldo_act_sim) if tope_act_sim == "SI" and tope_monto_sim > 0 else float('inf')
        if disp_sim != float('inf'): st.write(f"**Límite Máximo Activo:** S/ {f_m(tope_monto_sim)} (Puedes solicitar hasta S/ {f_m(disp_sim)} más en esta acción)")
        
        monto_req_sim = st.number_input("Monto a solicitar (S/):", min_value=0.0, max_value=float(disp_sim) if disp_sim != float('inf') else None, step=100.0)
        
        if st.button("🔮 CALCULAR SIMULACIÓN", type="primary"):
            if monto_req_sim <= 0: st.warning("Ingresa un monto mayor a 0 para simular.")
            else:
                nuevo_saldo_sim = sp_sim = saldo_act_sim + monto_req_sim
                tot_i_sim, primera_cuota_cap, primera_cuota_int, es_primera = 0.0, 0.0, 0.0, True
                
                while sp_sim > 0.01:
                    am_sim = min(float(math.ceil((saldo_act_sim + monto_req_sim) * amort_pct_val_sim)) if float(math.ceil((saldo_act_sim + monto_req_sim) * amort_pct_val_sim)) >= m_min_sim else float(m_min_sim), sp_sim) if amort_pct_act_sim == "SI" else min(m_min_sim, sp_sim)
                    int_mes_sim = float(math.ceil(sp_sim * tasa_sim))
                    if es_primera: primera_cuota_cap, primera_cuota_int, es_primera = am_sim, int_mes_sim, False
                    tot_i_sim += int_mes_sim; sp_sim -= am_sim
                
                st.divider(); st.markdown("### 📊 RESULTADOS DE LA SIMULACIÓN"); col_r1, col_r2, col_r3 = st.columns(3)
                col_r1.metric("Nueva Deuda Total (Capital)", f"S/ {f_m(nuevo_saldo_sim)}", f"+ S/ {f_m(monto_req_sim)} solicitados")
                col_r2.metric("Intereses Proyectados Totales", f"S/ {f_m(tot_i_sim)}")
                col_r3.metric("Total a Devolver (Cap + Int)", f"S/ {f_m(nuevo_saldo_sim + tot_i_sim)}")
                st.info(f"**🔹 Proyección de tu Próxima Cuota (Mes 1):**\n- Amortización a Capital: S/ {f_m(primera_cuota_cap)}\n- Interés del mes: S/ {f_m(primera_cuota_int)}\n- **Total a pagar en cuota 1: S/ {f_m(primera_cuota_cap + primera_cuota_int)}**")

    elif menu_s == "📈 SIM. DE INVERSIÓN":
        st.subheader("📈 SIMULADOR DE INVERSIÓN (COMPRA DE ACCIONES)")
        cant_acc_soc = st.number_input("ACCIONES A ADQUIRIR:", 1, 4, 1, key="sim_inv_socio")
        if st.button("CALCULAR INVERSIÓN", use_container_width=True, key="btn_sim_inv_socio"):
            c_hist, i_hist = calcular_nivelacion_por_accion()
            t_cap, t_int, t_ins = c_hist * cant_acc_soc, math.ceil(i_hist) * cant_acc_soc, get_config("cuota_inscripcion", 0.0) * cant_acc_soc
            tot_hoy = t_cap + t_int + t_ins
            
            nuevo_c_hist = c_hist + get_config("aporte_mensual", 0.0)
            t_cap_prox, t_int_prox = nuevo_c_hist * cant_acc_soc, math.ceil(i_hist + (nuevo_c_hist * (get_config("interes_prestamo", 0.0) / 100.0))) * cant_acc_soc
            
            m_actual_idx = datetime.now().month - 1
            meses_n = ["Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio", "Julio", "Agosto", "Septiembre", "Octubre", "Noviembre", "Diciembre"]
            
            col_h, col_p = st.columns(2)
            with col_h:
                st.success(f"### Inversión {meses_n[m_actual_idx]}:\n### S/ {f_m(tot_hoy)}")
                st.write(f"- Inscripción ({cant_acc_soc} acc): S/ {f_m(t_ins)}\n- Aporte Nivelado: S/ {f_m(t_cap)}\n- Interés Nivelado: S/ {f_m(t_int)}")
            with col_p:
                st.warning(f"### Inversión {meses_n[(m_actual_idx + 1) % 12]}:\n### S/ {f_m(t_cap_prox + t_int_prox + t_ins)}")
                st.write(f"- Inscripción ({cant_acc_soc} acc): S/ {f_m(t_ins)}\n- Aporte Nivelado: S/ {f_m(t_cap_prox)}\n- Interés Nivelado: S/ {f_m(t_int_prox)}")

    elif menu_s == "🗳️ VOTO VIRTUAL":
        st.subheader("🗳️ VOTO VIRTUAL (VOTACIONES)")
        votaciones_abiertas = db_query("SELECT id, pregunta, opciones, fecha_creacion FROM votaciones WHERE estado='ABIERTA' ORDER BY id DESC")
        if votaciones_abiertas:
            st.write("Tu voto es estrictamente igualitario. Cada socio equivale a un (1) solo voto, independientemente de sus acciones.")
            for v_id, preg, ops_str, f_crea in votaciones_abiertas:
                with st.container(border=True):
                    st.markdown(f"#### {preg}"); st.caption(f"Publicada el: {f_crea}")
                    ya_voto = db_query("SELECT opcion FROM votos WHERE id_votacion=? AND dni_socio=?", (v_id, s_dni))
                    if ya_voto: st.success(f"✅ Ya emitiste tu voto en esta consulta. Elegiste: **{ya_voto[0][0]}**")
                    else:
                        opcion_elegida = st.radio(f"Selecciona tu respuesta:", [o.strip() for o in ops_str.split(',')], key=f"radio_voto_{v_id}")
                        if st.button("🗳️ EMITIR MI VOTO", type="primary", key=f"btn_votar_{v_id}"):
                            db_query("INSERT INTO votos (id_votacion, dni_socio, opcion, peso) VALUES (?,?,?,?)", (v_id, s_dni, opcion_elegida, 1), fetch=False)
                            st.success("Voto registrado con éxito."); st.rerun()
        else: st.info("No hay votaciones abiertas en este momento.")
            
        st.divider()
        with st.expander("📊 VER RESULTADOS DE VOTACIONES PASADAS"):
            vot_cerradas = db_query("SELECT id, pregunta, opciones, fecha_creacion FROM votaciones WHERE estado='CERRADA' ORDER BY id DESC")
            if vot_cerradas:
                for v_id, preg, ops_str, f_crea in vot_cerradas:
                    st.write(f"**{preg}**")
                    resultados = db_query("SELECT opcion, COUNT(*) as votos FROM votos WHERE id_votacion=? GROUP BY opcion", (v_id,))
                    if resultados: st.bar_chart(pd.DataFrame(resultados, columns=["Opción", "Votos (1 x Socio)"]).set_index("Opción"), color="#2563eb")
                    else: st.write("Nadie votó en esta consulta.")
                    st.write("---")
            else: st.write("No hay historial de votaciones cerradas.")

# -----------------------------------------------------------------------------
# VISTA: SUPERADMIN
# -----------------------------------------------------------------------------
elif st.session_state.vista == 'superadmin':
    render_top_header()
    menu_t = st.radio("MÓDULOS DEL ADMINISTRADOR:", ["📝 REGISTRAR SOCIOS", "⚙️ ASIGNAR JUNTA DIRECTIVA", "🔑 ACCESOS DE SOCIOS"], horizontal=True)

    if menu_t == "📝 REGISTRAR SOCIOS": ui_registro_nuevo_socio()
    elif menu_t == "⚙️ ASIGNAR JUNTA DIRECTIVA":
        ffun_str = get_config("fecha_fundacion", datetime.now().strftime("%Y-%m-%d"), str)
        try: ffun_date = datetime.strptime(ffun_str, "%Y-%m-%d").date()
        except: ffun_date = date.today()
            
        ffun = st.date_input("Fecha de Fundación", value=ffun_date)
        # Cargamos la lista de socios
        lista_socios_db = db_query("SELECT nombres, apellidos, correo FROM socios ORDER BY nombres ASC")
        opciones_socios = ["No asignado"] + [f"{r[0]} {r[1]}".strip() for r in lista_socios_db]

        st.divider(); st.write("#### PRESIDENCIA")
        cpres = st.selectbox("Presidente(a)", opciones_socios, index=opciones_socios.index(get_config("presidente", "No asignado", str)) if get_config("presidente", "No asignado", str) in opciones_socios else 0)
        
        # --- LÓGICA DE DETECCIÓN MEJORADA ---
        correo_detectado = ""
        if cpres != "No asignado":
            # Buscamos en la lista que ya cargamos para evitar errores de consulta SQL
            for r in lista_socios_db:
                nombre_completo_iter = f"{r[0]} {r[1]}".strip()
                if nombre_completo_iter == cpres:
                    correo_detectado = r[2] if r[2] else ""
                    break
        
        if cpres != "No asignado":
            if correo_detectado:
                st.success(f"📧 Correo vinculado para Alertas: **{correo_detectado}**")
            else:
                st.error("⚠️ El socio seleccionado no tiene correo registrado en el padrón.")

        cpass = st.text_input("Clave Secreta de Autorización (Romper Cerrojos)", get_config("password_presidente", "123456", str), type="password")
        
        st.divider(); st.write("#### TESORERÍA")
        ctes = st.selectbox("Tesorero(a)", opciones_socios, index=opciones_socios.index(get_config("tesorero", "No asignado", str)) if get_config("tesorero", "No asignado", str) in opciones_socios else 0)
        u_t = db_query("SELECT usuario, password FROM usuarios WHERE rol='tesorero'")
        ut_usr = st.text_input("Usuario de Acceso (Tesorero)", u_t[0][0] if u_t else "tesorero")
        ut_pwd = st.text_input("Clave de Acceso (Tesorero)", u_t[0][1] if u_t else "teso123", type="password")
        
        st.divider(); st.write("#### SECRETARÍA")
        csec = st.selectbox("Secretario(a)", opciones_socios, index=opciones_socios.index(get_config("secretario", "No asignado", str)) if get_config("secretario", "No asignado", str) in opciones_socios else 0)
        u_s = db_query("SELECT usuario, password FROM usuarios WHERE rol='secretario'")
        us_usr = st.text_input("Usuario de Acceso (Secretario)", u_s[0][0] if u_s else "secretaria")
        us_pwd = st.text_input("Clave de Acceso (Secretario)", u_s[0][1] if u_s else "secre123", type="password")
        
        if st.button("💾 GUARDAR CONFIGURACIÓN", type="primary"):
            # Guardamos el correo detectado en la tabla configuracion
            db_query("UPDATE configuracion SET valor=? WHERE clave='correo_presidente'", (correo_detectado,), fetch=False)
            
            for clave, val in [('fecha_fundacion', str(ffun)), ('presidente', cpres), ('password_presidente', cpass), ('tesorero', ctes), ('secretario', csec)]: 
                db_query("UPDATE configuracion SET valor=? WHERE clave=?", (val, clave), fetch=False)
            
            # Actualizar perfiles de usuario
            if db_query("SELECT id FROM usuarios WHERE rol='tesorero'"): 
                db_query("UPDATE usuarios SET nombre=?, usuario=?, password=? WHERE rol='tesorero'", (ctes, ut_usr, ut_pwd), fetch=False)
            else: 
                db_query("INSERT INTO usuarios (nombre, usuario, password, rol) VALUES (?, ?, ?, 'tesorero')", (ctes, ut_usr, ut_pwd), fetch=False)
                
            if db_query("SELECT id FROM usuarios WHERE rol='secretario'"): 
                db_query("UPDATE usuarios SET nombre=?, usuario=?, password=? WHERE rol='secretario'", (csec, us_usr, us_pwd), fetch=False)
            else: 
                db_query("INSERT INTO usuarios (nombre, usuario, password, rol) VALUES (?, ?, ?, 'secretario')", (csec, us_usr, us_pwd), fetch=False)
            
            st.success("Configuración actualizada correctamente.")
            st.rerun()
            
    elif menu_t == "🔑 ACCESOS DE SOCIOS":
        st.write("Si un socio perdió acceso a su correo o no puede entrar a su portal, puedes ver su contraseña actual o asignarle una nueva aquí.")
        if 'pwd_success_msg' in st.session_state: st.success(st.session_state.pwd_success_msg); del st.session_state.pwd_success_msg
            
        socios_pwd = db_query("SELECT dni, nombres, apellidos, password FROM socios ORDER BY nombres ASC")
        if socios_pwd:
            dict_sp = {f"{s[0]} - {s[1]} {s[2]}": s[0] for s in socios_pwd}
            dni_sp = dict_sp[st.selectbox("SELECCIONE AL SOCIO:", list(dict_sp.keys()), key="select_pwd_socio")]
            
            with st.container():
                fresh_data = db_query("SELECT nombres, apellidos, password FROM socios WHERE dni=?", (dni_sp,))
                if fresh_data:
                    nom_sp, pwd_sp = f"{fresh_data[0][0]} {fresh_data[0][1]}", fresh_data[0][2]
                    st.markdown(f"**Socio Seleccionado:** {nom_sp}")
                    st.markdown(f"🟢 **Contraseña actual:** {pwd_sp}" if pwd_sp else "🟠 **Estado:** Este socio aún no ha registrado una contraseña.")
                    st.markdown("---"); st.write("¿Deseas cambiar la contraseña manualmente?")
                    
                    n_pwd = st.text_input("Escriba la nueva contraseña:", type="password", key="admin_super_pwd_input")
                    if st.button("ACTUALIZAR CONTRASEÑA", type="primary", key="admin_super_pwd_btn"):
                        if len(n_pwd) >= 4:
                            db_query("UPDATE socios SET password=? WHERE dni=?", (n_pwd, dni_sp), fetch=False)
                            st.session_state.pwd_success_msg = f"Contraseña actualizada correctamente para {nom_sp}."
                            st.rerun()
                        else: st.warning("La contraseña debe tener al menos 4 caracteres.")
        else: st.info("No hay socios registrados en el sistema.")

# -----------------------------------------------------------------------------
# VISTA: SECRETARÍA
# -----------------------------------------------------------------------------
elif st.session_state.vista == 'secretario':
    render_top_header()
    
    mes_actual, dia_actual = datetime.now().month, datetime.now().day
    cumplen_este_mes_alerta = [f"{n.split()[0]} {a.split()[0]}" for n, a, fnac in db_query("SELECT nombres, apellidos, fecha_nacimiento FROM socios WHERE acciones > 0") if fnac and datetime.strptime(fnac, "%Y-%m-%d").month == mes_actual and dia_actual <= datetime.strptime(fnac, "%Y-%m-%d").day + 1]
    if cumplen_este_mes_alerta: st.info(f"🎂 **ALERTA DE CUMPLEAÑOS:** Próximos a cumplir años: **{', '.join(cumplen_este_mes_alerta)}**. " + ("Los socios ya fueron notificados para realizar el abono." if get_config("jugar_cumpleanos", "SI", str) == "SI" else "Recuerde coordinar el presente institucional."))
    
    m = st.radio("MENÚ PRINCIPAL:", ["📅 AGENDAR REUNIÓN", "✏️ ACTUALIZAR SOCIOS", "📥 MESA DE PARTES", "📜 CONSTANCIAS", "📢 COMUNICADOS", "🙋 ASISTENCIA", "🎂 CUMPLEAÑOS", "🗳️ VOTACIONES"], horizontal=True)
    
    if m == "📅 AGENDAR REUNIÓN":
        st.write("El Tesorero SOLO podrá iniciar sesión para cobrar o prestar dinero en la fecha seleccionada. Además, se agregará un aviso automático al historial del portal de socios.")
        try: f_obj = datetime.strptime(get_config("proxima_reunion", "2000-01-01", str), "%Y-%m-%d").date()
        except: f_obj = datetime.now().date()
        if getattr(f_obj, 'year', 2000) == 2000: f_obj = datetime.now().date()
        try: h_obj = datetime.strptime(get_config("proxima_reunion_hora", "16:00", str), "%H:%M").time()
        except: h_obj = datetime.strptime("16:00", "%H:%M").time()
        
        c1, c2 = st.columns(2)
        nueva_fecha = c1.date_input("Fecha de la Próxima Reunión Oficial:", value=f_obj)
        nueva_hora = c2.time_input("Hora de la Reunión:", value=h_obj)
        
        if st.button("💾 GUARDAR FECHA Y PUBLICAR AVISO", type="primary"):
            db_query("UPDATE configuracion SET valor=? WHERE clave='proxima_reunion'", (str(nueva_fecha),), fetch=False)
            db_query("UPDATE configuracion SET valor=? WHERE clave='proxima_reunion_hora'", (nueva_hora.strftime("%H:%M"),), fetch=False)
            db_query("INSERT INTO comunicados (mensaje, fecha) VALUES (?,?)", (f"Se ha agendado la próxima asamblea general y apertura de caja para el día {format_fecha(str(nueva_fecha))} a las {nueva_hora.strftime('%I:%M %p')}.", datetime.now().strftime("%d/%m/%Y %I:%M %p")), fetch=False)
            st.success(f"✅ Bóveda programada para el {format_fecha(str(nueva_fecha))}. El aviso oficial se ha agregado al historial de los socios.")

    elif m == "✏️ ACTUALIZAR SOCIOS":
        dni_s = st.text_input("Ingrese DNI del Socio para actualizar sus datos:")
        if dni_s:
            if 'update_success_sec' in st.session_state: st.success(st.session_state.update_success_sec); del st.session_state['update_success_sec']
            s = db_query("SELECT nombres, apellidos, telefono, direccion, correo, sexo, fecha_nacimiento FROM socios WHERE dni=?", (dni_s,))
            if s:
                nom, ape, tel, dir_, cor, sex, fnac_str = s[0]
                st.write(f"Editando a: **{nom} {ape}**")
                with st.form("edit_soc"):
                    try: fnac_obj = datetime.strptime(fnac_str, "%Y-%m-%d").date() if fnac_str else date(1990, 1, 1)
                    except: fnac_obj = date(1990, 1, 1)
                    
                    c1, c2 = st.columns(2)
                    unom, uape = c1.text_input("Nombres", value=nom), c2.text_input("Apellidos", value=ape)
                    utel, udir = c1.text_input("Teléfono", value=tel if tel else ""), c2.text_input("Dirección", value=dir_ if dir_ else "")
                    ucor, usex = c1.text_input("Correo", value=cor if cor else ""), c2.selectbox("Sexo", ["Masculino", "Femenino"], index=0 if sex == "Masculino" else 1)
                    unac = c1.date_input("Fecha de Nacimiento", value=fnac_obj, min_value=date(1900, 1, 1), max_value=date.today())
                    
                    if st.form_submit_button("💾 GUARDAR CAMBIOS EN EL PADRÓN", type="primary"):
                        db_query("UPDATE socios SET nombres=?, apellidos=?, telefono=?, direccion=?, correo=?, sexo=?, fecha_nacimiento=? WHERE dni=?", (unom, uape, utel, udir, ucor, usex, str(unac), dni_s), fetch=False)
                        st.session_state.update_success_sec = "✅ Datos personales actualizados con éxito en la Base de Datos."; st.rerun()
            else: st.error("Socio no encontrado.")

    elif m == "📥 MESA DE PARTES":
        with st.form("form_mp"):
            tdni, ttipo, tdet = st.text_input("DNI Socio Solicitante:"), st.selectbox("Tipo de Trámite:", ["Solicitud de Renuncia", "Justificación de Inasistencia", "Queja / Sugerencia", "Otros"]), st.text_area("Detalle del documento recibido:")
            if st.form_submit_button("REGISTRAR INGRESO DE DOCUMENTO", type="primary"):
                if tdni and tdet:
                    db_query("INSERT INTO tramites (dni_socio, tipo, detalle, estado, fecha, respuesta) VALUES (?,?,?,?,?,?)", (tdni, ttipo, tdet, "En Revisión", datetime.now().strftime("%Y-%m-%d"), ""), fetch=False)
                    st.success("Trámite registrado con éxito y en espera de revisión por la Directiva.")
                else: st.warning("DNI y Detalle son obligatorios.")
        
        st.divider(); st.write("### GESTIÓN DE TRÁMITES")
        tramites_pendientes = db_query("SELECT id, dni_socio, tipo, estado FROM tramites ORDER BY id DESC")
        if tramites_pendientes:
            with st.expander("🔄 Actualizar Estado de un Trámite", expanded=True):
                with st.form("form_update_tr"):
                    opciones_tr = {f"ID {t[0]} - DNI: {t[1]} - {t[2]} ({t[3]})": t[0] for t in tramites_pendientes}
                    id_tr_sel = opciones_tr[st.selectbox("Seleccione el Trámite a actualizar:", list(opciones_tr.keys()))]
                    nuevo_est, nueva_resp = st.selectbox("Nuevo Estado:", ["En Revisión", "Aprobado", "Rechazado", "Finalizado / Archivo"]), st.text_input("Respuesta Oficial de la Directiva:")
                    if st.form_submit_button("GUARDAR ACTUALIZACIÓN", type="primary"):
                        db_query("UPDATE tramites SET estado=?, respuesta=? WHERE id=?", (nuevo_est, nueva_resp, id_tr_sel), fetch=False)
                        st.success(f"Trámite ID {id_tr_sel} actualizado correctamente.")

        st.divider(); st.write("### HISTORIAL GENERAL DE TRÁMITES")
        df_t = pd.DataFrame(db_query("SELECT id, dni_socio, tipo, estado, fecha, respuesta FROM tramites ORDER BY id DESC"), columns=["ID", "DNI", "Tipo", "Estado", "Fecha Ingreso", "Respuesta/Resolución"])
        df_t["Fecha Ingreso"] = df_t["Fecha Ingreso"].apply(format_fecha); st.dataframe(df_t, use_container_width=True)

    elif m == "📜 CONSTANCIAS":
        cdni = st.text_input("DNI del Socio:")
        if cdni:
            s = db_query("SELECT nombres, apellidos FROM socios WHERE dni=?", (cdni,))
            if s:
                nom_comp = f"{s[0][0]} {s[0][1]}"
                st.write(f"Socio: **{nom_comp}**"); st.divider()
                c1, c2 = st.columns(2)
                with c1:
                    st.info("📜 Constancia de Membresía")
                    if st.button("GENERAR CONSTANCIA DE SOCIO ACTIVO", use_container_width=True):
                        st.download_button("📥 DESCARGAR CONSTANCIA PDF", generar_pdf_constancia("Socio Activo", nom_comp, cdni), f"Constancia_Socio_Activo_{cdni}.pdf", type="primary", use_container_width=True)
                with c2:
                    st.info("📜 Constancia Financiera")
                    if not db_query("SELECT id FROM prestamos WHERE dni_socio=? AND estado='ACTIVO'", (cdni,)):
                        if st.button("GENERAR CONSTANCIA DE NO ADEUDO", use_container_width=True):
                            st.download_button("📥 DESCARGAR CONSTANCIA PDF", generar_pdf_constancia("No Adeudo", nom_comp, cdni), f"Constancia_No_Adeudo_{cdni}.pdf", type="primary", use_container_width=True)
                    else: st.error("El socio tiene deudas activas en el Banquito. NO es posible emitir Constancia de No Adeudo.")

    elif m == "📢 COMUNICADOS":
        st.write("El texto que escribas aquí se añadirá al Muro de Avisos del portal de los socios.")
        msg = st.text_area("Escriba el comunicado:")
        if st.button("PUBLICAR AVISO A TODOS LOS SOCIOS", type="primary"):
            db_query("INSERT INTO comunicados (mensaje, fecha) VALUES (?,?)", (msg, datetime.now().strftime("%Y-%m-%d %H:%M:%S")), fetch=False)
            st.success("Comunicado publicado. Todos los socios lo verán al instante en su historial.")
        st.divider(); st.write("### 🧹 LIMPIAR PIZARRA")
        if st.button("🗑️ BORRAR TODO EL HISTORIAL DE COMUNICADOS"):
            db_query("DELETE FROM comunicados", fetch=False); db_query("UPDATE configuracion SET valor=? WHERE clave='proxima_reunion'", ("2000-01-01",), fetch=False)
            st.success("La pizarra de comunicados ha sido vaciada con éxito y el aviso de reunión se ha ocultado.")

    elif m == "🙋 ASISTENCIA":
        fecha_as = st.date_input("Fecha de Asamblea", value=datetime.now()); st.write("Marque la asistencia de los socios:")
        lista_socios = db_query("SELECT dni, nombres, apellidos FROM socios ORDER BY nombres ASC")
        with st.form("form_asistencia"):
            for sc in lista_socios: st.radio(f"👤 {sc[1]} {sc[2]} (DNI: {sc[0]})", ["Presente", "Tardanza", "Faltó"], key=f"as_{sc[0]}", horizontal=True); st.divider()
            if st.form_submit_button("💾 GUARDAR REGISTRO DE ASISTENCIA COMPLETO", type="primary"):
                for sc in lista_socios: db_query("INSERT INTO asistencia (dni_socio, fecha_asamblea, estado) VALUES (?,?,?)", (sc[0], str(fecha_as), st.session_state[f"as_{sc[0]}"]), fetch=False)
                st.success(f"La asistencia para el día {format_fecha(str(fecha_as))} fue guardada exitosamente in los registros.")
                
    elif m == "🎂 CUMPLEAÑOS": ui_cumpleanos_admin(es_tesorero=False)
    elif m == "🗳️ VOTACIONES": ui_votaciones_admin()

# -----------------------------------------------------------------------------
# VISTA: TESORERO
# -----------------------------------------------------------------------------
elif st.session_state.vista == 'tesorero':
    render_top_header()
    opciones_menu_t = ["📊 PANEL DE CONTROL", "👥 SOCIOS Y COMPRAS", "💳 PAGOS Y PRÉSTAMOS", "💰 CAJA GLOBAL", "📥 CAJA CHICA", "⚙️ REGLAS FINANCIERAS", "🎁 REPARTO UTILIDADES", "↩️ ANULAR OPERACIÓN"]
    
    menu_t = st.radio("MÓDULOS FINANCIEROS:", opciones_menu_t, horizontal=True)

    # Lógica para auto-bloquear las reglas si sale de la pestaña
    if st.session_state.get('last_menu_t') != menu_t:
        st.session_state.reglas_unlocked = False
        st.session_state.last_menu_t = menu_t
    
    if menu_t == "📊 PANEL DE CONTROL": ui_panel_control()
                
    elif menu_t == "👥 SOCIOS Y COMPRAS":
        t1, t2 = st.tabs(["🔍 BÚSQUEDA AVANZADA Y ACCIONES EXTRA", "📝 REGISTRO DE NUEVO SOCIO"])
        with t1:
            dni_busq = st.text_input("🔍 BUSCAR DNI SOCIO:", on_change=limpiar_formularios_socio)
            if dni_busq:
                soc_full = db_query("SELECT nombres, apellidos, telefono, direccion, correo, sexo, fecha_nacimiento, fecha_ingreso, acciones, es_fundador FROM socios WHERE dni=?", (dni_busq,))
                if soc_full:
                    nom, ape, tel, dir_, cor, sex, fnac_str, fing, acc_act, esf = soc_full[0]
                    nombre_completo = f"{nom} {ape}"
                    st.markdown(f"### {'🏅 SOCIO FUNDADOR' if esf == 1 else '👤 SOCIO REGULAR'}: {nombre_completo}")
                    c1, c2, c3 = st.columns(3)
                    c1.write(f"**DNI:** {dni_busq}\n\n**Teléfono:** {tel or '---'}\n\n**Correo:** {cor or '---'}")
                    c2.write(f"**Dirección:** {dir_ or '---'}\n\n**Sexo:** {sex or '---'}\n\n**Fecha Ingreso:** {format_fecha(fing)}")
                    tot_ah = db_query("SELECT SUM(monto) FROM movimientos WHERE tipo LIKE '%Aporte%' AND tipo LIKE ?", (f"%{dni_busq}%",))[0][0] or 0.0
                    c3.metric("Acciones Activas", acc_act)
                    c3.info(f"💰 **Total Ahorrado:** S/ {f_m(tot_ah)}")
                    
                    nombre_fmt_busq = f"{nom.split()[0]} {ape.split()[0] if ape else ''}".strip()
                    with st.expander("📋 Ver Historial Completo de Movimientos"):
                        movs = db_query("SELECT id, fecha, tipo, monto FROM movimientos WHERE (tipo LIKE ? OR tipo LIKE ?) ORDER BY id DESC", (f"%{dni_busq}%", f"%{nombre_fmt_busq}%"))
                        if movs:
                            historial_procesado = {}
                            for id_mov, f_mov, t_mov, mon in movs:
                                if "Pago Cuota" in t_mov or "Interés Cuota" in t_mov:
                                    acc_match = re.search(r'\(Acción (\d+)\)', t_mov)
                                    acc_num = acc_match.group(1) if acc_match else "1"
                                    key = f"PAGO_{f_mov[:10]}_ACC_{acc_num}"
                                    if key not in historial_procesado: historial_procesado[key] = {'fecha': f_mov, 'detalle': f"Pago Préstamo (Acc. {acc_num})", 'cap': 0.0, 'int': 0.0, 'total': 0.0}
                                    if "Pago Cuota" in t_mov: historial_procesado[key]['cap'] += abs(mon)
                                    else: historial_procesado[key]['int'] += abs(mon)
                                    historial_procesado[key]['total'] += abs(mon)
                                elif "Préstamo a" in t_mov: historial_procesado[f"DESEMB_{id_mov}"] = {'fecha': f_mov, 'detalle': "Desembolso Préstamo", 'cap': abs(mon), 'int': 0.0, 'total': abs(mon)}
                                else:
                                    t_limpio = t_mov.split("(")[0].strip() if "(" in t_mov and "Acción" in t_mov else t_mov
                                    historial_procesado[f"OTRO_{id_mov}"] = {'fecha': f_mov, 'detalle': format_movimiento(t_limpio), 'cap': 0.0, 'int': 0.0, 'total': abs(mon)}
                            st.dataframe(pd.DataFrame([[format_fecha(v['fecha']), v['detalle'], f_m(v['cap']), f_m(v['int']), f_m(v['total'])] for v in historial_procesado.values()], columns=["Fecha", "Concepto / Detalle", "Capital (S/)", "Interés (S/)", "Total (S/)"]), use_container_width=True)
                        else: st.write("El socio no tiene movimientos registrados.")
                            
                    st.write("#### 📑 ESTADO DE PRÉSTAMOS Y REPORTES POR ACCIÓN")
                    tasa, amort_pct_act, amort_pct_val, m_min_fijo = get_config("interes_prestamo", 0.0)/100.0, get_config("amort_porcentaje_activo", "NO", str), get_config("amort_porcentaje_valor", 0.0)/100.0, get_config("monto_minimo_capital", 0.0)
                    for i in range(1, acc_act + 1):
                        with st.container(border=True):
                            col_a, col_b = st.columns([2, 1])
                            with col_a:
                                st.write(f"**Acción {i}**")
                                prest_activo = db_query("SELECT saldo_actual, monto_original FROM prestamos WHERE dni_socio=? AND accion_asociada=? AND estado='ACTIVO'", (dni_busq, i))
                                if prest_activo:
                                    saldo_actual, m_orig = prest_activo[0][0], prest_activo[0][1]
                                    st.warning(f"Deuda Vigente: S/ {f_m(saldo_actual)}")
                                    am = min(float(math.ceil(m_orig * amort_pct_val)) if float(math.ceil(m_orig * amort_pct_val)) >= m_min_fijo else float(m_min_fijo), saldo_actual) if amort_pct_act == "SI" else min(m_min_fijo, saldo_actual)
                                    interes = float(math.ceil(saldo_actual * tasa))
                                    st.info(f"**Proyección Próxima Cuota:** Capital S/ {f_m(am)} + Interés S/ {f_m(interes)} = **Total S/ {f_m(am + interes)}**")
                                else: st.success("✅ Sin deudas")
                            with col_b:
                                st.download_button(label=f"📄 DESCARGAR HISTORIAL (ACCIÓN {i})", data=generar_pdf_estado_cuenta(nombre_completo, dni_busq, i), file_name=f"Reporte_Completo_{dni_busq}_Acc{i}.pdf", mime="application/pdf", key=f"btn_descarga_{dni_busq}_{i}", use_container_width=True)

                    with st.expander("➕ COMPRAR ACCIÓN EXTRA", expanded=True):
                        if st.session_state.get('ce_done', False):
                            st.success("🎉 ¡Pago registrado en la Caja y Acción Extra asignada en la Base de Datos!")
                            st.info(st.session_state.ce_msg_correo)
                            st.download_button(label="🖨️ DESCARGAR VOUCHER (IMPRIMIR Y FIRMAR)", data=st.session_state.ce_pdf_bytes, file_name=f"Voucher_Extra_{dni_busq}.pdf", mime="application/pdf", type="primary")
                            if st.button("FINALIZAR Y LIMPIAR VENTANA"): limpiar_formularios_socio(); st.rerun()
                        else:
                            if acc_act >= 4: st.info("✅ Este socio ya posee el máximo de 4 acciones permitidas.")
                            else:
                                ce_acc = st.number_input("Cantidad de Acciones a comprar:", 1, 4-acc_act, 1)
                                c_hist, i_hist = calcular_nivelacion_por_accion()
                                ce_cap, ce_int, ce_ins = c_hist * ce_acc, math.ceil(i_hist) * ce_acc, get_config("cuota_inscripcion", 0.0) * ce_acc
                                ce_tot = ce_cap + ce_int + ce_ins
                                
                                st.markdown("### 📄 Desglose del Pago")
                                st.write(f"- **Aportes (Capital de Nivelación):** S/ {f_m(ce_cap)}\n- **Inscripción ({ce_acc} acc):** S/ {f_m(ce_ins)}\n- **Interés de Nivelación:** S/ {f_m(ce_int)}")
                                st.info(f"**TOTAL A PAGAR E INGRESAR A CAJA:** S/ {f_m(ce_tot)}")
                                
                                if st.button("💸 PAGAR Y ASIGNAR ACCIÓN", type="primary"):
                                    db_query("UPDATE socios SET acciones = acciones + ? WHERE dni=?", (ce_acc, dni_busq), fetch=False)
                                    db_query("UPDATE cuentas SET saldo = saldo + ? WHERE id_usuario=1", (ce_tot,), fetch=False)
                                    fh = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                                    nombre_fmt = f"{nom.split()[0]} {ape.split()[0]}"
                                    
                                    if ce_cap > 0: db_query("INSERT INTO movimientos (id_usuario, tipo, monto, fecha) VALUES (1, ?, ?, ?)", (f"Aporte por Compra Extra - {nombre_fmt} ({ce_acc} acc)", ce_cap, fh), fetch=False)
                                    if ce_int > 0: db_query("INSERT INTO movimientos (id_usuario, tipo, monto, fecha) VALUES (1, ?, ?, ?)", (f"Interés por Compra Extra - {nombre_fmt} ({ce_acc} acc)", ce_int, fh), fetch=False)
                                    if ce_ins > 0: db_query("INSERT INTO movimientos (id_usuario, tipo, monto, fecha) VALUES (1, ?, ?, ?)", (f"Derecho Inscripción Extra - {nombre_fmt} ({ce_acc} acc)", ce_ins, fh), fetch=False)
                                    
                                    txt_v = f"======================================\n      BANQUITO LA COLMENA\n     COMPRA DE ACCION EXTRA\n======================================\nFecha: {format_fecha(fh)}\nSocio: {nom} {ape}\nDNI:   {dni_busq}\n--------------------------------------\n"
                                    txt_v += f"Acciones Compradas : {ce_acc}\nAportes Nivelacion : S/ {f_m(ce_cap)}\nInteres Nivelacion : S/ {f_m(ce_int)}\nInscripcion        : S/ {f_m(ce_ins)}\n--------------------------------------\nTOTAL INGRESADO    : S/ {f_m(ce_tot)}\n======================================\n\n\n     ____________________________\n          FIRMA DEL SOCIO\n"
                                    
                                    st.session_state.ce_pdf_bytes = generar_pdf_voucher(txt_v, dni_busq)
                                    exito, st.session_state.ce_msg_correo = enviar_correo_generico(cor, "Voucher Compra Acción Extra - Banquito La Colmena", f"Estimado/a {nom} {ape},\n\nAdjuntamos su comprobante de compra de acciones extra.\n\nAtentamente,\nBanquito La Colmena.", st.session_state.ce_pdf_bytes, f"Voucher_Extra_{dni_busq}.pdf")
                                    st.session_state.ce_done = True; st.rerun()
                else: st.error("Socio no encontrado en el sistema.")
                
        with t2: ui_registro_nuevo_socio()

    elif menu_t == "💳 PAGOS Y PRÉSTAMOS":
        t1, t2, t3 = st.tabs(["💰 REALIZAR PAGO UNIFICADO", "✋ SOLICITUDES EN COLA", "⚖️ EVALUACIÓN Y DESEMBOLSO"])
        
        with t1:
            pdni = st.text_input("DNI Socio a pagar:", on_change=limpiar_formularios_pago)
            if pdni:
                if st.session_state.get('pu_done', False):
                    st.success("🎉 ¡Pago registrado en la Caja exitosamente!")
                    st.info(st.session_state.pu_msg_correo)
                    st.download_button("🖨️ DESCARGAR VOUCHER (IMPRIMIR Y FIRMAR)", data=st.session_state.pu_pdf_bytes, file_name=f"Voucher_Pago_{pdni}.pdf", mime="application/pdf", type="primary")
                    if st.button("FINALIZAR Y LIMPIAR VENTANA"): limpiar_formularios_pago(); st.rerun()
                else:
                    soc = db_query("SELECT nombres, apellidos, acciones, correo FROM socios WHERE dni=?", (pdni,))
                    if soc:
                        n, a, acc, correo = soc[0]
                        nombre_fmt = f"{n.split()[0]} {a.split()[0]}"
                        st.subheader(f"👤 Socio: {n} {a}"); st.write(f"**Acciones Totales:** {acc}"); st.divider()
                        st.markdown("### 📥 Aportes Mensuales")
                        ap_fijo = get_config("aporte_mensual", 0.0)
                        if st.checkbox(f"Pagar Aportes este mes", value=True):
                            for i in range(1, acc + 1): st.write(f"- Aporte Acción {i}: S/ {f_m(ap_fijo)}")
                        
                        st.divider(); st.markdown("### 💳 Pago de Préstamos")
                        deudas = db_query("SELECT id, accion_asociada, saldo_actual, monto_original, conteo_minimos FROM prestamos WHERE dni_socio=? AND estado='ACTIVO'", (pdni,))
                        tasa, amort_pct_act, amort_pct_val, m_min_fijo = get_config("interes_prestamo", 0.0)/100.0, get_config("amort_porcentaje_activo", "NO", str), get_config("amort_porcentaje_valor", 0.0)/100.0, get_config("monto_minimo_capital", 0.0)
                        mes_limite, mes_actual = int(get_config("mes_limite_minimos", 12)), datetime.now().month
                        
                        pagos_deudas = {}
                        if deudas:
                            for d in deudas:
                                d_id, d_acc, d_saldo, d_orig, d_conteo = d[0], d[1], d[2], d[3], d[4]
                                st.markdown(f"**Préstamo en Acción {d_acc}** (Saldo Restante: S/ {f_m(d_saldo)} | Original: S/ {f_m(d_orig)} | **Mínimos usados: {d_conteo}/3**)")
                                m_pct = float(math.ceil(d_orig * amort_pct_val)) if amort_pct_act == "SI" else float(m_min_fijo)
                                if m_pct < m_min_fijo: m_pct = float(m_min_fijo)
                                
                                is_min_obligatorio = False 
                                if amort_pct_act == "SI":
                                    if d_conteo < 3 and mes_actual <= mes_limite:
                                        min_allowed = min(m_min_fijo, d_saldo)
                                        default_val = min(m_pct, d_saldo)
                                        if m_pct <= m_min_fijo:
                                             is_min_obligatorio = True; st.info(f"💡 Amortización obligatoria de S/ {f_m(default_val)} (El porcentaje es menor al mínimo vital). NO gasta vida.")
                                        else: st.info(f"💡 Sugerido: S/ {f_m(default_val)} (Puede bajar hasta S/ {f_m(min_allowed)} por {3 - d_conteo} veces más hasta el mes {mes_limite})")
                                    elif d_conteo >= 3:
                                        default_val = min_allowed = min(m_pct, d_saldo); st.warning(f"⚠️ Agotó sus 3 pagos mínimos. Amortización obligatoria: S/ {f_m(min_allowed)}")
                                    else:
                                        default_val = min_allowed = min(m_pct, d_saldo); st.warning(f"⚠️ Plazo expirado (Mes actual > {mes_limite}). Amortización obligatoria: S/ {f_m(min_allowed)}")
                                else:
                                    default_val = min_allowed = min(m_min_fijo, d_saldo)
                                    
                                c1, c2 = st.columns(2)
                                with c1: cap_input = st.number_input(f"Abono a Capital (Acc {d_acc})", min_value=0.0, max_value=float(d_saldo), value=float(default_val), step=10.0, key=f"cap_{d_id}")
                                with c2:
                                    int_calc = float(math.ceil(d_saldo * tasa))
                                    st.info(f"Interés a pagar: S/ {f_m(int_calc)}")
                                    
                                pagos_deudas[d_id] = {'acc': d_acc, 'saldo': d_saldo, 'cap': cap_input, 'int': int_calc if cap_input > 0 or int_calc > 0 else 0.0, 'is_min': True if amort_pct_act == "SI" and not is_min_obligatorio and (cap_input < min(m_pct, d_saldo)) and (cap_input > 0.01) else False, 'min_req': min_allowed}
                                st.write("---")
                        else: st.success("✅ El socio no tiene deudas activas.")
                            
                        if st.button("1. CALCULAR DETALLE Y GENERAR VOUCHER", type="primary"):
                            detalles_aportes, total_aportes = ([(i, ap_fijo) for i in range(1, acc + 1)], acc * ap_fijo) if 'pagar_ap' in locals() and pagar_ap else ([], 0.0)
                            detalles_prestamos, total_cap, total_int, needs_auth = [], 0.0, 0.0, False
                            for d_id, data in pagos_deudas.items():
                                if data['cap'] > 0 or data['int'] > 0:
                                    if data['cap'] < data['min_req'] and abs(data['cap'] - data['saldo']) > 0.01: needs_auth = True
                                    detalles_prestamos.append({'id': d_id, 'acc': data['acc'], 'cap': data['cap'], 'int': data['int'], 'saldo': data['saldo'], 'is_min': data['is_min']})
                                    total_cap += data['cap']; total_int += data['int']
                            if (total_aportes + total_cap + total_int) == 0: st.warning("El monto total a pagar es S/ 0.00. Ingrese algún pago.")
                            else:
                                st.session_state.update({'pu_tot': total_aportes + total_cap + total_int, 'pu_det_ap': detalles_aportes, 'pu_tot_ap': total_aportes, 'pu_det_pr': detalles_prestamos, 'pu_tot_cap': total_cap, 'pu_tot_int': total_int, 'pu_needs_auth': needs_auth, 'pu_show_voucher': True, 'pu_done': False})
                                
                        if st.session_state.get('pu_show_voucher', False) and not st.session_state.get('pu_done', False):
                            st.markdown("### 🧾 Vista Previa del Voucher")
                            fh_pre = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                            txt_v = f"======================================\n      BANQUITO LA COLMENA\n     COMPROBANTE DE PAGO\n======================================\nFecha: {format_fecha(fh_pre)}\nSocio: {n} {a}\nDNI:   {pdni}\n--------------------------------------\n"
                            if st.session_state.pu_tot_ap > 0:
                                txt_v += "APORTES MENSUALES:\n" + "".join([f" - Accion {ap[0]:<2} :           S/ {f_m(ap[1])}\n" for ap in st.session_state.pu_det_ap]) + f"   Subtotal Aportes :   S/ {f_m(st.session_state.pu_tot_ap)}\n--------------------------------------\n"
                            if st.session_state.pu_tot_cap > 0 or st.session_state.pu_tot_int > 0:
                                txt_v += "PAGO DE PRESTAMOS:\n" + "".join([f" - Accion {pr['acc']}:\n      Capital :         S/ {f_m(pr['cap'])}\n      Interes :         S/ {f_m(pr['int'])}\n      Saldo Cap. Act. : S/ {f_m(max(0.0, pr['saldo'] - pr['cap']))}\n" for pr in st.session_state.pu_det_pr]) + f"   Subtotal Prestamos : S/ {f_m(st.session_state.pu_tot_cap + st.session_state.pu_tot_int)}\n--------------------------------------\n"
                            txt_v += f"TOTAL A PAGAR         : S/ {f_m(st.session_state.pu_tot)}\n======================================\n\n\n     ____________________________\n          FIRMA DEL SOCIO\n"
                            st.text(txt_v)
                            
                            can_proceed = True
                            if st.session_state.get('pu_needs_auth', False):
                                if not st.session_state.get('pu_auth_success', False):
                                    with st.form("f_pu_auth", clear_on_submit=True):
                                        st.warning(f"⚠️ Un abono a capital es menor al mínimo requerido. Se requiere autorización del Presidente.")
                                        if st.form_submit_button("Autorizar"):
                                            if st.text_input("Clave del Presidente para autorizar:", type="password") == get_config("password_presidente", "123456", str): st.session_state.pu_auth_success = True; st.rerun()
                                            else: st.error("❌ Clave incorrecta.")
                                    can_proceed = False
                                else: st.success("✅ Pago autorizado por la Presidencia."); can_proceed = True
                                    
                            if can_proceed:
                                if st.button("✅ 2. CONFIRMAR Y REGISTRAR PAGO A CAJA", type="primary"):
                                    fh = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                                    if st.session_state.pu_tot_ap > 0:
                                        db_query("UPDATE cuentas SET saldo = saldo + ? WHERE id_usuario=1", (st.session_state.pu_tot_ap,), fetch=False)
                                        for ap in st.session_state.pu_det_ap: db_query("INSERT INTO movimientos (id_usuario, tipo, monto, fecha) VALUES (1, ?, ?, ?)", (f"Aporte Mensual - {nombre_fmt} (Acción {ap[0]})", ap[1], fh), fetch=False)
                                    for pr in st.session_state.pu_det_pr:
                                        ns = pr['saldo'] - pr['cap']; est = "PAGADO" if ns < 0.1 else "ACTIVO"
                                        db_query("UPDATE prestamos SET saldo_actual=?, estado=? WHERE id=?", (0 if est=="PAGADO" else ns, est, pr['id']), fetch=False)
                                        if pr['is_min']: db_query("UPDATE prestamos SET conteo_minimos = conteo_minimos + 1 WHERE id=?", (pr['id'],), fetch=False)
                                        db_query("UPDATE cuentas SET saldo = saldo + ? WHERE id_usuario=1", (pr['cap'] + pr['int'],), fetch=False)
                                        if pr['cap'] > 0: db_query("INSERT INTO movimientos (id_usuario, tipo, monto, fecha) VALUES (1, ?, ?, ?)", (f"Pago Cuota Capital - {nombre_fmt} (Acción {pr['acc']})", pr['cap'], fh), fetch=False)
                                        if pr['int'] > 0: db_query("INSERT INTO movimientos (id_usuario, tipo, monto, fecha) VALUES (1, ?, ?, ?)", (f"Interés Cuota Préstamo - {nombre_fmt} (Acción {pr['acc']})", pr['int'], fh), fetch=False)
                                    
                                    st.session_state.pu_pdf_bytes = generar_pdf_voucher(txt_v, pdni)
                                    exito, st.session_state.pu_msg_correo = enviar_correo_generico(correo, "Voucher de Pago - Banquito La Colmena", f"Estimado/a {n} {a},\n\nAdjuntamos su comprobante de pago de la fecha.\n\nAtentamente,\nBanquito La Colmena.", st.session_state.pu_pdf_bytes, f"Voucher_Pago_{pdni}.pdf")
                                    st.session_state.update({'pu_done': True, 'pu_auth_success': False}); st.rerun()
                    else: st.error("Socio no encontrado.")

        with t2:
            st.write("Anota a los socios que solicitan préstamo en asamblea. El sistema los guardará en la cola para evaluarlos luego.")
            socios_ops = db_query("SELECT dni, nombres, apellidos, acciones FROM socios WHERE acciones > 0 ORDER BY nombres ASC")
            if socios_ops:
                dict_socios = {f"{s[0]} - {s[1]} {s[2]} (Acciones: {s[3]})": s for s in socios_ops}
                c_s1, c_s2 = st.columns(2)
                soc_sel = dict_socios[c_s1.selectbox("1. Seleccionar Socio", list(dict_socios.keys()))]
                acc_sel = c_s2.selectbox("2. ¿En qué Acción?", [i for i in range(1, soc_sel[3]+1)])
                
                tope_act, tope_monto = get_config("tope_prestamo_activo", "NO", str), get_config("tope_prestamo_monto", 0.0)
                deuda_act = db_query("SELECT saldo_actual FROM prestamos WHERE dni_socio=? AND accion_asociada=? AND estado='ACTIVO'", (soc_sel[0], acc_sel))
                monto_deuda = float(deuda_act[0][0]) if deuda_act else 0.0
                st.info(f"💳 Deuda actual en la Acción {acc_sel}: S/ {f_m(monto_deuda)}")
                
                if tope_act == "SI" and tope_monto > 0:
                    disp_tope = max(0.0, tope_monto - monto_deuda)
                    st.write(f"**Tope máximo configurado:** S/ {f_m(tope_monto)} (Disponible para solicitar: S/ {f_m(disp_tope)})")
                    monto_sol = disp_tope if st.checkbox(f"Solicitar al Tope (S/ {f_m(disp_tope)})") else st.number_input("3. Monto Solicitado (S/)", min_value=10.0, step=100.0)
                else: monto_sol = st.number_input("3. Monto Solicitado (S/)", min_value=10.0, step=100.0)
                
                if st.button("➕ AGREGAR A LA COLA", type="primary"):
                    if monto_sol <= 0: st.warning("El monto solicitado debe ser mayor a 0.")
                    elif db_query("SELECT id FROM solicitudes_prestamo WHERE dni_socio=? AND accion=? AND estado='PENDIENTE'", (soc_sel[0], acc_sel)): st.error("⚠️ Este socio ya tiene una solicitud en espera para esa acción.")
                    else: db_query("INSERT INTO solicitudes_prestamo (dni_socio, accion, monto, fecha) VALUES (?,?,?,?)", (soc_sel[0], acc_sel, monto_sol, datetime.now().strftime("%Y-%m-%d %H:%M:%S")), fetch=False); st.success("✅ Solicitud registrada con éxito."); st.rerun()
                        
                st.divider(); st.write("#### 📋 Cola Actual (En Espera)")
                pendientes = db_query("SELECT id, dni_socio, accion, monto FROM solicitudes_prestamo WHERE estado='PENDIENTE'")
                if pendientes:
                    for p_id, p_dni, p_acc, p_mon in pendientes:
                        s_info = db_query("SELECT nombres, apellidos FROM socios WHERE dni=?", (p_dni,))[0]
                        c1_p, c2_p, c3_p, c4_p = st.columns([3, 2, 1, 1])
                        c1_p.write(f"👤 **{s_info[0]} {s_info[1]}** (Acción {p_acc})"); c2_p.write(f"💰 Solicitó: **S/ {f_m(p_mon)}**")
                        if c4_p.button("❌ Borrar", key=f"del_sol_{p_id}"): db_query("DELETE FROM solicitudes_prestamo WHERE id=?", (p_id,), fetch=False); st.rerun()
                        st.write("---")
                else: st.info("No hay solicitudes en espera.")
            
        with t3:
            st.write("El sistema ordena automáticamente a los solicitantes dando **máxima prioridad a quienes tienen la MENOR deuda actual**. Evalúe y atienda uno por uno de manera estricta.")
            caja_prin_disp = (float(db_query("SELECT SUM(monto) FROM movimientos")[0][0] or 0.0) - ((db_query("SELECT SUM(monto) FROM movimientos WHERE tipo LIKE 'Ingreso Caja Chica%' OR tipo = 'Depósito Caja'")[0][0] or 0.0) - abs(db_query("SELECT SUM(monto) FROM movimientos WHERE tipo LIKE 'Egreso Caja Chica%' OR tipo = 'Retiro Caja'")[0][0] or 0.0)))
            st.info(f"💰 **Fondo Disponible en Caja Principal:** S/ {f_m(caja_prin_disp)}")
            
            if st.session_state.get('pres_done', False):
                st.success("🎉 ¡Préstamo desembolsado exitosamente de la Caja Principal!")
                if st.session_state.get('pres_msg_correo'): st.info(st.session_state.pres_msg_correo)
                st.download_button("🖨️ DESCARGAR PAQUETE COMPLETO (VOUCHER + CONTRATO)", data=st.session_state.pres_pdf, file_name=f"Desembolso_{st.session_state.get('pres_dni','')}.pdf", mime="application/pdf", type="primary", use_container_width=True)
                if st.button("FINALIZAR Y CONTINUAR"): limpiar_formularios_pago(); st.rerun()
            else:
                solicitudes = db_query("SELECT id, dni_socio, accion, monto FROM solicitudes_prestamo WHERE estado='PENDIENTE'")
                if solicitudes:
                    lista_eval = []
                    for sol_id, d_socio, acc, m_req in solicitudes:
                        soc_info = db_query("SELECT nombres, apellidos, correo FROM socios WHERE dni=?", (d_socio,))
                        if not soc_info: continue
                        deuda_act = db_query("SELECT saldo_actual FROM prestamos WHERE dni_socio=? AND accion_asociada=? AND estado='ACTIVO'", (d_socio, acc))
                        lista_eval.append({"id": sol_id, "dni": d_socio, "socio": f"{soc_info[0][0]} {soc_info[0][1]}", "correo": soc_info[0][2], "accion": acc, "monto_req": m_req, "deuda_act": float(deuda_act[0][0]) if deuda_act else 0.0})
                        
                    lista_eval.sort(key=lambda x: x['deuda_act']); caja_simulada = caja_prin_disp
                    
                    for index, item in enumerate(lista_eval):
                        with st.container(border=True):
                            c1_e, c2_e, c3_e, c4_e = st.columns([3, 2, 2, 3])
                            c1_e.markdown(f"## 👤 {item['socio']}\n*(Acción {item['accion']})*"); c2_e.metric("Deuda Actual", f"S/ {f_m(item['deuda_act'])}")
                            
                            if index == 0:
                                input_key = f"in_monto_{item['id']}"
                                c3_e.number_input("Solicitó (S/)", value=float(item['monto_req']), min_value=10.0, step=10.0, key=input_key, on_change=update_monto_inline, args=(item['id'], input_key))
                                current_req = st.session_state.get(input_key, float(item['monto_req']))
                                
                                with c4_e:
                                    if caja_simulada >= current_req:
                                        st.success("✅ Alcanza el dinero"); caja_simulada -= current_req
                                        cb1, cb2 = st.columns(2)
                                        if cb1.button("💸 APROBAR", key=f"desemb_{item['id']}", use_container_width=True):
                                            m_p, pdni2, acc_n = current_req, item['dni'], item['accion']
                                            nombre_fmt_l = item['socio'].split()[0] + " " + (item['socio'].split()[1] if len(item['socio'].split()) > 1 else "")
                                            
                                            p_act = db_query("SELECT id, monto_original, saldo_actual FROM prestamos WHERE dni_socio=? AND accion_asociada=? AND estado='ACTIVO'", (pdni2, acc_n))
                                            if p_act: m_proy = p_act[0][2] + m_p; db_query("UPDATE prestamos SET monto_original=?, saldo_actual=? WHERE id=?", (m_proy, m_proy, p_act[0][0]), fetch=False)
                                            else:
                                                m_proy = m_p; prev_conteo_req = db_query("SELECT SUM(conteo_minimos) FROM prestamos WHERE dni_socio=? AND accion_asociada=? AND substr(fecha_inicio, 1, 4)=?", (pdni2, acc_n, str(datetime.now().year)))
                                                db_query("INSERT INTO prestamos (dni_socio, monto_original, saldo_actual, fecha_inicio, estado, accion_asociada, conteo_minimos) VALUES (?, ?, ?, ?, 'ACTIVO', ?, ?)", (pdni2, m_proy, m_proy, datetime.now().strftime("%Y-%m-%d"), acc_n, prev_conteo_req[0][0] if prev_conteo_req and prev_conteo_req[0][0] else 0), fetch=False)
                                            
                                            fh_exacta = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                                            db_query("UPDATE cuentas SET saldo = saldo - ? WHERE id_usuario=1", (m_p,), fetch=False); db_query("INSERT INTO movimientos (id_usuario, tipo, monto, fecha) VALUES (1, ?, ?, ?)", (f"Préstamo Desembolsado - {nombre_fmt_l} (Acción {acc_n})", -m_p, fh_exacta), fetch=False); db_query("UPDATE solicitudes_prestamo SET estado='APROBADO' WHERE id=?", (item['id'],), fetch=False)
                                            
                                            sp, cuotas, tot_i, fh_d = m_proy, [], 0, datetime.now()
                                            m, a, tasa, m_min = fh_d.month, fh_d.year, get_config("interes_prestamo", 0.0) / 100.0, get_config("monto_minimo_capital", 50.0)
                                            num_c = 1
                                            while sp > 0.01:
                                                m = m + 1 if m < 12 else 1; a += 1 if m == 1 else 0
                                                am = min(max(float(math.ceil(m_proy * (get_config("amort_porcentaje_valor", 0.0) / 100.0))), m_min) if get_config("amort_porcentaje_activo", "NO", str) == "SI" else m_min, sp)
                                                i = math.ceil(sp * tasa); cuotas.append((f"Cuota {num_c}", f"{['Enero', 'Febrero', 'Marzo', 'Abril', 'Mayo', 'Junio', 'Julio', 'Agosto', 'Septiembre', 'Octubre', 'Noviembre', 'Diciembre'][m-1]} {a}", am, i, am+i)); tot_i += i; sp -= am; num_c += 1
                                                
                                            st.session_state.pres_pdf = generar_pdf_desembolso(item['socio'], pdni2, acc_n, m_p, m_proy, tot_i, cuotas, fh_exacta, tasa, True)
                                            exito, st.session_state.pres_msg_correo = enviar_correo_generico(item['correo'], "Cronograma de Préstamo - Banquito La Colmena", f"Estimado/a {item['socio']},\n\nSu préstamo ha sido aprobado exitosamente. Adjuntamos su nuevo cronograma de pagos.\n\nAtentamente,\nLa Junta Directiva.", generar_pdf_desembolso(item['socio'], pdni2, acc_n, m_p, m_proy, tot_i, cuotas, fh_exacta, tasa, False), f"Cronograma_{pdni2}.pdf")
                                            st.session_state.update({'pres_dni': pdni2, 'pres_done': True}); st.rerun()
                                            
                                        if cb2.button("❌ ANULAR", key=f"anular_{item['id']}", use_container_width=True): db_query("UPDATE solicitudes_prestamo SET estado='RECHAZADO' WHERE id=?", (item['id'],), fetch=False); st.rerun()
                                    elif caja_simulada > 0:
                                        st.warning(f"⚠️ Alcanza S/ {f_m(caja_simulada)}")
                                        cb1, cb2 = st.columns(2)
                                        if cb1.button(f"💸 PRESTAR PARCIAL", key=f"desemb_parcial_{item['id']}", use_container_width=True):
                                            m_p, pdni2, acc_n = caja_simulada, item['dni'], item['accion']
                                            nombre_fmt_l = item['socio'].split()[0] + " " + (item['socio'].split()[1] if len(item['socio'].split()) > 1 else "")
                                            
                                            p_act = db_query("SELECT id, monto_original, saldo_actual FROM prestamos WHERE dni_socio=? AND accion_asociada=? AND estado='ACTIVO'", (pdni2, acc_n))
                                            if p_act: m_proy = p_act[0][2] + m_p; db_query("UPDATE prestamos SET monto_original=?, saldo_actual=? WHERE id=?", (m_proy, m_proy, p_act[0][0]), fetch=False)
                                            else:
                                                m_proy = m_p; prev_conteo_req = db_query("SELECT SUM(conteo_minimos) FROM prestamos WHERE dni_socio=? AND accion_asociada=? AND substr(fecha_inicio, 1, 4)=?", (pdni2, acc_n, str(datetime.now().year)))
                                                db_query("INSERT INTO prestamos (dni_socio, monto_original, saldo_actual, fecha_inicio, estado, accion_asociada, conteo_minimos) VALUES (?, ?, ?, ?, 'ACTIVO', ?, ?)", (pdni2, m_p, m_p, datetime.now().strftime("%Y-%m-%d"), acc_n, prev_conteo_req[0][0] if prev_conteo_req and prev_conteo_req[0][0] else 0), fetch=False)
                                            
                                            fh_exacta = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                                            db_query("UPDATE cuentas SET saldo = saldo - ? WHERE id_usuario=1", (m_p,), fetch=False); db_query("INSERT INTO movimientos (id_usuario, tipo, monto, fecha) VALUES (1, ?, ?, ?)", (f"Préstamo Desembolsado - {nombre_fmt_l} (Acción {acc_n})", -m_p, fh_exacta), fetch=False); db_query("UPDATE solicitudes_prestamo SET estado='APROBADO PARCIAL' WHERE id=?", (item['id'],), fetch=False)
                                            
                                            sp, cuotas, tot_i, fh_d = m_proy, [], 0, datetime.now()
                                            m, a, tasa, m_min = fh_d.month, fh_d.year, get_config("interes_prestamo", 0.0) / 100.0, get_config("monto_minimo_capital", 50.0)
                                            num_c = 1
                                            while sp > 0.01:
                                                m = m + 1 if m < 12 else 1; a += 1 if m == 1 else 0
                                                am = min(max(float(math.ceil(m_proy * (get_config("amort_porcentaje_valor", 0.0) / 100.0))), m_min) if get_config("amort_porcentaje_activo", "NO", str) == "SI" else m_min, sp)
                                                i = math.ceil(sp * tasa); cuotas.append((f"Cuota {num_c}", f"{['Enero', 'Febrero', 'Marzo', 'Abril', 'Mayo', 'Junio', 'Julio', 'Agosto', 'Septiembre', 'Octubre', 'Noviembre', 'Diciembre'][m-1]} {a}", am, i, am+i)); tot_i += i; sp -= am; num_c += 1
                                                
                                            st.session_state.pres_pdf = generar_pdf_desembolso(item['socio'], pdni2, acc_n, m_p, m_proy, tot_i, cuotas, fh_exacta, tasa, True)
                                            exito, st.session_state.pres_msg_correo = enviar_correo_generico(item['correo'], "Voucher y Cronograma de Préstamo - Banquito La Colmena", f"Estimado/a {item['socio']},\n\nSu préstamo parcial ha sido aprobado exitosamente. Adjuntamos el voucher y su nuevo cronograma de pagos.\n\nAtentamente,\nLa Junta Directiva.", generar_pdf_desembolso(item['socio'], pdni2, acc_n, m_p, m_proy, tot_i, cuotas, fh_exacta, tasa, False), f"Prestamo_{pdni2}.pdf")
                                            st.session_state.update({'pres_dni': pdni2, 'pres_done': True}); st.rerun()
                                            
                                        if cb2.button("❌ ANULAR", key=f"anular_parc_{item['id']}", use_container_width=True): db_query("UPDATE solicitudes_prestamo SET estado='RECHAZADO' WHERE id=?", (item['id'],), fetch=False); st.rerun()
                                    else:
                                        st.error("❌ Sin Fondos")
                                        if st.button("🗑️ ANULAR / BORRAR", key=f"rech_{item['id']}", use_container_width=True): db_query("UPDATE solicitudes_prestamo SET estado='RECHAZADO' WHERE id=?", (item['id'],), fetch=False); st.rerun()
                            else:
                                c3_e.metric("Solicitó", f"S/ {f_m(item['monto_req'])}")
                                with c4_e: st.info("⏳ Esperando turno...")
                    if caja_simulada > 0: st.write(f"**Proyección:** Quedará en caja S/ {f_m(caja_simulada)} libre para nuevos préstamos.")
                else: st.success("No hay solicitudes pendientes en la cola. Vaya a la pestaña 'Solicitudes en Cola' para agregarlas.")

    elif menu_t == "💰 CAJA GLOBAL":
        s_tot = float(db_query("SELECT SUM(monto) FROM movimientos")[0][0] or 0.0)
        i_cc = db_query("SELECT SUM(monto) FROM movimientos WHERE tipo LIKE 'Ingreso Caja Chica%' OR tipo = 'Depósito Caja'")[0][0] or 0.0
        e_cc = abs(db_query("SELECT SUM(monto) FROM movimientos WHERE tipo LIKE 'Egreso Caja Chica%' OR tipo = 'Retiro Caja'")[0][0] or 0.0)
        f_cc = i_cc - e_cc
        c_prin = s_tot - f_cc
        
        c1, c2, c3 = st.columns(3)
        c1.metric("Caja Principal (Préstamos)", f"S/ {f_m(c_prin)}")
        c2.metric("Caja Chica (Multas/Varios)", f"S/ {f_m(f_cc)}")
        c3.metric("Efectivo Total Físico", f"S/ {f_m(s_tot)}")
        
        st.divider(); st.markdown("### 🔮 Proyección de Ingresos (Próxima Asamblea)"); st.write("Cálculo estimado del dinero que ingresará a la caja el próximo mes basado en las reglas actuales.")
        
        tot_acc = int(db_query("SELECT SUM(acciones) FROM socios")[0][0] or 0)
        proy_aportes = tot_acc * get_config("aporte_mensual", 0.0)
        deudas_activas = db_query("SELECT saldo_actual, monto_original, conteo_minimos FROM prestamos WHERE estado='ACTIVO'")
        proy_interes, proy_capital = 0.0, 0.0
        tasa_proy, amort_pct_act_proy, amort_pct_val_proy, m_min_fijo_proy, mes_limite_proy, mes_actual_proy = get_config("interes_prestamo", 0.0)/100.0, get_config("amort_porcentaje_activo", "NO", str), get_config("amort_porcentaje_valor", 0.0)/100.0, get_config("monto_minimo_capital", 0.0), int(get_config("mes_limite_minimos", 12)), datetime.now().month
        
        if deudas_activas:
            for ds, dorig, dconteo in deudas_activas:
                proy_interes += float(math.ceil(ds * tasa_proy))
                min_req = min(max(float(math.ceil(dorig * amort_pct_val_proy)), m_min_fijo_proy) if dconteo >= 3 or mes_actual_proy > mes_limite_proy else m_min_fijo_proy, ds) if amort_pct_act_proy == "SI" else min(m_min_fijo_proy, ds)
                proy_capital += min_req
                
        cp1, cp2, cp3, cp4 = st.columns(4)
        cp1.metric("1️⃣ Aportes Estimados", f"S/ {f_m(proy_aportes)}", f"De {tot_acc} acciones")
        cp2.metric("2️⃣ Intereses Estimados", f"S/ {f_m(proy_interes)}")
        cp3.metric("3️⃣ Capital Estimado", f"S/ {f_m(proy_capital)}", "Amortización mínima")
        cp4.metric("✨ FONDOS PROYECTADOS", f"S/ {f_m(c_prin + proy_aportes + proy_interes + proy_capital)}", "Disponible para prestar")
        
        st.divider(); st.subheader("📊 Resumen General del Banquito")
        tot_int_disponible = max(0.0, float(db_query("SELECT SUM(monto) FROM movimientos WHERE tipo LIKE '%nter%' AND tipo NOT LIKE '%Caja Chica%'")[0][0] or 0.0) + float(db_query("SELECT SUM(monto) FROM movimientos WHERE tipo LIKE 'Pago Directiva%' OR tipo LIKE 'Pago Utilidades%' OR tipo LIKE 'Ajuste Interno - Salida de Utilidades%'")[0][0] or 0.0))
        tot_ins = float(db_query("SELECT SUM(monto) FROM movimientos WHERE tipo LIKE '%Inscripc%'")[0][0] or 0.0)
        tot_aportes = float(db_query("SELECT SUM(monto) FROM movimientos WHERE tipo LIKE '%Aporte%'")[0][0] or 0.0)
        cap_esperado_por_accion, _ = calcular_nivelacion_por_accion()
        
        col_res1, col_res2, col_res3, col_res4, col_res5 = st.columns(5)
        col_res1.metric("Capital Total (Aportes)", f"S/ {f_m(tot_aportes)}")
        col_res2.metric("Intereses sin Repartir", f"S/ {f_m(tot_int_disponible)}")
        col_res3.metric("Total Inscripciones", f"S/ {f_m(tot_ins)}")
        col_res4.metric("Acciones Activas", f"{tot_acc}")
        col_res5.metric("Aporte Ideal x Acción", f"S/ {f_m(cap_esperado_por_accion)}")
        
        st.divider(); st.subheader("📋 Auditoría de Aportes por Socio")
        st.write(f"Para asegurar que todos estén nivelados, el sistema toma como meta la acción con mayor capital registrado. El aporte ideal debe ser **S/ {f_m(cap_esperado_por_accion)}** por CADA acción a la fecha. Aquí se reporta si a alguien le falta nivelarse:")
        
        resumen_socios, morosos = [], False
        for s_dni, s_nom, s_ape, s_acc in db_query("SELECT dni, nombres, apellidos, acciones FROM socios ORDER BY nombres ASC"):
            ap_socio = db_query("SELECT SUM(monto) FROM movimientos WHERE tipo LIKE '%Aporte%' AND tipo LIKE ?", (f"%{s_dni}%",))[0][0] or 0.0
            deuda = (cap_esperado_por_accion * s_acc) - ap_socio
            estado = f"⚠️ Falta S/ {f_m(deuda)}" if deuda > 0.01 else (f"⭐ Adelantó S/ {f_m(abs(deuda))}" if deuda < -0.01 else "✅ Al Día")
            if deuda > 0.01: morosos = True
            resumen_socios.append((f"{s_nom.split()[0]} {s_ape.split()[0]}", s_acc, f_m(ap_socio / s_acc if s_acc > 0 else 0.0), f_m(ap_socio), f_m(cap_esperado_por_accion * s_acc), estado))
            
        if morosos:
            st.error("⚠️ **ALERTA: Existen socios que no han pagado la cantidad correcta de aportes.** Revisa la columna 'Estado'.")
        else:
            st.success("✅ ¡Felicidades! Todos los socios están al día (o tienen saldo adelantado).")
            
        st.dataframe(pd.DataFrame(resumen_socios, columns=["Socio", "Acciones", "Tiene por Acción (S/)", "Total Aportado (S/)", "Debería Tener (S/)", "Estado"]), use_container_width=True)
        
        st.divider(); st.subheader("📋 Historial de Movimientos de Caja")
        col_f1, col_f2, col_f3 = st.columns(3)
        caja_f_ini, caja_f_fin, caja_f_dni = col_f1.date_input("Desde la fecha:", value=date(date.today().year, 1, 1), key="caja_fini"), col_f2.date_input("Hasta la fecha:", value=date.today(), key="caja_ffin"), col_f3.text_input("Buscar por DNI (Opcional):", key="caja_fdni")
        
        query, params = "SELECT fecha, tipo, monto FROM movimientos WHERE date(fecha) >= ? AND date(fecha) <= ?", [str(caja_f_ini), str(caja_f_fin)]
        if caja_f_dni:
            soc_b = db_query("SELECT nombres, apellidos FROM socios WHERE dni=?", (caja_f_dni,))
            if soc_b:
                nombre_fmt_b = f"{soc_b[0][0].split()[0]} {soc_b[0][1].split()[0] if soc_b[0][1] else ''}".strip()
                query += " AND (tipo LIKE ? OR tipo LIKE ?)"
                params.extend([f"%{caja_f_dni}%", f"%{nombre_fmt_b}%"])
            else:
                query += " AND tipo LIKE ?"; params.append(f"%{caja_f_dni}%")
        query += " ORDER BY fecha DESC"
        
        movs_caja = db_query(query, tuple(params))
        if movs_caja:
            movs_caja_fmt = [(format_fecha(m[0]), format_movimiento(m[1]), m[2]) for m in movs_caja]
            df_caja = pd.DataFrame(movs_caja_fmt, columns=["Fecha", "Detalle de Operación", "Monto (S/)"])
            df_caja["Monto (S/)"] = df_caja["Monto (S/)"].apply(lambda x: f"S/ {f_m(x)}")
            st.dataframe(df_caja, use_container_width=True)
            st.download_button(label="📥 DESCARGAR REPORTE EN PDF", data=generar_pdf_historial_caja(movs_caja_fmt, caja_f_ini, caja_f_fin, caja_f_dni), file_name=f"Reporte_Caja_{datetime.now().strftime('%Y%m%d')}.pdf", mime="application/pdf", type="primary")
        else: st.info("No se encontraron movimientos en ese rango de fechas o con ese DNI.")

    elif menu_t == "📥 CAJA CHICA":
        i_cc = db_query("SELECT SUM(monto) FROM movimientos WHERE tipo LIKE 'Ingreso Caja Chica%' OR tipo = 'Depósito Caja'")[0][0] or 0.0
        e_cc = abs(db_query("SELECT SUM(monto) FROM movimientos WHERE tipo LIKE 'Egreso Caja Chica%' OR tipo = 'Retiro Caja'")[0][0] or 0.0)
        st.subheader(f"Fondo Actual Caja Chica: S/ {f_m(i_cc - e_cc)}")
        
        t1, t2, t3 = st.tabs(["+ Ingreso", "- Egreso", "📊 Reporte de Rendimiento"])
        with t1:
            i_con, i_det, i_mon = st.selectbox("Concepto:", ["Multa", "Tardanza", "Otro"]), st.text_input("Detalle (Opcional):"), st.number_input("Monto Ingreso (S/):", min_value=0.0)
            if st.button("Registrar Ingreso", type="primary"):
                fh = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                db_query("UPDATE cuentas SET saldo = saldo + ? WHERE id_usuario=1", (i_mon,), fetch=False); db_query("INSERT INTO movimientos (id_usuario, tipo, monto, fecha) VALUES (1, ?, ?, ?)", (f"Ingreso Caja Chica - {i_con} | {i_det}", i_mon, fh), fetch=False)
                st.success("Ingreso registrado en Caja Chica.")
        with t2:
            e_con, e_det, e_mon = st.selectbox("Concepto Egreso:", ["Insumos", "Administrativo", "Otro"]), st.text_input("Detalle Egreso:"), st.number_input("Monto Egreso (S/):", min_value=0.0)
            if st.button("Registrar Egreso"):
                fh = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                db_query("UPDATE cuentas SET saldo = saldo - ? WHERE id_usuario=1", (e_mon,), fetch=False); db_query("INSERT INTO movimientos (id_usuario, tipo, monto, fecha) VALUES (1, ?, ?, ?)", (f"Egreso Caja Chica - {e_con} | {e_det}", -e_mon, fh), fetch=False)
                st.success("Egreso registrado en Caja Chica.")
        with t3:
            st.write("### Historial y Balance de Caja Chica")
            c_r1, c_r2, c_r3 = st.columns(3); c_r1.metric("Total Ingresos", f"S/ {f_m(i_cc)}"); c_r2.metric("Total Egresos", f"S/ {f_m(e_cc)}"); c_r3.metric("Saldo Neto", f"S/ {f_m(i_cc - e_cc)}")
            movs_cc = db_query("SELECT fecha, tipo, monto FROM movimientos WHERE tipo LIKE '%Caja Chica%' OR tipo = 'Depósito Caja' OR tipo = 'Retiro Caja' ORDER BY id DESC")
            if movs_cc:
                df_cc = pd.DataFrame(movs_cc, columns=["Fecha", "Concepto / Detalle", "Monto"])
                df_cc["Fecha"], df_cc["Concepto / Detalle"], df_cc["Monto"] = df_cc["Fecha"].apply(format_fecha), df_cc["Concepto / Detalle"].apply(format_movimiento), df_cc["Monto"].apply(lambda x: f"S/ {f_m(x)}")
                st.dataframe(df_cc, use_container_width=True)
                st.download_button(label="📥 DESCARGAR REPORTE EN EXCEL (CSV)", data=df_cc.to_csv(index=False).encode('utf-8'), file_name=f"Reporte_CajaChica_{datetime.now().strftime('%Y%m%d')}.csv", mime="text/csv", type="primary")
            else: st.info("Aún no hay movimientos registrados en la Caja Chica.")

    elif menu_t == "⚙️ REGLAS FINANCIERAS":
        if 'reglas_unlocked' not in st.session_state: st.session_state.reglas_unlocked = False
        st.warning("⚠️ Cuidado: Requiere clave de autorización del Presidente")
        if not st.session_state.reglas_unlocked:
            with st.form("form_auth_reglas"):
                if st.form_submit_button("Autorizar", type="primary"):
                    if st.text_input("Clave del Presidente", type="password") == get_config("password_presidente", "123456", str): st.session_state.reglas_unlocked = True; st.rerun()
                    else: st.error("❌ Clave de presidente incorrecta.")
        
        if st.session_state.reglas_unlocked:
            st.success("✅ Autorización Exitosa. Puedes modificar las reglas.")
            
            st.write("#### 🎂 CONFIGURACIÓN DE CUMPLEAÑOS")
            jugar_c = st.radio("¿Se jugará Cumpleaños este año?", ["SI", "NO"], index=0 if get_config("jugar_cumpleanos", "SI", str) == "SI" else 1, horizontal=True)
            cuota_c = st.number_input("Cuota por Socio para el Cumpleañero (S/)", value=get_config("cuota_cumpleanos", 0.0))
            st.divider()
            
            ap_m, am_min = st.number_input("Aporte Mensual por Acción", value=get_config("aporte_mensual", 0.0)), st.number_input("Amortización Mínima a Capital (Fija)", value=get_config("monto_minimo_capital", 0.0))
            ins, int_p = st.number_input("Inscripción Base por Acción (S/)", value=get_config("cuota_inscripcion", 0.0)), st.number_input("Interés Mensual del Préstamo (%)", value=get_config("interes_prestamo", 0.0))
            
            st.divider(); st.write("#### 💳 Tope de Préstamo por Acción")
            tope_act, tope_monto = st.radio("Activar Tope Máximo de Préstamo por Acción", ["SI", "NO"], index=0 if get_config("tope_prestamo_activo", "NO", str) == "SI" else 1, horizontal=True), st.number_input("Monto Máximo de Préstamo (S/)", value=get_config("tope_prestamo_monto", 0.0))
            
            st.divider(); st.write("#### 📉 Amortización de Préstamos")
            amort_pct_act, amort_pct_val = st.radio("Amortización por Porcentaje (sobre monto inicial de la acción)", ["SI", "NO"], index=0 if get_config("amort_porcentaje_activo", "NO", str) == "SI" else 1, horizontal=True), st.number_input("Porcentaje Mínimo (%)", value=get_config("amort_porcentaje_valor", 0.0))
            mes_lim = st.number_input("Mes Límite para los 3 pagos mínimos fijos (1-12)", min_value=1, max_value=12, value=int(get_config("mes_limite_minimos", 12)))
            
            c1_r, c2_r = st.columns(2)
            if c1_r.button("💾 GUARDAR NUEVAS REGLAS", type="primary"):
                for clave, val in [('jugar_cumpleanos', jugar_c), ('cuota_cumpleanos', cuota_c), ('aporte_mensual', ap_m), ('monto_minimo_capital', am_min), ('cuota_inscripcion', ins), ('interes_prestamo', int_p), ('tope_prestamo_activo', tope_act), ('tope_prestamo_monto', tope_monto), ('amort_porcentaje_activo', amort_pct_act), ('amort_porcentaje_valor', amort_pct_val), ('mes_limite_minimos', str(int(mes_lim)))]: db_query("UPDATE configuracion SET valor=? WHERE clave=?", (val, clave), fetch=False)
                st.session_state.reglas_unlocked = False; st.success("Reglas financieras actualizadas con éxito."); st.rerun()
            if c2_r.button("🔒 BLOQUEAR PANEL"): st.session_state.reglas_unlocked = False; st.rerun()
        
    elif menu_t == "🎁 REPARTO UTILIDADES":
        st.subheader("🎁 Reparto de Utilidades (Ganancias)")
        st.write("Esta sección permite distribuir el dinero generado por los intereses. El pozo se reinicia automáticamente después de cada reparto.")

        caja_prin_disp = (float(db_query("SELECT SUM(monto) FROM movimientos")[0][0] or 0.0) - ((db_query("SELECT SUM(monto) FROM movimientos WHERE tipo LIKE 'Ingreso Caja Chica%' OR tipo = 'Depósito Caja'")[0][0] or 0.0) - abs(db_query("SELECT SUM(monto) FROM movimientos WHERE tipo LIKE 'Egreso Caja Chica%' OR tipo = 'Retiro Caja'")[0][0] or 0.0)))
        tot_int_disponible = max(0.0, float(db_query("SELECT SUM(monto) FROM movimientos WHERE tipo LIKE '%nter%' AND tipo NOT LIKE '%Caja Chica%'")[0][0] or 0.0) + float(db_query("SELECT SUM(monto) FROM movimientos WHERE tipo LIKE 'Pago Directiva%' OR tipo LIKE 'Pago Utilidades%' OR tipo LIKE 'Ajuste Interno - Salida de Utilidades%'")[0][0] or 0.0))
        tot_acciones = int(db_query("SELECT SUM(acciones) FROM socios")[0][0] or 0)
        anio_actual = datetime.now().year

        with st.expander("🔮 Proyección de Ganancias a Diciembre (Cierre de Año)", expanded=False):
            tasa, m_min = get_config("interes_prestamo", 0.0) / 100.0, get_config("monto_minimo_capital", 50.0)
            meses_restantes = max(0, 12 - datetime.now().month)
            proyeccion_futura_int = 0.0
            
            prestamos_activos = db_query("SELECT saldo_actual FROM prestamos WHERE estado='ACTIVO'")
            if meses_restantes > 0 and prestamos_activos:
                for p in prestamos_activos:
                    saldo_sim = p[0]
                    for _ in range(meses_restantes):
                        if saldo_sim > 0.01:
                            int_mes = float(math.ceil(saldo_sim * tasa)); proyeccion_futura_int += int_mes; saldo_sim -= min(m_min if m_min > 0 else 50.0, saldo_sim)
                            
            st.write(f"Meses restantes hasta Diciembre: **{meses_restantes}**")
            c_proy1, c_proy2, c_proy3 = st.columns(3)
            c_proy1.metric("Pozo Actual Disponible", f"S/ {f_m(tot_int_disponible)}")
            c_proy2.metric(f"Intereses Futuros Estimados", f"S/ {f_m(proyeccion_futura_int)}")
            c_proy3.metric("Total Esperado a Diciembre", f"S/ {f_m(tot_int_disponible + proyeccion_futura_int)}")
            st.info("💡 Usa este **Total Esperado a Diciembre** para saber cuánto efectivo debes retener en la Caja Principal y no quedarte sin fondos para los pagos de fin de año al seguir prestando.")

        if tot_acciones > 0 and tot_int_disponible > 0:
            directivos = [f"{cargo}: {nombre}" for cargo, nombre in zip(["Presidente", "Tesorero", "Secretario"], [get_config("presidente", "No asignado", str), get_config("tesorero", "No asignado", str), get_config("secretario", "No asignado", str)]) if nombre != "No asignado"]
            
            st.write("### 1. Pago a la Junta Directiva (3%)")
            seleccionados = st.multiselect("Seleccione a los directivos que recibirán pago en este momento:", directivos, default=directivos)
            
            monto_3_pct = tot_int_disponible * 0.03
            excedente_3 = monto_3_pct
            
            if seleccionados:
                pago_cu_truncado = truncar_a_un_decimal(monto_3_pct / len(seleccionados))
                excedente_3 = monto_3_pct - (pago_cu_truncado * len(seleccionados))
                
                for ds in seleccionados:
                    ya_pagado_dir = db_query("SELECT id FROM movimientos WHERE tipo = ? AND monto < 0", (f"Pago Directiva {anio_actual} - {ds}",))
                    c1, c2 = st.columns([3, 1])
                    c1.write(f"**{ds}**: S/ {f_m(pago_cu_truncado)}")
                    if ya_pagado_dir: c2.success("✅ Pagado")
                    else:
                        if c2.button(f"💸 Pagar {ds.split(':')[0]}", key=f"pay_dir_{ds}"):
                            if caja_prin_disp >= pago_cu_truncado:
                                fh_exacta = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                                db_query("UPDATE cuentas SET saldo = saldo - ? WHERE id_usuario=1", (pago_cu_truncado,), fetch=False)
                                db_query("INSERT INTO movimientos (id_usuario, tipo, monto, fecha) VALUES (1, ?, ?, ?)", (f"Pago Directiva {anio_actual} - {ds}", -pago_cu_truncado, fh_exacta), fetch=False)
                                st.rerun()
                            else: st.error("⚠️ Faltan fondos en Caja Principal.")
            else: st.info("No se seleccionó a nadie de la directiva. El 100% del 3% pasará al pozo de socios.")
                
            st.divider()

            monto_socios_bruto = (tot_int_disponible * 0.97) + excedente_3
            pago_por_accion_truncado = truncar_a_un_decimal(monto_socios_bruto / tot_acciones) if tot_acciones > 0 else 0.0
            sobrante_caja_chica = monto_socios_bruto - (pago_por_accion_truncado * tot_acciones)

            st.write("### 2. Reparto a Socios (97% + Excedentes)")
            c1, c2, c3 = st.columns(3)
            c1.metric("Fondo de Socios", f"S/ {f_m(monto_socios_bruto)}")
            c2.metric("A Pagar x Acción", f"S/ {f_m(pago_por_accion_truncado)}")
            c3.metric("Sobrante para Caja Chica", f"S/ {f_m(sobrante_caja_chica)}")

            socios_data = db_query("SELECT dni, nombres, apellidos, acciones FROM socios ORDER BY nombres ASC")
            todos_pagados = True
            if pago_por_accion_truncado > 0:
                for s_dni, s_nom, s_ape, s_acc in socios_data:
                    if not db_query("SELECT id FROM movimientos WHERE tipo = ? AND monto < 0", (f"Pago Utilidades {anio_actual} - {s_dni} ({s_acc} acc)",)):
                        todos_pagados = False; break

            if sobrante_caja_chica > 0.01:
                if db_query("SELECT id FROM movimientos WHERE tipo = ?", (f"Ingreso Caja Chica - Sobrante Utilidades {anio_actual}",)): st.success("✅ El sobrante ya fue trasladado a Caja Chica.")
                else:
                    if not todos_pagados: st.warning("⏳ Debes pagar a todos los socios antes de poder pasar el sobrante a la Caja Chica.")
                    elif caja_prin_disp < sobrante_caja_chica: st.error("❌ No hay fondos reales en la Caja Principal para realizar el pase a la Caja Chica.")
                    else:
                        if st.button("📥 Pasar Sobrante a Caja Chica", type="primary"):
                            fh_exacta = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                            db_query("INSERT INTO movimientos (id_usuario, tipo, monto, fecha) VALUES (1, ?, ?, ?)", (f"Ajuste Interno - Salida de Utilidades {anio_actual}", -sobrante_caja_chica, fh_exacta), fetch=False)
                            db_query("INSERT INTO movimientos (id_usuario, tipo, monto, fecha) VALUES (1, ?, ?, ?)", (f"Ingreso Caja Chica - Sobrante Utilidades {anio_actual}", sobrante_caja_chica, fh_exacta), fetch=False)
                            st.rerun()

            st.write("#### Lista de Pagos a Socios")
            if pago_por_accion_truncado > 0:
                for s_dni, s_nom, s_ape, s_acc in socios_data:
                    monto_pagar = pago_por_accion_truncado * s_acc
                    col1, col2, col3, col4 = st.columns([3, 1, 2, 2])
                    col1.write(f"**{s_nom.split()[0]} {s_ape.split()[0]}**"); col2.write(f"{s_acc} Acciones"); col3.write(f"**S/ {f_m(monto_pagar)}**")
                    with col4:
                        if db_query("SELECT id FROM movimientos WHERE tipo = ? AND monto < 0", (f"Pago Utilidades {anio_actual} - {s_dni} ({s_acc} acc)",)): st.success("✅ Pagado")
                        else:
                            if st.button(f"💸 Pagar Socio", key=f"pay_socio_{s_dni}"):
                                if caja_prin_disp >= monto_pagar:
                                    fh_exacta = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                                    db_query("UPDATE cuentas SET saldo = saldo - ? WHERE id_usuario=1", (monto_pagar,), fetch=False)
                                    db_query("INSERT INTO movimientos (id_usuario, tipo, monto, fecha) VALUES (1, ?, ?, ?)", (f"Pago Utilidades {anio_actual} - {s_dni} ({s_acc} acc)", -monto_pagar, fh_exacta), fetch=False)
                                    st.rerun()
                                else: st.error("⚠️ Faltan fondos en la Caja Principal para realizar este pago.")
                    st.write("---")
            else: st.info("El monto por acción calculado es 0. Aún no hay suficientes utilidades.")
                
            st.divider(); st.subheader("📄 Acta de Cierre de Año")
            st.write(f"Descarga el documento formal en PDF con el resumen de todos los pagos realizados a la directiva, socios y caja chica en el año {anio_actual}.")
            if db_query("SELECT id FROM movimientos WHERE tipo LIKE ? OR tipo LIKE ?", (f"Pago Utilidades {anio_actual}%", f"Pago Directiva {anio_actual}%")):
                st.download_button("📥 DESCARGAR ACTA DE CIERRE PDF", data=generar_pdf_acta_cierre(anio_actual), file_name=f"Acta_Cierre_{anio_actual}.pdf", mime="application/pdf", type="primary")
            else: st.info("Aún no se han realizado pagos de utilidades en este año. El acta estará disponible cuando comiences a pagar.")
        else: st.warning("No hay acciones registradas o no se han generado intereses para repartir.")

    elif menu_t == "🎂 CUMPLEAÑOS": ui_cumpleanos_admin(es_tesorero=True)

    elif menu_t == "↩️ ANULAR OPERACIÓN":
        st.subheader("↩️ Anular Operación (Corrección de Errores)")
        st.write("Esta herramienta permite revertir un movimiento registrado por error. El sistema devolverá el dinero a la Caja Principal y eliminará el registro.")
        
        if 'anular_success' in st.session_state: st.success(st.session_state.anular_success); del st.session_state['anular_success']

        movs_recientes = db_query("SELECT id, fecha, tipo, monto FROM movimientos ORDER BY id DESC LIMIT 50")
        if movs_recientes:
            opciones_mov = {f"[{format_fecha(m[1][:16])}] {format_movimiento(m[2])} | S/ {f_m(m[3])} (ID: {m[0]})": m for m in movs_recientes}
            id_mov, f_mov, t_mov, m_mov = opciones_mov[st.selectbox("Seleccione el movimiento a anular:", list(opciones_mov.keys()))]
            
            st.warning("⚠️ **Atención:** Esta acción requiere autorización presidencial. El saldo de la Caja Principal se ajustará automáticamente.")
            st.info("💡 **Nota Importante:** El sistema ajustará automáticamente el número de acciones o el saldo de las deudas según el tipo de operación que se esté anulando.")
            
            with st.form("form_anular_op"):
                cp = st.text_input("Clave del Presidente para autorizar:", type="password")
                if st.form_submit_button("🚨 CONFIRMAR Y ANULAR OPERACIÓN", type="primary"):
                    if cp == get_config("password_presidente", "123456", str):
                        db_query("UPDATE cuentas SET saldo = saldo - ? WHERE id_usuario=1", (m_mov,), fetch=False)
                        try:
                            if "Pago Cuota" in t_mov:
                                dni_match, acc_match = re.search(r'\b\d+\b', t_mov), re.search(r'Acción (\d+)', t_mov)
                                if dni_match and acc_match: db_query("UPDATE prestamos SET saldo_actual = saldo_actual + ?, estado='ACTIVO', conteo_minimos = MAX(0, conteo_minimos - 1) WHERE dni_socio=? AND accion_asociada=?", (m_mov, dni_match.group(0), int(acc_match.group(1))), fetch=False)
                            elif "Préstamo a" in t_mov:
                                dni_match, acc_match = re.search(r'\b\d+\b', t_mov), re.search(r'Acción (\d+)', t_mov)
                                if dni_match and acc_match: db_query("UPDATE prestamos SET monto_original = monto_original - ?, saldo_actual = saldo_actual - ? WHERE dni_socio=? AND accion_asociada=?", (abs(m_mov), abs(m_mov), dni_match.group(0), int(acc_match.group(1))), fetch=False)
                            elif "Aporte Inicial" in t_mov or "Compra Extra" in t_mov:
                                dni_match, acc_q_match = re.search(r'\b\d+\b', t_mov), re.search(r'\((\d+) acc\)', t_mov)
                                if dni_match and acc_q_match: db_query("UPDATE socios SET acciones = acciones - ? WHERE dni=?", (int(acc_q_match.group(1)), dni_match.group(0)), fetch=False)
                        except: pass 
                        
                        db_query("DELETE FROM movimientos WHERE id=?", (id_mov,), fetch=False)
                        db_query("INSERT INTO historial_anulaciones (fecha, detalle, autorizador) VALUES (?,?,?)", (datetime.now().strftime("%Y-%m-%d %H:%M:%S"), f"Se anuló operación ID {id_mov}: {format_movimiento(t_mov)} por S/ {f_m(m_mov)}", "Presidente"), fetch=False)
                        st.session_state.anular_success = "✅ Operación anulada correctamente. Caja, Deudas y Acciones han sido restauradas."; st.rerun()
                    else: st.error("❌ Clave de presidente incorrecta.")
                        
            st.divider(); st.write("### 📜 Historial de Anulaciones")
            historial_anul = db_query("SELECT fecha, detalle, autorizador FROM historial_anulaciones ORDER BY id DESC")
            if historial_anul:
                df_ha = pd.DataFrame(historial_anul, columns=["Fecha", "Detalle", "Autorizador"])
                df_ha["Fecha"], df_ha["Detalle"] = df_ha["Fecha"].apply(format_fecha), df_ha["Detalle"].apply(format_movimiento)
                st.dataframe(df_ha, use_container_width=True)
                st.download_button("📥 DESCARGAR HISTORIAL (CSV)", data=df_ha.to_csv(index=False).encode('utf-8'), file_name="Historial_Anulaciones.csv", mime="text/csv", type="primary")
            else: st.info("No hay anulaciones registradas en el historial.")