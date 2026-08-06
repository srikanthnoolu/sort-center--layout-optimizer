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

st.title("📦 AI-Powered Sort Center Layout & Flow Auditor")
st.caption("Automated industrial engineering CAD/PDF auditor for Material/Man Movement and Happy/Non-Happy Flows")

# =========================================================
# HELPER FUNCTION: DRAW ANNOTATIONS & BOUNDING BOXES
# =========================================================
def annotate_layout_image(image, highlights):
    """Draws visual bounding boxes, highlight zones, and callout tags on the layout image."""
    annotated_img = image.copy()
    draw = ImageDraw.Draw(annotated_img)
    w, h = image.size

    colors = [
        "#FF3333",  # Red - Flow Conflict / Bottleneck
        "#FF9900",  # Orange - Man/Material Intersection
        "#3399FF",  # Blue - Happy Flow Node
        "#33CC33",  # Green - Compliance Area
        "#9933FF"   # Purple - Non-Happy / Exception Stream
    ]

    for idx, item in enumerate(highlights):
        box = item.get("box_2d", [])  # [ymin, xmin, ymax, xmax] in 0-1000 scale
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
            
            draw.rectangle([left, top, min(left + 240, right), top + 28], fill=color)
            draw.text((left + 6, top + 6), f"#{idx+1}: {label}", fill="#FFFFFF")

    return annotated_img

# =========================================================
# HELPER FUNCTION: API CALL WITH RETRY AND FALLBACK
# =========================================================
def generate_content_with_retry(client, contents):
    """Retries API call on transient errors and falls back to alternate models."""
    candidate_models = ["gemini-3.5-flash", "gemini-1.5-flash"]
    last_exception = None

    for model_name in candidate_models:
        for attempt in range(3):
            try:
                response = client.models.generate_content(
                    model=model_name,
                    contents=contents
                )
                return response
            except Exception as e:
                last_exception = e
                err_msg = str(e)
                if "503" in err_msg or "UNAVAILABLE" in err_msg or "429" in err_msg or "RESOURCE_EXHAUSTED" in err_msg:
                    time.sleep(2 * (attempt + 1))
                    continue
                else:
                    raise e

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
    b2c_smalls = st.checkbox("B2C Non-Large (Smalls & Bags)", value=True)
    b2c_volumetric = st.checkbox("B2C Volumetric / Semi-Large", value=True)
    b2c_large = st.checkbox("B2C Large / Heavy (Non-Conveyable)", value=True)
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

        if st.button("🚀 Run Flow & Layout Audit", type="primary"):
            if not api_key:
                st.error("Please enter your Gemini API Key in the sidebar.")
            else:
                with st.spinner("Auditing Material/Man Movement and Happy/Non-Happy Flows..."):
                    try:
                        client = genai.Client(api_key=api_key)
                        
                        system_prompt = f"""
                        You are a Senior Supply Chain Industrial Engineer auditing a warehouse layout drawing.
                        
                        FACILITY CONTEXT: {facility_type} ({building_levels})
                        ACTIVE STREAMS: Smalls ({b2c_smalls}), Volumetric ({b2c_volumetric}), Large ({b2c_large}), B2B ({b2b_stream}), Reverse ({reverse_stream}).
                        
                        EVALUATE THE BLUEPRINT AGAINST THESE PROCESS & FLOW RULES:

                        1. DOCK & BAG SORTATION (FORWARD FLOW):
                           - Inbound Non-Large/Smalls bags go directly from Unloading Docks to a Forward Bag Sortation & Debagging Area.
                           - TBC (Telescopic Conveyor) Docks require 20 FT clear depth behind dock doors.
                           - Non-Conveyable/Large items must bypass the Bag Sortation area directly upon unloading.

                        2. MATERIAL MOVEMENT (FORWARD vs EXCEPTION):
                           - Happy Flow: Inbound Dock -> Bag Sortation -> CBS Induction -> CBS Sorter -> Outbound Chutes -> Staging -> Outbound Dock.
                           - Non-Happy Flows: Check separation for No-Read/Reject Chutes, CBS Recirculation, and dedicated Reverse Logistics/Fraud Screening zones.
                           - Path Widths: Main Bag pathways >= 10 FT; Shipment pathways >= 8 FT; Heavy HPT highways >= 10 FT.

                        3. MAN (HUMAN) MOVEMENT & SAFETY:
                           - Pedestrian/operator walkways must NOT cross high-speed MHE or Forklift highways.
                           - Minimum 1.2m (4 FT) maintenance perimeter around CBS loop.
                           - Minimum 1.8m (6 FT) workstation depth for induction and bag-sorting operators.
                           - Crossover bridges with stairs must exist for any island isolated inside a sorter loop.

                        IMPORTANT INSTRUCTION:
                        Return a JSON object with:
                        1. "highlights": List of up to 5 spatial locations for Flow Violations, Man/Material Crossings, Chute Bottlenecks, or Incorrect Stream Merges.
                           Each item MUST have:
                           - "box_2d": [ymin, xmin, ymax, xmax] normalized on a 0-1000 scale.
                           - "label": Short 2-4 word description (e.g. "Man/Material Crossing", "Forward Bag Congestion", "Non-Happy Re-run Block").
                        2. "report_markdown": Standard Markdown string structured as follows:
                           - ## 1. Material Movement Analysis (Happy vs Non-Happy Path Continuity)
                           - ## 2. Man Movement & Ergonomics (Safety, Walkways, MHE Separation)
                           - ## 3. Forward Bag Sortation & CBS Integration Audit
                           - ## 4. Critical Flow Bottlenecks & Recommendations

                        Ensure all newlines inside string values are properly escaped as \\n.
                        """

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

                        # Save image to PNG byte buffer
                        img_byte_arr = io.BytesIO()
                        annotated_img.save(img_byte_arr, format='PNG')
                        annotated_bytes = img_byte_arr.getvalue()

                        with image_container:
                            col1, col2 = st.columns([1, 1])
                            with col1:
                                st.subheader("🖼️ Flow & Bottleneck Highlights")
                                st.image(annotated_img, use_container_width=True)
                                
                                st.download_button(
                                    label="📥 Download Annotated Layout",
                                    data=annotated_bytes,
                                    file_name="audited_flow_layout.png",
                                    mime="image/png",
                                    type="secondary",
                                    use_container_width=True
                                )
                                
                            with col2:
                                st.subheader("📋 Original Blueprint")
                                st.image(img, use_container_width=True)

                        st.markdown("---")
                        st.subheader("📊 Material & Man Movement Audit Report")
                        st.markdown(markdown_report)

                    except Exception as e:
                        st.error(f"Error during layout processing: {e}")

    except Exception as e:
        st.error(f"Error loading uploaded layout file: {e}")