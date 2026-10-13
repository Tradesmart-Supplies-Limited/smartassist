import io

import fitz  # PyMuPDF
import streamlit as st

from core.excel_reader import clean_sheet, detect_header_row, read_raw_sheets

st.set_page_config(page_title="DocuLoop", layout="wide")
st.title("DocuLoop")
st.caption("Step 1: upload the sample PDF. Step 2: upload the client's Excel sheet.")

col1, col2 = st.columns(2)
with col1:
    st.subheader("1. Sample PDF (template)")
    pdf_file = st.file_uploader(
        "Drag and drop the sample PDF here, or click Browse files",
        type=["pdf"], key="pdf",
    )
with col2:
    st.subheader("2. Client Excel sheet")
    xl_file = st.file_uploader(
        "Drag and drop the Excel file here, or click Browse files",
        type=["xlsx", "xlsm", "csv"], key="xl",
    )

if pdf_file:
    st.divider()
    st.header("Sample PDF analysis")
    doc = fitz.open(stream=pdf_file.getvalue(), filetype="pdf")
    for i, page in enumerate(doc, start=1):
        text = page.get_text()
        shapes = len(page.get_drawings())
        st.write(f"**Page {i}:** {len(text)} characters of text, {shapes} drawn lines/shapes")
        if len(text) == 0:
            st.warning("No text found. This page may be a scanned image.")
        with st.expander(f"Text found on page {i}"):
            st.text(text[:3000])

if xl_file:
    st.divider()
    st.header("Excel data")
    raw_sheets = read_raw_sheets(io.BytesIO(xl_file.getvalue()), xl_file.name)
    sheet_name = st.selectbox("Sheet", list(raw_sheets))
    raw = raw_sheets[sheet_name]

    if len(raw) == 0:
        st.warning("This sheet is empty.")
    else:
        guess = detect_header_row(raw)
        header_row = st.number_input(
            "Row that contains the column titles (the first row is 1)",
            min_value=1, max_value=len(raw), value=guess + 1,
        ) - 1
        df = clean_sheet(raw, int(header_row))
        st.write(f"**{len(df)} data rows, {len(df.columns)} columns**")
        st.write("Columns found:", list(df.columns))
        st.dataframe(df, use_container_width=True)