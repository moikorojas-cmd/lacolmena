import streamlit as st
import sqlite3
import math
from datetime import datetime, date, time
import pandas as pd
import os
import smtplib
import re
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.application import MIMEApplication

try:
    from fpdf import FPDF
except ImportError:
    st.error("Falta instalar FPDF. Agrega 'fpdf' a tu archivo requirements.txt")

# =============================================================================
# 1. CONFIGURACIÓN INICIAL Y BASE DE DATOS
# =============================================================================
st.set_page_config(page_title="Banquito La Colmena", page_icon="🐝", layout="wide")

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

        try: c.execute('''ALTER TABLE socios ADD COLUMN fecha_nacimiento TEXT''')
        except: pass
        try: c.execute('''ALTER TABLE tramites ADD COLUMN respuesta TEXT''')
        except: pass

        try:
            hoy_str = datetime.now().strftime("%Y-%m-%d")
            c.execute("INSERT OR IGNORE INTO configuracion (clave, valor) VALUES (?, ?)", ("fecha_fundacion", hoy_str))
            c.execute("INSERT OR IGNORE INTO configuracion (clave, valor) VALUES (?, ?)", ("monto_minimo_capital", "0.0"))
            c.execute("INSERT OR IGNORE INTO configuracion (clave, valor) VALUES (?, ?)", ("cuota_inscripcion", "0.0"))
            c.execute("INSERT OR IGNORE INTO configuracion (clave, valor) VALUES (?, ?)", ("interes_prestamo", "0.0"))
            c.execute("INSERT OR IGNORE INTO configuracion (clave, valor) VALUES (?, ?)", ("aporte_mensual", "0.0"))
            c.execute("INSERT OR IGNORE INTO configuracion (clave, valor) VALUES (?, ?)", ("presidente", "No asignado"))
            c.execute("INSERT OR IGNORE INTO configuracion (clave, valor) VALUES (?, ?)", ("telefono_presidente", ""))
            c.execute("INSERT OR IGNORE INTO configuracion (clave, valor) VALUES (?, ?)", ("tesorero", "No asignado"))
            c.execute("INSERT OR IGNORE INTO configuracion (clave, valor) VALUES (?, ?)", ("secretario", "No asignado"))
            c.execute("INSERT OR IGNORE INTO configuracion (clave, valor) VALUES (?, ?)", ("password_presidente", "123456"))
            c.execute("INSERT OR IGNORE INTO configuracion (clave, valor) VALUES (?, ?)", ("proxima_reunion", hoy_str))
            c.execute("INSERT OR IGNORE INTO configuracion (clave, valor) VALUES (?, ?)", ("proxima_reunion_hora", "16:00"))
            c.execute("INSERT OR IGNORE INTO usuarios (id, nombre, usuario, password, rol) VALUES (1, 'Administrador Principal', 'admin', 'admin123', 'superadmin')")
            c.execute("INSERT OR IGNORE INTO cuentas (id_usuario, saldo) VALUES (1, 0.0)")
        except: pass
        conn.commit()

inicializar_db()

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

def enviar_alerta_sms_simulada(usuario_intruso):
    tel_presi = get_config("telefono_presidente", "No registrado", str)
    st.toast(f"📱 SMS ENVIADO al {tel_presi}: ALERTA. El usuario '{usuario_intruso}' intentó acceder a la bóveda fuera de la fecha agendada.", icon="🚨")

# =============================================================================
# 2. LÓGICA MATEMÁTICA Y FINANCIERA (PDFs)
# =============================================================================
def calcular_nivelacion_por_accion():
    fundador = db_query("SELECT dni, acciones FROM socios WHERE es_fundador = 1 AND acciones > 0 ORDER BY id ASC LIMIT 1")
    if not fundador: return 0.0, 0.0
    dni_f, acc_f = fundador[0][0], float(fundador[0][1] or 1.0)
    movs = db_query("SELECT fecha, monto FROM movimientos WHERE tipo LIKE '%Aporte%' AND tipo LIKE ?", (f"%{dni_f}%",))
    aportes_mes = {}
    for f, m in movs:
        mes = f[:7]
        aportes_mes[mes] = aportes_mes.get(mes, 0.0) + float(m)
    tasa = get_config("interes_prestamo", 0.0) / 100.0
    mes_actual = datetime.now().strftime("%Y-%m")
    cap_global, int_global = 0.0, 0.0
    for mes in sorted(aportes_mes.keys()):
        cap_global += aportes_mes[mes]
        if mes < mes_actual: int_global += cap_global * tasa
    return cap_global / acc_f, int_global / acc_f

def generar_pdf_estado_cuenta(nombre_completo, dni, acc_num):
    tasa = get_config("interes_prestamo", 0.0) / 100.0
    m_min = get_config("monto_minimo_capital", 50.0)
    res_p = db_query("SELECT saldo_actual FROM prestamos WHERE dni_socio=? AND accion_asociada=? AND estado='ACTIVO'", (dni, acc_num))
    saldo_hoy = res_p[0][0] if res_p else 0.0
    filtro = f"%{dni}%(Acción {acc_num})%"
    movs = db_query("SELECT fecha, tipo, monto FROM movimientos WHERE tipo LIKE ? AND (tipo LIKE '%Préstamo%' OR tipo LIKE '%Pago Cuota%' OR tipo LIKE '%Interés Cuota%') ORDER BY fecha ASC", (filtro,))
    pdf = FPDF(); pdf.add_page(); pdf.set_font("Courier", size=9)
    header = f"ESTADO DE CUENTA DETALLADO - ACCIÓN {acc_num}\nBANQUITO LA COLMENA 🐝\n" + "="*85 + "\n"
    header += f"Socio: {nombre_completo}\nDNI  : {dni}\nFecha de reporte: {datetime.now().strftime('%d/%m/%Y %H:%M')}\n" + "="*85 + "\n\n"
    header += "⏪ PARTE 1: HISTORIAL DE MOVIMIENTOS REALIZADOS\n" + "-"*85 + "\n"
    header += f"{'FECHA':<10} | {'DETALLE':<20} | {'CAPITAL':<9} | {'INTERES':<9} | {'CUOTA':<9} | {'SALDO CAP.'}\n" + "-"*85 + "\n"
    reporte_texto = header; saldo_acumulado = 0.0; historial_agrupado = {}
    for m in movs:
        f, t, mon = m[0], m[1], m[2]
        if f not in historial_agrupado: historial_agrupado[f] = {'cap': 0.0, 'int': 0.0, 'tipo': ''}
        if "Préstamo" in t: historial_agrupado[f]['cap'] = abs(mon); historial_agrupado[f]['tipo'] = "DESEMBOLSO"
        elif "Pago Cuota" in t: historial_agrupado[f]['cap'] = -abs(mon); historial_agrupado[f]['tipo'] = "PAGO"
        elif "Interés" in t: historial_agrupado[f]['int'] = abs(mon)
    for f in sorted(historial_agrupado.keys()):
        d_mov = historial_agrupado[f]
        if d_mov['tipo'] == "DESEMBOLSO":
            saldo_acumulado += d_mov['cap']
            reporte_texto += f"{f[:10]:<10} | {'NUEVO PRÉSTAMO':<20} | {d_mov['cap']:>9.2f} | {'0.00':>9} | {d_mov['cap']:>9.2f} | {saldo_acumulado:>10.2f}\n"
        else:
            saldo_acumulado += d_mov['cap']
            cap_pagado, int_pagado = abs(d_mov['cap']), d_mov['int']
            reporte_texto += f"{f[:10]:<10} | {'PAGO CUOTA':<20} | {cap_pagado:>9.2f} | {int_pagado:>9.2f} | {cap_pagado+int_pagado:>9.2f} | {saldo_acumulado:>10.2f}\n"
    reporte_texto += "\n\n⏩ PARTE 2: PROYECCIÓN DE PAGOS PENDIENTES\n" + "-"*85 + "\n"
    reporte_texto += f"{'FECHA':<10} | {'DETALLE':<20} | {'CAPITAL':<9} | {'INTERES':<9} | {'CUOTA':<9} | {'SALDO CAP.'}\n" + "-"*85 + "\n"
    sp, fh, mes, anio, total_proyectado = saldo_hoy, datetime.now(), datetime.now().month, datetime.now().year, 0.0
    amort_minima_real = m_min if m_min > 0 else 50.0
    while sp > 0.01:
        mes += 1
        if mes > 12: mes = 1; anio += 1
        i = float(math.ceil(sp * tasa)); am = min(amort_minima_real, sp); cuo = am + i; sp -= am; total_proyectado += cuo
        reporte_texto += f"06/{mes:02d}/{anio:<5} | {'CUOTA PENDIENTE':<20} | {am:>9.2f} | {i:>9.2f} | {cuo:>9.2f} | {max(0.0, sp):>10.2f}\n"
    reporte_texto += "-"*85 + "\n" + f"Saldo actual de capital: S/ {saldo_hoy:.2f}\nTotal estimado para liquidar deuda: S/ {total_proyectado:.2f}\n" + "="*85 + "\n"
    for line in reporte_texto.split('\n'): pdf.cell(0, 5, txt=line.encode('latin-1','ignore').decode('latin-1'), ln=True)
    f_n = f"R_{dni}_{acc_num}.pdf"; pdf.output(f_n)
    with open(f_n, "rb") as f: b = f.read()
    os.remove(f_n); return b

def generar_pdf_desembolso_completo(nom_soc, d, n_a, m_prestado, m_proy, tot_i, cuotas, fh, tasa):
    nom_presi, nom_teso, nom_secri, anio_actual = get_config("presidente", "No asignado", str), get_config("tesorero", "No asignado", str), get_config("secretario", "No asignado", str), datetime.now().year
    pdf = FPDF()
    # PÁGINA 1
    pdf.add_page(); pdf.set_font("Courier", 'B', 14); pdf.cell(0, 10, "BANQUITO LA COLMENA - VOUCHER DE DESEMBOLSO", ln=True, align='C')
    pdf.set_font("Courier", size=12); pdf.ln(5)
    texto_v = f"Fecha: {fh}\nSocio: {nom_soc}\nDNI:   {d} | Accion Vinculada: {n_a}\n" + "-"*50 + f"\nMONTO DESEMBOLSADO EN EFECTIVO : S/ {m_prestado:.2f}\n" + "-"*50 + "\n\n\n     ____________________________\n          FIRMA DEL SOCIO\n"
    for l in texto_v.split('\n'): pdf.cell(0, 6, txt=l.encode('latin-1','ignore').decode('latin-1'), ln=True)
    # PÁGINA 2
    pdf.add_page(); pdf.set_font("Courier", 'B', 14); pdf.cell(0, 10, "CRONOGRAMA DE PRESTAMO", ln=True, align='C'); pdf.set_font("Courier", size=10); pdf.ln(5)
    tc = f"Socio: {nom_soc}\nDNI: {d} | Accion: {n_a}\nFecha de Emision: {fh}\nDeuda Total Capital: S/ {m_proy:.2f} | Int. Proyectado: S/ {tot_i:.2f} | Total a Pagar: S/ {m_proy+tot_i:.2f}\n----------------------------------------------------------------\n{'FECHA':<10} | {'DETALLE':<15} | {'CAPITAL':<8} | {'INTERES':<8} | {'CUOTA':<8} | {'SALDO CAP.'}\n----------------------------------------------------------------\n"
    saldo = m_proy
    for c in cuotas: 
        fecha, cap, interes, cuota = c[0], c[1], c[2], c[3]
        saldo -= cap
        if saldo < 0.01: saldo = 0.0
        tc += f"{fecha:<10} | {'Cuota Mensual':<15} | {cap:>8.2f} | {interes:>8.2f} | {cuota:>8.2f} | {saldo:>10.2f}\n"
    for l in tc.split('\n'): pdf.cell(0, 5, txt=l.encode('latin-1','ignore').decode('latin-1'), ln=True)
    # PÁGINA 3
    pdf.add_page(); pdf.set_font("Arial", 'B', 14); pdf.cell(0, 10, "CONTRATO PRIVADO DE PRÉSTAMO DE DINERO", ln=True, align='C'); pdf.ln(5)
    pdf.set_font("Arial", '', 11)
    intro = f"Conste por el presente documento privado de préstamo de dinero que celebran, de una parte, la Junta Directiva del periodo {anio_actual} del BANQUITO LA COLMENA, debidamente representada por:"
    pdf.multi_cell(0, 6, txt=intro.encode('latin-1','ignore').decode('latin-1'), align='C'); pdf.ln(4)
    pdf.set_font("Arial", 'B', 11); pdf.cell(0, 6, "EL PRESTAMISTA", ln=True, align='C'); pdf.set_font("Arial", '', 11)
    pdf.multi_cell(0, 6, txt=f"Presidente(a): {nom_presi} | Tesorero(a): {nom_teso} | Secretario(a): {nom_secri}".encode('latin-1','ignore').decode('latin-1'), align='C'); pdf.ln(4)
    pdf.set_font("Arial", 'B', 11); pdf.cell(0, 6, "EL PRESTATARIO", ln=True, align='C'); pdf.set_font("Arial", '', 11)
    pdf.multi_cell(0, 6, txt=f"Socio(a): {nom_soc} | DNI: {d}".encode('latin-1','ignore').decode('latin-1'), align='C'); pdf.ln(6)
    pdf.set_font("Arial", 'B', 11); pdf.cell(0, 6, "CLÁUSULAS DEL CONTRATO", ln=True, align='C'); pdf.ln(2)
    pdf.set_font("Arial", 'B', 11); pdf.multi_cell(0, 6, "PRIMERA: DEL PRÉSTAMO Y LA DEUDA TOTAL", align='C'); pdf.set_font("Arial", '', 11)
    clausula_1 = f"EL PRESTAMISTA otorga a EL PRESTATARIO un nuevo desembolso en efectivo por la suma de S/ {m_prestado:.2f}. "
    if m_proy > m_prestado: clausula_1 += f"Sumado al saldo deudor anterior, la DEUDA TOTAL ACTUALIZADA asciende a la suma de S/ {m_proy:.2f}, "
    else: clausula_1 += f"La DEUDA TOTAL ACTUALIZADA asciende a la suma de S/ {m_proy:.2f}, "
    clausula_1 += f"vinculada a la Acción Nro. {n_a}."
    pdf.multi_cell(0, 6, txt=clausula_1.encode('latin-1','ignore').decode('latin-1'), align='C'); pdf.ln(3)
    pdf.set_font("Arial", 'B', 11); pdf.multi_cell(0, 6, "SEGUNDA: DE LOS INTERESES", align='C'); pdf.set_font("Arial", '', 11)
    pdf.multi_cell(0, 6, txt=f"El capital total prestado devengará un interés compensatorio mensual del {tasa * 100:.1f}%.".encode('latin-1','ignore').decode('latin-1'), align='C'); pdf.ln(3)
    pdf.set_font("Arial", 'B', 11); pdf.multi_cell(0, 6, "TERCERA: DE LA DEVOLUCIÓN", align='C'); pdf.set_font("Arial", '', 11)
    pdf.multi_cell(0, 6, txt="EL PRESTATARIO se obliga y compromete a devolver el capital total prestado más los intereses generados mediante pagos mensuales y continuos los días 06 de cada mes, cumpliendo estrictamente con la amortización mínima obligatoria pactada en asamblea general.".encode('latin-1','ignore').decode('latin-1'), align='C'); pdf.ln(3)
    pdf.set_font("Arial", 'B', 11); pdf.multi_cell(0, 6, "CUARTA: DEL INCUMPLIMIENTO", align='C'); pdf.set_font("Arial", '', 11)
    pdf.multi_cell(0, 6, txt="En caso de demora, morosidad o incumplimiento en el pago de las cuotas, EL PRESTATARIO acepta y autoriza someterse a las multas, sanciones o al descuento directo y automático de sus ahorros (capitalización) depositados en EL BANQUITO, conforme al reglamento interno vigente.".encode('latin-1','ignore').decode('latin-1'), align='C'); pdf.ln(8)
    pdf.multi_cell(0, 6, txt=f"Suscrito y firmado en señal de estricta conformidad, el día {fh[:10]}.".encode('latin-1','ignore').decode('latin-1'), align='C'); pdf.ln(20)
    firmas = "_____________________________                 _____________________________\nEL PRESTATARIO                               POR EL PRESTAMISTA\n"
    firmas += f"DNI: {d:<15}                       (Junta Directiva {anio_actual})"
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
    pdf.set_font("Arial", 'B', 12); pdf.cell(0, 10, f"CONSTANCIA DE {tipo.upper()}", ln=True, align='C'); pdf.ln(10); pdf.set_font("Arial", '', 12)
    fecha_hoy = datetime.now().strftime("%d de %B de %Y")
    if tipo == "Socio Activo": texto = f"La Junta Directiva del Banquito La Colmena hace constar que el Sr(a). {socio_nom.upper()}, identificado con DNI {dni}, se encuentra registrado como SOCIO ACTIVO de nuestra institucion, cumpliendo con sus aportaciones a la fecha.\n\nSe expide el presente documento a solicitud del interesado para los fines que considere convenientes."
    else: texto = f"La Junta Directiva del Banquito La Colmena certifica que el Sr(a). {socio_nom.upper()}, con DNI {dni}, NO MANTIENE DEUDAS PENDIENTES por concepto de prestamos en ninguna de sus acciones a la fecha de hoy.\n\nSe extiende la presente constancia para acreditar su solvencia interna dentro de la organizacion."
    pdf.multi_cell(0, 8, txt=texto.encode('latin-1','ignore').decode('latin-1'), align='J')
    pdf.ln(30); pdf.cell(0, 10, "__________________________", ln=True, align='C'); pdf.cell(0, 5, "Secretaria / Junta Directiva", ln=True, align='C'); pdf.cell(0, 5, f"Fecha: {fecha_hoy}", ln=True, align='C')
    f = f"C_{dni}.pdf"; pdf.output(f)
    with open(f, "rb") as fi: b = fi.read()
    os.remove(f); return b

def limpiar_formularios_socio():
    claves = ['ce_pdf_bytes', 'ce_msg_correo', 'ce_done', 'ns_pdf_bytes', 'ns_msg_correo', 'ns_done', 'update_success_sec']
    for clave in claves:
        if clave in st.session_state: del st.session_state[clave]

def limpiar_formularios_pago():
    claves = ['pu_tot', 'pu_det_ap', 'pu_tot_ap', 'pu_det_pr', 'pu_tot_cap', 'pu_tot_int', 'pu_show_voucher', 'pu_done', 'pu_pdf_bytes', 'pu_msg_correo', 'pu_needs_auth', 'pres_done', 'pres_pdf', 'pres_dni']
    for clave in claves:
        if clave in st.session_state: del st.session_state[clave]

# =============================================================================
# 3. GESTIÓN DE SESIONES Y BÓVEDA DE TIEMPO
# =============================================================================
if 'usuario_id' not in st.session_state:
    st.session_state.usuario_id = None
    st.session_state.usuario_rol = None
    st.session_state.usuario_nombre = None
    st.session_state.vista = 'publico'
    st.session_state.tesorero_bloqueado = False
    st.session_state.tesorero_id_temp = None

with st.sidebar:
    if st.session_state.usuario_id is None:
        st.header("🔐 Acceso Institucional")
        
        if not st.session_state.tesorero_bloqueado:
            usr = st.text_input("Usuario")
            pwd = st.text_input("Contraseña", type="password")
            if st.button("Ingresar", use_container_width=True):
                res = db_query("SELECT id, nombre, rol FROM usuarios WHERE usuario=? AND password=?", (usr, pwd))
                if res:
                    u_id, u_nom, u_rol = res[0]
                    
                    if u_rol == 'tesorero':
                        f_reunion = get_config("proxima_reunion", datetime.now().strftime("%Y-%m-%d"), str)
                        hoy_str = datetime.now().strftime("%Y-%m-%d")
                        
                        if f_reunion != hoy_str:
                            st.session_state.tesorero_bloqueado = True
                            st.session_state.tesorero_id_temp = (u_id, u_rol, u_nom)
                            enviar_alerta_sms_simulada(u_nom)
                            st.rerun()
                        else:
                            st.session_state.usuario_id = u_id
                            st.session_state.usuario_rol = u_rol
                            st.session_state.usuario_nombre = u_nom
                            st.session_state.vista = u_rol
                            st.rerun()
                    else:
                        st.session_state.usuario_id = u_id
                        st.session_state.usuario_rol = u_rol
                        st.session_state.usuario_nombre = u_nom
                        st.session_state.vista = u_rol
                        st.rerun()
                else:
                    st.error("Credenciales incorrectas")
        else:
            st.error("🛑 ACCESO A BÓVEDA DENEGADO")
            st.write("El sistema detectó que **hoy no es la fecha agendada** para la asamblea/reunión financiera.")
            st.warning("🚨 Se ha enviado una alerta SMS de seguridad al celular del Presidente.")
            
            auth_p = st.text_input("Clave del Presidente para autorizar apertura extraordinaria:", type="password")
            c1, c2 = st.columns(2)
            if c1.button("Desbloquear", type="primary"):
                if auth_p == get_config("password_presidente", "123456", str):
                    st.session_state.usuario_id = st.session_state.tesorero_id_temp[0]
                    st.session_state.usuario_rol = st.session_state.tesorero_id_temp[1]
                    st.session_state.usuario_nombre = st.session_state.tesorero_id_temp[2]
                    st.session_state.vista = st.session_state.tesorero_id_temp[1]
                    st.session_state.tesorero_bloqueado = False
                    st.success("✅ Acceso autorizado por Presidencia.")
                    st.rerun()
                else:
                    st.error("❌ Clave incorrecta.")
            if c2.button("Cancelar"):
                st.session_state.tesorero_bloqueado = False
                st.rerun()
                
        st.divider()
        if st.button("🌐 Ir al Portal de Socios", use_container_width=True):
            st.session_state.vista = 'publico'
            st.rerun()
    else:
        st.header(f"👋 Hola, {st.session_state.usuario_nombre}")
        st.write(f"**Rol:** {st.session_state.usuario_rol.upper()}")
        if st.button("Cerrar Sesión", type="primary", use_container_width=True):
            st.session_state.usuario_id = None
            st.session_state.usuario_rol = None
            st.session_state.usuario_nombre = None
            st.session_state.vista = 'publico'
            st.rerun()

# =============================================================================
# 4. VISTAS DEL SISTEMA
# =============================================================================

# -----------------------------------------------------------------------------
# VISTA: PÚBLICA (SOCIOS)
# -----------------------------------------------------------------------------
if st.session_state.vista == 'publico':
    st.title("🐝 Portal Web - Banquito La Colmena")
    
    # --- LÓGICA DE AVISOS E HISTORIAL ---
    f_reu_str = get_config("proxima_reunion", "2000-01-01", str)
    h_reu_str = get_config("proxima_reunion_hora", "16:00", str)
    try: f_reu_dt = datetime.strptime(f_reu_str, "%Y-%m-%d").date()
    except: f_reu_dt = date.today()
    
    # SOLO MOSTRAR EL HISTORIAL SI AÚN NO HA PASADO LA REUNIÓN
    if date.today() <= f_reu_dt:
        try: h_format = datetime.strptime(h_reu_str, '%H:%M').strftime('%I:%M %p')
        except: h_format = h_reu_str
        st.warning(f"📅 **PRÓXIMA REUNIÓN CONFIRMADA:** El día **{f_reu_dt.strftime('%d/%m/%Y')}** a las **{h_format}**. Por favor, acudir con puntualidad.")
        
        coms = db_query("SELECT mensaje, fecha FROM comunicados ORDER BY id DESC")
        if coms:
            with st.expander("📢 HISTORIAL DE COMUNICADOS (Muro de Avisos)", expanded=True):
                for msg, f_msg in coms:
                    st.write(f"🕒 **{f_msg}**")
                    st.write(f"📝 {msg}")
                    st.divider()
        
    t1, t2 = st.tabs(["📊 Mi Estado de Cuenta", "🤝 Simulador de Inversión"])
    
    with t1:
        dni_in = st.text_input("Ingrese su DNI para consultar:", max_chars=8)
        if st.button("Consultar"):
            soc = db_query("SELECT nombres, apellidos, acciones FROM socios WHERE dni=?", (dni_in,))
            if soc:
                n, a, acc = soc[0]
                st.header(f"Socio: {n} {a}")
                c1, c2 = st.columns(2)
                with c1:
                    st.subheader("💰 Ahorros")
                    tot_ah = db_query("SELECT SUM(monto) FROM movimientos WHERE tipo LIKE '%Aporte%' AND tipo LIKE ?", (f"%{dni_in}%",))[0][0] or 0.0
                    st.metric("Total Capitalizado", f"S/ {tot_ah:.2f}")
                    ap_fijo = get_config("aporte_mensual", 0.0)
                    st.info(f"**Aporte Mensual Obligatorio:** S/ {acc * ap_fijo:.2f} ({acc} acciones)")
                with c2:
                    st.subheader("💳 Préstamos")
                    prest = db_query("SELECT accion_asociada, saldo_actual FROM prestamos WHERE dni_socio=? AND estado='ACTIVO'", (dni_in,))
                    if prest:
                        for p in prest: st.warning(f"**Acción {p[0]}** - Saldo Capital: S/ {p[1]:.2f}")
                    else: st.success("Sin deudas activas.")
                    
                st.divider()
                st.subheader("📥 Mis Trámites (Mesa de Partes)")
                mis_tramites = db_query("SELECT fecha, tipo, estado, respuesta FROM tramites WHERE dni_socio=? ORDER BY id DESC", (dni_in,))
                if mis_tramites:
                    df_mt = pd.DataFrame(mis_tramites, columns=["Fecha", "Tipo de Trámite", "Estado Actual", "Respuesta/Resolución"])
                    st.dataframe(df_mt, use_container_width=True)
                else:
                    st.info("No tienes trámites ni solicitudes en curso.")
            else: st.error("Socio no encontrado.")
            
    with t2:
        cant_acc = st.number_input("Acciones a adquirir:", 1, 4, 1)
        if st.button("Calcular Inversión"):
            c_hist, i_hist = calcular_nivelacion_por_accion()
            ins_base = get_config("cuota_inscripcion", 0.0)
            
            t_cap = c_hist * cant_acc
            t_int = math.ceil(i_hist) * cant_acc 
            t_ins = ins_base * cant_acc
            
            st.success(f"### Total a invertir hoy: S/ {t_cap + t_int + t_ins:.2f}")
            st.write(f"- Inscripción ({cant_acc} acc): S/ {t_ins:.2f}\n- Aporte Nivelado: S/ {t_cap:.2f}\n- Interés Nivelado (Redondeado): S/ {t_int:.2f}")

# -----------------------------------------------------------------------------
# VISTA: SUPERADMIN
# -----------------------------------------------------------------------------
elif st.session_state.vista == 'superadmin':
    st.title("👑 Panel de Super Administrador")
    t1, t2 = st.tabs(["📝 Registrar Socios Fundadores", "⚙️ Asignar Junta Directiva"])
    
    with t1:
        st.subheader("Registrar Nuevo Fundador")
        with st.form("form_fun"):
            c1, c2 = st.columns(2)
            fdni = c1.text_input("DNI*")
            fnom = c1.text_input("Nombres*")
            fape = c1.text_input("Apellidos")
            ftel = c2.text_input("Teléfono")
            fdir = c2.text_input("Dirección")
            fcor = c2.text_input("Correo")
            fsex = c1.selectbox("Sexo", ["Masculino", "Femenino"])
            fnac = c2.date_input("Fecha de Nacimiento", value=date(1990, 1, 1), min_value=date(1900, 1, 1), max_value=date.today())
            facc = c1.number_input("Acciones Iniciales", 1, 4, 1)
            fap_ini = c2.number_input("Aporte Inicial por Acción (S/)", 0.0)
            
            if st.form_submit_button("Guardar Fundador", type="primary"):
                if fdni and fnom:
                    try:
                        db_query("INSERT INTO socios (dni, nombres, apellidos, telefono, direccion, correo, sexo, fecha_nacimiento, es_fundador, acciones, fecha_ingreso) VALUES (?,?,?,?,?,?,?,?,1,?,?)", 
                                 (fdni, fnom, fape, ftel, fdir, fcor, fsex, str(fnac), facc, datetime.now().strftime("%Y-%m-%d")), fetch=False)
                        tot = facc * fap_ini
                        db_query("UPDATE cuentas SET saldo = saldo + ? WHERE id_usuario=1", (tot,), fetch=False)
                        if tot>0: db_query("INSERT INTO movimientos (id_usuario, tipo, monto) VALUES (1, ?, ?)", (f"Aporte Inicial {fdni} ({facc} acc)", tot), fetch=False)
                        st.success("Fundador registrado correctamente en el padrón y caja principal.")
                    except sqlite3.IntegrityError: 
                        st.error("Error: Ese DNI ya existe en la base de datos.")
                else: st.warning("DNI y Nombres son campos obligatorios.")
                
    with t2:
        st.subheader("Configuración General de Autoridades y Accesos")
        ffun = st.text_input("Fecha de Fundación (AAAA-MM-DD)", get_config("fecha_fundacion", datetime.now().strftime("%Y-%m-%d"), str))
        socios = ["No asignado"] + [f"{r[0]} {r[1]}" for r in db_query("SELECT nombres, apellidos FROM socios ORDER BY nombres ASC")]
        
        st.divider()
        st.write("#### Presidencia")
        cpres = st.selectbox("Presidente(a)", socios, index=socios.index(get_config("presidente", "No asignado", str)) if get_config("presidente", "No asignado", str) in socios else 0)
        t_presi = st.text_input("Teléfono del Presidente (Para recibir Alertas SMS)", get_config("telefono_presidente", "", str))
        cpass = st.text_input("Clave Secreta de Autorización (Romper Cerrojos)", get_config("password_presidente", "123456", str), type="password")
        
        st.divider()
        st.write("#### Tesorería")
        ctes = st.selectbox("Tesorero(a)", socios, index=socios.index(get_config("tesorero", "No asignado", str)) if get_config("tesorero", "No asignado", str) in socios else 0)
        u_t = db_query("SELECT usuario, password FROM usuarios WHERE rol='tesorero'")
        ut_usr = st.text_input("Usuario de Acceso (Tesorero)", u_t[0][0] if u_t else "tesorero")
        ut_pwd = st.text_input("Clave de Acceso (Tesorero)", u_t[0][1] if u_t else "teso123", type="password")
        
        st.divider()
        st.write("#### Secretaría")
        csec = st.selectbox("Secretario(a)", socios, index=socios.index(get_config("secretario", "No asignado", str)) if get_config("secretario", "No asignado", str) in socios else 0)
        u_s = db_query("SELECT usuario, password FROM usuarios WHERE rol='secretario'")
        us_usr = st.text_input("Usuario de Acceso (Secretario)", u_s[0][0] if u_s else "secretaria")
        us_pwd = st.text_input("Clave de Acceso (Secretario)", u_s[0][1] if u_s else "secre123", type="password")
        
        if st.button("💾 Guardar Configuración del Sistema", type="primary"):
            db_query("UPDATE configuracion SET valor=? WHERE clave='fecha_fundacion'", (ffun,), fetch=False)
            db_query("UPDATE configuracion SET valor=? WHERE clave='presidente'", (cpres,), fetch=False)
            db_query("UPDATE configuracion SET valor=? WHERE clave='telefono_presidente'", (t_presi,), fetch=False)
            db_query("UPDATE configuracion SET valor=? WHERE clave='password_presidente'", (cpass,), fetch=False)
            db_query("UPDATE configuracion SET valor=? WHERE clave='tesorero'", (ctes,), fetch=False)
            db_query("UPDATE configuracion SET valor=? WHERE clave='secretario'", (csec,), fetch=False)
            
            if db_query("SELECT id FROM usuarios WHERE rol='tesorero'"):
                db_query("UPDATE usuarios SET nombre=?, usuario=?, password=? WHERE rol='tesorero'", (ctes, ut_usr, ut_pwd), fetch=False)
            else:
                db_query("INSERT INTO usuarios (nombre, usuario, password, rol) VALUES (?, ?, ?, 'tesorero')", (ctes, ut_usr, ut_pwd), fetch=False)
                
            if db_query("SELECT id FROM usuarios WHERE rol='secretario'"):
                db_query("UPDATE usuarios SET nombre=?, usuario=?, password=? WHERE rol='secretario'", (csec, us_usr, us_pwd), fetch=False)
            else:
                db_query("INSERT INTO usuarios (nombre, usuario, password, rol) VALUES (?, ?, ?, 'secretario')", (csec, us_usr, us_pwd), fetch=False)
                
            st.success("Configuración de la Junta Directiva y Accesos guardada con éxito.")

# -----------------------------------------------------------------------------
# VISTA: SECRETARÍA (MESA DE PARTES Y GESTIÓN)
# -----------------------------------------------------------------------------
elif st.session_state.vista == 'secretario':
    st.title("📂 Panel de Secretaría")
    m = st.radio("Menú:", ["📅 Agendar Reunión", "✏️ Actualizar Socios", "📥 Mesa de Partes", "📜 Constancias", "📢 Comunicados", "🙋 Asistencia"], horizontal=True)
    
    if m == "📅 Agendar Reunión":
        st.subheader("Agendar Próxima Asamblea / Apertura de Bóveda")
        st.write("El Tesorero SOLO podrá iniciar sesión para cobrar o prestar dinero en la fecha seleccionada. Además, se agregará un aviso automático al historial del portal de socios.")
        
        fecha_actual_str = get_config("proxima_reunion", datetime.now().strftime("%Y-%m-%d"), str)
        hora_actual_str = get_config("proxima_reunion_hora", "16:00", str)
        
        try: f_obj = datetime.strptime(fecha_actual_str, "%Y-%m-%d").date()
        except: f_obj = datetime.now().date()
        
        try: h_obj = datetime.strptime(hora_actual_str, "%H:%M").time()
        except: h_obj = datetime.strptime("16:00", "%H:%M").time()
        
        c1, c2 = st.columns(2)
        nueva_fecha = c1.date_input("Fecha de la Próxima Reunión Oficial:", value=f_obj)
        nueva_hora = c2.time_input("Hora de la Reunión:", value=h_obj)
        
        if st.button("💾 Guardar Fecha y Publicar Aviso", type="primary"):
            db_query("UPDATE configuracion SET valor=? WHERE clave='proxima_reunion'", (str(nueva_fecha),), fetch=False)
            db_query("UPDATE configuracion SET valor=? WHERE clave='proxima_reunion_hora'", (nueva_hora.strftime("%H:%M"),), fetch=False)
            
            fecha_hora_exacta = datetime.now().strftime("%d/%m/%Y %I:%M %p")
            mensaje_auto = f"Se ha agendado la próxima asamblea general y apertura de caja para el día {nueva_fecha.strftime('%d/%m/%Y')} a las {nueva_hora.strftime('%I:%M %p')}."
            db_query("INSERT INTO comunicados (mensaje, fecha) VALUES (?,?)", (mensaje_auto, fecha_hora_exacta), fetch=False)
            
            st.success(f"✅ Bóveda programada para el {nueva_fecha}. El aviso oficial se ha agregado al historial de los socios.")

    elif m == "✏️ Actualizar Socios":
        st.subheader("Buscador del Padrón de Socios")
        dni_s = st.text_input("Ingrese DNI del Socio para actualizar sus datos:")
        if dni_s:
            if 'update_success_sec' in st.session_state:
                st.success(st.session_state.update_success_sec)
                del st.session_state['update_success_sec']
                
            s = db_query("SELECT nombres, apellidos, telefono, direccion, correo, sexo, fecha_nacimiento FROM socios WHERE dni=?", (dni_s,))
            if s:
                nom, ape, tel, dir_, cor, sex, fnac_str = s[0]
                st.write(f"Editando a: **{nom} {ape}**")
                
                with st.form("edit_soc"):
                    try: fnac_obj = datetime.strptime(fnac_str, "%Y-%m-%d").date() if fnac_str else date(1990, 1, 1)
                    except: fnac_obj = date(1990, 1, 1)
                    
                    c1, c2 = st.columns(2)
                    unom = c1.text_input("Nombres", value=nom)
                    uape = c2.text_input("Apellidos", value=ape)
                    utel = c1.text_input("Teléfono", value=tel if tel else "")
                    udir = c2.text_input("Dirección", value=dir_ if dir_ else "")
                    ucor = c1.text_input("Correo", value=cor if cor else "")
                    
                    sex_index = 0 if sex == "Masculino" else 1
                    usex = c2.selectbox("Sexo", ["Masculino", "Femenino"], index=sex_index)
                    unac = c1.date_input("Fecha de Nacimiento", value=fnac_obj, min_value=date(1900, 1, 1), max_value=date.today())
                    
                    if st.form_submit_button("💾 Guardar Cambios en el Padrón", type="primary"):
                        db_query("UPDATE socios SET nombres=?, apellidos=?, telefono=?, direccion=?, correo=?, sexo=?, fecha_nacimiento=? WHERE dni=?", 
                                 (unom, uape, utel, udir, ucor, usex, str(unac), dni_s), fetch=False)
                        st.session_state.update_success_sec = "✅ Datos personales actualizados con éxito en la Base de Datos."
                        st.rerun()
            else:
                st.error("Socio no encontrado.")

    elif m == "📥 Mesa de Partes":
        st.subheader("Registro de Trámites y Documentos")
        with st.form("form_mp"):
            tdni = st.text_input("DNI Socio Solicitante:")
            ttipo = st.selectbox("Tipo de Trámite:", ["Solicitud de Renuncia", "Justificación de Inasistencia", "Queja / Sugerencia", "Otros"])
            tdet = st.text_area("Detalle del documento recibido:")
            
            if st.form_submit_button("Registrar Ingreso de Documento", type="primary"):
                if tdni and tdet:
                    db_query("INSERT INTO tramites (dni_socio, tipo, detalle, estado, fecha, respuesta) VALUES (?,?,?,?,?,?)", (tdni, ttipo, tdet, "En Revisión", datetime.now().strftime("%Y-%m-%d"), ""), fetch=False)
                    st.success("Trámite registrado con éxito y en espera de revisión por la Directiva.")
                else:
                    st.warning("DNI y Detalle son obligatorios.")
        
        st.divider()
        st.write("### Gestión de Trámites")
        tramites_pendientes = db_query("SELECT id, dni_socio, tipo, estado FROM tramites ORDER BY id DESC")
        if tramites_pendientes:
            with st.expander("🔄 Actualizar Estado de un Trámite", expanded=True):
                with st.form("form_update_tr"):
                    opciones_tr = {f"ID {t[0]} - DNI: {t[1]} - {t[2]} ({t[3]})": t[0] for t in tramites_pendientes}
                    sel_tr_str = st.selectbox("Seleccione el Trámite a actualizar:", list(opciones_tr.keys()))
                    id_tr_sel = opciones_tr[sel_tr_str]
                    
                    nuevo_est = st.selectbox("Nuevo Estado:", ["En Revisión", "Aprobado", "Rechazado", "Finalizado / Archivo"])
                    nueva_resp = st.text_input("Respuesta Oficial de la Directiva (El socio lo verá en su portal):")
                    
                    if st.form_submit_button("Guardar Actualización", type="primary"):
                        db_query("UPDATE tramites SET estado=?, respuesta=? WHERE id=?", (nuevo_est, nueva_resp, id_tr_sel), fetch=False)
                        st.success(f"Trámite ID {id_tr_sel} actualizado correctamente.")

        st.divider()
        st.write("### Historial General de Trámites")
        df_t = pd.DataFrame(db_query("SELECT id, dni_socio, tipo, estado, fecha, respuesta FROM tramites ORDER BY id DESC"), columns=["ID", "DNI", "Tipo", "Estado", "Fecha Ingreso", "Respuesta/Resolución"])
        st.dataframe(df_t, use_container_width=True)

    elif m == "📜 Constancias":
        st.subheader("Emisión de Certificados Oficiales")
        cdni = st.text_input("DNI del Socio:")
        if cdni:
            s = db_query("SELECT nombres, apellidos FROM socios WHERE dni=?", (cdni,))
            if s:
                nom_comp = f"{s[0][0]} {s[0][1]}"
                st.write(f"Socio: **{nom_comp}**")
                st.divider()
                c1, c2 = st.columns(2)
                
                with c1:
                    st.info("📜 Constancia de Membresía")
                    if st.button("Generar Constancia de Socio Activo", use_container_width=True):
                        b = generar_pdf_constancia("Socio Activo", nom_comp, cdni)
                        st.download_button("📥 Descargar Constancia PDF", b, f"Constancia_Socio_Activo_{cdni}.pdf", type="primary", use_container_width=True)
                
                with c2:
                    st.info("📜 Constancia Financiera")
                    deudas = db_query("SELECT id FROM prestamos WHERE dni_socio=? AND estado='ACTIVO'", (cdni,))
                    if not deudas:
                        if st.button("Generar Constancia de No Adeudo", use_container_width=True):
                            b = generar_pdf_constancia("No Adeudo", nom_comp, cdni)
                            st.download_button("📥 Descargar Constancia PDF", b, f"Constancia_No_Adeudo_{cdni}.pdf", type="primary", use_container_width=True)
                    else: 
                        st.error("El socio tiene deudas activas en el Banquito. NO es posible emitir Constancia de No Adeudo.")

    elif m == "📢 Comunicados":
        st.subheader("Agregar Aviso al Historial de Socios")
        st.write("El texto que escribas aquí se añadirá al Muro de Avisos del portal de los socios.")
        msg = st.text_area("Escriba el comunicado:")
        
        if st.button("Publicar Aviso a todos los socios", type="primary"):
            fecha_hora_exacta = datetime.now().strftime("%d/%m/%Y %I:%M %p")
            db_query("INSERT INTO comunicados (mensaje, fecha) VALUES (?,?)", (msg, fecha_hora_exacta), fetch=False)
            st.success("Comunicado publicado. Todos los socios lo verán al instante en su historial.")
            
        st.divider()
        st.write("### 🧹 Limpiar Pizarra")
        st.write("Si la reunión mensual ya pasó, es recomendable borrar los avisos antiguos para mantener la pizarra limpia para el próximo mes.")
        if st.button("🗑️ Borrar Todo el Historial de Comunicados"):
            db_query("DELETE FROM comunicados", fetch=False)
            st.success("La pizarra de comunicados ha sido vaciada con éxito.")

    elif m == "🙋 Asistencia":
        st.subheader("Registro de Asistencia a Asambleas Generales")
        fecha_as = st.date_input("Fecha de Asamblea", value=datetime.now())
        
        st.write("Marque la asistencia de los socios:")
        lista_socios = db_query("SELECT dni, nombres, apellidos FROM socios ORDER BY nombres ASC")
        
        with st.form("form_asistencia"):
            for sc in lista_socios:
                st.radio(f"👤 {sc[1]} {sc[2]} (DNI: {sc[0]})", ["Presente", "Tardanza", "Faltó"], key=f"as_{sc[0]}", horizontal=True)
                st.divider()
            
            if st.form_submit_button("💾 Guardar Registro de Asistencia Completo", type="primary"):
                for sc in lista_socios:
                    estado_selec = st.session_state[f"as_{sc[0]}"]
                    db_query("INSERT INTO asistencia (dni_socio, fecha_asamblea, estado) VALUES (?,?,?)", (sc[0], str(fecha_as), estado_selec), fetch=False)
                st.success(f"La asistencia para el día {fecha_as} fue guardada exitosamente en los registros.")

# -----------------------------------------------------------------------------
# VISTA: TESORERO (OPERACIONES Y PAGOS)
# -----------------------------------------------------------------------------
elif st.session_state.vista == 'tesorero':
    st.title("💼 Panel de Tesorería")
    menu_t = st.radio("Módulos:", ["👥 Socios y Compras", "💳 Pagos y Préstamos", "💰 Caja Global", "📥 Caja Chica", "⚙️ Reglas Financieras"], horizontal=True)
    
    if menu_t == "👥 Socios y Compras":
        t1, t2 = st.tabs(["🔍 Búsqueda Avanzada y Acciones Extra", "📝 Registro de Nuevo Socio"])
        
        with t1:
            dni_busq = st.text_input("🔍 Buscar DNI Socio:", on_change=limpiar_formularios_socio)
            
            if dni_busq:
                soc_full = db_query("SELECT nombres, apellidos, telefono, direccion, correo, sexo, fecha_nacimiento, fecha_ingreso, acciones, es_fundador FROM socios WHERE dni=?", (dni_busq,))
                if soc_full:
                    nom, ape, tel, dir_, cor, sex, fnac_str, fing, acc_act, esf = soc_full[0]
                    etiqueta = "🏅 SOCIO FUNDADOR" if esf == 1 else "👤 SOCIO REGULAR"
                    
                    st.markdown(f"### {etiqueta}: {nom} {ape}")
                    
                    c1, c2, c3 = st.columns(3)
                    c1.write(f"**DNI:** {dni_busq}\n\n**Teléfono:** {tel or '---'}\n\n**Correo:** {cor or '---'}")
                    c2.write(f"**Dirección:** {dir_ or '---'}\n\n**Sexo:** {sex or '---'}\n\n**Fecha Ingreso:** {fing}")
                    
                    tot_ah = db_query("SELECT SUM(monto) FROM movimientos WHERE tipo LIKE '%Aporte%' AND tipo LIKE ?", (f"%{dni_busq}%",))[0][0] or 0.0
                    c3.metric("Acciones Activas", acc_act)
                    c3.info(f"💰 **Total Ahorrado:** S/ {tot_ah:.2f}")
                    
                    with st.expander("📋 Ver Historial Completo de Movimientos"):
                        movs = db_query("SELECT id, fecha, tipo, monto FROM movimientos WHERE tipo LIKE ? ORDER BY id DESC", (f"%{dni_busq}%",))
                        if movs:
                            historial_procesado = {}
                            for id_mov, f_mov, t_mov, mon in movs:
                                fecha_exacta = f_mov
                                fecha_corta = f_mov[:10]
                                
                                if "Pago Cuota" in t_mov or "Interés Cuota" in t_mov:
                                    acc_match = re.search(r'\(Acción (\d+)\)', t_mov)
                                    acc_num = acc_match.group(1) if acc_match else "1"
                                    key = f"PAGO_{fecha_exacta}_ACC_{acc_num}"
                                    
                                    if key not in historial_procesado:
                                        historial_procesado[key] = {'fecha': fecha_corta, 'detalle': f"Pago Préstamo (Acc. {acc_num})", 'cap': 0.0, 'int': 0.0, 'total': 0.0}
                                    if "Pago Cuota" in t_mov:
                                        historial_procesado[key]['cap'] += abs(mon)
                                    else:
                                        historial_procesado[key]['int'] += abs(mon)
                                    historial_procesado[key]['total'] += abs(mon)
                                elif "Préstamo a" in t_mov:
                                    historial_procesado[f"DESEMB_{id_mov}"] = {'fecha': fecha_corta, 'detalle': "Desembolso Préstamo", 'cap': abs(mon), 'int': 0.0, 'total': abs(mon)}
                                else:
                                    t_limpio = t_mov.split("(")[0].strip() if "(" in t_mov and "Acción" in t_mov else t_mov
                                    historial_procesado[f"OTRO_{id_mov}"] = {'fecha': fecha_corta, 'detalle': t_limpio, 'cap': 0.0, 'int': 0.0, 'total': abs(mon)}

                            filas_df = []
                            for k, v in historial_procesado.items():
                                filas_df.append([v['fecha'], v['detalle'], v['cap'], v['int'], v['total']])
                            df_movs = pd.DataFrame(filas_df, columns=["Fecha", "Concepto / Detalle", "Capital (S/)", "Interés (S/)", "Total (S/)"])
                            st.dataframe(df_movs, use_container_width=True)
                        else:
                            st.write("El socio no tiene movimientos registrados.")
                            
                    st.write("#### 📑 Estado de Préstamos y Reportes por Acción")
                    for i in range(1, acc_act + 1):
                        with st.container(border=True):
                            col_a, col_b = st.columns([1, 2])
                            with col_a:
                                st.write(f"**Acción {i}**")
                                prest_activo = db_query("SELECT saldo_actual FROM prestamos WHERE dni_socio=? AND accion_asociada=? AND estado='ACTIVO'", (dni_busq, i))
                                if prest_activo:
                                    st.warning(f"Deuda Vigente: S/ {prest_activo[0][0]:.2f}")
                                else:
                                    st.success("✅ Sin deudas")
                            with col_b:
                                pdf_bytes = generar_pdf_estado_cuenta(f"{nom} {ape}", dni_busq, i)
                                st.download_button(
                                    label=f"📄 Descargar Historial y Cronograma (Acción {i})",
                                    data=pdf_bytes,
                                    file_name=f"Reporte_Completo_{dni_busq}_Acc{i}.pdf",
                                    mime="application/pdf",
                                    key=f"btn_descarga_{dni_busq}_{i}"
                                )

                    exp_abierto = 'ce_pdf_bytes' in st.session_state or 'ce_done' in st.session_state
                    with st.expander("➕ Comprar Acción Extra", expanded=True):
                        if st.session_state.get('ce_done', False):
                            st.success("🎉 ¡Pago registrado en la Caja y Acción Extra asignada en la Base de Datos!")
                            st.info(st.session_state.ce_msg_correo)
                            st.download_button(
                                label="🖨️ Descargar Voucher (Imprimir y Firmar)", 
                                data=st.session_state.ce_pdf_bytes, 
                                file_name=f"Voucher_Extra_{dni_busq}.pdf", 
                                mime="application/pdf",
                                type="primary"
                            )
                            if st.button("Finalizar y Limpiar Ventana"):
                                limpiar_formularios_socio()
                                st.rerun()
                        else:
                            if acc_act >= 4:
                                st.info("✅ Este socio ya posee el máximo de 4 acciones permitidas.")
                            else:
                                ce_acc = st.number_input("Cantidad de Acciones a comprar:", 1, 4-acc_act, 1)
                                c_hist, i_hist = calcular_nivelacion_por_accion()
                                ins_b = get_config("cuota_inscripcion", 0.0)
                                
                                ce_cap = c_hist * ce_acc
                                ce_int = math.ceil(i_hist) * ce_acc
                                ce_ins = ins_b * ce_acc
                                ce_tot = ce_cap + ce_int + ce_ins
                                
                                st.markdown("### 📄 Desglose del Pago")
                                st.write(f"- **Aportes (Capital de Nivelación):** S/ {ce_cap:.2f}")
                                st.write(f"- **Inscripción ({ce_acc} acc):** S/ {ce_ins:.2f}")
                                st.write(f"- **Interés de Nivelación:** S/ {ce_int:.2f}")
                                st.info(f"**TOTAL A PAGAR E INGRESAR A CAJA:** S/ {ce_tot:.2f}")
                                
                                if st.button("💸 PAGAR Y ASIGNAR ACCIÓN", type="primary"):
                                    db_query("UPDATE socios SET acciones = acciones + ? WHERE dni=?", (ce_acc, dni_busq), fetch=False)
                                    db_query("UPDATE cuentas SET saldo = saldo + ? WHERE id_usuario=?", (ce_tot, st.session_state.usuario_id), fetch=False)
                                    fh = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                                    if ce_cap > 0: db_query("INSERT INTO movimientos (id_usuario, tipo, monto, fecha) VALUES (?, ?, ?, ?)", (st.session_state.usuario_id, f"Aporte por Compra Extra {dni_busq} ({ce_acc} acc)", ce_cap, fh), fetch=False)
                                    if ce_int > 0: db_query("INSERT INTO movimientos (id_usuario, tipo, monto, fecha) VALUES (?, ?, ?, ?)", (st.session_state.usuario_id, f"Interés por Compra Extra {dni_busq} ({ce_acc} acc)", ce_int, fh), fetch=False)
                                    if ce_ins > 0: db_query("INSERT INTO movimientos (id_usuario, tipo, monto, fecha) VALUES (?, ?, ?, ?)", (st.session_state.usuario_id, f"Derecho Inscripción Extra {dni_busq} ({ce_acc} acc)", ce_ins, fh), fetch=False)
                                    
                                    txt_v = f"======================================\n      BANQUITO LA COLMENA\n     COMPRA DE ACCION EXTRA\n======================================\nFecha: {fh}\nSocio: {nom} {ape}\nDNI:   {dni_busq}\n--------------------------------------\n"
                                    txt_v += f"Acciones Compradas : {ce_acc}\n"
                                    txt_v += f"Aportes Nivelacion : S/ {ce_cap:.2f}\n"
                                    txt_v += f"Interes Nivelacion : S/ {ce_int:.2f}\n"
                                    txt_v += f"Inscripcion        : S/ {ce_ins:.2f}\n--------------------------------------\n"
                                    txt_v += f"TOTAL INGRESADO    : S/ {ce_tot:.2f}\n======================================\n\n\n     ____________________________\n          FIRMA DEL SOCIO\n"
                                    
                                    pdf_bytes = generar_pdf_voucher(txt_v, dni_busq)
                                    st.session_state.ce_pdf_bytes = pdf_bytes
                                    
                                    msg_correo = ""
                                    if cor:
                                        try:
                                            REMITENTE = "lacolmenabanco@gmail.com"
                                            PASSWORD = "fvux bnfk qbzv brad"
                                            msg = MIMEMultipart()
                                            msg['Subject'] = "Voucher Compra Acción Extra - Banquito La Colmena"
                                            msg['From'] = f"Banquito La Colmena <{REMITENTE}>"
                                            msg['To'] = cor
                                            cuerpo = f"Estimado/a {nom} {ape},\n\nAdjuntamos su comprobante de compra de acciones extra.\n\nAtentamente,\nBanquito La Colmena."
                                            msg.attach(MIMEText(cuerpo, 'plain', 'utf-8'))
                                            adj = MIMEApplication(pdf_bytes, _subtype="pdf")
                                            adj.add_header('Content-Disposition', 'attachment', filename=f"Voucher_Extra_{dni_busq}.pdf")
                                            server = smtplib.SMTP('smtp.gmail.com', 587); server.starttls(); server.login(REMITENTE, PASSWORD); server.send_message(msg); server.quit()
                                            msg_correo = "✅ Correo enviado con éxito al socio."
                                        except Exception as e: msg_correo = f"⚠️ Fallo el envío de correo: {e}"
                                    else: msg_correo = "ℹ️ Socio sin correo registrado."
                                        
                                    st.session_state.ce_msg_correo = msg_correo
                                    st.session_state.ce_done = True
                                    st.rerun()
                else: st.error("Socio no encontrado en el sistema.")
                
        with t2:
            st.subheader("📝 Registro de Nuevo Socio")
            if st.session_state.get('ns_done', False):
                st.success("🎉 ¡Socio nuevo registrado y pago ingresado en la Caja exitosamente!")
                st.info(st.session_state.ns_msg_correo)
                st.download_button("🖨️ Descargar Voucher (Imprimir y Firmar)", data=st.session_state.ns_pdf_bytes, file_name=f"Voucher_Ingreso.pdf", mime="application/pdf", type="primary")
                if st.button("Finalizar y Limpiar Formulario"):
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
                st.write(f"- **Aportes (Capital de Nivelación):** S/ {t_cap:.2f}\n- **Inscripción ({racc} acc):** S/ {t_ins:.2f}\n- **Interés de Nivelación:** S/ {t_int:.2f}")
                st.info(f"**TOTAL A PAGAR E INGRESAR A CAJA:** S/ {t_tot:.2f}")
                
                if st.button("💸 REGISTRAR SOCIO Y PAGAR", type="primary"):
                    if not rdni or not rnom: st.warning("DNI y Nombres son obligatorios.")
                    else:
                        if db_query("SELECT id FROM socios WHERE dni=?", (rdni,)): st.error("Error: Este DNI ya está registrado.")
                        else:
                            db_query("INSERT INTO socios (dni, nombres, apellidos, telefono, direccion, correo, sexo, fecha_nacimiento, acciones, fecha_ingreso) VALUES (?,?,?,?,?,?,?,?,?,?)", (rdni, rnom, rape, rtel, rdir, rcor, rsex, str(rnac), racc, datetime.now().strftime("%Y-%m-%d")), fetch=False)
                            db_query("UPDATE cuentas SET saldo = saldo + ? WHERE id_usuario=?", (t_tot, st.session_state.usuario_id), fetch=False)
                            fh = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                            if t_cap>0: db_query("INSERT INTO movimientos (id_usuario, tipo, monto, fecha) VALUES (?, ?, ?, ?)", (st.session_state.usuario_id, f"Aporte Inicial {rdni} ({racc} acc)", t_cap, fh), fetch=False)
                            if t_int>0: db_query("INSERT INTO movimientos (id_usuario, tipo, monto, fecha) VALUES (?, ?, ?, ?)", (st.session_state.usuario_id, f"Interés Inicial {rdni} ({racc} acc)", t_int, fh), fetch=False)
                            if t_ins>0: db_query("INSERT INTO movimientos (id_usuario, tipo, monto, fecha) VALUES (?, ?, ?, ?)", (st.session_state.usuario_id, f"Derecho Inscripción {rdni} ({racc} acc)", t_ins, fh), fetch=False)
                            
                            txt_ns = f"======================================\n      BANQUITO LA COLMENA\n     INGRESO DE NUEVO SOCIO\n======================================\nFecha: {fh}\nSocio: {rnom} {rape}\nDNI:   {rdni}\n--------------------------------------\n"
                            txt_ns += f"Acciones Iniciales : {racc}\nAportes Nivelacion : S/ {t_cap:.2f}\nInteres Nivelacion : S/ {t_int:.2f}\nInscripcion        : S/ {t_ins:.2f}\n--------------------------------------\nTOTAL INGRESADO    : S/ {t_tot:.2f}\n======================================\n\n\n     ____________________________\n          FIRMA DEL SOCIO\n"
                            pdf_bytes = generar_pdf_voucher(txt_ns, rdni)
                            st.session_state.ns_pdf_bytes = pdf_bytes
                            
                            msg_correo = ""
                            if rcor:
                                try:
                                    REMITENTE = "lacolmenabanco@gmail.com"; PASSWORD = "fvux bnfk qbzv brad"
                                    msg = MIMEMultipart(); msg['Subject'] = "Bienvenido al Banquito - Voucher de Ingreso"; msg['From'] = f"Banquito La Colmena <{REMITENTE}>"; msg['To'] = rcor
                                    msg.attach(MIMEText(f"Estimado/a {rnom} {rape},\n\n¡Bienvenido/a al Banquito La Colmena!\nAdjuntamos su comprobante de ingreso.\n\nAtentamente,\nLa Junta Directiva.", 'plain', 'utf-8'))
                                    adj = MIMEApplication(pdf_bytes, _subtype="pdf"); adj.add_header('Content-Disposition', 'attachment', filename=f"Voucher_Ingreso_{rdni}.pdf"); msg.attach(adj)
                                    server = smtplib.SMTP('smtp.gmail.com', 587); server.starttls(); server.login(REMITENTE, PASSWORD); server.send_message(msg); server.quit()
                                    msg_correo = "✅ Correo de bienvenida enviado con éxito al socio."
                                except Exception as e: msg_correo = f"⚠️ Fallo el envío de correo: {e}"
                            else: msg_correo = "ℹ️ Socio guardado sin correo registrado."
                                
                            st.session_state.ns_msg_correo = msg_correo
                            st.session_state.ns_done = True
                            st.rerun()

    elif menu_t == "💳 Pagos y Préstamos":
        t1, t2 = st.tabs(["💰 Realizar Pago Unificado", "💸 Otorgar Préstamo"])
        with t1:
            pdni = st.text_input("DNI Socio a pagar:", on_change=limpiar_formularios_pago)
            if pdni:
                if st.session_state.get('pu_done', False):
                    st.success("🎉 ¡Pago registrado en la Caja exitosamente!")
                    st.info(st.session_state.pu_msg_correo)
                    st.download_button("🖨️ Descargar Voucher (Imprimir y Firmar)", data=st.session_state.pu_pdf_bytes, file_name=f"Voucher_Pago_{pdni}.pdf", mime="application/pdf", type="primary")
                    if st.button("Finalizar y Limpiar Ventana"): limpiar_formularios_pago(); st.rerun()
                else:
                    soc = db_query("SELECT nombres, apellidos, acciones, correo FROM socios WHERE dni=?", (pdni,))
                    if soc:
                        n, a, acc, correo = soc[0]
                        st.write(f"**Socio:** {n} {a} | **Acciones Totales:** {acc}")
                        st.divider()
                        st.markdown("### 📥 Aportes Mensuales")
                        ap_fijo = get_config("aporte_mensual", 0.0)
                        pagar_ap = st.checkbox(f"Pagar Aportes este mes", value=True)
                        if pagar_ap:
                            for i in range(1, acc + 1): st.write(f"- Aporte Acción {i}: S/ {ap_fijo:.2f}")
                        
                        st.divider()
                        st.markdown("### 💳 Pago de Préstamos")
                        deudas = db_query("SELECT id, accion_asociada, saldo_actual FROM prestamos WHERE dni_socio=? AND estado='ACTIVO'", (pdni,))
                        m_min = get_config("monto_minimo_capital", 0.0)
                        tasa = get_config("interes_prestamo", 0.0) / 100.0
                        pagos_deudas = {}
                        if deudas:
                            for d in deudas:
                                d_id, d_acc, d_saldo = d[0], d[1], d[2]
                                st.markdown(f"**Préstamo en Acción {d_acc}** (Saldo Restante: S/ {d_saldo:.2f})")
                                c1, c2 = st.columns(2)
                                with c1:
                                    cap_input = st.number_input(f"Abono a Capital (Acc {d_acc})", min_value=0.0, max_value=float(d_saldo), value=float(min(m_min, d_saldo)), step=10.0, key=f"cap_{d_id}")
                                with c2:
                                    int_calc = float(math.ceil(d_saldo * tasa))
                                    st.info(f"Interés a pagar: S/ {int_calc:.2f}")
                                pagos_deudas[d_id] = {'acc': d_acc, 'saldo': d_saldo, 'cap': cap_input, 'int': int_calc if cap_input > 0 or int_calc > 0 else 0.0}
                                st.write("---")
                        else: st.success("✅ El socio no tiene deudas activas.")
                            
                        if st.button("1. Calcular Detalle y Generar Voucher"):
                            detalles_aportes = []
                            total_aportes = 0.0
                            if pagar_ap:
                                for i in range(1, acc + 1): detalles_aportes.append((i, ap_fijo)); total_aportes += ap_fijo
                            detalles_prestamos = []
                            total_cap = total_int = 0.0
                            needs_auth = False
                            for d_id, data in pagos_deudas.items():
                                if data['cap'] > 0 or data['int'] > 0:
                                    if data['cap'] < m_min and abs(data['cap'] - data['saldo']) > 0.01: needs_auth = True
                                    detalles_prestamos.append({'id': d_id, 'acc': data['acc'], 'cap': data['cap'], 'int': data['int'], 'saldo': data['saldo']})
                                    total_cap += data['cap']; total_int += data['int']
                            g_tot = total_aportes + total_cap + total_int
                            if g_tot == 0: st.warning("El monto total a pagar es S/ 0.00. Ingrese algún pago.")
                            else:
                                st.session_state.pu_tot, st.session_state.pu_det_ap, st.session_state.pu_tot_ap = g_tot, detalles_aportes, total_aportes
                                st.session_state.pu_det_pr, st.session_state.pu_tot_cap, st.session_state.pu_tot_int = detalles_prestamos, total_cap, total_int
                                st.session_state.pu_needs_auth, st.session_state.pu_show_voucher, st.session_state.pu_done = needs_auth, True, False
                                
                        if st.session_state.get('pu_show_voucher', False) and not st.session_state.get('pu_done', False):
                            st.markdown("### 🧾 Vista Previa del Voucher")
                            fh_pre = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                            txt_v = f"======================================\n      BANQUITO LA COLMENA\n     COMPROBANTE DE PAGO\n======================================\nFecha: {fh_pre}\nSocio: {n} {a}\nDNI:   {pdni}\n--------------------------------------\n"
                            if st.session_state.pu_tot_ap > 0:
                                txt_v += "APORTES MENSUALES:\n"
                                for ap in st.session_state.pu_det_ap: txt_v += f" - Accion {ap[0]:<2} :           S/ {ap[1]:.2f}\n"
                                txt_v += f"   Subtotal Aportes :   S/ {st.session_state.pu_tot_ap:.2f}\n--------------------------------------\n"
                            if st.session_state.pu_tot_cap > 0 or st.session_state.pu_tot_int > 0:
                                txt_v += "PAGO DE PRESTAMOS:\n"
                                for pr in st.session_state.pu_det_pr:
                                    txt_v += f" - Accion {pr['acc']}:\n      Capital :         S/ {pr['cap']:.2f}\n      Interes :         S/ {pr['int']:.2f}\n      Saldo Cap. Act. : S/ {max(0.0, pr['saldo'] - pr['cap']):.2f}\n"
                                txt_v += f"   Subtotal Prestamos : S/ {st.session_state.pu_tot_cap + st.session_state.pu_tot_int:.2f}\n--------------------------------------\n"
                            txt_v += f"TOTAL A PAGAR         : S/ {st.session_state.pu_tot:.2f}\n======================================\n\n\n     ____________________________\n          FIRMA DEL SOCIO\n"
                            st.text(txt_v)
                            can_proceed = True
                            if st.session_state.get('pu_needs_auth', False):
                                st.warning(f"⚠️ El abono a capital es menor al mínimo de S/ {m_min:.2f}. Se requiere autorización del Presidente.")
                                clave_presi = st.text_input("Clave del Presidente para autorizar:", type="password", key="auth_presi_pago")
                                if clave_presi:
                                    if clave_presi == get_config("password_presidente", "123456", str): st.success("✅ Pago autorizado por la Presidencia."); can_proceed = True
                                    else: st.error("❌ Clave incorrecta."); can_proceed = False
                                else: can_proceed = False
                                    
                            if can_proceed:
                                if st.button("✅ 2. Confirmar y Registrar Pago a Caja", type="primary"):
                                    fh = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                                    if st.session_state.pu_tot_ap > 0:
                                        db_query("UPDATE cuentas SET saldo = saldo + ? WHERE id_usuario=?", (st.session_state.pu_tot_ap, st.session_state.usuario_id), fetch=False)
                                        for ap in st.session_state.pu_det_ap: db_query("INSERT INTO movimientos (id_usuario, tipo, monto, fecha) VALUES (?, ?, ?, ?)", (st.session_state.usuario_id, f"Aporte Mensual {pdni} (Acción {ap[0]})", ap[1], fh), fetch=False)
                                    for pr in st.session_state.pu_det_pr:
                                        ns = pr['saldo'] - pr['cap']; est = "PAGADO" if ns < 0.1 else "ACTIVO"
                                        db_query("UPDATE prestamos SET saldo_actual=?, estado=? WHERE id=?", (0 if est=="PAGADO" else ns, est, pr['id']), fetch=False)
                                        db_query("UPDATE cuentas SET saldo = saldo + ? WHERE id_usuario=?", (pr['cap'] + pr['int'], st.session_state.usuario_id), fetch=False)
                                        if pr['cap'] > 0: db_query("INSERT INTO movimientos (id_usuario, tipo, monto, fecha) VALUES (?, ?, ?, ?)", (st.session_state.usuario_id, f"Pago Cuota {pdni} (Acción {pr['acc']})", pr['cap'], fh), fetch=False)
                                        if pr['int'] > 0: db_query("INSERT INTO movimientos (id_usuario, tipo, monto, fecha) VALUES (?, ?, ?, ?)", (st.session_state.usuario_id, f"Interés Cuota {pdni} (Acción {pr['acc']})", pr['int'], fh), fetch=False)
                                    pdf_bytes = generar_pdf_voucher(txt_v, pdni)
                                    st.session_state.pu_pdf_bytes = pdf_bytes
                                    msg_correo = ""
                                    if correo:
                                        try:
                                            REMITENTE = "lacolmenabanco@gmail.com"; PASSWORD = "fvux bnfk qbzv brad"
                                            msg = MIMEMultipart(); msg['Subject'] = "Voucher de Pago - Banquito La Colmena"; msg['From'] = f"Banquito La Colmena <{REMITENTE}>"; msg['To'] = correo
                                            msg.attach(MIMEText(f"Estimado/a {n} {a},\n\nAdjuntamos su comprobante de pago de la fecha.\n\nAtentamente,\nBanquito La Colmena.", 'plain', 'utf-8'))
                                            adj = MIMEApplication(pdf_bytes, _subtype="pdf"); adj.add_header('Content-Disposition', 'attachment', filename=f"Voucher_Pago_{pdni}.pdf"); msg.attach(adj)
                                            server = smtplib.SMTP('smtp.gmail.com', 587); server.starttls(); server.login(REMITENTE, PASSWORD); server.send_message(msg); server.quit()
                                            msg_correo = "✅ Correo enviado con éxito al socio."
                                        except Exception as e: msg_correo = f"⚠️ Fallo el envío de correo: {e}"
                                    else: msg_correo = "ℹ️ Socio sin correo registrado."
                                    st.session_state.pu_msg_correo, st.session_state.pu_done = msg_correo, True
                                    st.rerun()
                    else: st.error("Socio no encontrado.")

        with t2:
            st.subheader("💸 Desembolsar Nuevo Préstamo")
            s_tot_temp = float(db_query("SELECT SUM(monto) FROM movimientos")[0][0] or 0.0)
            i_cc_t = db_query("SELECT SUM(monto) FROM movimientos WHERE tipo LIKE 'Ingreso Caja Chica%' OR tipo = 'Depósito Caja'")[0][0] or 0.0
            e_cc_t = abs(db_query("SELECT SUM(monto) FROM movimientos WHERE tipo LIKE 'Egreso Caja Chica%' OR tipo = 'Retiro Caja'")[0][0] or 0.0)
            caja_prin_disp = s_tot_temp - (i_cc_t - e_cc_t)
            
            st.info(f"💰 **Fondo Disponible para Préstamos:** S/ {caja_prin_disp:.2f}")
            pdni2 = st.text_input("DNI Socio para Préstamo:", on_change=limpiar_formularios_pago)
            acc_p, soc = None, None
            max_disp = float(max(0, caja_prin_disp))
            m_p = st.number_input("Monto a Prestar (S/)", min_value=0.0, max_value=max_disp, step=100.0)
            
            if pdni2:
                soc = db_query("SELECT nombres, apellidos, acciones FROM socios WHERE dni=?", (pdni2,))
                if soc:
                    st.write(f"Socio válido: **{soc[0][0]} {soc[0][1]}** | Acciones: {soc[0][2]}")
                    acc_p = st.selectbox("Vincular a:", [f"Acción {i}" for i in range(1, soc[0][2] + 1)])
                else: st.error("Socio no encontrado.")
            
            if st.button("💸 DESEMBOLSAR", type="primary", use_container_width=True):
                if not pdni2: st.warning("Debe ingresar el DNI del socio.")
                elif not soc: st.warning("El DNI ingresado no pertenece a un socio válido.")
                elif m_p <= 0: st.warning("El monto a prestar debe ser mayor a S/ 0.00.")
                elif m_p > caja_prin_disp: st.error(f"Fondos insuficientes. Solo hay S/ {caja_prin_disp:.2f} disponibles.")
                else:
                    acc_n = int(acc_p.split(" ")[1])
                    p_act = db_query("SELECT id, monto_original, saldo_actual FROM prestamos WHERE dni_socio=? AND accion_asociada=? AND estado='ACTIVO'", (pdni2, acc_n))
                    m_proy = m_p
                    if p_act:
                        db_query("UPDATE prestamos SET monto_original=?, saldo_actual=? WHERE id=?", (p_act[0][1]+m_p, p_act[0][2]+m_p, p_act[0][0]), fetch=False)
                        m_proy = p_act[0][2]+m_p
                    else: db_query("INSERT INTO prestamos (dni_socio, monto_original, saldo_actual, fecha_inicio, estado, accion_asociada) VALUES (?, ?, ?, ?, 'ACTIVO', ?)", (pdni2, m_p, m_p, datetime.now().strftime("%Y-%m-%d"), acc_n), fetch=False)
                    
                    fh_exacta = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    db_query("UPDATE cuentas SET saldo = saldo - ? WHERE id_usuario=?", (m_p, st.session_state.usuario_id), fetch=False)
                    db_query("INSERT INTO movimientos (id_usuario, tipo, monto, fecha) VALUES (?, ?, ?, ?)", (st.session_state.usuario_id, f"Préstamo a {pdni2} ({acc_p})", -m_p, fh_exacta), fetch=False)
                    
                    sp, cuotas, tot_i, fh_d = m_proy, [], 0, datetime.now()
                    m, a = fh_d.month, fh_d.year
                    tasa = get_config("interes_prestamo", 0.0) / 100.0
                    m_min = get_config("monto_minimo_capital", 50.0)
                    
                    while sp > 0.01:
                        m = m + 1 if m < 12 else 1
                        if m == 1: a += 1
                        i = math.ceil(sp * tasa); am = min(m_min if m_min>0 else 50.0, sp)
                        cuotas.append((f"06/{m:02d}/{a}", am, i, am+i, "P")); tot_i += i; sp -= am
                        
                    pdf_bytes = generar_pdf_desembolso_completo(f"{soc[0][0]} {soc[0][1]}", pdni2, acc_n, m_p, m_proy, tot_i, cuotas, fh_exacta, tasa)
                    st.session_state.pres_done, st.session_state.pres_pdf, st.session_state.pres_dni = True, pdf_bytes, pdni2
                    st.rerun()
            
            if st.session_state.get('pres_done', False):
                st.success("🎉 ¡Préstamo desembolsado exitosamente de la Caja Principal!")
                st.download_button("🖨️ Descargar Paquete de Desembolso (Voucher + Cronograma + Contrato)", data=st.session_state.pres_pdf, file_name=f"Desembolso_{st.session_state.get('pres_dni','')}.pdf", mime="application/pdf", type="primary", use_container_width=True)
                if st.button("Finalizar y Limpiar Ventana"): limpiar_formularios_pago(); st.rerun()

    # --- MÓDULO CAJA GLOBAL ---
    elif menu_t == "💰 Caja Global":
        s_tot = float(db_query("SELECT SUM(monto) FROM movimientos")[0][0] or 0.0)
        i_cc = db_query("SELECT SUM(monto) FROM movimientos WHERE tipo LIKE 'Ingreso Caja Chica%' OR tipo = 'Depósito Caja'")[0][0] or 0.0
        e_cc = abs(db_query("SELECT SUM(monto) FROM movimientos WHERE tipo LIKE 'Egreso Caja Chica%' OR tipo = 'Retiro Caja'")[0][0] or 0.0)
        f_cc = i_cc - e_cc
        c_prin = s_tot - f_cc
        
        c1, c2, c3 = st.columns(3)
        c1.metric("Caja Principal (Préstamos)", f"S/ {c_prin:.2f}")
        c2.metric("Caja Chica (Multas/Varios)", f"S/ {f_cc:.2f}")
        c3.metric("Efectivo Total Físico", f"S/ {s_tot:.2f}")
        
        tot_int = float(db_query("SELECT SUM(monto) FROM movimientos WHERE tipo LIKE '%nter%' AND tipo NOT LIKE '%Caja Chica%'")[0][0] or 0.0)
        st.info(f"📈 **Proyección de Intereses Generados hasta la fecha:** S/ {tot_int:.2f} *(Sirve para calcular las utilidades de fin de año)*")
        
        st.write("### Últimos 20 Movimientos")
        movs_caja = db_query("SELECT fecha, tipo, monto FROM movimientos ORDER BY id DESC LIMIT 20")
        movs_caja_fmt = [(m[0][:10], m[1], m[2]) for m in movs_caja]
        df_caja = pd.DataFrame(movs_caja_fmt, columns=["Fecha", "Detalle", "Monto"])
        st.table(df_caja)

    # --- MÓDULO CAJA CHICA ---
    elif menu_t == "📥 Caja Chica":
        i_cc = db_query("SELECT SUM(monto) FROM movimientos WHERE tipo LIKE 'Ingreso Caja Chica%' OR tipo = 'Depósito Caja'")[0][0] or 0.0
        e_cc = abs(db_query("SELECT SUM(monto) FROM movimientos WHERE tipo LIKE 'Egreso Caja Chica%' OR tipo = 'Retiro Caja'")[0][0] or 0.0)
        st.subheader(f"Fondo Actual Caja Chica: S/ {i_cc - e_cc:.2f}")
        
        t1, t2 = st.tabs(["+ Ingreso", "- Egreso"])
        with t1:
            i_con = st.selectbox("Concepto:", ["Multa", "Tardanza", "Otro"])
            i_det = st.text_input("Detalle (Opcional):")
            i_mon = st.number_input("Monto Ingreso (S/):", min_value=0.0)
            if st.button("Registrar Ingreso", type="primary"):
                fh = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                db_query("UPDATE cuentas SET saldo = saldo + ? WHERE id_usuario=?", (i_mon, st.session_state.usuario_id), fetch=False)
                db_query("INSERT INTO movimientos (id_usuario, tipo, monto, fecha) VALUES (?, ?, ?, ?)", (st.session_state.usuario_id, f"Ingreso Caja Chica - {i_con} | {i_det}", i_mon, fh), fetch=False)
                st.success("Ingreso registrado en Caja Chica.")
                
        with t2:
            e_con = st.selectbox("Concepto Egreso:", ["Insumos", "Administrativo", "Otro"])
            e_det = st.text_input("Detalle Egreso:")
            e_mon = st.number_input("Monto Egreso (S/):", min_value=0.0)
            if st.button("Registrar Egreso"):
                fh = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                db_query("UPDATE cuentas SET saldo = saldo - ? WHERE id_usuario=?", (e_mon, st.session_state.usuario_id), fetch=False)
                db_query("INSERT INTO movimientos (id_usuario, tipo, monto, fecha) VALUES (?, ?, ?, ?)", (st.session_state.usuario_id, f"Egreso Caja Chica - {e_con} | {e_det}", -e_mon, fh), fetch=False)
                st.success("Egreso registrado en Caja Chica.")

    # --- MÓDULO REGLAS ---
    elif menu_t == "⚙️ Reglas Financieras":
        st.warning("⚠️ Cuidado: Requiere clave de autorización del Presidente")
        auth = st.text_input("Clave del Presidente", type="password")
        if auth == get_config("password_presidente", "123456", str):
            st.success("Autorización Exitosa. Puedes modificar las reglas.")
            ap_m = st.number_input("Aporte Mensual por Acción", value=get_config("aporte_mensual", 0.0))
            am_min = st.number_input("Amortización Mínima a Capital", value=get_config("monto_minimo_capital", 0.0))
            ins = st.number_input("Inscripción Base por Acción (S/)", value=get_config("cuota_inscripcion", 0.0))
            int_p = st.number_input("Interés Mensual del Préstamo (%)", value=get_config("interes_prestamo", 0.0))
            if st.button("Guardar Nuevas Reglas", type="primary"):
                db_query("UPDATE configuracion SET valor=? WHERE clave='aporte_mensual'", (ap_m,), fetch=False)
                db_query("UPDATE configuracion SET valor=? WHERE clave='monto_minimo_capital'", (am_min,), fetch=False)
                db_query("UPDATE configuracion SET valor=? WHERE clave='cuota_inscripcion'", (ins,), fetch=False)
                db_query("UPDATE configuracion SET valor=? WHERE clave='interes_prestamo'", (int_p,), fetch=False)
                st.success("Reglas financieras actualizadas con éxito.")
        elif auth: st.error("Clave de presidente incorrecta.")

st.sidebar.markdown("---")
st.sidebar.caption("Banquito La Colmena v14.30 Cloud Edition")