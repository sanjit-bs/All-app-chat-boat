import streamlit as st
import gspread
import pandas as pd
from openai import OpenAI

st.set_page_config(page_title="Dynamic Sheets Chatbot", layout="wide")
st.title("📊 Dynamic Multi-Sheet Chatbot")

# 1. Initialize OpenAI Client
client = OpenAI(api_key=st.secrets["OPENAI_API_KEY"])

# 2. Authenticate gspread Client directly from Secrets
@st.cache_resource
def get_gspread_client():
    creds = st.secrets["connections"]["gsheets"]["service_account_info"]
    return gspread.service_account_from_dict(creds)

gc = get_gspread_client()
spreadsheet_url = st.secrets["connections"]["gsheets"]["spreadsheet"]

# 3. Fetch All Available Tab Names Dynamically
@st.cache_data(ttl=600)
def get_all_sheet_names():
    sh = gc.open_by_url(spreadsheet_url)
    return [sheet.title for sheet in sh.worksheets()]

# 4. Safe Row Reader (Handles duplicate dates/headers safely)
@st.cache_data(ttl=300)
def load_selected_sheet_data(tab_names):
    sh = gc.open_by_url(spreadsheet_url)
    data_dict = {}
    
    for tab in tab_names:
        worksheet = sh.worksheet(tab)
        # Fetch raw rows to bypass header/duplicate errors
        rows = worksheet.get_all_values()
        
        if rows:
            headers = rows[0]
            values = rows[1:]
            df = pd.DataFrame(values, columns=headers)
        else:
            df = pd.DataFrame()
            
        data_dict[tab] = df
        
    return data_dict

# Step A: Get all sheet names from the Google Spreadsheet
all_tabs = get_all_sheet_names()

# Sidebar: Allow user to select specific sheets to target
with st.sidebar:
    st.header("🎯 Target Selection")
    
    # User selects which specific sheets the chatbot should work on
    active_tabs = st.multiselect(
        "Select sheet(s) for chatbot context:",
        options=all_tabs,
        default=[all_tabs[0]] if all_tabs else []
    )
    
    # Optional Data Inspector
    if active_tabs:
        inspect_tab = st.selectbox("Inspect sheet content:", active_tabs)
        sheets_preview = load_selected_sheet_data([inspect_tab])
        st.dataframe(sheets_preview[inspect_tab].head(10))

# Fetch data ONLY for the selected sheets
if active_tabs:
    sheets_dict = load_selected_sheet_data(active_tabs)
else:
    sheets_dict = {}
    st.warning("Please select at least one sheet in the sidebar to start chatting.")

# 5. Context Builder (Feeds only selected sheets to the LLM)
def build_dataset_context(data_dict):
    context = "You are an assistant. You are currently analyzing ONLY the following selected sheet tabs:\n\n"
    for tab_name, df in data_dict.items():
        context += f"=== TAB NAME: {tab_name} ===\n"
        # Convert first 50 rows of data to CSV string format
        context += df.head(50).to_csv(index=False) + "\n\n"
    return context

# 6. Initialize Chat History & Reset if active tabs change
if "active_tabs_cache" not in st.session_state or st.session_state.active_tabs_cache != active_tabs:
    st.session_state.active_tabs_cache = active_tabs
    st.session_state.messages = [
        {"role": "system", "content": build_dataset_context(sheets_dict)}
    ]

# 7. Render Chat Messages
for msg in st.session_state.messages:
    if msg["role"] != "system":
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])

# 8. Handle User Chat Input
if prompt := st.chat_input("Ask anything about the selected sheet(s)..."):
    if not active_tabs:
        st.error("Please select a sheet from the sidebar first!")
    else:
        st.chat_message("user").markdown(prompt)
        st.session_state.messages.append({"role": "user", "content": prompt})

        with st.chat_message("assistant"):
            response = client.chat.completions.create(
                model="gpt-4o-mini",
                messages=st.session_state.messages
            )
            reply = response.choices[0].message.content
            st.markdown(reply)

        st.session_state.messages.append({"role": "assistant", "content": reply})
