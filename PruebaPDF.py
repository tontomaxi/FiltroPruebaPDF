import streamlit as st
import pandas as pd
import re
from collections import Counter
import io
import PyPDF2
import warnings

# --- CORRECCIÓN DE ADVERTENCIAS ---
warnings.filterwarnings('ignore', category=UserWarning, module='openpyxl')

# --- CONFIGURACIÓN DE LA PÁGINA ---
st.set_page_config(page_title="Filtro de Pallets", page_icon="📊", layout="wide")

# --- LISTA DE CAMPOS ---
CAMPOS_SUGERIDOS = [
    "Folio", "N° Semana", "Fecha Análisis", "Fecha Etiqueta", "Analista", 
    "Turno", "Lote", "Cliente", "Tipo de producto", "Condición GF/convencional", 
    "Espesor inferior", "Espesor superrior", "% Humedad inferior FT", "% Humedad superior FT", 
    "Hora", "Cantidad sacos/maxisaco", "Peso saco/maxisaco", "Kilos producidos", "Humedad", 
    "Temperatura producto", "Enzimática", "Peso hectolitro", "Filamentos", "Cáscaras", 
    "Semillas Extrañas", "Gelatinas", "Quemadas", "Granos sin aplastar", 
    "Granos Parcialmente Aplastados", "Trigos", "Cebada", "Centeno", "Materiales extraños", 
    "Retención malla 7", "Bajo malla 25", "Espesor 1", "Espesor 2", "Espesor 3", 
    "Espesor 4", "Espesor 5", "Espesor 6", "Espesor 7", "Espesor 8", "Espesor 9", 
    "Espesor 10", "Promedio espesor", "Sacos detector de metales", 
    "Verificación de patrones PCC", "ESTADO", "Motivo Retención"
]

# --- FUNCIONES AUXILIARES ---
@st.cache_data
def extraer_info_pdf(pdf_file):
    try:
        reader = PyPDF2.PdfReader(pdf_file)
        texto_completo = ""
        for page in reader.pages:
            texto_completo += page.extract_text() + "\n"
        
        patron_contenedor = r"([A-Z]{4}(?:\s*\d){6,7}(?:\s*-\s*\d)?)"
        match_contenedor = re.search(patron_contenedor, texto_completo)
        
        contenedor_encontrado = ""
        if match_contenedor:
            contenedor_encontrado = match_contenedor.group(1).replace(" ", "").replace("\n", "")
            
        return contenedor_encontrado, texto_completo
    except Exception as e:
        return "", str(e)

def detectar_patron_inteligente(texto_sucio):
    if not texto_sucio: return "", 0, "", ""
    texto_sin_fechas = re.sub(r'\d{1,2}/\d{1,2}/\d{2,4}', '', texto_sucio)
    candidatos_sanos = re.findall(r'\b\d{10,14}\b', texto_sin_fechas)
    if not candidatos_sanos: return "", 0, "", ""
    
    prefijos = [c[:4] for c in candidatos_sanos]
    sufijos = [c[-2:] for c in candidatos_sanos]
    comun_prefix = Counter(prefijos).most_common(1)[0][0]
    comun_suffix = Counter(sufijos).most_common(1)[0][0]
    
    patron_generado = rf"({comun_prefix}[\d\s]+?{comun_suffix})\b"
    return patron_generado, len(candidatos_sanos), comun_prefix, comun_suffix

# --- INTERFAZ DE USUARIO ---
st.title("📊 Generador de Reportes")
st.markdown("Sube tanto el archivo Excel maestro como el Registro de Transporte de Carga para cruzar la información.")

# 1. CARGA DE ARCHIVOS
col1, col2 = st.columns(2)

with col1:
    st.info("📂 **Archivo Excel Maestro**")
    archivo_maestro_upload = st.file_uploader("Sube el Excel (.xlsx) aquí", type=["xlsx"])

with col2:
    st.info("📄 **Registro de Transporte de Carga**")
    archivo_pdf_upload = st.file_uploader("Sube el PDF aquí", type=["pdf"])

# 2. PROCESAMIENTO INICIAL
contenedor_final = ""
patron_final = ""
texto_pdf_final = ""
hoja_seleccionada = None
cols_seleccionadas_excel = []
cols_para_promediar = []
prefijo_auto = ""
sufijo_auto = ""

if archivo_pdf_upload:
    with st.spinner('Analizando PDF...'):
        cont_detectado, texto_pdf = extraer_info_pdf(archivo_pdf_upload)
        patron_detectado, num_candidatos, pref_det, suf_det = detectar_patron_inteligente(texto_pdf)
        
        prefijo_auto = pref_det
        sufijo_auto = suf_det
        
        if not cont_detectado: st.toast("⚠️ No se detectó contenedor.", icon="⚠️")
        if not patron_detectado: st.toast("⚠️ No se detectó patrón.", icon="⚠️")

    st.divider()
    st.subheader("🛠️ Validación y Edición Manual")
    
    c_val1, c_val2 = st.columns(2)
    file_id = archivo_pdf_upload.name 
    
    with c_val1:
        contenedor_final = st.text_input("📦 Contenedor Identificado:", value=cont_detectado, key=f"cont_{file_id}")
    
    with c_val2:
        patron_final = st.text_input(
            "🔍 Patrón Regex (Completo):", 
            value=patron_detectado, 
            key=f"pat_{file_id}",
            help="El \\b al final es importante para no cortar números antes de tiempo."
        )

    c_rec1, c_rec2 = st.columns(2)
    with c_rec1:
        prefijo_final = st.text_input("✂️ Prefijo (se borrará):", value=prefijo_auto, key=f"pref_{file_id}")
    with c_rec2:
        sufijo_final = st.text_input("✂️ Sufijo (se borrará):", value=sufijo_auto, key=f"suf_{file_id}")

    with st.expander("📝 Ver/Editar Texto del PDF (Opcional)"):
        texto_pdf_final = st.text_area("Contenido extraído:", value=texto_pdf, height=150, key=f"txt_{file_id}")

# 3. CONFIGURACIÓN DE EXCEL
if archivo_maestro_upload:
    try:
        excel_file = pd.ExcelFile(archivo_maestro_upload)
        nombres_hojas = excel_file.sheet_names
        
        st.subheader("⚙️ Configuración del Excel")
        c_conf1, c_conf2 = st.columns([1, 2])
        
        with c_conf1:
            hoja_seleccionada = st.selectbox("Hoja de Trabajo:", nombres_hojas)
        
        if hoja_seleccionada:
            df_sample = excel_file.parse(hoja_seleccionada, header=1, nrows=5)
            cols_reales = df_sample.columns.tolist()
            cols_numericas_reales = df_sample.select_dtypes(include=['number']).columns.tolist()
            defaults = [c for c in CAMPOS_SUGERIDOS if c in cols_reales]
            
            with c_conf2:
                # Selector 1: Columnas generales
                cols_seleccionadas_excel = st.multiselect(
                    "1️⃣ Columnas a incluir en el Reporte:", 
                    options=cols_reales, 
                    default=defaults
                )
                
                columnas_excluidas_promedio = ["Folio", "N° Semana", "Hora", "Cliente", "Fecha Etiqueta", "Motivo Retención", "Verificación de patrones PCC"]
                
                opciones_validas_promedio = [
                    c for c in cols_seleccionadas_excel 
                    if c in cols_numericas_reales and c not in columnas_excluidas_promedio
                ]
                
                # Selector 2: Promedios
                cols_para_promediar = st.multiselect(
                    "2️⃣ Columnas para calcular Promedios (Solo numéricas):", 
                    options=opciones_validas_promedio, 
                    default=opciones_validas_promedio, 
                    help="Se excluyeron automáticamente 'Folio' y 'N° Semana'."
                )

    except Exception as e:
        st.error(f"Error al leer el Excel cargado: {e}")

# --- BOTÓN DE PROCESAR FINAL ---
st.divider()
boton_procesar = st.button("🚀 Procesar", type="primary", disabled=(not archivo_pdf_upload or not archivo_maestro_upload))

if boton_procesar:
    if not contenedor_final or not patron_final or not cols_seleccionadas_excel:
        st.error("⚠️ Faltan datos (Contenedor, Patrón o Columnas). Revísalos arriba.")
    else:
        try:
            # 1. Leer Excel (Completo)
            with st.spinner(f'Leyendo datos de "{hoja_seleccionada}"...'):
                df_hojuelaavena = pd.read_excel(archivo_maestro_upload, sheet_name=hoja_seleccionada, header=1)
                
                col_folio_nombre = next((c for c in df_hojuelaavena.columns if str(c).lower().strip() == "folio"), None)
                if col_folio_nombre:
                    df_hojuelaavena[col_folio_nombre] = pd.to_numeric(df_hojuelaavena[col_folio_nombre], errors='coerce')
            
            # 2. Extracción de Folios Y Sacos del PDF
            # Construimos un regex que busque el folio seguido de los sacos
            # patron_final suele terminar en \b, lo quitamos para buscar lo que sigue
            patron_base = patron_final.rstrip(r'\b')
            # Buscamos: Folio + Espacios + Numero (Sacos)
            regex_con_sacos = rf"{patron_base}\s+(\d+)"
            
            hallazgos_sacos = re.findall(regex_con_sacos, texto_pdf_final)
            
            # Mapa: { Folio_INT : Cantidad_Sacos_INT }
            mapa_folios_sacos = {}
            
            len_p = len(prefijo_final)
            len_s = len(sufijo_final)
            
            # Procesamos para limpiar el folio (quitar prefijo/sufijo) y guardar los sacos
            for raw_folio, raw_sacos in hallazgos_sacos:
                s_clean = raw_folio.replace(" ", "").replace("\n", "")
                
                if len(s_clean) > (len_p + len_s):
                    folio_recortado_str = s_clean[len_p : -len_s] if len_s > 0 else s_clean[len_p:]
                    if folio_recortado_str.isdigit():
                        f_int = int(folio_recortado_str)
                        s_int = int(raw_sacos)
                        # Guardamos en el mapa. Si hay duplicados, se sobrescribe (asumimos consistencia)
                        mapa_folios_sacos[f_int] = s_int

            # Obtenemos la lista de folios únicos a buscar en Excel
            lista_folios_a_buscar = sorted(list(mapa_folios_sacos.keys()))
            
            total_items = len(lista_folios_a_buscar)
            filas_encontradas = []
            folios_no_encontrados = []
            coincidencias = 0
            
            if total_items == 0:
                st.warning("⚠️ No se extrajeron números válidos. Revisa el patrón o los recortes.")
            else:
                barra = st.progress(0)
                
                if not col_folio_nombre:
                    st.error(f"❌ La hoja '{hoja_seleccionada}' no tiene columna 'Folio'.")
                else:
                    for idx, folio_buscado in enumerate(lista_folios_a_buscar):
                        fila_match = df_hojuelaavena[df_hojuelaavena[col_folio_nombre] == folio_buscado]
                        
                        if not fila_match.empty:
                            coincidencias += 1
                            datos_fila = fila_match.iloc[0].to_dict()
                            
                            # Agregamos datos visuales y los sacos extraídos del PDF
                            datos_fila["Contenedor - Folio"] = f"{contenedor_final} - {folio_buscado}"
                            datos_fila["Sacos PDF"] = mapa_folios_sacos.get(folio_buscado, 0)
                            
                            filas_encontradas.append(datos_fila)
                        else:
                            folios_no_encontrados.append(folio_buscado)

                        barra.progress((idx + 1) / total_items)
                    
                    st.success(f"✅ Finalizado: {coincidencias} encontrados, {len(folios_no_encontrados)} no encontrados.")

                    if folios_no_encontrados:
                        st.warning(f"⚠️ {len(folios_no_encontrados)} folios no encontrados.")
                        df_missing = pd.DataFrame(folios_no_encontrados, columns=["Folio (No hallado)"]).astype(str)
                        st.dataframe(
                            df_missing, 
                            use_container_width=True, 
                            hide_index=True,
                            column_config={"Folio (No hallado)": st.column_config.Column(pinned=True)}
                        )

                    if filas_encontradas:
                        df_exportar = pd.DataFrame(filas_encontradas)
                        # Aseguramos que "Sacos PDF" no esté en la vista previa principal si el usuario no la pidió,
                        # pero la usaremos para cálculos internos.
                        lista_columnas_final = ["Contenedor - Folio"] + cols_seleccionadas_excel
                        df_final = df_exportar.reindex(columns=lista_columnas_final)
                        
                        st.subheader("📋 Vista Previa")
                        st.dataframe(
                            df_final, 
                            hide_index=True,
                            column_config={"Contenedor - Folio": st.column_config.Column(pinned=True)}
                        )

                        # --- CÁLCULO DE PROMEDIOS ---
                        st.subheader("📈 Promedios")
                        if cols_para_promediar:
                            df_proms = df_final[cols_para_promediar].apply(pd.to_numeric, errors='coerce')
                            proms = df_proms.mean().dropna()
                            if not proms.empty:
                                st.dataframe(proms.to_frame("Promedio").round(2).T, hide_index=True)
                            else:
                                st.warning("No se pudieron calcular promedios (datos vacíos).")
                        else:
                            st.info("No se seleccionaron columnas para promediar.")

                        # --- RESUMEN DE SACOS POR FECHA (USANDO DATOS DEL PDF) ---
                        st.subheader("📅 Resumen Diario de Sacos")
                        
                        col_fecha_etiqueta = "Fecha Etiqueta"
                        
                        # Usamos df_exportar que tiene TODAS las columnas, incluida "Sacos PDF"
                        if col_fecha_etiqueta in df_exportar.columns:
                            try:
                                df_resumen = df_exportar.copy()
                                
                                # Normalizar fecha
                                if pd.api.types.is_datetime64_any_dtype(df_resumen[col_fecha_etiqueta]):
                                    df_resumen[col_fecha_etiqueta] = df_resumen[col_fecha_etiqueta].dt.date
                                
                                # Agrupar por Fecha y Sumar la columna "Sacos PDF"
                                tabla_agrupada = df_resumen.groupby(col_fecha_etiqueta)[["Sacos PDF"]].sum().reset_index()
                                tabla_agrupada.rename(columns={"Sacos PDF": "Total Sacos"}, inplace=True)
                                
                                # Fila de Total
                                total_global_sacos = tabla_agrupada["Total Sacos"].sum()
                                df_total = pd.DataFrame({
                                    col_fecha_etiqueta: ["TOTAL"], 
                                    "Total Sacos": [total_global_sacos]
                                })
                                
                                tabla_final_sacos = pd.concat([tabla_agrupada, df_total], ignore_index=True)
                                
                                st.dataframe(
                                    tabla_final_sacos, 
                                    use_container_width=True, 
                                    hide_index=True,
                                    column_config={
                                        col_fecha_etiqueta: st.column_config.Column(pinned=True)
                                    }
                                )
                                
                            except Exception as e:
                                st.error(f"Error calculando resumen de sacos: {e}")
                        else:
                            st.info(f"⚠️ Para ver este resumen, asegúrate de incluir la columna '{col_fecha_etiqueta}' en el selector de columnas principal.")

                        # --- EXPORTAR EXCEL ---
                        output = io.BytesIO()
                        with pd.ExcelWriter(output, engine='openpyxl') as writer:
                            df_final.to_excel(writer, index=False, sheet_name='Reporte')
                            worksheet = writer.sheets['Reporte']
                            worksheet.auto_filter.ref = worksheet.dimensions
                            worksheet.freeze_panes = 'B2'
                            for column in worksheet.columns:
                                max_len = 0
                                col_let = column[0].column_letter
                                for cell in column:
                                    try: max_len = max(max_len, len(str(cell.value)))
                                    except: pass
                                worksheet.column_dimensions[col_let].width = max_len + 2
                        
                        st.download_button(
                            label="📥 Descargar Reporte Excel",
                            data=output.getvalue(),
                            file_name=f"Reporte_{contenedor_final}.xlsx",
                            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                        )
                    else:
                        st.error("❌ Ninguno de los folios se encontró en el Excel.")

        except Exception as e:
            st.error(f"Error procesando: {e}")
