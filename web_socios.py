import streamlit as st
import sqlite3
import math
from datetime import datetime
import os

# Intentamos importar FPDF para crear el PDF
try:
    from fpdf import FPDF
except ImportError:
    st.error("Falta instalar la librería FPDF. Ejecuta: pip install fpdf en tu terminal.")

# =============================================================================
# FUNCIÓN PARA GENERAR EL PDF COMPLETO (HISTORIAL + PROYECCIÓN)
# =============================================================================
def generar_pdf_estado_cuenta(nombre_completo, dni, acc_num):
    with sqlite3.connect("banquito.db") as conn:
        cur = conn.cursor()
        
        # 1. Obtener datos del préstamo actual
        cur.execute("SELECT saldo_actual FROM prestamos WHERE dni_socio=? AND accion_asociada=? AND estado='ACTIVO'", (dni, acc_num))
        res_p = cur.fetchone()
        saldo_hoy = res_p[0] if res_p else 0.0

        # 2. Obtener Movimientos Históricos (Pasado)
        filtro = f"%{dni}%(Acción {acc_num})%"
        cur.execute("""
            SELECT fecha, tipo, monto 
            FROM movimientos 
            WHERE tipo LIKE ? AND (tipo LIKE '%Préstamo%' OR tipo LIKE '%Pago Cuota%' OR tipo LIKE '%Interés Cuota%')
            ORDER BY fecha ASC
        """, (filtro,))
        movs = cur.fetchall()

    # --- PROCESAR PASADO ---
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Courier", size=9)
    
    header = f"ESTADO DE CUENTA DETALLADO - ACCIÓN {acc_num}\n"
    header += f"BANQUITO LA COLMENA 🐝\n"
    header += "="*60 + "\n"
    header += f"Socio: {nombre_completo}\n"
    header += f"DNI  : {dni}\n"
    header += f"Fecha de reporte: {datetime.now().strftime('%d/%m/%Y %H:%M')}\n"
    header += "="*60 + "\n\n"
    
    header += "⏪ PARTE 1: HISTORIAL DE MOVIMIENTOS REALIZADOS\n"
    header += "-"*85 + "\n"
    header += f"{'FECHA':<12} | {'DETALLE':<25} | {'AMORT.':<10} | {'INT.':<8} | {'SALDO CAP.'}\n"
    header += "-"*85 + "\n"

    reporte_texto = header
    saldo_acumulado = 0.0
    
    # Agrupar movimientos históricos por fecha y hora exacta para fusionar cap e int
    historial_agrupado = {}
    for m in movs:
        f, t, mon = m[0], m[1], m[2]
        if f not in historial_agrupado: historial_agrupado[f] = {'cap': 0.0, 'int': 0.0, 'tipo': ''}
        
        if "Préstamo" in t:
            historial_agrupado[f]['cap'] = abs(mon)
            historial_agrupado[f]['tipo'] = "DESEMBOLSO"
        elif "Pago Cuota" in t:
            historial_agrupado[f]['cap'] = -abs(mon)
            historial_agrupado[f]['tipo'] = "PAGO"
        elif "Interés" in t:
            historial_agrupado[f]['int'] = abs(mon)

    for f in sorted(historial_agrupado.keys()):
        d = historial_agrupado[f]
        if d['tipo'] == "DESEMBOLSO":
            saldo_acumulado += d['cap']
            reporte_texto += f"{f[:10]:<12} | {'NUEVO PRÉSTAMO':<25} | {d['cap']:>10.2f} | {'---':<8} | {saldo_acumulado:>10.2f}\n"
        else:
            saldo_acumulado += d['cap'] # cap es negativo en pagos
            reporte_texto += f"{f[:10]:<12} | {'PAGO CUOTA':<25} | {abs(d['cap']):>10.2f} | {d['int']:>8.2f} | {saldo_acumulado:>10.2f}\n"

    # --- PROCESAR FUTURO (PROYECCIÓN) ---
    reporte_texto += "\n\n⏩ PARTE 2: PROYECCIÓN DE PAGOS PENDIENTES\n"
    reporte_texto += "-"*85 + "\n"
    reporte_texto += f"{'FECHA PAGO':<12} | {'CONCEPTO':<25} | {'CAPITAL':<10} | {'INT.':<8} | {'CUOTA TOT.'}\n"
    reporte_texto += "-"*85 + "\n"

    sp = saldo_hoy
    fh = datetime.now()
    mes, anio = fh.month, fh.year
    total_proyectado = 0.0

    while sp > 0.01:
        mes += 1
        if mes > 12: mes = 1; anio += 1
        fecha_p = f"06/{mes:02d}/{anio}"
        interes = math.ceil(sp * 0.015)
        amort = min(50.0, sp)
        cuota = amort + interes
        reporte_texto += f"{fecha_p:<12} | {'CUOTA PENDIENTE':<25} | {amort:>10.2f} | {interes:>8.2f} | {cuota:>10.2f}\n"
        sp -= amort
        total_proyectado += cuota

    reporte_texto += "-"*85 + "\n"
    reporte_texto += f"Saldo actual de capital: S/ {saldo_hoy:.2f}\n"
    reporte_texto += f"Total estimado para liquidar deuda: S/ {total_proyectado:.2f}\n"
    reporte_texto += "="*85 + "\n"

    for line in reporte_texto.split('\n'):
        pdf.cell(0, 5, txt=line.encode('latin-1','ignore').decode('latin-1'), ln=True)
    
    temp_path = f"EstadoCuenta_{dni}.pdf"
    pdf.output(temp_path)
    with open(temp_path, "rb") as f: pdf_bytes = f.read()
    
    try:
        os.remove(temp_path)
    except:
        pass
        
    return pdf_bytes

# =============================================================================
# CONFIGURACIÓN DE LA PÁGINA WEB (STREAMLIT)
# =============================================================================
st.set_page_config(page_title="Banquito La Colmena", page_icon="🐝", layout="wide")

st.title("🐝 Portal del Socio - Banquito La Colmena")
st.write("Consulta tus ahorros, historial de préstamos y cuánto debes pagar en la próxima reunión.")

dni_input = st.text_input("Ingrese su DNI:", max_chars=8)

if st.button("Consultar Estado"):
    if dni_input:
        try:
            with sqlite3.connect("banquito.db") as conn:
                cur = conn.cursor()
                cur.execute("SELECT nombres, apellidos, acciones FROM socios WHERE dni=?", (dni_input,))
                socio = cur.fetchone()

                if socio:
                    nombres, apellidos, acciones = socio
                    st.header(f"👋 Bienvenido, {nombres}")
                    
                    col1, col2 = st.columns(2)
                    
                    # --- COLUMNA 1: AHORROS Y APORTES ---
                    with col1:
                        st.subheader("💰 Tus Ahorros")
                        cur.execute("SELECT SUM(monto) FROM movimientos WHERE tipo LIKE '%Aporte%' AND tipo LIKE ?", (f"%{dni_input}%",))
                        tot_ahorro = cur.fetchone()[0] or 0.0
                        st.metric("Total Capitalizado", f"S/ {tot_ahorro:.2f}")
                        
                        st.write("---")
                        st.write("### 📥 Aportes Mensuales")
                        monto_aporte = acciones * 100.0
                        st.info(f"Tienes **{acciones} acciones** activas.")
                        st.write(f"Tu aporte obligatorio mensual es de: **S/ {monto_aporte:.2f}**")

                    # --- COLUMNA 2: PRÉSTAMOS ---
                    with col2:
                        st.subheader("💳 Tus Préstamos")
                        cur.execute("SELECT accion_asociada, saldo_actual, monto_original FROM prestamos WHERE dni_socio=? AND estado='ACTIVO'", (dni_input,))
                        prestamos = cur.fetchall()
                        
                        total_cuotas_prestamos = 0.0

                        if not prestamos:
                            st.success("✅ Estás al día. No tienes deudas activas.")
                        else:
                            for p in prestamos:
                                acc, s_act, m_orig = p
                                
                                # Cálculo de la próxima cuota para esta acción
                                int_proj = math.ceil(s_act * 0.015)
                                cap_proj = min(50.0, s_act)
                                cuota_total_accion = cap_proj + int_proj
                                total_cuotas_prestamos += cuota_total_accion
                                
                                st.warning(f"**Préstamo en Acción {acc}**")
                                st.write(f"📉 Saldo Pendiente de Capital: S/ {s_act:.2f}")
                                st.write(f"💸 Próxima Cuota (Cap + Int): **S/ {cuota_total_accion:.2f}**")
                                
                                # Botón para el PDF
                                pdf_data = generar_pdf_estado_cuenta(f"{nombres} {apellidos}", dni_input, acc)
                                st.download_button(
                                    label=f"📄 Descargar Estado de Cuenta (Acción {acc})",
                                    data=pdf_data,
                                    file_name=f"EstadoCuenta_Accion{acc}_{dni_input}.pdf",
                                    mime="application/pdf"
                                )
                    
                    # --- GRAN TOTAL A PAGAR ---
                    st.divider()
                    st.write("## 🔥 RESUMEN PARA LA PRÓXIMA REUNIÓN")
                    gran_total = monto_aporte + total_cuotas_prestamos
                    
                    resumen_col1, resumen_col2, resumen_col3 = st.columns(3)
                    resumen_col1.metric("1. Total Aportes", f"S/ {monto_aporte:.2f}")
                    resumen_col2.metric("2. Total Cuotas Préstamos", f"S/ {total_cuotas_prestamos:.2f}")
                    resumen_col3.metric("🔥 TOTAL A PAGAR", f"S/ {gran_total:.2f}")
                    
                    st.caption("*(Lleva el monto exacto a la reunión del día 06 para facilitar el trabajo del cajero).*")

                    # --- HISTORIAL RÁPIDO ---
                    st.divider()
                    st.write("### 📜 Tus Últimos Movimientos (Solo Préstamos y Cuotas)")
                    cur.execute("""
                        SELECT fecha, tipo, monto FROM movimientos 
                        WHERE tipo LIKE ? AND (tipo LIKE '%Préstamo%' OR tipo LIKE '%Pago Cuota%' OR tipo LIKE '%Interés Cuota%')
                        ORDER BY fecha DESC LIMIT 10
                    """, (f"%{dni_input}%",))
                    movs_web = cur.fetchall()
                    if movs_web:
                        # Limpiamos el texto para que se vea mejor en la tabla web
                        tabla_limpia = []
                        for m in movs_web:
                            concepto = m[1].split('(')[0].strip() # Quita lo de "(Acción 1)" para que se lea mejor
                            monto_str = f"S/ {abs(m[2]):.2f}"
                            # Le ponemos un signo (-) si fue un pago que salió del bolsillo del socio
                            if "Pago" in concepto or "Interés" in concepto:
                                monto_str = f"- {monto_str}"
                                
                            tabla_limpia.append({
                                "Fecha": m[0][:10], 
                                "Concepto": concepto, 
                                "Monto": monto_str
                            })
                        st.table(tabla_limpia)
                    else:
                        st.write("No hay movimientos recientes de préstamos.")

                else:
                    st.error("DNI no registrado en el sistema.")
        except Exception as e:
            st.error(f"Error interno: {e}")
    else:
        st.warning("Por favor, escriba su número de DNI arriba y presione Consultar.")

st.caption("🐝 Banquito La Colmena - Transparencia y Crecimiento.")