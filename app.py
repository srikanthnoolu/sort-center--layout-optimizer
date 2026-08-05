import streamlit as st
import fitz  # PyMuPDF
from PIL import Image
import io
from google import genai

# Streamlit Page Config
st.set_page_config(
    page_title="Sort Center Layout Optimizer",
    layout="wide",
    page_icon="📦"
)

st.title("📦 AI-Powered Sort Center Layout & Compliance Analyzer")
st.caption("Automated industrial engineering CAD/PDF layout auditor")

# =========================================================
# SIDEBAR CONFIGURATION
# =========================================================
with st.sidebar:
    st.header("⚙️ Audit Configuration")
    api_key = st.text_input("Enter Gemini API Key:", type="password", help="Get key from aistudio.google.com")
    
    facility_type = st.selectbox("Facility Type:", ["Full Sort Center (SC)", "Cross-Dock / DSC", "Fulfillment Center Integration"])
    building_levels = st.selectbox("Building Structure:", ["Single Level (Ground Floor)", "Multi-Level (Ground + G+1 Mezzanine)"])
    
    st.subheader("Active Operational Streams")
    b2c_smalls = st.checkbox("B2C Non-Large (Smalls)", value=True)
    b2c_volumetric = st.checkbox("B2C Volumetric / Semi-Large", value=True)
    b2c_large = st.checkbox("B2C Large / Heavy", value=True)
    b2b_stream = st.checkbox("B2B Direct Stream", value=True)
    reverse_stream = st.checkbox("Reverse & Fraud Screening", value=True)

# =========================================================
# MAIN APP FLOW
# =========================================================
uploaded_file = st.file_uploader("Upload Facility Layout (PDF, PNG, JPG)", type=["pdf", "png", "jpg"])

if uploaded_file:
    try:
        # Read byte buffer safely for Streamlit Cloud
        file_bytes = uploaded_file.getvalue()
        
        if uploaded_file.name.lower().endswith(".pdf"):
            doc = fitz.open(stream=file_bytes, filetype="pdf")
            page = doc[0]
            pix = page.get_pixmap(dpi=200)
            img = Image.open(io.BytesIO(pix.tobytes("png")))
        else:
            img = Image.open(io.BytesIO(file_bytes))

        col1, col2 = st.columns([1, 1])

        with col1:
            st.subheader("🖼️ Layout Blueprint")
            st.image(img, use_container_width=True)

        with col2:
            st.subheader("📋 AI Layout Audit & Compliance Report")
            
            if st.button("🚀 Run Layout Audit", type="primary"):
                if not api_key:
                    st.error("Please enter your Gemini API Key in the sidebar.")
                else:
                    with st.spinner("Analyzing layout against operational rules..."):
                        try:
                            client = genai.Client(api_key=api_key)
                            
                            system_prompt = f"""
                            You are a Senior Industrial Engineer evaluating a logistics facility blueprint.
                            
                            FACILITY TYPE: {facility_type} ({building_levels})
                            ACTIVE STREAMS: Smalls ({b2c_smalls}), Volumetric ({b2c_volumetric}), Large ({b2c_large}), B2B ({b2b_stream}), Reverse ({reverse_stream}).
                            
                            EVALUATE THE DIAGRAM AGAINST THESE MANDATORY OPERATIONAL RULES:
                            
                            1. REVERSE LOGISTICS FLOW:
                               - Inbound Reverse bags arrive at Docks -> Bag-by-Bag Processing Area.
                               - DUAL SPLIT: High-risk/Fraud items -> 8 ft pathway to X-Ray & Fraud Screening. Standard cleared items -> Directly to Fast Sorter Machine (FSM).
                               - Post X-Ray cleared items -> Main FSM line -> Secondary Sortation (PTL Racks / Put Walls).
                            
                            2. DOCK INFRASTRUCTURE & CLEARANCES:
                               - Docks with Telescopic Belt Conveyors (TBC) for 32ft+ trucks MUST maintain a 20 FT clear buffer depth behind dock doors.
                               - Intracity/Zonal docks require 5-6 way dockside bag sorting area.
                            
                            3. PATHWAY & AISLE STANDARDS:
                               - Bag Movement Pathways: Min 10 FT (3.05m) wide.
                               - Shipment Movement Pathways: Min 8 FT (2.44m) wide.
                               - Heavy HPT / B2B Highways: Min 10 FT (3.05m) wide along perimeters.
                               - PTL Working Aisles: Min 6 to 8 FT.
                            
                            4. STAGING & VERTICAL NODES:
                               - Outbound Staging: 7x7 FT barricaded grids with 10 FT cross-aisles every 6-10 grids.
                               - Vertical Nodes (G+1 lifts/chutes): 15x15 FT clear trolley staging grid.

                            PROVIDE A STRUCTURED AUDIT REPORT IN MARKDOWN:
                            - **Overall Space Efficiency Score** (0-100)
                            - **Critical Bottlenecks & Rule Violations**
                            - **Reverse & Security Process Assessment**
                            - **Actionable Optimization Recommendations**
                            """

                            response = client.models.generate_content(
                                model='gemini-3.5-flash',
                                contents=[img, system_prompt]
                            )
                            
                            st.markdown(response.text)
                            
                        except Exception as e:
                            st.error(f"API Audit Error: {e}")

    except Exception as e:
        st.error(f"Error loading uploaded file: {e}")