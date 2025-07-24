import streamlit as st
import pandas as pd
import itertools
from collections import Counter
from pulp import LpProblem, LpVariable, LpMaximize, lpSum, LpBinary, LpStatusOptimal
import io
from datetime import datetime
import json

# --- Google Sheets Feedback Integration ---
import gspread
from google.oauth2.service_account import Credentials

SHEET_ID = "1Bk3dhEUGiPbkmHR-ENiZD7SmpHTY0i4uyOZ6wYNkbZg"
TAB_NAME = "Sheet1"
CREDS_FILE = "gcreds.json"  # Use relative path for deployment

def append_feedback_to_gsheet(feedback_text):
    scope = [
        "https://www.googleapis.com/auth/spreadsheets",
        "https://www.googleapis.com/auth/drive"
    ]
    creds = Credentials.from_service_account_file(CREDS_FILE, scopes=scope)
    gc = gspread.authorize(creds)
    sh = gc.open_by_key(SHEET_ID)
    worksheet = sh.worksheet(TAB_NAME)
    worksheet.append_row([datetime.now().isoformat(), feedback_text])

# --- Constants ---
PART_BASE_VALUES = {
    'E': 1000, 'R4': 850, 'R3': 700, 'R2': 550, 'R1': 400,
    'R': 300, 'Y3': 200, 'Y2': 150, 'Y1': 100, 'Y': 50
}
MULTIPLIER_DATA = {
    0: 1.0, 1: 1.2, 2: 1.4, 4: 1.6, 6: 1.8, 9: 2.0, 12: 2.2, 16: 2.4,
    20: 2.6, 25: 2.8, 30: 3.0, 36: 3.2, 42: 3.4, 48: 3.6, 54: 3.8,
    60: 4.0, 66: 4.2, 72: 4.4, 78: 4.6, 84: 4.8, 90: 5.0
}
PARTS_PER_TB = 3

# --- Preset Templates ---
PRESETS = {
    "Default (empty)": {
        "parts": {k: 0 for k in PART_BASE_VALUES},
        "chips": 0,
        "num_tbs": 3,
        "min_reqs": [0, 0, 0]
    },
    "Sample 1": {
        "parts": {'E': 2, 'R4': 1, 'R3': 0, 'R2': 6, 'R1': 2, 'R': 2, 'Y3': 0, 'Y2': 0, 'Y1': 0, 'Y': 0},
        "chips": 23,
        "num_tbs": 3,
        "min_reqs": [4500, 3500, 3000]
    },
    "Sample 2": {
        "parts": {'E': 1, 'R4': 2, 'R3': 1, 'R2': 3, 'R1': 1, 'R': 1, 'Y3': 0, 'Y2': 0, 'Y1': 0, 'Y': 0},
        "chips": 15,
        "num_tbs": 2,
        "min_reqs": [3000, 2000]
    }
}

# --- Session State for Presets ---
if "preset" not in st.session_state:
    st.session_state.preset = "Default (empty)"
if "custom_presets" not in st.session_state:
    st.session_state.custom_presets = {}

# --- Title and Help ---
st.title("TB Resonance Optimizer")
st.markdown("Enter your available parts, total chips, and minimum resonance requirements for each TB. Click **Solve** to get the best configuration!")

with st.expander("ℹ️ FAQ / Help"):
    st.write("""
    - **What is this?**  
      This tool helps you find the best TB resonance configuration given your parts and constraints.
    - **How do I use it?**  
      Enter your available parts, chips, and minimum resonance for each TB, then click Solve.
    - **What if I get 'No valid configuration'?**  
      You may not have enough parts, chips, or your requirements are too high.
    - **What are Presets?**  
      Presets let you quickly load or save common setups.
    - **How is the result optimal?**  
      The app uses mathematical optimization to maximize total resonance.
    """)

# --- Preset Templates + Custom Presets ---
all_preset_names = list(PRESETS.keys()) + list(st.session_state.custom_presets.keys())
preset_choice = st.selectbox("Load a preset template:", all_preset_names, index=all_preset_names.index(st.session_state.preset))
if st.button("Load Preset"):
    st.session_state.preset = preset_choice

if preset_choice in PRESETS:
    preset = PRESETS[preset_choice]
else:
    preset = st.session_state.custom_presets[preset_choice]

NUM_TBS = st.number_input("Number of TBs", min_value=1, value=preset["num_tbs"], step=1, help="How many TBs to configure?")
total_chips_available = st.number_input("Total chips available", min_value=0, value=preset["chips"], step=1, help="Total chips you can use.")

st.subheader("Available Parts")
cols = st.columns(5)
available_parts_input = {}
for idx, part in enumerate(PART_BASE_VALUES):
    with cols[idx % 5]:
        default_val = preset["parts"].get(part, 0)
        available_parts_input[part] = st.number_input(f"{part}", min_value=0, value=default_val, step=1, key=f"part_{part}", help=f"How many {part} parts you have?")

st.subheader("Minimum resonance per TB")
min_reqs_per_tb = []
for i in range(NUM_TBS):
    default_val = preset["min_reqs"][i] if i < len(preset["min_reqs"]) else 0
    min_reqs_per_tb.append(st.number_input(f"TB {i+1} minimum resonance", min_value=0, value=default_val, step=1, key=f"minreq_{i}", help="Minimum resonance required for this TB."))

# --- Save/Load Custom Preset (Download/Upload) ---
with st.expander("⭐ Save/Load Custom Preset"):
    new_preset_name = st.text_input("Preset name", "")
    if st.button("Save as Custom Preset"):
        if new_preset_name.strip():
            preset_data = {
                "parts": available_parts_input.copy(),
                "chips": total_chips_available,
                "num_tbs": NUM_TBS,
                "min_reqs": min_reqs_per_tb.copy()
            }
            st.session_state.custom_presets[new_preset_name.strip()] = preset_data
            st.success(f"Preset '{new_preset_name.strip()}' saved! You can now download it below.")
            # Download button
            st.download_button(
                label="Download this preset as JSON",
                data=json.dumps(preset_data, indent=2),
                file_name=f"{new_preset_name.strip()}.json",
                mime="application/json"
            )
        else:
            st.warning("Please enter a name for your custom preset.")

    # Upload button
    uploaded_file = st.file_uploader("Upload a custom preset (JSON)", type="json")
    if uploaded_file is not None:
        try:
            preset_data = json.load(uploaded_file)
            st.session_state.custom_presets["Uploaded Preset"] = preset_data
            st.success("Preset uploaded! Select 'Uploaded Preset' from the preset list above.")
        except Exception as e:
            st.error(f"Failed to load preset: {e}")

# --- Input Validation ---
input_issues = []
if sum(available_parts_input.values()) < PARTS_PER_TB * NUM_TBS:
    input_issues.append("Not enough parts to fill all TBs.")
if total_chips_available < NUM_TBS:
    input_issues.append("Chips are very low; you may not be able to meet requirements.")
if any(x > sum(PART_BASE_VALUES[p] for p in PART_BASE_VALUES) * max(MULTIPLIER_DATA.values()) for x in min_reqs_per_tb):
    input_issues.append("One or more minimum resonance requirements are impossibly high.")

if input_issues:
    st.warning("⚠️ " + " ".join(input_issues))

# --- Solve Button ---
if st.button("Solve"):
    with st.spinner("Calculating..."):
        part_instance_list = []
        for part_type, count in available_parts_input.items():
            for _ in range(count):
                part_instance_list.append(part_type)
        N = len(part_instance_list)
        if input_issues:
            st.error("Please fix input issues before solving.")
        else:
            # Progress bar for combo generation
            progress = st.progress(0, text="Generating combinations...")
            combos = []
            total_combos = 0
            total_possible = max(1, len(list(itertools.combinations(range(N), PARTS_PER_TB))))
            for idxs in itertools.combinations(range(N), PARTS_PER_TB):
                parts = tuple(part_instance_list[i] for i in idxs)
                base = sum(PART_BASE_VALUES[p] for p in parts)
                for chips, mult in MULTIPLIER_DATA.items():
                    resonance = base * mult
                    combos.append({
                        'idxs': idxs,
                        'parts': parts,
                        'chips': chips,
                        'resonance': resonance
                    })
                total_combos += 1
                if total_combos % 100 == 0 or total_combos == total_possible:
                    progress.progress(min(1.0, total_combos / total_possible), text=f"Generated {total_combos} combos...")
            progress.empty()

            prob = LpProblem("TB_Resonance_Max", LpMaximize)
            x = {}
            for tb in range(NUM_TBS):
                for cidx, c in enumerate(combos):
                    if c['resonance'] >= min_reqs_per_tb[tb]:
                        x[(cidx, tb)] = LpVariable(f"x_{cidx}_{tb}", 0, 1, LpBinary)
            prob += lpSum(x[(cidx, tb)] * combos[cidx]['resonance'] for (cidx, tb) in x)
            for tb in range(NUM_TBS):
                prob += lpSum(x[(cidx, tb)] for (cidx, tb2) in x if tb2 == tb) == 1
            for i in range(N):
                prob += lpSum(x[(cidx, tb)] for (cidx, tb) in x if i in combos[cidx]['idxs']) <= 1
            prob += lpSum(x[(cidx, tb)] * combos[cidx]['chips'] for (cidx, tb) in x) <= total_chips_available
            status = prob.solve()
            explanation = ""
            if status == LpStatusOptimal:
                tb_configs = [None] * NUM_TBS
                for (cidx, tb), var in x.items():
                    if var.varValue > 0.5:
                        tb_configs[tb] = combos[cidx]
                st.success("Best Configuration Found!")
                data = []
                total_resonance_sum = 0
                for i, config in enumerate(tb_configs):
                    parts_string = ", ".join(config['parts'])
                    multiplier_value = MULTIPLIER_DATA[config['chips']]
                    data.append({
                        "TB": f"TB {i+1}",
                        "Parts Used": parts_string,
                        "Multiplier": f"{multiplier_value:.1f}x",
                        "Chips": config['chips'],
                        "Resonance": int(config['resonance'])
                    })
                    total_resonance_sum += config['resonance']
                df = pd.DataFrame(data)
                st.table(df)
                st.write(f"**Total Resonance:** {int(total_resonance_sum)}")
                explanation = (
                    "The configuration above is optimal because it maximizes the total resonance "
                    "while meeting all your constraints (parts, chips, and minimum resonance per TB). "
                    "No part is used more than once, and the chip limit is not exceeded."
                )
                # --- CSV with all input and output in table format ---
                output = io.StringIO()
                output.write("INPUTS\n")
                output.write("Parameter,Value\n")
                output.write(f"Number of TBs,{NUM_TBS}\n")
                output.write(f"Total chips available,{total_chips_available}\n")
                output.write("\nParts\nPart,Count\n")
                for k in PART_BASE_VALUES.keys():
                    output.write(f"{k},{available_parts_input[k]}\n")
                output.write("\nMinimum resonance per TB\nTB,Min Resonance\n")
                for i, val in enumerate(min_reqs_per_tb):
                    output.write(f"TB {i+1},{val}\n")
                output.write("\nOUTPUT\n")
                df.to_csv(output, index=False)
                output.write(f"\nTotal Resonance,,,{int(total_resonance_sum)}\n")
                st.download_button(
                    label="Download All (Inputs + Results) as CSV",
                    data=output.getvalue(),
                    file_name="tb_resonance_full_results.csv",
                    mime="text/csv"
                )
            else:
                st.error("No valid configuration found with the given parts and chips.")
                explanation = (
                    "No solution was found. This usually means you do not have enough parts, "
                    "chips, or your minimum resonance requirements are too high for the available resources. "
                    "Try lowering your requirements or increasing your available parts/chips."
                )
            with st.expander("📝 Result Explanation"):
                st.write(explanation)

# --- Feedback Form ---
st.markdown("---")
with st.expander("💬 Feedback / Report an Issue"):
    feedback = st.text_area("Your feedback or issue:", "")
    if st.button("Submit Feedback"):
        if feedback.strip():
            try:
                append_feedback_to_gsheet(feedback.strip())
                st.success("Thank you for your feedback! It has been sent.")
            except Exception as e:
                st.error(f"Failed to send feedback: {e}")
        else:
            st.warning("Please enter some feedback before submitting.")

st.caption("Created by Inzamam Khan (Ikhan) | Discord: inzamamkhan#1504 | [GitHub](https://github.com/Inzamam-khan123)")