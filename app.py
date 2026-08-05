import streamlit as st
import fitz  # PyMuPDF
from PIL import Image, ImageDraw, ImageFont
import io
import json
import re
from google import genai

# Streamlit Page Config
st.set_page_config(
    page_title="Sort Center Layout Optimizer & Visual Auditor",
    layout="wide",
    page_icon="📦"
)

st.title("📦 AI-Powered Sort Center Layout & Visual Compliance Auditor")
st.caption("Automated industrial engineering CAD/PDF auditor with visual spatial highlighting")

# =========================================================
# HELPER FUNCTION: DRAW ANNOTATIONS & BOUNDING BOXES
# =========================================================
def annotate_layout_image(image, highlights):
    """Draws visual bounding boxes, highlight zones, and callout tags on the layout image."""
    annotated_img = image.copy()
    draw = ImageDraw.Draw(annotated_img)
    w, h = image.size

    # Color palette for highlights
    colors = [
        "#FF3333",  # Red - Violations / Heavy Bottlenecks
        "#FF9900",  # Orange - Buffers & Clearances
        "#3399FF",  # Blue - Pathways & Transit Nodes
        "#33CC33",  # Green - Compliance & Correct Zones
        "#9933FF"   # Purple - Specialized Streams (Reverse/Volumetric)
    ]

    for idx, item in enumerate(highlights):
        box = item.get("box_2d", [])  # Expected [ymin, xmin, ymax, xmax] in 0-1000 scale
        label = item.get("label", f"Zone #{idx+1}")
        
        if len(box) == 4:
            ymin, xmin, ymax, xmax = box
            left = int((xmin / 1000.0) * w)
            top = int((ymin / 1000.0) * h)
            right = int((xmax / 1000.0) * w)
            bottom = int((ymax / 1000.0) * h)

            color = colors[idx % len(colors)]
            
            # Draw thick bounding box (4px width)
            for offset in range(4):
                draw.rectangle(
                    [left - offset, top - offset, right + offset, bottom + offset], 
                    outline=color
                )
            
            # Draw callout banner box
            banner_height = 28
            draw.rectangle([left, top, min(left + 220, right), top + banner_height], fill=color)
            
            # Draw label text
            draw.text((left + 6, top + 6), f"#{idx+1}: {label}", fill="#FFFFFF")

    return annotated_img

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
        file_bytes = uploaded_file.getvalue()
        
        if uploaded_file.name.lower().endswith(".pdf"):
            doc = fitz.open(stream=file_bytes, filetype="pdf")
            page = doc[0]
            pix = page.get_pixmap(dpi=200)
            img = Image.open(io.BytesIO(pix.tobytes("png")))
        else:
            img = Image.open(io.BytesIO(file_bytes))

        # Placeholder container for layout comparison
        image_container = st.container()

        if st.button("🚀 Run Visual Layout Audit", type="primary"):
            if not api_key:
                st.error("Please enter your Gemini API Key in the sidebar.")
            else:
                with st.spinner("Analyzing layout spatial coordinates and generating visual report..."):
                    try:
                        client = genai.Client(api_key=api_key)
                        
                        system_prompt = f"""
                        You are a Senior Supply Chain Industrial Engineer auditing a warehouse layout drawing.
                        
                        FACILITY CONTEXT: {facility_type} ({building_levels})
                        ACTIVE STREAMS: Smalls ({b2c_smalls}), Volumetric ({b2c_volumetric}), Large ({b2c_large}), B2B ({b2b_stream}), Reverse ({reverse_stream}).
                        
                        EVALUATE THE DIAGRAM AGAINST THESE OPERATIONAL RULES:
                        1. REVERSE LOGISTICS: Inbound Reverse -> Bag-by-Bag -> Dual Split (8ft pathway to X-Ray/FSM vs Direct FSM) -> Secondary PTL.
                        2. DOCK CLEARANCES: TBC 32ft trucks require 20 FT clear depth behind dock doors.
                        3. AISLES: 10 FT Bag pathways, 8 FT Shipment pathways, 10 FT Heavy HPT Highways.
                        4. STAGING & VERTICAL NODES: 7x7 FT grids with 10 FT cross-aisles every 6-10 grids; 15x15 FT landing grids at vertical lifts.

                        IMPORTANT INSTRUCTION:
                        Return a valid JSON object containing:
                        1. "highlights": A list of up to 5 spatial locations corresponding to bottlenecks, TBC violations, vertical node congestion, or reverse flow areas.
                           Each item MUST have:
                           - "box_2d": [ymin, xmin, ymax, xmax] normalized on a 0-1000 scale.
                           - "label": A short 2-4 word description (e.g. "TBC Buffer Breach", "Reverse Bag Processing", "Elevator Landing Grid").
                        2. "report_markdown": A comprehensive markdown report covering Key Metrics, Critical Bottlenecks, Reverse Flow Analysis, and Actionable Recommendations.

                        OUTPUT FORMAT: Return ONLY raw JSON without additional conversational text.
                        """

                        response = client.models.generate_content(
                            model='gemini-3.5-flash',
                            contents=[img, system_prompt]
                        )
                        
                        # Parse JSON response
                        raw_text = response.text.strip()
                        # Clean code fence blocks if present
                        cleaned_json = re.sub(r"^```json\s*|\s*```$", "", raw_text, flags=re.MULTILINE)
                        
                        data = json.loads(cleaned_json)
                        highlights = data.get("highlights", [])
                        markdown_report = data.get("report_markdown", raw_text)

                        # Annotate image with visual boxes
                        annotated_img = annotate_layout_image(img, highlights)

                        # Render visual image comparison and report
                        with image_container:
                            col1, col2 = st.columns([1, 1])
                            with col1:
                                st.subheader("🖼️ Annotated Layout (Visual Highlights)")
                                st.image(annotated_img, use_container_width=True)
                            with col2:
                                st.subheader("📋 Original Blueprint")
                                st.image(img, use_container_width=True)

                        st.markdown("---")
                        st.subheader("📊 Engineering Audit Report")
                        st.markdown(markdown_report)

                    except Exception as e:
                        st.error(f"Audit processing error: {e}")
                        # Fallback to direct image rendering if JSON parsing fails
                        with image_container:
                            st.image(img, use_container_width=True)

    except Exception as e:
        st.error(f"Error loading uploaded layout file: {e}")