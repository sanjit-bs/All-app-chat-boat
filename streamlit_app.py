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

# 3. Fetch All Tab Names Dynamically
@st.cache_data(ttl=600)
def get_all_sheet_names():
    sh = gc.open_by_url(spreadsheet_url)
    return [sheet.title for sheet in sh.worksheets()]

# 4. Load Data from Every Tab using gspread (Fixes HTTP 400 Bad Request)
@st.cache_data(ttl=300)
def load_all_sheet_data(tab_names):
    sh = gc.open_by_url(spreadsheet_url)
    all_data = {}
    for tab in tab_names:
        worksheet = sh.worksheet(tab)
        records = worksheet.get_all_records()
        all_data[tab] = pd.DataFrame(records)
    return all_data

# Fetch tabs & load datasets
tabs = get_all_sheet_names()
sheets_dict = load_all_sheet_data(tabs)

# Sidebar Viewer
with st.sidebar:
    st.header(f"Workbook Tabs ({len(tabs)})")
    selected_tab = st.selectbox("Inspect sheet:", tabs)
    st.dataframe(sheets_dict[selected_tab].head(10))

# 5. Context Builder for System Prompt
def build_dataset_context(data_dict):
    context = "You are an assistant with access to a Google Sheet containing the following tabs:\n\n"
    for tab_name, df in data_dict.items():
        context += f"=== TAB: {tab_name} ===\n"
        # Convert first 50 rows per tab to CSV string to avoid token limit errors
        context += df.head(50).to_csv(index=False) + "\n\n"
    return context

# 6. Initialize Chat History
if "messages" not in st.session_state:
    st.session_state.messages = [
        {"role": "system", "content": build_dataset_context(sheets_dict)}
    ]

# 7. Render Messages
for msg in st.session_state.messages:
    if msg["role"] != "system":
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])

# 8. Handle User Chat Input
if prompt := st.chat_input("Ask anything across any tab..."):
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
