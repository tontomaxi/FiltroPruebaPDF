import streamlit as st
import pandas as pd
import re
from collections import Counter
import io
import PyPDF2

# --- CONFIGURACIÓN DE LA PÁGINA ---
st.set_page_config(page_title="Filtro de Pallets PDF", page_icon="📊", layout="wide")

# --- LISTA DE CAMPOS PREFERIDOS ---
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
        
        # CAMBIO: Regex flexible que permite espacios entre los números del contenedor
        # [A-Z]{4}       -> 4 letras iniciales
        # (?:\s*\d){6,7} -> 6 o 7 dígitos, permitiendo espacios opcionales (\s*) entre ellos
        # (?:\s*-\s*\d)? -> Guion y dígito final opcionales
        patron_contenedor = r"([A-Z]{4}(?:\s*\d){6,7}(?:\s*-\s*\d)?)"
        
        match_contenedor = re.search(patron_contenedor, texto_completo)
        
        contenedor_encontrado = ""
        if match_contenedor:
            # Limpiamos los espacios para normalizar el resultado (ej: "MSDU 123" -> "MSDU123")
            contenedor_encontrado = match_contenedor.group(1).replace(" ", "").replace("\n", "")
            
        return contenedor_encontrado, texto_completo
    except Exception as e:
        return "", str(e)

def detectar_patron_inteligente(texto_sucio):
    if not texto_sucio: return "", 0, "", ""
    texto_sin_fechas = re.sub(r'\d{1,2}/\d{1,2}/\d{2,4}', '', texto_sucio)
    candidatos_sanos = re.findall(r'\b\d{10,14}\b', texto_sin_fechas)
    if not candidatos_sanos: return "", 0, "", ""
    
    # 1. Detectar prefijo y sufijo comunes
    prefijos = [c[:4] for c in candidatos_sanos]
    sufijos = [c[-2:] for c in candidatos_sanos]
    comun_prefix = Counter(prefijos).most_common(1)[0][0]
    comun_suffix = Counter(sufijos).most_common(1)[0][0]
    
    # 2. Generar Patrón ROBUSTO
    # Agregamos \b al final. Esto obliga a que el sufijo sea realmente el final del número.
    # Ejemplo: Si el número es ...4052626
    # Sin \b: Se detiene en el primer 26 -> Captura ...40526 (Error)
    # Con \b: Se detiene solo en el último 26 -> Captura ...4052626 (Correcto)
    patron_generado = rf"({comun_prefix}[\d\s]+?{comun_suffix})\b"
    
    return patron_generado, len(candidatos_sanos), comun_prefix, comun_suffix

# --- INTERFAZ DE USUARIO ---
st.title("📊 Generador de Reportes)")
st.markdown("Sube el archivo Excel maestro y el registro de transporte de carga(en pdf) para cruzar la información.")

# 1. CARGA DE ARCHIVOS
col1, col2 = st.columns(2)
with col1:
    archivo_maestro = st.file_uploader("1️⃣ Cargar Excel Maestro", type=["xlsx", "xlsm","xlsb","xls","xlt","xltx","xltm","csv"])
with col2:
    archivo_pdf = st.file_uploader("2️⃣ Cargar PDF de registro de transporte de carga", type=["pdf"])

# 2. PROCESAMIENTO INICIAL
contenedor_final = ""
patron_final = ""
texto_pdf_final = ""
hoja_seleccionada = None
cols_seleccionadas_excel = []
prefijo_auto = ""
sufijo_auto = ""

if archivo_pdf:
    with st.spinner('Analizando PDF...'):
        cont_detectado, texto_pdf = extraer_info_pdf(archivo_pdf)
        patron_detectado, num_candidatos, pref_det, suf_det = detectar_patron_inteligente(texto_pdf)
        
        prefijo_auto = pref_det
        sufijo_auto = suf_det
        
        if not cont_detectado: st.toast("⚠️ No se detectó contenedor.", icon="⚠️")
        if not patron_detectado: st.toast("⚠️ No se detectó patrón.", icon="⚠️")

    st.divider()
    st.subheader("🛠️ Validación y Edición Manual")
    
    c_val1, c_val2, c_val3 = st.columns(3)
    file_id = archivo_pdf.name 
    
    with c_val1:
        contenedor_final = st.text_input("📦 Contenedor Identificado:", value=cont_detectado, key=f"cont_{file_id}")
    
    with c_val2:
        patron_final = st.text_input(
            "🔍 Patrón Regex (Completo):", 
            value=patron_detectado, 
            key=f"pat_{file_id}",
            help="El \\b al final es importante para no cortar números antes de tiempo."
        )

    with c_val3:
        # Campos para definir cuánto cortar, editables por el usuario
        prefijo_final = st.text_input("✂️ Prefijo (se borrará):", value=prefijo_auto, key=f"pref_{file_id}")
        sufijo_final = st.text_input("✂️ Sufijo (se borrará):", value=sufijo_auto, key=f"suf_{file_id}")

    with st.expander("📝 Ver/Editar Texto del PDF (Opcional)"):
        texto_pdf_final = st.text_area("Contenido extraído:", value=texto_pdf, height=150, key=f"txt_{file_id}")

# 3. CONFIGURACIÓN DE EXCEL
if archivo_maestro:
    try:
        excel_file = pd.ExcelFile(archivo_maestro)
        nombres_hojas = excel_file.sheet_names
        
        st.subheader("⚙️ Configuración del Excel")
        c_conf1, c_conf2 = st.columns([1, 2])
        
        with c_conf1:
            hoja_seleccionada = st.selectbox("Hoja de Trabajo:", nombres_hojas)
        
        if hoja_seleccionada:
            df_cols = pd.read_excel(archivo_maestro, sheet_name=hoja_seleccionada, header=1, nrows=0)
            cols_reales = df_cols.columns.tolist()
            defaults = [c for c in CAMPOS_SUGERIDOS if c in cols_reales]
            
            with c_conf2:
                cols_seleccionadas_excel = st.multiselect(
                    "Columnas del Excel a incluir:", 
                    options=cols_reales, 
                    default=defaults
                )
    except Exception as e:
        st.error(f"Error Excel: {e}")

# --- BOTÓN DE PROCESAR FINAL ---
st.divider()
boton_procesar = st.button("🚀 Procesar", type="primary", disabled=(not archivo_pdf or not archivo_maestro))

if boton_procesar:
    if not contenedor_final or not patron_final or not cols_seleccionadas_excel:
        st.error("⚠️ Faltan datos (Contenedor, Patrón o Columnas). Revísalos arriba.")
    else:
        try:
            # 1. Leer Excel
            with st.spinner(f'Leyendo datos de "{hoja_seleccionada}"...'):
                df_hojuelaavena = pd.read_excel(archivo_maestro, sheet_name=hoja_seleccionada, header=1)
                
                col_folio_nombre = next((c for c in df_hojuelaavena.columns if str(c).lower().strip() == "folio"), None)
                if col_folio_nombre:
                    df_hojuelaavena[col_folio_nombre] = pd.to_numeric(df_hojuelaavena[col_folio_nombre], errors='coerce')
            
            # 2. Extracción y Recorte
            # findall con el nuevo regex traerá los números COMPLETOS correctamente
            hallazgos_crudos = re.findall(patron_final, texto_pdf_final)
            
            # Limpiar espacios
            lista_strings_limpios = [x.replace(" ", "").replace("\n", "") for x in hallazgos_crudos]
            
            lista_folios_a_buscar = []
            
            # Longitudes a recortar (basadas en lo que diga el usuario en los inputs)
            len_p = len(prefijo_final)
            len_s = len(sufijo_final)
            
            for s in lista_strings_limpios:
                # Validar que el string sea lo suficientemente largo para recortar
                if len(s) > (len_p + len_s):
                    # Recorte estricto por posición
                    # Si s="03024052626", len_p=4 ("0302"), len_s=2 ("26")
                    # s[4 : -2]  => "40526" (CORRECTO)
                    folio_recortado_str = s[len_p : -len_s] if len_s > 0 else s[len_p:]
                    
                    if folio_recortado_str.isdigit():
                        lista_folios_a_buscar.append(int(folio_recortado_str))
            
            lista_folios_a_buscar = sorted(list(set(lista_folios_a_buscar)))
            
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
                        # Búsqueda EXACTA del folio ya recortado
                        fila_match = df_hojuelaavena[df_hojuelaavena[col_folio_nombre] == folio_buscado]
                        
                        if not fila_match.empty:
                            coincidencias += 1
                            datos_fila = fila_match.iloc[0].to_dict()
                            datos_fila["Contenedor - Folio"] = f"{contenedor_final} - {folio_buscado}"
                            filas_encontradas.append(datos_fila)
                        else:
                            folios_no_encontrados.append(folio_buscado)

                        barra.progress((idx + 1) / total_items)
                    
                    st.success(f"✅ Finalizado: {coincidencias} encontrados, {len(folios_no_encontrados)} no encontrados.")

                    if folios_no_encontrados:
                        st.warning(f"⚠️ {len(folios_no_encontrados)} folios no encontrados.")
                        df_missing = pd.DataFrame(folios_no_encontrados, columns=["Folio (No hallado)"]).astype(str)
                        st.dataframe(df_missing, use_container_width=True)

                    if filas_encontradas:
                        df_exportar = pd.DataFrame(filas_encontradas)
                        lista_columnas_final = ["Contenedor - Folio"] + cols_seleccionadas_excel
                        df_final = df_exportar.reindex(columns=lista_columnas_final)
                        
                        st.subheader("📋 Vista Previa")
                        st.dataframe(df_final)

                        st.subheader("📈 Promedios")
                        df_num = df_final.select_dtypes(include=['float64', 'int64'])
                        keywords = ["Humedad", "Espesor", "Peso", "FT"] 
                        cols_prom = [c for c in df_num.columns if any(k in c for k in keywords)]
                        if cols_prom:
                            proms = df_final[cols_prom].mean(numeric_only=True).dropna()
                            if not proms.empty:
                                st.dataframe(proms.to_frame("Promedio").round(2).T)
                        
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
