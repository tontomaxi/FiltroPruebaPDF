import streamlit as st
import pandas as pd
import re
from collections import Counter
import io
import openpyxl
import PyPDF2

# --- CONFIGURACIÓN DE LA PÁGINA ---
st.set_page_config(page_title="Filtro de Pallets PDF", page_icon="📊", layout="wide")

# --- LISTA DE CAMPOS ---
campos = [
    "Contenedor - Folio", "Folio", "N° Semana", "Fecha Análisis", "Fecha Etiqueta", "Analista", 
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

# --- FUNCIÓN DE EXTRACCIÓN DE PDF ---
def extraer_info_pdf(pdf_file):
    reader = PyPDF2.PdfReader(pdf_file)
    texto_completo = ""
    for page in reader.pages:
        texto_completo += page.extract_text() + "\n"
    
    # 1. Buscar Contenedor (Patrón: 4 letras mayúsculas, 6-7 dígitos, opcional guion y dígito)
    # Ej: GAOU755639-5
    match_contenedor = re.search(r"([A-Z]{4}\d{6,7}(?:-\d)?)", texto_completo)
    contenedor_encontrado = match_contenedor.group(1) if match_contenedor else None
    
    return contenedor_encontrado, texto_completo

# --- FUNCIÓN DE DETECCIÓN INTELIGENTE (Misma lógica) ---
def detectar_patron_inteligente(texto_sucio):
    texto_sin_fechas = re.sub(r'\d{1,2}/\d{1,2}/\d{2,4}', '', texto_sucio)
    candidatos = re.findall(r'\b\d{10,14}\b', texto_sin_fechas)
    
    if not candidatos:
        return None, None
    
    prefijos = [c[:4] for c in candidatos]
    sufijos = [c[-2:] for c in candidatos]

    comun_prefix = Counter(prefijos).most_common(1)[0][0]
    comun_suffix = Counter(sufijos).most_common(1)[0][0]

    patron_generado = rf"{comun_prefix}(\d+?){comun_suffix}"
    
    return patron_generado, len(candidatos)

# --- INTERFAZ DE USUARIO ---
st.title("📊 Generador de Reportes de Hojuela (Vía PDF)")
st.markdown("Sube el archivo Excel maestro y el PDF de transporte para cruzar la información.")

# 1. Subir Archivos
col1, col2 = st.columns(2)
with col1:
    archivo_maestro = st.file_uploader("1️⃣ Cargar Excel Maestro ('Control de producto...')", type=["xlsx"])
with col2:
    archivo_pdf = st.file_uploader("2️⃣ Cargar PDF de Transporte", type=["pdf"])

# --- BOTÓN DE PROCESAR ---
if st.button("🚀 Procesar y Generar Excel"):
    if not archivo_maestro:
        st.error("⚠️ Falta el archivo Excel maestro.")
    elif not archivo_pdf:
        st.error("⚠️ Falta el archivo PDF de transporte.")
    else:
        try:
            # A) Leer PDF y extraer datos
            with st.spinner('Extrayendo información del PDF...'):
                contenedor, pallets_texto = extraer_info_pdf(archivo_pdf)
            
            if not contenedor:
                st.warning("⚠️ No se encontró un número de contenedor válido en el PDF. Se usará 'DESCONOCIDO'.")
                contenedor = "DESCONOCIDO"
            else:
                st.info(f"📦 Contenedor detectado: **{contenedor}**")

            # B) Leer Excel Maestro
            with st.spinner('Leyendo base de datos maestra...'):
                df_hojuelaavena = pd.read_excel(archivo_maestro, sheet_name="HOJUELA", header=1)
            
            # C) Detectar Patrón de Pallets
            patron, num_candidatos = detectar_patron_inteligente(pallets_texto)
            
            if patron:
                st.success(f"✅ Patrón detectado en {num_candidatos} pallets (Regex: `{patron}`)")
                
                lista_limpia = re.findall(patron, pallets_texto)
                lista_int = [int(x) for x in lista_limpia]
                lista_int.sort()
                
                filas_encontradas = []
                coincidencias = 0
                
                # Barra de progreso
                barra = st.progress(0)
                total_items = len(lista_int)

                for idx, folio_buscado in enumerate(lista_int):
                    fila_match = df_hojuelaavena[df_hojuelaavena["Folio"] == folio_buscado]
                    
                    if not fila_match.empty:
                        coincidencias += 1
                        datos_fila = fila_match.iloc[0].to_dict()
                        datos_fila["Contenedor - Folio"] = f"{contenedor} - {folio_buscado}"
                        filas_encontradas.append(datos_fila)
                    
                    barra.progress((idx + 1) / total_items)
                
                st.write(f"**Resultados:** {coincidencias} coincidencias de {total_items} códigos buscados.")

                # Generar Excel
                if filas_encontradas:
                    df_exportar = pd.DataFrame(filas_encontradas)
                    df_final = df_exportar.reindex(columns=campos)
                    
                    st.dataframe(df_final.head())
                    
                    output = io.BytesIO()
                    with pd.ExcelWriter(output, engine='openpyxl') as writer:
                        df_final.to_excel(writer, index=False, sheet_name='Reporte')
                        worksheet = writer.sheets['Reporte']
                        
                        # Formatos
                        worksheet.auto_filter.ref = worksheet.dimensions
                        worksheet.freeze_panes = 'B2'
                        for column in worksheet.columns:
                            max_length = 0
                            column_letter = column[0].column_letter
                            for cell in column:
                                try:
                                    if len(str(cell.value)) > max_length:
                                        max_length = len(str(cell.value))
                                except: pass
                            adjusted_width = (max_length + 2)
                            worksheet.column_dimensions[column_letter].width = adjusted_width
                    
                    excel_data = output.getvalue()
                    
                    st.download_button(
                        label="📥 Descargar Reporte Excel",
                        data=excel_data,
                        file_name=f"Reporte_Contenedor_{contenedor}.xlsx",
                        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                    )
                else:
                    st.warning("No se encontraron coincidencias en el Excel maestro para los pallets del PDF.")
            else:
                st.error("No se pudieron detectar pallets válidos en el PDF.")
                
        except Exception as e:
            st.error(f"Ocurrió un error: {e}")
