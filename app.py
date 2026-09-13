import os
import streamlit as st
import pandas as pd
from groq import Groq

# Page configuration
st.set_page_config(
    page_title="Property BOQ & Rate Library Manager",
    page_icon="🏗️",
    layout="wide"
)

# Initialize Groq client
GROQ_API_KEY = os.environ.get("GROQ_API_KEY") or st.secrets.get("GROQ_API_KEY", "")

@st.cache_resource
def get_groq_client(api_key):
    if not api_key:
        return None
    return Groq(api_key=api_key)

client = get_groq_client(GROQ_API_KEY)

# Initialize Session State Data (Simulating PostgreSQL tables)
if "rate_library" not in st.session_state:
    st.session_state.rate_library = pd.DataFrame([
        {
            "item_id": "RL-101",
            "csi_code": "09 29 00",
            "description": "Gypsum Board Finish (5/8 inch)",
            "unit_of_measure": "sq_ft",
            "base_material_rate": 2.50,
            "base_labor_rate": 3.75
        },
        {
            "item_id": "RL-102",
            "csi_code": "09 30 00",
            "description": "Porcelain Floor Tile (12x12 inch)",
            "unit_of_measure": "sq_ft",
            "base_material_rate": 5.20,
            "base_labor_rate": 6.50
        },
        {
            "item_id": "RL-103",
            "csi_code": "09 91 00",
            "description": "Interior Acrylic Latex Painting",
            "unit_of_measure": "sq_ft",
            "base_material_rate": 0.80,
            "base_labor_rate": 1.20
        }
    ])

if "boq_items" not in st.session_state:
    st.session_state.boq_items = pd.DataFrame(columns=[
        "line_item_id", "csi_code", "description", "quantity", 
        "unit_of_measure", "waste_factor", "applied_material_rate", 
        "applied_labor_rate", "total_line_cost"
    ])

# UI Layout Header
st.title("🏗️ Automated Property BOQ Engine")
st.caption("Powered by Groq API (Qwen / Llama OSS Models) & Streamlit")

# Sidebar: Configuration & Groq Setup
with st.sidebar:
    st.header("⚙️ Configuration")
    if not GROQ_API_KEY:
        GROQ_API_KEY = st.text_input("Enter Groq API Key:", type="password")
        if GROQ_API_KEY:
            client = get_groq_client(GROQ_API_KEY)
            
    selected_model = st.selectbox(
        "Groq Model:",
        [
            "qwen-2.5-coder-32b",
            "llama-3.3-70b-versatile",
            "deepseek-r1-distill-llama-70b"
        ],
        help="Select the open-weight LLM for parsing property scope and generating BOQ lines."
    )
    
    st.divider()
    st.subheader("🏢 Property Context")
    property_name = st.text_input("Property Name:", "Sunset Heights Complex")
    unit_number = st.text_input("Unit / Scope:", "Unit 4B - Full Bathroom Rehab")

# Main Content Tabs
tab_boq, tab_ai, tab_rates = st.tabs(["📋 Active BOQ Workspace", "🤖 AI Scope Parser", "📚 Rate Library"])

# TAB 1: BOQ WORKSPACE
with tab_boq:
    st.subheader(f"BOQ Schedule: {property_name} ({unit_number})")
    
    if st.session_state.boq_items.empty:
        st.info("No line items added yet. Add items manually below or use the AI Scope Parser.")
    else:
        edited_df = st.data_editor(
            st.session_state.boq_items,
            num_rows="dynamic",
            use_container_width=True,
            column_config={
                "quantity": st.column_config.NumberColumn(min_value=0, format="%.2f"),
                "waste_factor": st.column_config.NumberColumn(min_value=0, max_value=100, format="%.1f%%"),
                "applied_material_rate": st.column_config.NumberColumn(format="$%.2f"),
                "applied_labor_rate": st.column_config.NumberColumn(format="$%.2f"),
                "total_line_cost": st.column_config.NumberColumn(format="$%.2f", disabled=True),
            }
        )
        
        # Recalculate totals dynamically
        if not edited_df.empty:
            total_qty = edited_df["quantity"] * (1 + (edited_df["waste_factor"] / 100))
            edited_df["total_line_cost"] = total_qty * (edited_df["applied_material_rate"] + edited_df["applied_labor_rate"])
            st.session_state.boq_items = edited_df

        # Aggregations & Metrics
        col1, col2, col3 = st.columns(3)
        total_mat = (total_qty * edited_df["applied_material_rate"]).sum()
        total_lab = (total_qty * edited_df["applied_labor_rate"]).sum()
        grand_total = edited_df["total_line_cost"].sum()

        col1.metric("Total Material Cost", f"${total_mat:,.2f}")
        col2.metric("Total Labor Cost", f"${total_lab:,.2f}")
        col3.metric("Grand Total BOQ Value", f"${grand_total:,.2f}")

    st.divider()
    st.subheader("➕ Add Line Item from Master Catalog")
    
    c1, c2, c3, c4 = st.columns([3, 1, 1, 1])
    selected_catalog_item = c1.selectbox(
        "Select Rate Library Item:",
        st.session_state.rate_library["description"].tolist()
    )
    input_qty = c2.number_input("Quantity:", min_value=1.0, value=100.0)
    input_waste = c3.number_input("Waste %:", min_value=0.0, max_value=50.0, value=10.0)
    
    if c4.button("Add to BOQ", use_container_width=True):
        rate_row = st.session_state.rate_library[
            st.session_state.rate_library["description"] == selected_catalog_item
        ].iloc[0]
        
        total_line = (input_qty * (1 + input_waste/100)) * (rate_row["base_material_rate"] + rate_row["base_labor_rate"])
        
        new_row = pd.DataFrame([{
            "line_item_id": f"LINE-{len(st.session_state.boq_items) + 1:03d}",
            "csi_code": rate_row["csi_code"],
            "description": rate_row["description"],
            "quantity": input_qty,
            "unit_of_measure": rate_row["unit_of_measure"],
            "waste_factor": input_waste,
            "applied_material_rate": rate_row["base_material_rate"],
            "applied_labor_rate": rate_row["base_labor_rate"],
            "total_line_cost": total_line
        }])
        
        st.session_state.boq_items = pd.concat([st.session_state.boq_items, new_row], ignore_index=True)
        st.rerun()

# TAB 2: AI SCOPE PARSER (GROQ INTEGRATION)
with tab_ai:
    st.subheader("🤖 Convert Unstructured Inspection Notes to Structured BOQ")
    st.markdown("Paste field inspection notes or renovation requests below. The selected LLM will extract measurements, CSI codes, and matching scope.")

    sample_text = "Bathroom scope: Replace 150 sq ft of wall tile with porcelain tile. Needs complete repainting for 300 sq ft wall area including drywall repairs."
    scope_input = st.text_area("Scope Description / Site Inspection Notes:", value=sample_text, height=120)

    if st.button("Generate BOQ via Groq API", type="primary"):
        if not client:
            st.error("Please provide a valid Groq API key in the sidebar or via secrets.")
        else:
            with st.spinner(f"Analyzing scope using `{selected_model}`..."):
                prompt = f"""
                You are a senior real estate quantity surveyor. 
                Extract line items from this scope description: "{scope_input}"
                
                Match items against this available catalog:
                {st.session_state.rate_library.to_json(orient='records')}
                
                Output ONLY a JSON array with objects containing:
                - "description": matching description from catalog or reasonable match
                - "csi_code": corresponding CSI MasterFormat code
                - "quantity": extracted numerical quantity
                - "unit_of_measure": unit extracted
                - "waste_factor": suggested waste percentage (default 10)
                """
                
                try:
                    completion = client.chat.completions.create(
                        model=selected_model,
                        messages=[{"role": "user", "content": prompt}],
                        temperature=0.1,
                        response_format={"type": "json_object"}
                    )
                    
                    st.subheader("Parsed AI Recommendation")
                    st.json(completion.choices[0].message.content)
                    st.success("Scope parsed successfully! You can now apply these recommendations to the active BOQ tab.")
                except Exception as e:
                    st.error(f"Error calling Groq API: {str(e)}")

# TAB 3: RATE LIBRARY MANAGEMENT
with tab_rates:
    st.subheader("📚 Master Cost Rate Library")
    st.markdown("Centralized catalog storing base material and labor rates.")
    
    st.dataframe(st.session_state.rate_library, use_container_width=True)
    
    with st.expander("➕ Add New Master Rate Item"):
        r_csi = st.text_input("CSI Code:", "06 10 00")
        r_desc = st.text_input("Description:", "Rough Carpentry Framing")
        r_unit = st.selectbox("Unit:", ["sq_ft", "sq_m", "linear_ft", "hours", "lump_sum"])
        r_mat = st.number_input("Base Material Rate ($):", min_value=0.0, value=12.0)
        r_lab = st.number_input("Base Labor Rate ($):", min_value=0.0, value=18.0)
        
        if st.button("Save to Rate Library"):
            new_catalog_entry = pd.DataFrame([{
                "item_id": f"RL-{len(st.session_state.rate_library) + 101}",
                "csi_code": r_csi,
                "description": r_desc,
                "unit_of_measure": r_unit,
                "base_material_rate": r_mat,
                "base_labor_rate": r_lab
            }])
            st.session_state.rate_library = pd.concat([st.session_state.rate_library, new_catalog_entry], ignore_index=True)
            st.success(f"Added '{r_desc}' to Rate Library!")
            st.rerun()