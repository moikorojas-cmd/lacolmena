import streamlit as st
import sqlite3
import math
from datetime import datetime
import pandas as pd
import os
import smtplib
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
        c.execute('''CREATE TABLE IF NOT EXISTS socios (id INTEGER PRIMARY KEY AUTOINCREMENT, dni TEXT UNIQUE NOT NULL, nombres TEXT NOT NULL, apellidos TEXT, telefono TEXT, direccion TEXT, correo TEXT, sexo TEXT, fecha_ingreso TEXT, es_fundador INTEGER DEFAULT 0, acciones INTEGER DEFAULT 0)''')
        c.execute('''CREATE TABLE IF NOT EXISTS prestamos (id INTEGER PRIMARY KEY AUTOINCREMENT, dni_socio TEXT, monto_original REAL, saldo_actual REAL, fecha_inicio TEXT, estado TEXT DEFAULT 'ACTIVO', accion_asociada INTEGER DEFAULT 1)''')
        
        try:
            hoy_str = datetime.now().strftime("%Y-%m-%d")
            c.execute("INSERT OR IGNORE INTO configuracion (clave, valor) VALUES (?, ?)", ("fecha_fundacion", hoy_str))
            c.execute("INSERT OR IGNORE INTO configuracion (clave, valor) VALUES (?, ?)", ("monto_minimo_capital", "0.0"))
            c.execute("INSERT OR IGNORE INTO configuracion (clave, valor) VALUES (?, ?)", ("cuota_inscripcion", "0.0"))
            c.execute("INSERT OR IGNORE INTO configuracion (clave, valor) VALUES (?, ?)", ("interes_prestamo", "0.0"))
            c.execute("INSERT OR IGNORE INTO configuracion (clave, valor) VALUES (?, ?)", ("aporte_mensual", "0.0"))
            c.execute("INSERT OR IGNORE INTO configuracion (clave, valor) VALUES (?, ?)", ("presidente", "No asignado"))
            c.execute("INSERT OR IGNORE INTO configuracion (clave, valor) VALUES (?, ?)", ("tesorero", "No asignado"))
            c.execute("INSERT OR IGNORE INTO configuracion (clave, valor) VALUES (?, ?)", ("secretario", "No asignado"))
            c.execute("INSERT OR IGNORE INTO configuracion (clave, valor) VALUES (?, ?)", ("password_presidente", "123456"))
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

# =============================================================================
# 2. LÓGICA MATEMÁTICA Y FINANCIERA
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

def generar_pdf_crono(nom_soc, d, n_a, m_proy, tot_i, cuotas, fh):
    pdf = FPDF(); pdf.add_page(); pdf.set_font("Courier", size=10)
    tc = f"==========================================\n  CRONOGRAMA DE PRESTAMO - BANQUITO LA COLMENA\n==========================================\nSocio: {nom_soc}\nDNI: {d} | Accion: {n_a}\nFecha: {fh}\nMonto: S/ {m_proy:.2f} | Int: S/ {tot_i:.2f} | Tot: S/ {m_proy+tot_i:.2f}\n------------------------------------------\n FECHA PAGO | AMORT. | INTERES | CUOTA | COND\n------------------------------------------\n"
    for c in cuotas: tc += f" {c[0]} | S/{c[1]:>5.2f}| S/{c[2]:>6.2f}| S/{c[3]:>6.2f}|   {c[4]}\n"
    for l in tc.split('\n'): pdf.cell(0, 5, txt=l.encode('latin-1','ignore').decode('latin-1'), ln=True)
    pdf.output("temp_crono.pdf")
    with open("temp_crono.pdf", "rb") as f: b = f.read()
    return b

def generar_pdf_voucher(t):
    pdf = FPDF(); pdf.add_page(); pdf.set_font("Courier", size=12)
    for l in t.replace("🐝", "").split('\n'): pdf.cell(0, 6, txt=l.encode('latin-1','ignore').decode('latin-1'), ln=True)
    pdf.output("temp_v.pdf")
    with open("temp_v.pdf", "rb") as f: b = f.read()
    return b

# =============================================================================
# 3. GESTIÓN DE SESIONES (LOGIN)
# =============================================================================
if 'usuario_id' not in st.session_state:
    st.session_state.usuario_id = None
    st.session_state.usuario_rol = None
    st.session_state.usuario_nombre = None
    st.session_state.vista = 'publico'

with st.sidebar:
    if st.session_state.usuario_id is None:
        st.header("🔐 Acceso Personal")
        usr = st.text_input("Usuario")
        pwd = st.text_input("Contraseña", type="password")
        if st.button("Ingresar", use_container_width=True):
            res = db_query("SELECT id, nombre, rol FROM usuarios WHERE usuario=? AND password=?", (usr, pwd))
            if res:
                st.session_state.usuario_id = res[0][0]
                st.session_state.usuario_nombre = res[0][1]
                st.session_state.usuario_rol = res[0][2]
                st.session_state.vista = res[0][2]
                st.rerun()
            else:
                st.error("Credenciales incorrectas")
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
            else: st.error("Socio no encontrado.")
            
    with t2:
        cant_acc = st.number_input("Acciones a adquirir:", 1, 4, 1)
        if st.button("Calcular Inversión"):
            c_hist, i_hist = calcular_nivelacion_por_accion()
            ins_base = get_config("cuota_inscripcion", 0.0)
            
            t_cap = c_hist * cant_acc
            t_int = math.ceil(i_hist * cant_acc)
            t_ins = ins_base * cant_acc
            
            st.success(f"### Total a invertir hoy: S/ {t_cap + t_int + t_ins:.2f}")
            st.write(f"- Inscripción: S/ {t_ins:.2f}")
            st.write(f"- Aporte Nivelado: S/ {t_cap:.2f}")
            st.write(f"- Interés Nivelado: S/ {t_int:.2f}")

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
            facc = c2.number_input("Acciones", 1, 4, 1)
            fap_ini = c2.number_input("Aporte Inicial por Acción (S/)", 0.0)
            if st.form_submit_submit_button("Guardar Fundador", type="primary"):
                if fdni and fnom:
                    try:
                        db_query("INSERT INTO socios (dni, nombres, apellidos, es_fundador, acciones, fecha_ingreso) VALUES (?,?,?,1,?,?)", (fdni, fnom, fape, facc, datetime.now().strftime("%Y-%m-%d")), fetch=False)
                        tot = facc * fap_ini
                        db_query("UPDATE cuentas SET saldo = saldo + ? WHERE id_usuario=1", (tot,), fetch=False)
                        if tot>0: db_query("INSERT INTO movimientos (id_usuario, tipo, monto) VALUES (1, ?, ?)", (f"Aporte Inicial {fdni} ({facc} acc)", tot), fetch=False)
                        st.success("Fundador registrado.")
                    except: st.error("Error o DNI duplicado.")
                else: st.warning("DNI y Nombres requeridos.")
                
    with t2:
        st.subheader("Configurar Sistema")
        ffun = st.text_input("Fecha Fundación (AAAA-MM-DD)", get_config("fecha_fundacion", datetime.now().strftime("%Y-%m-%d"), str))
        socios = ["No asignado"] + [f"{r[0]} {r[1]}" for r in db_query("SELECT nombres, apellidos FROM socios ORDER BY nombres ASC")]
        
        cpres = st.selectbox("Presidente(a)", socios, index=socios.index(get_config("presidente", "No asignado", str)) if get_config("presidente", "No asignado", str) in socios else 0)
        cpass = st.text_input("Clave Autorización Presidente", get_config("password_presidente", "123456", str), type="password")
        
        ctes = st.selectbox("Tesorero(a)", socios, index=socios.index(get_config("tesorero", "No asignado", str)) if get_config("tesorero", "No asignado", str) in socios else 0)
        u_t = db_query("SELECT usuario, password FROM usuarios WHERE rol='tesorero'")
        ut_usr = st.text_input("Usuario Tesorero", u_t[0][0] if u_t else "tesorero")
        ut_pwd = st.text_input("Clave Tesorero", u_t[0][1] if u_t else "teso123", type="password")
        
        csec = st.selectbox("Secretario(a)", socios, index=socios.index(get_config("secretario", "No asignado", str)) if get_config("secretario", "No asignado", str) in socios else 0)
        
        if st.button("Guardar Junta Directiva", type="primary"):
            db_query("UPDATE configuracion SET valor=? WHERE clave='fecha_fundacion'", (ffun,), fetch=False)
            db_query("UPDATE configuracion SET valor=? WHERE clave='presidente'", (cpres,), fetch=False)
            db_query("UPDATE configuracion SET valor=? WHERE clave='password_presidente'", (cpass,), fetch=False)
            db_query("UPDATE configuracion SET valor=? WHERE clave='tesorero'", (ctes,), fetch=False)
            db_query("UPDATE configuracion SET valor=? WHERE clave='secretario'", (csec,), fetch=False)
            
            if db_query("SELECT id FROM usuarios WHERE rol='tesorero'"):
                db_query("UPDATE usuarios SET nombre=?, usuario=?, password=? WHERE rol='tesorero'", (ctes, ut_usr, ut_pwd), fetch=False)
            else:
                db_query("INSERT INTO usuarios (nombre, usuario, password, rol) VALUES (?, ?, ?, 'tesorero')", (ctes, ut_usr, ut_pwd), fetch=False)
            st.success("Configuración guardada.")

# -----------------------------------------------------------------------------
# VISTA: TESORERO (OPERACIONES)
# -----------------------------------------------------------------------------
elif st.session_state.vista == 'tesorero':
    st.title("💼 Panel de Tesorería")
    menu_t = st.radio("Módulos:", ["👥 Socios y Compras", "💳 Pagos y Préstamos", "💰 Caja Global", "📥 Caja Chica", "⚙️ Reglas Financieras"], horizontal=True)
    
    # --- MÓDULO SOCIOS ---
    if menu_t == "👥 Socios y Compras":
        t1, t2 = st.tabs(["🔍 Búsqueda y Acciones Extra", "📝 Nuevo Socio Regular"])
        
        with t1:
            dni_busq = st.text_input("Buscar DNI Socio:")
            if dni_busq:
                soc = db_query("SELECT nombres, apellidos, acciones FROM socios WHERE dni=?", (dni_busq,))
                if soc:
                    n, a, acc_act = soc[0]
                    st.success(f"**{n} {a}** | Acciones actuales: {acc_act}")
                    
                    with st.expander("Comprar Acción Extra"):
                        ce_acc = st.number_input("Cantidad a comprar", 1, 4-acc_act, 1)
                        if st.button("Calcular Total Extra"):
                            c_hist, i_hist = calcular_nivelacion_por_accion()
                            ins_b = get_config("cuota_inscripcion", 0.0)
                            
                            st.session_state.ce_tot = (c_hist * ce_acc) + math.ceil(i_hist * ce_acc) + (ins_b * ce_acc)
                            st.session_state.ce_cap = c_hist * ce_acc
                            st.session_state.ce_int = math.ceil(i_hist * ce_acc)
                            st.session_state.ce_ins = ins_b * ce_acc
                            
                        if 'ce_tot' in st.session_state:
                            st.info(f"Total a pagar: S/ {st.session_state.ce_tot:.2f}")
                            if st.button("Pagar y Asignar Acción"):
                                db_query("UPDATE socios SET acciones = acciones + ? WHERE dni=?", (ce_acc, dni_busq), fetch=False)
                                db_query("UPDATE cuentas SET saldo = saldo + ? WHERE id_usuario=?", (st.session_state.ce_tot, st.session_state.usuario_id), fetch=False)
                                fh = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                                if st.session_state.ce_cap>0: db_query("INSERT INTO movimientos (id_usuario, tipo, monto, fecha) VALUES (?, ?, ?, ?)", (st.session_state.usuario_id, f"Aporte por Compra Extra {dni_busq} ({ce_acc} acc)", st.session_state.ce_cap, fh), fetch=False)
                                if st.session_state.ce_int>0: db_query("INSERT INTO movimientos (id_usuario, tipo, monto, fecha) VALUES (?, ?, ?, ?)", (st.session_state.usuario_id, f"Interés por Compra Extra {dni_busq} ({ce_acc} acc)", st.session_state.ce_int, fh), fetch=False)
                                if st.session_state.ce_ins>0: db_query("INSERT INTO movimientos (id_usuario, tipo, monto, fecha) VALUES (?, ?, ?, ?)", (st.session_state.usuario_id, f"Derecho Inscripción Extra {dni_busq} ({ce_acc} acc)", st.session_state.ce_ins, fh), fetch=False)
                                st.success("Acción asignada correctamente.")
                                del st.session_state['ce_tot']
                else: st.error("Socio no encontrado.")
                
        with t2:
            with st.form("form_reg_soc"):
                rdni = st.text_input("DNI*")
                rnom = st.text_input("Nombres*")
                rape = st.text_input("Apellidos")
                racc = st.number_input("Acciones a Iniciar", 1, 4, 1)
                
                submitted = st.form_submit_button("Calcular y Guardar", type="primary")
                if submitted and rdni and rnom:
                    c_hist, i_hist = calcular_nivelacion_por_accion()
                    ins_b = get_config("cuota_inscripcion", 0.0)
                    
                    t_cap = c_hist * racc
                    t_int = math.ceil(i_hist * racc)
                    t_ins = ins_b * racc
                    t_tot = t_cap + t_int + t_ins
                    
                    try:
                        db_query("INSERT INTO socios (dni, nombres, apellidos, acciones, fecha_ingreso) VALUES (?,?,?,?,?)", (rdni, rnom, rape, racc, datetime.now().strftime("%Y-%m-%d")), fetch=False)
                        db_query("UPDATE cuentas SET saldo = saldo + ? WHERE id_usuario=?", (t_tot, st.session_state.usuario_id), fetch=False)
                        fh = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                        if t_cap>0: db_query("INSERT INTO movimientos (id_usuario, tipo, monto, fecha) VALUES (?, ?, ?, ?)", (st.session_state.usuario_id, f"Aporte Inicial {rdni} ({racc} acc)", t_cap, fh), fetch=False)
                        if t_int>0: db_query("INSERT INTO movimientos (id_usuario, tipo, monto, fecha) VALUES (?, ?, ?, ?)", (st.session_state.usuario_id, f"Interés Inicial {rdni} ({racc} acc)", t_int, fh), fetch=False)
                        if t_ins>0: db_query("INSERT INTO movimientos (id_usuario, tipo, monto, fecha) VALUES (?, ?, ?, ?)", (st.session_state.usuario_id, f"Derecho Inscripción {rdni} ({racc} acc)", t_ins, fh), fetch=False)
                        st.success(f"Socio guardado. Cobrado: S/ {t_tot:.2f}")
                    except: st.error("Error. DNI duplicado.")

    # --- MÓDULO PAGOS Y PRÉSTAMOS ---
    elif menu_t == "💳 Pagos y Préstamos":
        t1, t2 = st.tabs(["💰 Realizar Pago Unificado", "💸 Otorgar Préstamo"])
        
        with t1:
            pdni = st.text_input("DNI Socio a pagar:")
            if pdni:
                soc = db_query("SELECT nombres, apellidos, acciones, correo FROM socios WHERE dni=?", (pdni,))
                if soc:
                    n, a, acc, correo = soc[0]
                    st.write(f"**{n} {a}** | Acciones: {acc}")
                    
                    # Aportes
                    ap_fijo = get_config("aporte_mensual", 0.0)
                    pagar_ap = st.checkbox(f"Incluir pago de Aportes Mensuales (S/ {acc * ap_fijo:.2f})", value=True)
                    m_ap = (acc * ap_fijo) if pagar_ap else 0.0
                    
                    # Deudas
                    deudas = db_query("SELECT id, accion_asociada, saldo_actual FROM prestamos WHERE dni_socio=? AND estado='ACTIVO'", (pdni,))
                    deuda_sel = None
                    m_cap = 0.0
                    m_int = 0.0
                    
                    if deudas:
                        opts = {f"Acción {d[1]} - Saldo S/ {d[2]:.2f}": d for d in deudas}
                        sel_str = st.selectbox("Seleccionar Deuda a Amortizar", list(opts.keys()))
                        deuda_sel = opts[sel_str]
                        
                        m_min = get_config("monto_minimo_capital", 0.0)
                        m_cap = st.number_input("Abono a Capital (S/)", min_value=0.0, max_value=float(deuda_sel[2]), value=float(min(m_min, deuda_sel[2])), step=10.0)
                        tasa = get_config("interes_prestamo", 0.0) / 100.0
                        m_int = float(math.ceil(deuda_sel[2] * tasa))
                        st.caption(f"Interés calculado sobre el saldo actual: S/ {m_int:.2f}")
                    else: st.success("Sin deudas activas.")
                    
                    g_tot = m_ap + m_cap + m_int
                    st.header(f"Total a Pagar: S/ {g_tot:.2f}")
                    
                    if g_tot > 0 and st.button("✅ Procesar Pago", type="primary"):
                        try:
                            fh = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                            if m_ap > 0:
                                db_query("UPDATE cuentas SET saldo = saldo + ? WHERE id_usuario=?", (m_ap, st.session_state.usuario_id), fetch=False)
                                for i in range(1, acc + 1): db_query("INSERT INTO movimientos (id_usuario, tipo, monto, fecha) VALUES (?, ?, ?, ?)", (st.session_state.usuario_id, f"Aporte Mensual {pdni} (Acción {i})", ap_fijo, fh), fetch=False)
                            if m_cap > 0 or m_int > 0:
                                ns = deuda_sel[2] - m_cap
                                est = "PAGADO" if ns < 0.1 else "ACTIVO"
                                db_query("UPDATE prestamos SET saldo_actual=?, estado=? WHERE id=?", (0 if est=="PAGADO" else ns, est, deuda_sel[0]), fetch=False)
                                db_query("UPDATE cuentas SET saldo = saldo + ? WHERE id_usuario=?", (m_cap + m_int, st.session_state.usuario_id), fetch=False)
                                if m_cap > 0: db_query("INSERT INTO movimientos (id_usuario, tipo, monto, fecha) VALUES (?, ?, ?, ?)", (st.session_state.usuario_id, f"Pago Cuota {pdni} (Acción {deuda_sel[1]})", m_cap, fh), fetch=False)
                                if m_int > 0: db_query("INSERT INTO movimientos (id_usuario, tipo, monto, fecha) VALUES (?, ?, ?, ?)", (st.session_state.usuario_id, f"Interés Cuota {pdni} (Acción {deuda_sel[1]})", m_int, fh), fetch=False)
                            
                            st.success("Pago procesado en BD.")
                            
                            # PDF Voucher
                            txt_v = f"BANQUITO LA COLMENA\nVOUCHER DE PAGO\nFecha: {fh}\nSocio: {n} {a}\nDNI: {pdni}\n------------------\n"
                            if m_ap>0: txt_v += f"Aportes: S/ {m_ap:.2f}\n"
                            if m_cap>0: txt_v += f"Capital Acc {deuda_sel[1]}: S/ {m_cap:.2f}\n"
                            if m_int>0: txt_v += f"Interés Acc {deuda_sel[1]}: S/ {m_int:.2f}\n"
                            txt_v += f"TOTAL: S/ {g_tot:.2f}"
                            
                            v_bytes = generar_pdf_voucher(txt_v)
                            st.download_button("📄 Descargar Voucher de Pago", data=v_bytes, file_name=f"Voucher_{pdni}.pdf", mime="application/pdf")
                            
                        except Exception as e: st.error(f"Error: {e}")

        with t2:
            pdni2 = st.text_input("DNI Socio para Préstamo:")
            if pdni2:
                soc = db_query("SELECT nombres, apellidos, acciones FROM socios WHERE dni=?", (pdni2,))
                if soc:
                    st.write(f"Socio válido. Acciones: {soc[0][2]}")
                    acc_p = st.selectbox("Vincular a:", [f"Acción {i}" for i in range(1, soc[0][2] + 1)])
                    m_p = st.number_input("Monto a Prestar (S/)", min_value=0.0, step=100.0)
                    
                    if m_p > 0 and st.button("💸 Desembolsar", type="primary"):
                        caja_glb = db_query("SELECT SUM(saldo) FROM cuentas")[0][0] or 0.0
                        if m_p > caja_glb:
                            st.error("Fondos insuficientes en caja.")
                        else:
                            acc_n = int(acc_p.split(" ")[1])
                            p_act = db_query("SELECT id, monto_original, saldo_actual FROM prestamos WHERE dni_socio=? AND accion_asociada=? AND estado='ACTIVO'", (pdni2, acc_n))
                            
                            m_proy = m_p
                            if p_act:
                                db_query("UPDATE prestamos SET monto_original=?, saldo_actual=? WHERE id=?", (p_act[0][1]+m_p, p_act[0][2]+m_p, p_act[0][0]), fetch=False)
                                m_proy = p_act[0][2]+m_p
                            else:
                                db_query("INSERT INTO prestamos (dni_socio, monto_original, saldo_actual, fecha_inicio, estado, accion_asociada) VALUES (?, ?, ?, ?, 'ACTIVO', ?)", (pdni2, m_p, m_p, datetime.now().strftime("%Y-%m-%d"), acc_n), fetch=False)
                            
                            fh = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                            db_query("UPDATE cuentas SET saldo = saldo - ? WHERE id_usuario=?", (m_p, st.session_state.usuario_id), fetch=False)
                            db_query("INSERT INTO movimientos (id_usuario, tipo, monto, fecha) VALUES (?, ?, ?, ?)", (st.session_state.usuario_id, f"Préstamo a {pdni2} ({acc_p})", -m_p, fh), fetch=False)
                            
                            st.success("Préstamo desembolsado exitosamente.")
                            
                            # Generar proyeccion rapida para el PDF
                            sp, cuotas, tot_i, fh_d = m_proy, [], 0, datetime.now()
                            m, a = fh_d.month, fh_d.year
                            tasa = get_config("interes_prestamo", 0.0) / 100.0
                            m_min = get_config("monto_minimo_capital", 50.0)
                            while sp > 0.01:
                                m = m + 1 if m < 12 else 1
                                if m == 1: a += 1
                                i = math.ceil(sp * tasa)
                                am = min(m_min if m_min>0 else 50.0, sp)
                                cuotas.append((f"06/{m:02d}/{a}", am, i, am+i, "P"))
                                tot_i += i; sp -= am
                                
                            pdf_b = generar_pdf_crono(f"{soc[0][0]} {soc[0][1]}", pdni2, acc_n, m_proy, tot_i, cuotas, fh_d.strftime("%Y-%m-%d"))
                            st.download_button("📄 Descargar Cronograma", data=pdf_b, file_name=f"Crono_{pdni2}.pdf", mime="application/pdf")

    # --- MÓDULO CAJA GLOBAL ---
    elif menu_t == "💰 Caja Global":
        s_tot = float(db_query("SELECT SUM(saldo) FROM cuentas")[0][0] or 0.0)
        i_cc = db_query("SELECT SUM(monto) FROM movimientos WHERE tipo LIKE 'Ingreso Caja Chica%' OR tipo = 'Depósito Caja'")[0][0] or 0.0
        e_cc = abs(db_query("SELECT SUM(monto) FROM movimientos WHERE tipo LIKE 'Egreso Caja Chica%' OR tipo = 'Retiro Caja'")[0][0] or 0.0)
        f_cc = i_cc - e_cc
        c_prin = s_tot - f_cc
        
        c1, c2, c3 = st.columns(3)
        c1.metric("Caja Principal (Préstamos)", f"S/ {c_prin:.2f}")
        c2.metric("Caja Chica (Multas/Varios)", f"S/ {f_cc:.2f}")
        c3.metric("Efectivo Total Físico", f"S/ {s_tot:.2f}")

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
                st.success("Registrado.")
                
        with t2:
            e_con = st.selectbox("Concepto Egreso:", ["Insumos", "Administrativo", "Otro"])
            e_det = st.text_input("Detalle Egreso:")
            e_mon = st.number_input("Monto Egreso (S/):", min_value=0.0)
            if st.button("Registrar Egreso"):
                fh = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                db_query("UPDATE cuentas SET saldo = saldo - ? WHERE id_usuario=?", (e_mon, st.session_state.usuario_id), fetch=False)
                db_query("INSERT INTO movimientos (id_usuario, tipo, monto, fecha) VALUES (?, ?, ?, ?)", (st.session_state.usuario_id, f"Egreso Caja Chica - {e_con} | {e_det}", -e_mon, fh), fetch=False)
                st.success("Egreso Registrado.")

    # --- MÓDULO REGLAS ---
    elif menu_t == "⚙️ Reglas Financieras":
        st.warning("⚠️ Requiere autorización del Presidente")
        auth = st.text_input("Clave del Presidente", type="password")
        if auth == get_config("password_presidente", "123456", str):
            st.success("Autorización Exitosa. Puede modificar las reglas.")
            ap_m = st.number_input("Aporte Mensual", value=get_config("aporte_mensual", 0.0))
            am_min = st.number_input("Amortización Mínima", value=get_config("monto_minimo_capital", 0.0))
            ins = st.number_input("Inscripción Base (S/)", value=get_config("cuota_inscripcion", 0.0))
            int_p = st.number_input("Interés Préstamo (%)", value=get_config("interes_prestamo", 0.0))
            if st.button("Guardar Nuevas Reglas", type="primary"):
                db_query("UPDATE configuracion SET valor=? WHERE clave='aporte_mensual'", (ap_m,), fetch=False)
                db_query("UPDATE configuracion SET valor=? WHERE clave='monto_minimo_capital'", (am_min,), fetch=False)
                db_query("UPDATE configuracion SET valor=? WHERE clave='cuota_inscripcion'", (ins,), fetch=False)
                db_query("UPDATE configuracion SET valor=? WHERE clave='interes_prestamo'", (int_p,), fetch=False)
                st.success("Reglas actualizadas.")
        elif auth: st.error("Clave incorrecta.")