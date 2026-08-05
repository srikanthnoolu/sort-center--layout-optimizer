import streamlit as st
import fitz  # PyMuPDF
from PIL import Image
import io
from google import genai

# Streamlit Page Config
st.set_page_config(
    page_title="Sort Center Layout & Process Optimizer",
    layout="wide",
    page_icon="📦"
)

# App Header
st.title("📦 AI-Powered Sort Center Layout & Compliance Analyzer")
st.caption("Automated architectural CAD/PDF audit engine built on Industrial Engineering standards & SLP guidelines.")

# =========================================================
# SIDEBAR CONFIGURATION
# =========================================================
with st.sidebar:
    st.header("⚙️ Audit Configuration")
    api_key = st.text_input("Enter Gemini API Key:", type="password", help="Get key from aistudio.google.com")
    
    st.subheader("Facility Metadata")
    facility_type = st.selectbox("Facility Type:", ["Full Sort Center (SC)", "Cross-Dock / DSC", "Fulfillment Center (FC) Integration"])
    building_levels = st.selectbox("Building Structure:", ["Single Level (Ground Floor)", "Multi-Level (Ground + G+1 Mezzanine)", "Multi-Level (Ground + G+2+)"])
    
    st.subheader("Active Operational Streams")
    b2c_smalls = st.checkbox("B2C Non-Large (Smalls)", value=True)
    b2c_volumetric = st.checkbox("B2C Volumetric / Semi-Large", value=True)
    b2c_large = st.checkbox("B2C Large / Heavy", value=True)
    b2b_stream = st.checkbox("B2B Direct Stream", value=True)
    reverse_stream = st.checkbox("Reverse & Fraud Screening", value=True)

    st.markdown("---")
    st.markdown("**Standards Applied:**\n- OSHA 1910.176(a)\n- ISO 28000 / C-TPAT\n- NFPA 13 Fire Safety\n- ISO 11228 Ergonomics")

# =========================================================
# MAIN CONTENT AREA
# =========================================================
uploaded_file = st.file_uploader("Upload Facility Layout Drawing (PDF, PNG, JPG)", type=["pdf", "png", "jpg"])

if uploaded_file:
    # Convert PDF to High-Res Image or open raw image
    if uploaded_file.name.lower().endswith(".pdf"):
        doc = fitz.open(stream=uploaded_file.read(), filetype="pdf")
        page = doc[0]
        pix = page.get_pixmap(dpi=300) # High-res rendering for clear CAD text reading
        img = Image.open(io.BytesIO(pix.tobytes("png")))
    else:
        img = Image.open(uploaded_file)

    col1, col2 = st.columns([1, 1])

    with col1:
        st.subheader("🖼️ Layout Blueprint")
        st.image(img, use_container_width=True)

    with col2:
        st.subheader("📋 AI Compliance & Bottleneck Report")
        
        if st.button("🚀 Run Layout Audit", type="primary"):
            if not api_key:
                st.error("Please enter your Gemini API Key in the sidebar to proceed.")
            else:
                with st.spinner("Auditing layout against industrial engineering rules and safety norms..."):
                    try:
                        client = genai.Client(api_key=api_key)
                        
                        system_prompt = f"""
                        You are a Lead Industrial Engineer and Supply Chain Architect evaluating a logistics facility blueprint.
                        
                        FACILITY CONTEXT:
                        - Facility Type: {facility_type}
                        - Elevation/Levels: {building_levels}
                        - Active Streams: B2C Smalls ({b2c_smalls}), Volumetric ({b2c_volumetric}), B2C Large ({b2c_large}), B2B ({b2b_stream}), Reverse Logistics ({reverse_stream}).
                        
                        EVALUATE THE BLUEPRINT AGAINST THESE MANDATORY FRAMEWORK & INDUSTRY NORMS:
                        
                        1. REVERSE LOGISTICS & FRAUD FLOW (CRITICAL RULE):
                           - Inbound Reverse bags arrive at Docks -> Bag-by-Bag Processing Area (debagging, scan, initial sort).
                           - DUAL SPLIT: 
                             a) High-Risk/Fraud shipments loaded into Shipment Trolleys -> transported via 8 ft pathway to X-Ray & Fraud Screening Area (FSM/X-Ray).
                             b) Standard cleared returns -> directly fed to Fast Sorter Machine (FSM).
                           - Post X-Ray cleared items feed into main FSM line -> Secondary Sortation (PTL Racks / Put Walls).
                           - Verify physical separation between uninspected reverse zones and clean outbound grids (ISO 28000 / C-TPAT).
                        
                        2. DOCK INFRASTRUCTURE & CLEARANCES:
                           - Docks with Telescopic Belt Conveyors (TBC) for 32ft+ trucks MUST maintain a 20 FT (~6.1m) clear buffer depth behind dock doors (No fixed staging/racks).
                           - Intracity/Zonal docks require 5-6 way dockside bag sorting area.
                           - L-Flow or U-Flow isolation between IB and OB docks to prevent vehicle/trolley collisions.
                        
                        3. PATHWAYS & AISLE STANDARDS (OSHA 1910.176(a)):
                           - Bag Movement Pathways: Min 10 FT (3.05m) wide (2-way trolley passage).
                           - Shipment Movement Pathways: Min 8 FT (2.44m) wide.
                           - Heavy HPT / B2B Highways: Min 10 FT (3.05m) wide along perimeters.
                           - PTL Working Aisles: Min 6 to 8 FT (1.8 - 2.4m).
                        
                        4. STAGING & VERTICAL ARCHITECTURE:
                           - OB Staging: 7x7 FT barricaded grids. MUST have 10 FT cross-aisles every 6-10 grids (NFPA 13 egress compliance).
                           - Vertical Nodes (G+1/Mezzanine lifts/chutes): MUST feature a 15x15 FT clear trolley staging grid at landing zones.
                        
                        5. SPECIALIZED ZONES:
                           - Volumetric: DWS (Dimension Weight Scanner) footprint + 3m infeed/outfeed buffer.
                           - Quarantine Hold: 100-200 SQFT enclosed area directly adjacent to X-Ray outfeed.

                        GENERATE A STRUCTURED AUDIT REPORT IN MARKDOWN:
                        
                        ### 📊 1. Key Metrics & Extracted Specifications
                        - Estimated Carpet / Processing Area (if visible on title block/labels)
                        - Estimated Staging Grid Capacity & Dock Count
                        - Space Utilization Score (0-100%)
                        - Overall Layout Efficiency Rating (Pass / Needs Revision / Critical Re-design)

                        ### 🚨 2. Critical Bottlenecks & Rule Violations
                        - Highlight exact flow collisions, missing pathway widths, TBC clearance breaches, or staging bottlenecks.

                        ### 🔄 3. Reverse Logistics & Security Audit
                        - Detailed check of the Bag-by-Bag -> X-Ray / FSM -> PTL workflow compliance.

                        ### 🛠️ 4. Actionable Engineering Recommendations
                        - Provide a numbered step-by-step modification guide for the draft layout.
                        """

                        response = client.models.generate_content(
                            model='gemini-2.5-flash',
                            contents=[img, system_prompt]
                        )
                        
                        st.markdown(response.text)
                        
                    except Exception as e:
                        st.error(f"Error analyzing blueprint: {e}")
else:
    st.info("👈 Please upload a PDF or image of your facility layout drawing to begin.")