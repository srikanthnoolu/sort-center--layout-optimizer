import streamlit as st
import fitz  # PyMuPDF
from PIL import Image, ImageDraw
import io
import json
import re
import time
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

    colors = [
        "#FF3333",  # Red - Violations / Bottlenecks
        "#FF9900",  # Orange - Buffers & Clearances
        "#3399FF",  # Blue - Pathways & Transit Nodes
        "#33CC33",  # Green - Compliance & Correct Zones
        "#9933FF"   # Purple - Specialized Streams
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
            
            for offset in range(4):
                draw.rectangle(
                    [left - offset, top - offset, right + offset, bottom + offset], 
                    outline=color
                )
            
            draw.rectangle([left, top, min(left + 220, right), top + 28], fill=color)
            draw.text((left + 6, top + 6), f"#{idx+1}: {label}", fill="#FFFFFF")

    return annotated_img

# =========================================================
# HELPER FUNCTION: API CALL WITH RETRY AND MODEL FALLBACK
# =========================================================
def generate_content_with_retry(client, contents):
    """Retries API call on 503/429 errors and falls back to alternate models if needed."""
    candidate_models = ["gemini-3.5-flash", "gemini-1.5-flash"]
    last_exception = None

    for model_name in candidate_models:
        for attempt in range(3):  # Retry up to 3 times per model
            try:
                response = client.models.generate_content(
                    model=model_name,
                    contents=contents
                )
                return response
            except Exception as e:
                last_exception = e
                err_msg = str(e)
                # Check for rate limit or server capacity issues (503, 429)
                if "503" in err_msg or "UNAVAILABLE" in err_msg or "429" in err_msg or "RESOURCE_EXHAUSTED" in err_msg:
                    time.sleep(2 * (attempt + 1))  # Exponential wait: 2s, 4s, 6s
                    continue
                else:
                    raise e  # Fail immediately on authentication or non-transient errors

    raise last_exception

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

        image_container = st.container()

        if st.button("🚀 Run Visual Layout Audit", type="primary"):
            if not api_key:
                st.error("Please enter your Gemini API Key in the sidebar.")
            else:
                with st.spinner("Analyzing layout spatial coordinates and generating visual report (auto-retrying if servers are busy)..."):
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
                        Return a JSON object with:
                        1. "highlights": List of up to 5 spatial locations for bottlenecks, TBC violations, vertical node congestion, or reverse flow areas.
                           Each item MUST have:
                           - "box_2d": [ymin, xmin, ymax, xmax] normalized on a 0-1000 scale.
                           - "label": Short 2-4 word description (e.g. "TBC Buffer Breach", "Reverse Bag Area").
                        2. "report_markdown": Standard Markdown string covering Key Metrics, Bottlenecks, Reverse Flow Analysis, and Recommendations.

                        Ensure all newlines inside string values are properly escaped as \\n.
                        """

                        # Call API with backoff & fallback
                        response = generate_content_with_retry(
                            client=client,
                            contents=[img, system_prompt]
                        )
                        
                        raw_text = response.text.strip()
                        
                        # Clean markdown code fence wrappers
                        cleaned_json = re.sub(r"^```(?:json)?\s*", "", raw_text, flags=re.IGNORECASE | re.MULTILINE)
                        cleaned_json = re.sub(r"\s*```$", "", cleaned_json, flags=re.MULTILINE).strip()

                        # Parse JSON non-strictly
                        try:
                            data = json.loads(cleaned_json, strict=False)
                            highlights = data.get("highlights", [])
                            markdown_report = data.get("report_markdown", raw_text)
                        except Exception:
                            highlights = []
                            markdown_report = raw_text

                        annotated_img = annotate_layout_image(img, highlights) if highlights else img

                        with image_container:
                            col1, col2 = st.columns([1, 1])
                            with col1:
                                st.subheader("🖼️ Visual Highlights")
                                st.image(annotated_img, use_container_width=True)
                            with col2:
                                st.subheader("📋 Original Layout")
                                st.image(img, use_container_width=True)

                        st.markdown("---")
                        st.subheader("📊 Engineering Audit Report")
                        st.markdown(markdown_report)

                    except Exception as e:
                        st.error(f"Server is currently overloaded. Please wait 10 seconds and click 'Run Visual Layout Audit' again. Details: {e}")

    except Exception as e:
        st.error(f"Error loading uploaded layout file: {e}")