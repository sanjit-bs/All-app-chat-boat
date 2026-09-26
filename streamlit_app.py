import streamlit as st
from streamlit_gsheets import GSheetsConnection
import gspread
import pandas as pd
# from openai import OpenAI
from google import genai

st.set_page_config(page_title="Dynamic Sheets Chatbot", layout="wide")
st.title("📊 Dynamic Multi-Sheet Chatbot")

# Initialize the Gemini client using st.secrets
client = genai.Client(api_key=st.secrets["GEMINI_API_KEY"])

# Generate text response
response = client.models.generate_content(
    model="gemini-2.0-flash",
    contents="Explain how to analyze data in Streamlit."
)

# 2. Fetch All Tab Names Dynamically via gspread
@st.cache_data(ttl=600)
def get_all_sheet_names():
    # Re-use service account credentials defined under [connections.gsheets]
    creds = st.secrets["connections"]["gsheets"]["service_account_info"]
    spreadsheet_url = st.secrets["connections"]["gsheets"]["spreadsheet"]
    
    # Authenticate gspread client
    gc = gspread.service_account_from_dict(creds)
    sh = gc.open_by_url(spreadsheet_url)
    
    # Return list of all tab titles
    return [sheet.title for sheet in sh.worksheets()]

# 3. Load Data from Every Tab
@st.cache_data(ttl=300)
def load_all_sheet_data(tab_names):
    all_data = {}
    for tab in tab_names:
        all_data[tab] = conn.read(worksheet=tab)
    return all_data

# Fetch tabs dynamically
tabs = get_all_sheet_names()
sheets_dict = load_all_sheet_data(tabs)

# Sidebar Viewer
with st.sidebar:
    st.header(f"Workbook Tabs ({len(tabs)})")
    selected_tab = st.selectbox("Inspect sheet:", tabs)
    st.dataframe(sheets_dict[selected_tab].head(10))

# 4. Context Builder
def build_dataset_context(data_dict):
    context = "You are an assistant with access to a Google Sheet containing the following tabs:\n\n"
    for tab_name, df in data_dict.items():
        context += f"=== TAB: {tab_name} ===\n"
        context += df.to_csv(index=False) + "\n\n"
    return context

# 5. Initialize Chat History
if "messages" not in st.session_state:
    st.session_state.messages = [
        {"role": "system", "content": build_dataset_context(sheets_dict)}
    ]

# 6. Render Messages
for msg in st.session_state.messages:
    if msg["role"] != "system":
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])

# 7. Handle User Chat Input
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
