# app_seguimiento_contratos_mejorado_v5.py
# Streamlit app: seguimiento de contratos - CRUD (SQLite) + alertas (semáforo)
# Requisitos: pip install streamlit pandas openpyxl python-dateutil plotly

import streamlit as st
import sqlite3
import pandas as pd
from datetime import datetime, date
from dateutil import parser
import io
import plotly.express as px

DB_FILE = "contratos.db"
TABLE_NAME = "contratos"

# --- Definir columnas ---
COLUMNS = [
    "Código Interno / Proceso",
    "Nombre del Proceso / Objeto del Contrato",
    "Estado Actual del Proceso",
    "Tipo de Contrato",
    "Fuente de financiamiento",
    "Modalidad de selección",
    "Fecha de estructuración",
    "Fecha de envio a Contratos",
    "Fecha de respuesta de contratos",
    "Número del contrato",
    "Valor estimado en la vigencia actual",
    "Adición CDP",
    "Valor disminuido CDP",
    "Valor total CDP",
    "Valor contratado",
    "Saldo disponible CDP",
    "Adición en la ejecución",
    "Valor total contratado",
    "Supervisor",
    "Supervisor (Apoyo)",
    "Abogado OTIC",
    "Estructurador Técnico OTIC",
    "Abogados GIT Gestión Contractual",
    "Economico GIT",
    "Fecha acta de inicio / Fecha Inicio",
    "Mes de inicio1",
    "Mes de inicio2",
    "Fecha Final Contrato",
    "Fecha final de licencia/servicio",
    "Proveedor / Contratista",
    "Enlace SharePoint",
    "Seguimiento periódico",
    "Alerta Enviada"
]

# --- Opciones parametrizadas según la solicitud ---
ESTADO_PROCESO_OPTS = ['Iniciado', 'Estructuración', 'En proceso de selección', 'Adjudicado', 'Perfeccionamiento del Contrato', 'En Ejecución', 'Liquidado']
TIPO_CONTRATO_OPTS = ['Bienes y servicios']
FUENTE_FINANCIAMIENTO_OPTS = ['Funcionamiento', 'Inversión']
MODALIDAD_SELECCION_OPTS = ['Mínima Cuantía', 'Selección Abreviada - Acuerdo Marco', 'Contratación Directa']
MESES = ["", "Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio", "Julio", "Agosto", "Septiembre", "Octubre", "Noviembre", "Diciembre"]

# --- Utilidades ---
def safe_parse_date(s):
    if s is None or str(s).strip() == "":
        return None
    try:
        # Parsear la fecha y devolver solo la parte de la fecha
        return parser.parse(str(s)).date()
    except Exception:
        return None

def compute_alert_color(row):
    try:
        if str(row.get('Alerta Enviada', '')).strip().lower() in ['si', 'sí', 's', 'true', '1']:
            return '🟢'
        ffc = safe_parse_date(row.get('Fecha Final Contrato'))
        if ffc:
            days = (ffc - date.today()).days
            if days <= 30:
                return '🔴'
            elif days <= 90:
                return '🟡'
            else:
                return '🟢'
    except Exception:
        pass
    return '⚪'

def format_currency(value):
    try:
        if pd.isna(value) or value == "":
            return ""
        # Convertir a flotante, luego a entero, y formatear con signo de pesos y separador de miles
        return f"$ {int(float(value)):,d}"
    except (ValueError, TypeError):
        return str(value)

def format_numeric_no_decimals(value):
    try:
        if pd.isna(value) or value == "":
            return ""
        # Convertir a flotante y luego a entero para eliminar decimales
        return int(float(value))
    except (ValueError, TypeError):
        return value

def format_date_only(value):
    try:
        if pd.isna(value) or value == "":
            return ""
        # Convertir a formato de fecha y luego a cadena sin la hora
        return pd.to_datetime(value).strftime('%Y-%m-%d')
    except (ValueError, TypeError):
        return value
        
# --- DB helpers ---
def init_db():
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    cols = ", ".join([f'"{col}" TEXT' for col in COLUMNS])
    sql = f"CREATE TABLE IF NOT EXISTS {TABLE_NAME} (id INTEGER PRIMARY KEY AUTOINCREMENT, {cols})"
    c.execute(sql)
    conn.commit()
    conn.close()

def df_from_db():
    conn = sqlite3.connect(DB_FILE)
    df = pd.read_sql_query(f"SELECT * FROM {TABLE_NAME}", conn)
    conn.close()
    return df

def insert_record(values: dict):
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    cols = ", ".join([f'"{k}"' for k in values.keys()])
    placeholders = ",".join(["?" for _ in values.keys()])
    sql = f"INSERT INTO {TABLE_NAME} ({cols}) VALUES ({placeholders})"
    c.execute(sql, list(values.values()))
    conn.commit()
    conn.close()

def update_record(record_id: int, values: dict):
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    assignments = ", ".join([f'"{k}" = ?' for k in values.keys()])
    sql = f"UPDATE {TABLE_NAME} SET {assignments} WHERE id = ?"
    c.execute(sql, list(values.values()) + [record_id])
    conn.commit()
    conn.close()

def delete_record(record_id: int):
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute(f"DELETE FROM {TABLE_NAME} WHERE id = ?", (record_id,))
    conn.commit()
    conn.close()

# --- Configuración y UI ---
st.set_page_config(page_title="Bienes y Servicios", layout="wide", page_icon="📋")
init_db()
st.title("📋 Bienes y Servicios - Seguimiento de Contratos")

with st.spinner("Cargando datos..."):
    df_all = df_from_db()

# --- Sidebar ---
st.sidebar.header("Menú Principal")
st.sidebar.markdown("---")
menu_options = ["Ver Contratos", "Agregar registro", "Editar registro", "Eliminar registro", "Exportar Excel", "Tablero de Control", "Alertas de Vencimiento"]
action = st.sidebar.selectbox("Selecciona una acción", menu_options)

if 'current_page' not in st.session_state:
    st.session_state.current_page = "Ver Contratos"

if action != st.session_state.current_page:
    st.session_state.current_page = action
    st.rerun()

# --- Tablero de control ---
if st.session_state.current_page == "Tablero de Control":
    st.header("📊 Tablero de Control General")
    st.markdown("---")

    # [INICIO DE CAMBIO] - Nuevo selector para filtrar por contrato
    if not df_all.empty:
        contract_options = ['Todos los Contratos'] + list(df_all["Código Interno / Proceso"].unique())
        selected_contract = st.selectbox(
            "Selecciona un contrato para ver su información detallada:",
            options=contract_options
        )
        
        if selected_contract == 'Todos los Contratos':
            df_display = df_all.copy()
            st.subheader("Análisis General de Contratos")
        else:
            df_display = df_all[df_all["Código Interno / Proceso"] == selected_contract].copy()
            st.subheader(f"Análisis Detallado del Contrato: {selected_contract}")

    else:
        st.info("No hay datos para mostrar en el tablero. Agrega un registro primero.")
        df_display = pd.DataFrame() # DataFrame vacío para evitar errores

    if not df_display.empty:
        df_display['Semaforo'] = df_display.apply(compute_alert_color, axis=1)
        
        # Tarjetas de métricas
        total_contratos = len(df_display)
        contratos_rojo = df_display['Semaforo'].tolist().count('🔴')
        contratos_amarillo = df_display['Semaforo'].tolist().count('🟡')
        contratos_verde = df_display['Semaforo'].tolist().count('🟢')
        contratos_sin_fecha = df_display['Semaforo'].tolist().count('⚪')

        # [CAMBIO] - Métricas adicionales y refactorización para ser reactivas al filtro
        col1, col2, col3, col4, col5 = st.columns(5)
        col1.metric("📑 Total", total_contratos)
        col2.metric("🟢 Sin riesgo", contratos_verde)
        col3.metric("🟡 Próximos", contratos_amarillo)
        col4.metric("🔴 Alerta", contratos_rojo)
        col5.metric("⚪ Sin fecha", contratos_sin_fecha)
        st.markdown("---")

        # [CAMBIO] - Nuevas métricas solicitadas
        if selected_contract != 'Todos los Contratos':
            contrato_iniciado = "Sí" if df_display[df_display["Estado Actual del Proceso"] == "Iniciado"].shape[0] > 0 else "No"
            # [CAMBIO] Formatear a entero y con signo $
            valor_estimado = df_display["Valor estimado en la vigencia actual"].astype(float).sum()
            valor_contratado = df_display["Valor contratado"].astype(float).sum()
            
            st.markdown("### Resumen del Contrato Seleccionado")
            col_single1, col_single2, col_single3 = st.columns(3)
            col_single1.metric("Proceso Iniciado", contrato_iniciado)
            col_single2.metric("Valor Estimado Inicial", f"$ {int(valor_estimado):,d}")
            col_single3.metric("Valor Contratado Real", f"$ {int(valor_contratado):,d}")
            st.markdown("---")

        # Gráficos interactivos
        c1, c2 = st.columns(2)
        with c1:
            st.subheader("📌 Distribución por Estado Actual")
            estado_counts = df_display["Estado Actual del Proceso"].value_counts().reset_index()
            estado_counts.columns = ['Estado', 'Conteo']
            fig1 = px.bar(
                estado_counts,
                x="Estado",
                y="Conteo",
                title="Contratos por Estado",
                color="Estado"
            )
            st.plotly_chart(fig1, use_container_width=True)
        with c2:
            st.subheader("📌 Distribución de Alertas (Semáforo)")
            semaforo_counts = df_display["Semaforo"].value_counts().reset_index()
            semaforo_counts.columns = ['Color', 'Conteo']
            color_map = {'🟢': 'green', '🟡': 'yellow', '🔴': 'red', '⚪': 'gray'}
            fig2 = px.pie(
                semaforo_counts,
                values="Conteo",
                names="Color",
                title="Distribución de Contratos por Alerta",
                color="Color",
                color_discrete_map=color_map
            )
            st.plotly_chart(fig2, use_container_width=True)

        c3, c4 = st.columns(2)
        with c3:
            st.subheader("📌 Contratos por Fuente de financiamiento")
            fuente_counts = df_display["Fuente de financiamiento"].value_counts().reset_index()
            fuente_counts.columns = ['Fuente', 'Conteo']
            fig3 = px.bar(
                fuente_counts,
                x="Fuente",
                y="Conteo",
                title="Contratos por Fuente de Financiamiento",
                color="Fuente"
            )
            st.plotly_chart(fig3, use_container_width=True)
        with c4:
            st.subheader("📌 Contratos por Modalidad de Selección")
            modalidad_counts = df_display["Modalidad de selección"].value_counts().reset_index()
            modalidad_counts.columns = ['Modalidad', 'Conteo']
            fig4 = px.pie(
                modalidad_counts,
                values="Conteo",
                names="Modalidad",
                title="Distribución por Modalidad de Selección",
                color="Modalidad"
            )
            st.plotly_chart(fig4, use_container_width=True)
            
        # [INICIO DE CAMBIO] - Nuevo gráfico: Procesos por fecha de inicio
        st.markdown("---")
        st.subheader("📌 Procesos por Fecha de Inicio")
        df_display['Fecha acta de inicio / Fecha Inicio'] = pd.to_datetime(df_display['Fecha acta de inicio / Fecha Inicio'], errors='coerce')
        df_start_dates = df_display.dropna(subset=['Fecha acta de inicio / Fecha Inicio']).copy()
        df_start_dates['Año-Mes'] = df_start_dates['Fecha acta de inicio / Fecha Inicio'].dt.to_period('M').astype(str)
        
        if not df_start_dates.empty:
            start_counts = df_start_dates['Año-Mes'].value_counts().sort_index().reset_index()
            start_counts.columns = ['Año-Mes', 'Conteo']
            fig5 = px.line(
                start_counts,
                x="Año-Mes",
                y="Conteo",
                title="Cantidad de Procesos Iniciados por Mes",
                markers=True
            )
            st.plotly_chart(fig5, use_container_width=True)
        else:
            st.info("No hay fechas de inicio registradas para este filtro.")
        # [FIN DE CAMBIO]

# --- Alertas ---
elif st.session_state.current_page == "Alertas de Vencimiento":
    st.header("🚨 Alertas de Vencimiento de Contratos")
    st.markdown("---")
    if df_all.empty:
        st.info("No hay registros que mostrar.")
    else:
        df_alerts = df_all[df_all.apply(lambda row: compute_alert_color(row) in ['🔴', '🟡'], axis=1)].copy()
        if not df_alerts.empty:
            df_alerts['Días Restantes'] = df_alerts.apply(
                lambda row: (safe_parse_date(row.get('Fecha Final Contrato')) - date.today()).days if safe_parse_date(row.get('Fecha Final Contrato')) else None,
                axis=1
            )
            df_alerts['Semaforo'] = df_alerts.apply(compute_alert_color, axis=1)
            cols_show = ['Semaforo', 'Días Restantes', 'Fecha Final Contrato', 'Código Interno / Proceso', 'Nombre del Proceso / Objeto del Contrato', 'Proveedor / Contratista', 'Supervisor']
            
            # Formatear la columna de fecha
            df_alerts['Fecha Final Contrato'] = df_alerts['Fecha Final Contrato'].apply(format_date_only)
            
            st.dataframe(df_alerts[cols_show].sort_values(by='Días Restantes', ascending=True), use_container_width=True)
        else:
            st.success("¡No hay contratos en estado de alerta (rojo o amarillo)!")

# --- Ver contratos (con nueva funcionalidad de búsqueda) ---
elif st.session_state.current_page == "Ver Contratos":
    st.header("🔍 Ver Contratos")
    st.markdown("---")
    filtered_df = df_all.copy()
    
    with st.expander("Filtros avanzados 🔎"):
        filter_cols = st.multiselect("Selecciona las columnas para filtrar", options=COLUMNS, key="filter_cols_select")
        if filter_cols:
            for col in filter_cols:
                if "Fecha" in col:
                    try:
                        # Se usa .copy() para evitar SettingWithCopyWarning
                        temp_df = filtered_df.copy()
                        temp_df[f'{col}_date'] = pd.to_datetime(temp_df[col], errors='coerce').dt.date
                        min_date, max_date = temp_df[f'{col}_date'].min(), temp_df[f'{col}_date'].max()
                        if pd.notna(min_date) and pd.notna(max_date):
                            start_date, end_date = st.date_input(
                                f"Rango de Fechas para **{col}**",
                                value=(min_date, max_date),
                                min_value=min_date,
                                max_value=max_date,
                                key=f'date_filter_{col}'
                            )
                            filtered_df = filtered_df[pd.to_datetime(filtered_df[col], errors='coerce').dt.date.between(start_date, end_date)]
                    except Exception as e:
                        st.warning(f"No se pudo aplicar el filtro de fecha para '{col}'. Error: {e}")
                elif "Valor" in col or "Saldo" in col or "Adición" in col:
                    try:
                        temp_df = filtered_df.copy()
                        temp_df[f'{col}_numeric'] = pd.to_numeric(temp_df[col], errors='coerce')
                        min_val, max_val = temp_df[f'{col}_numeric'].min(), temp_df[f'{col}_numeric'].max()
                        if pd.notna(min_val) and pd.notna(max_val):
                            min_input, max_input = st.slider(
                                f"Rango de Valores para **{col}**",
                                min_value=float(min_val),
                                max_value=float(max_val),
                                value=(float(min_val), float(max_val)),
                                key=f'numeric_filter_{col}'
                            )
                            filtered_df = filtered_df[pd.to_numeric(filtered_df[col], errors='coerce').between(min_input, max_input)]
                    except Exception as e:
                        st.warning(f"No se pudo aplicar el filtro numérico para '{col}'. Error: {e}")
                elif col in ["Estado Actual del Proceso", "Tipo de Contrato", "Fuente de financiamiento", "Modalidad de selección", "Proveedor / Contratista", "Supervisor", "Código Interno / Proceso", "Nombre del Proceso / Objeto del Contrato"]:
                    options = sorted(list(filtered_df[col].dropna().unique()))
                    selected_options = st.multiselect(
                        f"Filtra por **{col}**",
                        options=options,
                        key=f'multiselect_filter_{col}'
                    )
                    if selected_options:
                        filtered_df = filtered_df[filtered_df[col].isin(selected_options)]
                else:
                    search_term = st.text_input(f"Busca en **{col}**", "", key=f'text_filter_{col}')
                    if search_term:
                        filtered_df = filtered_df[filtered_df[col].astype(str).str.contains(search_term, case=False, na=False)]

    st.markdown("---")
    st.subheader(f"Resultados ({len(filtered_df)} contratos)")
    
    if filtered_df.empty:
        st.info("No se encontraron contratos que coincidan con los filtros.")
    else:
        # Preparar el DataFrame para la visualización
        df_display = filtered_df.copy()
        
        # Aplicar formato a las columnas numéricas y de fecha
        for col in ["Valor estimado en la vigencia actual", "Adición CDP", "Valor disminuido CDP", "Valor total CDP", "Valor contratado", "Saldo disponible CDP", "Adición en la ejecución", "Valor total contratado"]:
            df_display[col] = df_display[col].apply(format_currency)
        
        for col in ["Fecha de estructuración", "Fecha de envio a Contratos", "Fecha de respuesta de contratos", "Fecha acta de inicio / Fecha Inicio", "Fecha Final Contrato", "Fecha final de licencia/servicio"]:
            df_display[col] = df_display[col].apply(format_date_only)

        # Formatear la columna "Número del contrato" a entero
        df_display["Número del contrato"] = df_display["Número del contrato"].apply(format_numeric_no_decimals)

        # Formatear las columnas "Mes de inicio" a entero
        df_display["Mes de inicio1"] = df_display["Mes de inicio1"].apply(format_numeric_no_decimals)
        df_display["Mes de inicio2"] = df_display["Mes de inicio2"].apply(format_numeric_no_decimals)

        # Se eliminó la línea df_display['Semaforo'] = df_display.apply(compute_alert_color, axis=1)
        
        cols_show = [c for c in COLUMNS if c in df_display.columns]
        st.dataframe(df_display[cols_show].sort_values(by='Código Interno / Proceso', ascending=True), use_container_width=True)

# --- Agregar registro ---
elif st.session_state.current_page == "Agregar registro":
    st.subheader("📝 Agregar nuevo registro de Bienes y Servicios")
    st.markdown("---")
    
    with st.form("add_form", clear_on_submit=True):
        inputs = {}
        
        # Uso de tabs para organizar el formulario
        tab_info_basica, tab_fechas, tab_valores, tab_otros_detalles = st.tabs(["Información Básica", "Fechas Clave", "Valores Financieros", "Otros Detalles"])

        with tab_info_basica:
            cols1 = st.columns(2)
            inputs["Código Interno / Proceso"] = cols1[0].text_input("Código Interno / Proceso")
            inputs["Nombre del Proceso / Objeto del Contrato"] = cols1[1].text_input("Nombre del Proceso / Objeto del Contrato")
            cols2 = st.columns(3)
            inputs["Estado Actual del Proceso"] = cols2[0].selectbox("Estado Actual del Proceso", options=[''] + ESTADO_PROCESO_OPTS)
            inputs["Tipo de Contrato"] = cols2[1].selectbox("Tipo de Contrato", options=[''] + TIPO_CONTRATO_OPTS)
            inputs["Fuente de financiamiento"] = cols2[2].selectbox("Fuente de financiamiento", options=[''] + FUENTE_FINANCIAMIENTO_OPTS)
            inputs["Modalidad de selección"] = st.selectbox("Modalidad de selección", options=[''] + MODALIDAD_SELECCION_OPTS)
            inputs["Proveedor / Contratista"] = st.text_input("Proveedor / Contratista")
            inputs["Supervisor"] = st.text_input("Supervisor")
            inputs["Supervisor (Apoyo)"] = st.text_input("Supervisor (Apoyo)")
        
        with tab_fechas:
            cols3 = st.columns(3)
            inputs["Fecha de estructuración"] = cols3[0].date_input("Fecha de estructuración", value=None)
            inputs["Fecha de envio a Contratos"] = cols3[1].date_input("Fecha de envio a Contratos", value=None)
            inputs["Fecha de respuesta de contratos"] = cols3[2].date_input("Fecha de respuesta de contratos", value=None)
            cols4 = st.columns(3)
            inputs["Fecha acta de inicio / Fecha Inicio"] = cols4[0].date_input("Fecha acta de inicio / Fecha Inicio", value=None)
            inputs["Fecha Final Contrato"] = cols4[1].date_input("Fecha Final Contrato", value=None)
            inputs["Fecha final de licencia/servicio"] = cols4[2].date_input("Fecha final de licencia/servicio", value=None)
            cols5 = st.columns(2)
            inputs["Mes de inicio1"] = cols5[0].selectbox("Mes de inicio1", MESES)
            inputs["Mes de inicio2"] = cols5[1].selectbox("Mes de inicio2", MESES)

        with tab_valores:
            cols6 = st.columns(3)
            # [CAMBIO] Formato a entero y signo $
            inputs["Valor estimado en la vigencia actual"] = cols6[0].number_input("Valor estimado en la vigencia actual ($)", min_value=0, step=1)
            inputs["Adición CDP"] = cols6[1].number_input("Adición CDP ($)", min_value=0, step=1)
            inputs["Valor disminuido CDP"] = cols6[2].number_input("Valor disminuido CDP ($)", min_value=0, step=1)
            cols7 = st.columns(3)
            inputs["Valor total CDP"] = cols7[0].number_input("Valor total CDP ($)", min_value=0, step=1)
            inputs["Valor contratado"] = cols7[1].number_input("Valor contratado ($)", min_value=0, step=1)
            inputs["Saldo disponible CDP"] = cols7[2].number_input("Saldo disponible CDP ($)", min_value=0, step=1)
            cols8 = st.columns(2)
            inputs["Adición en la ejecución"] = cols8[0].number_input("Adición en la ejecución ($)", min_value=0, step=1)
            inputs["Valor total contratado"] = cols8[1].number_input("Valor total contratado ($)", min_value=0, step=1)
            
        with tab_otros_detalles:
            inputs["Número del contrato"] = st.text_input("Número del contrato")
            inputs["Abogado OTIC"] = st.text_input("Abogado OTIC")
            inputs["Estructurador Técnico OTIC"] = st.text_input("Estructurador Técnico OTIC")
            inputs["Abogados GIT Gestión Contractual"] = st.text_input("Abogados GIT Gestión Contractual")
            inputs["Economico GIT"] = st.text_input("Economico GIT")
            inputs["Enlace SharePoint"] = st.text_input("Enlace SharePoint")
            inputs["Seguimiento periódico"] = st.text_input("Seguimiento periódico")
            inputs["Alerta Enviada"] = st.text_input("Alerta Enviada")

        st.markdown("---")
        if st.form_submit_button("✅ Guardar Registro", use_container_width=True):
            values = {k: v.isoformat() if isinstance(v, (date, datetime)) else str(v) if v is not None else "" for k, v in inputs.items()}
            insert_record(values)
            st.success("Registro creado correctamente.")
            st.rerun()

# --- Editar registro ---
elif st.session_state.current_page == "Editar registro":
    st.subheader("✏️ Editar registro existente")
    st.markdown("---")
    if df_all.empty:
        st.info("No hay registros para editar")
    else:
        opts = df_all[['id', 'Código Interno / Proceso', 'Nombre del Proceso / Objeto del Contrato']].fillna("")
        opts['label'] = opts['Código Interno / Proceso'] + ' — ' + opts['Nombre del Proceso / Objeto del Contrato']
        sel_label = st.selectbox("Selecciona un registro para editar", options=[''] + opts['label'].tolist())

        if sel_label:
            rid = int(opts.loc[opts['label'] == sel_label, 'id'].values[0])
            row = df_all[df_all['id'] == rid].iloc[0]
            st.markdown(f"**Editando registro:** {sel_label}")

            with st.form("edit_form"):
                new_vals = {}

                tab_info_basica, tab_fechas, tab_valores, tab_otros_detalles = st.tabs(["Información Básica", "Fechas Clave", "Valores Financieros", "Otros Detalles"])

                with tab_info_basica:
                    cols1 = st.columns(2)
                    new_vals["Código Interno / Proceso"] = cols1[0].text_input("Código Interno / Proceso", value=row.get("Código Interno / Proceso", ""))
                    new_vals["Nombre del Proceso / Objeto del Contrato"] = cols1[1].text_input("Nombre del Proceso / Objeto del Contrato", value=row.get("Nombre del Proceso / Objeto del Contrato", ""))
                    cols2 = st.columns(3)
                    new_vals["Estado Actual del Proceso"] = cols2[0].selectbox("Estado Actual del Proceso", options=[''] + ESTADO_PROCESO_OPTS, index=ESTADO_PROCESO_OPTS.index(row.get("Estado Actual del Proceso", "")) + 1 if row.get("Estado Actual del Proceso", "") in ESTADO_PROCESO_OPTS else 0)
                    new_vals["Tipo de Contrato"] = cols2[1].selectbox("Tipo de Contrato", options=[''] + TIPO_CONTRATO_OPTS, index=TIPO_CONTRATO_OPTS.index(row.get("Tipo de Contrato", "")) + 1 if row.get("Tipo de Contrato", "") in TIPO_CONTRATO_OPTS else 0)
                    new_vals["Fuente de financiamiento"] = cols2[2].selectbox("Fuente de financiamiento", options=[''] + FUENTE_FINANCIAMIENTO_OPTS, index=FUENTE_FINANCIAMIENTO_OPTS.index(row.get("Fuente de financiamiento", "")) + 1 if row.get("Fuente de financiamiento", "") in FUENTE_FINANCIAMIENTO_OPTS else 0)
                    new_vals["Modalidad de selección"] = st.selectbox("Modalidad de selección", options=[''] + MODALIDAD_SELECCION_OPTS, index=MODALIDAD_SELECCION_OPTS.index(row.get("Modalidad de selección", "")) + 1 if row.get("Modalidad de selección", "") in MODALIDAD_SELECCION_OPTS else 0)
                    new_vals["Proveedor / Contratista"] = st.text_input("Proveedor / Contratista", value=row.get("Proveedor / Contratista", ""))
                    new_vals["Supervisor"] = st.text_input("Supervisor", value=row.get("Supervisor", ""))
                    new_vals["Supervisor (Apoyo)"] = st.text_input("Supervisor (Apoyo)", value=row.get("Supervisor (Apoyo)", ""))

                with tab_fechas:
                    cols3 = st.columns(3)
                    new_vals["Fecha de estructuración"] = cols3[0].date_input("Fecha de estructuración", value=safe_parse_date(row.get("Fecha de estructuración")))
                    new_vals["Fecha de envio a Contratos"] = cols3[1].date_input("Fecha de envio a Contratos", value=safe_parse_date(row.get("Fecha de envio a Contratos")))
                    new_vals["Fecha de respuesta de contratos"] = cols3[2].date_input("Fecha de respuesta de contratos", value=safe_parse_date(row.get("Fecha de respuesta de contratos")))
                    cols4 = st.columns(3)
                    new_vals["Fecha acta de inicio / Fecha Inicio"] = cols4[0].date_input("Fecha acta de inicio / Fecha Inicio", value=safe_parse_date(row.get("Fecha acta de inicio / Fecha Inicio")))
                    new_vals["Fecha Final Contrato"] = cols4[1].date_input("Fecha Final Contrato", value=safe_parse_date(row.get("Fecha Final Contrato")))
                    new_vals["Fecha final de licencia/servicio"] = cols4[2].date_input("Fecha final de licencia/servicio", value=safe_parse_date(row.get("Fecha final de licencia/servicio")))
                    cols5 = st.columns(2)
                    new_vals["Mes de inicio1"] = cols5[0].selectbox("Mes de inicio1", MESES, index=MESES.index(row.get("Mes de inicio1", "")) if row.get("Mes de inicio1", "") in MESES else 0)
                    new_vals["Mes de inicio2"] = cols5[1].selectbox("Mes de inicio2", MESES, index=MESES.index(row.get("Mes de inicio2", "")) if row.get("Mes de inicio2", "") in MESES else 0)

                with tab_valores:
                    cols6 = st.columns(3)
                    # [CAMBIO] Formato a entero y signo $
                    new_vals["Valor estimado en la vigencia actual"] = cols6[0].number_input("Valor estimado en la vigencia actual ($)", value=int(float(row.get("Valor estimado en la vigencia actual", 0))) if row.get("Valor estimado en la vigencia actual") else 0, step=1)
                    new_vals["Adición CDP"] = cols6[1].number_input("Adición CDP ($)", value=int(float(row.get("Adición CDP", 0))) if row.get("Adición CDP") else 0, step=1)
                    new_vals["Valor disminuido CDP"] = cols6[2].number_input("Valor disminuido CDP ($)", value=int(float(row.get("Valor disminuido CDP", 0))) if row.get("Valor disminuido CDP") else 0, step=1)
                    cols7 = st.columns(3)
                    new_vals["Valor total CDP"] = cols7[0].number_input("Valor total CDP ($)", value=int(float(row.get("Valor total CDP", 0))) if row.get("Valor total CDP") else 0, step=1)
                    new_vals["Valor contratado"] = cols7[1].number_input("Valor contratado ($)", value=int(float(row.get("Valor contratado", 0))) if row.get("Valor contratado") else 0, step=1)
                    new_vals["Saldo disponible CDP"] = cols7[2].number_input("Saldo disponible CDP ($)", value=int(float(row.get("Saldo disponible CDP", 0))) if row.get("Saldo disponible CDP") else 0, step=1)
                    cols8 = st.columns(2)
                    new_vals["Adición en la ejecución"] = cols8[0].number_input("Adición en la ejecución ($)", value=int(float(row.get("Adición en la ejecución", 0))) if row.get("Adición en la ejecución") else 0, step=1)
                    new_vals["Valor total contratado"] = cols8[1].number_input("Valor total contratado ($)", value=int(float(row.get("Valor total contratado", 0))) if row.get("Valor total contratado") else 0, step=1)

                with tab_otros_detalles:
                    new_vals["Número del contrato"] = st.text_input("Número del contrato", value=row.get("Número del contrato", ""))
                    new_vals["Abogado OTIC"] = st.text_input("Abogado OTIC", value=row.get("Abogado OTIC", ""))
                    new_vals["Estructurador Técnico OTIC"] = st.text_input("Estructurador Técnico OTIC", value=row.get("Estructurador Técnico OTIC", ""))
                    new_vals["Abogados GIT Gestión Contractual"] = st.text_input("Abogados GIT Gestión Contractual", value=row.get("Abogados GIT Gestión Contractual", ""))
                    new_vals["Economico GIT"] = st.text_input("Economico GIT", value=row.get("Economico GIT", ""))
                    new_vals["Enlace SharePoint"] = st.text_input("Enlace SharePoint", value=row.get("Enlace SharePoint", ""))
                    new_vals["Seguimiento periódico"] = st.text_input("Seguimiento periódico", value=row.get("Seguimiento periódico", ""))
                    new_vals["Alerta Enviada"] = st.text_input("Alerta Enviada", value=row.get("Alerta Enviada", ""))
                    
                st.markdown("---")
                if st.form_submit_button("💾 Actualizar Registro", use_container_width=True):
                    to_save = {k: v.isoformat() if isinstance(v, (date, datetime)) else str(v) if v is not None else "" for k, v in new_vals.items()}
                    update_record(rid, to_save)
                    st.success("Registro actualizado correctamente.")
                    st.rerun()

# --- Eliminar registro ---
elif st.session_state.current_page == "Eliminar registro":
    st.subheader("🗑️ Eliminar registro existente")
    st.markdown("---")
    if df_all.empty:
        st.info("No hay registros para eliminar")
    else:
        opts = df_all[['id', 'Código Interno / Proceso', 'Nombre del Proceso / Objeto del Contrato']].fillna("")
        opts['label'] = opts['Código Interno / Proceso'] + ' — ' + opts['Nombre del Proceso / Objeto del Contrato']
        sel_label = st.selectbox("Selecciona un registro para eliminar", options=[''] + opts['label'].tolist())
        if sel_label:
            rid = int(opts.loc[opts['label'] == sel_label, 'id'].values[0])
            st.warning(f"⚠️ ¿Estás seguro de que deseas eliminar el registro: **{sel_label}**?")
            if st.button("❌ Confirmar eliminación"):
                delete_record(rid)
                st.success("Registro eliminado correctamente.")
                st.rerun()

# --- Exportar Excel ---
elif st.session_state.current_page == "Exportar Excel":
    st.subheader("📤 Exportar base a Excel")
    st.markdown("---")
    if df_all.empty:
        st.info("No hay datos para exportar.")
    else:
        output = io.BytesIO()
        df_export = df_all.drop(columns=['id'], errors='ignore').copy()

        # Aplicar formato a las columnas de fecha y valores antes de exportar
        for col in ["Fecha de estructuración", "Fecha de envio a Contratos", "Fecha de respuesta de contratos", "Fecha acta de inicio / Fecha Inicio", "Fecha Final Contrato", "Fecha final de licencia/servicio"]:
            df_export[col] = df_export[col].apply(lambda x: safe_parse_date(x).isoformat() if safe_parse_date(x) else "")
        
        for col in ["Número del contrato", "Mes de inicio1", "Mes de inicio2", "Valor estimado en la vigencia actual", "Adición CDP", "Valor disminuido CDP", "Valor total CDP", "Valor contratado", "Saldo disponible CDP", "Adición en la ejecución", "Valor total contratado"]:
            try:
                # Convertir a numérico para asegurar el tipo de dato correcto en Excel
                df_export[col] = pd.to_numeric(df_export[col], errors='coerce').fillna("")
            except Exception:
                pass
        
        with pd.ExcelWriter(output, engine='openpyxl') as writer:
            df_export.to_excel(writer, index=False, sheet_name="Contratos")
        
        st.download_button(
            "⬇️ Descargar Excel",
            data=output.getvalue(),
            file_name="contratos_export.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            use_container_width=True
        )
