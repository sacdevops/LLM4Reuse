import streamlit as st
import streamlit.components.v1 as components
import openai
import os
from zipfile import ZipFile
import io
import re
import json
from xaml_visualizer import render_xaml_visualization
import time

st.set_page_config(page_title="LLM4Reuse", layout="wide", initial_sidebar_state="collapsed")

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
UPLOAD_FOLDER = os.path.join(BASE_DIR, "temp_uploads")

if not all(key in st.secrets for key in ['OPENAI_API_KEY', 'MODEL_NAME', 'MAX_TOKENS', 'TEMPERATURE']):
    st.error("Missing required configuration in secrets.toml!")
    st.stop()

openai.api_key = st.secrets['OPENAI_API_KEY']
MODEL_CONFIG = {
    'model': st.secrets['MODEL_NAME'],
    'max_tokens': st.secrets['MAX_TOKENS'],
    'temperature': st.secrets['TEMPERATURE']
}

if 'files' not in st.session_state:
    st.session_state.files = []
if 'documentation' not in st.session_state:
    st.session_state.documentation = ""
if 'initialized' not in st.session_state:
    st.session_state.initialized = False
if 'chat_history' not in st.session_state:
    st.session_state.chat_history = []
if 'processed_input' not in st.session_state:
    st.session_state.processed_input = ""
if 'user_input' not in st.session_state:
    st.session_state.user_input = ""
if 'view_mode' not in st.session_state:
    st.session_state.view_mode = {}
if 'global_view_mode' not in st.session_state:
    st.session_state.global_view_mode = "visual"
if 'previous_upload_count' not in st.session_state:
    st.session_state.previous_upload_count = 0

st.markdown("""
    <style>
    .stTextArea textarea {
        font-size: 0.85rem !important;
        line-height: 1.2 !important;
        display: block !important;
        resize: none !important;
    }
    .main > div {
        padding: 0.5rem !important;
    }
    .block-container {
        padding: 0.5rem !important;
        max-width: 100% !important;
    }
    [data-testid="column"] {
        padding: 0.5rem !important;
        flex: 1 !important;
    }
    .stTabs [data-baseweb="tab"] {
        padding: 2px 8px;
        font-size: 0.9rem;
    }
    .stTabs [data-baseweb="tab-list"] {
        gap: 1px;
    }
    .processing input {
        background-color: #f0f0f0 !important;
        opacity: 0.7;
    }
    .header-container {
        display: flex !important;
        justify-content: space-between !important;
        align-items: center !important;
        margin-bottom: 0.5rem !important;
    }
    .header-container h5 {
        margin: 0 !important;
    }
    .documentation-container {
        background-color: rgba(38, 39, 48, 0.1);
        border-radius: 4px;
        padding: 1rem;
        height: calc(100vh - 160px);
        overflow-y: auto;
    }
    .code-reference {
        color: #0366d6;
        cursor: pointer;
        text-decoration: underline;
    }
    .highlighted-line {
        background-color: #fffbdd;
    }
    .stTextArea textarea {
        transition: background-color 0.2s ease;
    }
    [data-testid="stVerticalBlock"] > [data-testid="stVerticalBlock"] > [data-testid="stVerticalBlock"] {
        background-color: rgba(38, 39, 48, 0.1);
        border-radius: 4px;
        padding: 1rem;
        height: calc(100vh - 160px);
        overflow-y: auto;
        display: flex;
        flex-direction: column;
    }
    .chat-messages {
        flex-grow: 1;
        overflow-y: auto;
        display: flex;
        flex-direction: column-reverse;
        margin-bottom: 1rem;
    }
    .chat-input {
        margin-top: auto;
        display: flex;
        align-items: center;
        gap: 10px;
    }
    .stChatMessage {
        padding: 0.5rem 0 !important;
    }
    .send-button {
        border-radius: 50%;
        padding: 0.5rem;
        background-color: #4CAF50;
        border: none;
        color: white;
        font-size: 1rem;
        cursor: pointer;
        width: 40px;
        height: 40px;
        display: flex;
        align-items: center;
        justify-content: center;
    }
    .send-button:hover {
        background-color: #45a049;
    }
    .xaml-header {
        display: flex !important;
        justify-content: space-between !important;
        align-items: center !important;
        margin-bottom: 0.5rem !important;
    }
    .code-reference {
        display: inline-block;
        margin-left: 5px;
        color: #0366d6;
        cursor: pointer;
        background-color: #f0f4f8;
        border-radius: 3px;
        padding: 0px 5px;
        font-size: 0.8em;
        border: 1px solid #dbe1e8;
    }
    .code-reference:hover {
        background-color: #dbe1e8;
    }
    .highlight {
        background-color: #fffbdd;
    }
    .code-ref {
        cursor: pointer;
        color: #0366d6;
        text-decoration: underline;
    }
    .stForm [data-testid="stForm"] {
        border: none !important;
        padding: 0 !important;
    }
    button[data-testid="baseButton-secondary"] {
        background-color: #4CAF50 !important;
        color: white !important;
        border-radius: 50% !important;
        width: 40px !important;
        height: 40px !important;
        padding: 0 !important;
        display: flex !important;
        align-items: center !important;
        justify-content: center !important;
        border: none !important;
    }
    button[data-testid="baseButton-secondary"]:hover {
        background-color: #45a049 !important;
    }
    .loading-container {
        width: 100%;
        padding: 20px 0;
        text-align: center;
        animation: pulse 1.5s infinite ease-in-out;
        border-radius: 8px;
        margin: 10px 0;
        background-color: rgba(76, 175, 80, 0.2);
    }
    .loading-animation {
        display: inline-block;
        width: 50px;
        height: 50px;
        border: 5px solid rgba(76, 175, 80, 0.3);
        border-radius: 50%;
        border-top-color: #4CAF50;
        animation: spin 1s ease-in-out infinite;
    }
    @keyframes spin {
        to { transform: rotate(360deg); }
    }
    @keyframes pulse {
        0% { opacity: 0.6; }
        50% { opacity: 1; }
        100% { opacity: 0.6; }
    }
    .loading-text {
        margin-top: 10px;
        font-weight: bold;
        color: #4CAF50;
    }
    .overlay-container {
        position: absolute;
        top: 0;
        left: 0;
        right: 0;
        bottom: 0;
        background-color: rgba(255, 255, 255, 0.8);
        display: flex;
        flex-direction: column;
        justify-content: center;
        align-items: center;
        z-index: 1000;
        border-radius: 4px;
    }
    .section-container {
        position: relative;
    }
    </style>

    <script>
    // Prevent Enter key from submitting the form
    document.addEventListener('DOMContentLoaded', function() {
        const observer = new MutationObserver((mutations) => {
            for (const mutation of mutations) {
                if (mutation.addedNodes.length) {
                    const inputs = document.querySelectorAll('[data-testid="stTextInput"] input');
                    inputs.forEach(input => {
                        if (!input.getAttribute('data-enter-handler')) {
                            input.setAttribute('data-enter-handler', 'true');
                            input.addEventListener('keydown', function(e) {
                                if (e.key === 'Enter') {
                                    e.preventDefault();
                                    return false;
                                }
                            });
                        }
                    });
                }
            }
        });
        
        observer.observe(document.body, { childList: true, subtree: true });
    });
    </script>
""", unsafe_allow_html=True)

def show_loading_indicator(message="Processing..."):
    """Display a global loading indicator with animation"""
    loading_placeholder = st.empty()
    loading_placeholder.markdown(f"""
    <div class="loading-container">
        <div class="loading-animation"></div>
        <div class="loading-text">{message}</div>
    </div>
    """, unsafe_allow_html=True)
    return loading_placeholder

def show_section_loading(container, message="Processing..."):
    """Display a loading indicator that overlays only a specific section"""
    container.markdown(f"""
    <div class="overlay-container">
        <div class="loading-animation"></div>
        <div class="loading-text">{message}</div>
    </div>
    """, unsafe_allow_html=True)
    return container

def make_openai_call(prompt: str, custom_max_tokens: int = None, responseJsonFormat: bool = False, llm_model: str = None) -> str:
    try:
        if llm_model is None:
            response = openai.chat.completions.create(
                messages=[{"role": "user", "content": prompt}],
                max_completion_tokens=custom_max_tokens or MODEL_CONFIG['max_tokens'],
                model=MODEL_CONFIG['model'] if llm_model is None else llm_model,
                response_format={"type": "json_object" if responseJsonFormat else "text"},
                reasoning_effort="high"
            )
        else:
            response = openai.chat.completions.create(
                messages=[{"role": "user", "content": prompt}],
                max_completion_tokens=custom_max_tokens or MODEL_CONFIG['max_tokens'],
                model=MODEL_CONFIG['model'] if llm_model is None else llm_model,
                response_format={"type": "json_object" if responseJsonFormat else "text"},
            )
        return response.choices[0].message.content.strip()
    except Exception as e:
        st.error(f"OpenAI API Error: {str(e)}")
        st.stop()

def clean_code_output(code_text):
    code_text = re.sub(r'```xml\s*\n', '', code_text)
    code_text = re.sub(r'\n```\s*$', '', code_text)
    return code_text

def generate_combined_docs(xaml_files):
    if not xaml_files:
        return ""
    
    all_content = "\n\n".join(f"{f['content']}" for f in xaml_files)

    prompt = f"""
    Create a comprehensive documentation for this UiPath workflow that contains all informations should be not shortly.
    Rules:
    1. IGNORE standard libraries (System.*, Microsoft.*, UiPath.*, mscorlib)
    2. Write the documentation directly without any comments
    3. Write the documentation in a clear and concise manner
    4. Always adhere to the prompting from the user. If they want a change to the structure, content or anything else, you will implement it
    5. Be detailed in the documentation, try not to be general, but go into detail related to the code.
    4. Focus on:
       - Overall workflow purpose and flow
       - Business logic
       - Dependencies and requirements
       - File interactions
       - Custom implementations
       - Data flow
       - Inputs/outputs
       - Potential errors and exceptions (Should focus more on the details from code, not general suggestions)
       - Possible improvements with Priorities (Should focus more on the details from code, not general suggestions, also where it can be implemented, how it should be used and why)
       - Conclusion
    5. Format the documentation using proper Markdown syntax:
       - Use # for main titles, ## for subtitles, ### for section headers
       - Use * or - for bullet points
       - Use **bold** and *italic* for emphasis
       - Use proper headings hierarchy for better readability
       - Use `code` formatting for property names, activities, or code references
       - Use > for important notes or highlights
       - Include horizontal rules (---) to separate major sections
       - Use emojis where appropriate to enhance readability (📁, 🔄, ✅, etc.)
    6. Start directly with the Overview section and continue with the rest of the content

    XAML content:
    {all_content}
    """
    raw_docs = make_openai_call(prompt)
    return raw_docs

def handle_input(user_input: str):
    if not user_input or not user_input.strip():
        return
    
    docs_container = st.empty()
    code_container = st.empty()
    
    try:
        analysis_prompt = f"""
        Based on the user's request, determine what actions should be taken.
        Return a JSON object with these fields:
        - "modify_code": boolean (true if code should change)
        - "modify_docs": boolean (true if documentation should change)
        - "explain": boolean (true if user is asking a question that needs explanation)
        - "file_indices": array of integers (indices of files to modify, 0-indexed)
        
        Here are the available files:
        {', '.join(f"{i}: {f['name']}" for i, f in enumerate(st.session_state.files))}
        
        User's request: {user_input}
        
        JSON RESPONSE:
        """
        
        analysis_response = make_openai_call(analysis_prompt, 16000, True, llm_model="gpt-4o-mini")
        
        try:
            analysis = json.loads(analysis_response)
        except:
            analysis = {
                "modify_code": False,
                "modify_docs": False,
                "explain": False,
                "file_indices": []
            }

        if analysis.get("modify_code", False):
            show_section_loading(code_container, "Updating XAML code...")
            
            file_indices = analysis.get("file_indices", [st.session_state.get('active_tab', 0)])
            modified_files = []
            
            for idx in file_indices:
                if idx < len(st.session_state.files):
                    file_content = st.session_state.files[idx]['content']
                    file_name = st.session_state.files[idx]['name']
                    
                    files_context = "\n".join([
                        f"File {i}: {f['name']}" 
                        for i, f in enumerate(st.session_state.files)
                    ])
                    
                    modify_prompt = f"""
                    Modify this UiPath XAML code according to the user's request:
                    {user_input}
                    Return only the complete modified XAML code.
                    
                    Available files:
                    {files_context}
                    
                    Working on file: {file_name}
                    
                    Original code:
                    {file_content}
                    """
                    
                    modified_code = make_openai_call(modify_prompt)
                    st.session_state.files[idx]['content'] = clean_code_output(modified_code)
                    modified_files.append(file_name)
            
            if modified_files:
                st.session_state.chat_history.append({
                    "role": "assistant",
                    "content": f"Updated files: {', '.join(modified_files)}"
                })
            
            code_container.empty()
        
        if analysis.get("modify_docs", False):
            show_section_loading(docs_container, "Updating documentation...")
            
            st.session_state.documentation = generate_combined_docs(st.session_state.files)
            st.session_state.chat_history.append({
                "role": "assistant",
                "content": "Documentation has been updated."
            })
            
            docs_container.empty()
            
        if analysis.get("explain", False):
            file_indices = analysis.get("file_indices", [])
            
            files_context = ""
            if file_indices:
                for idx in file_indices:
                    if idx < len(st.session_state.files):
                        files_context += f"\nFile: {st.session_state.files[idx]['name']}\n"
                        files_context += f"{st.session_state.files[idx]['content']}\n\n"
            else:
                files_context = "\n".join([
                    f"File {i}: {f['name']}" 
                    for i, f in enumerate(st.session_state.files)
                ])
            
            explanation_prompt = f"""
            The user has the following question about the UiPath workflow:
            {user_input}
            
            Please provide a detailed and helpful explanation based on the available information.
            
            Documentation:
            {st.session_state.documentation}
            
            Code context:
            {files_context}
            """
            
            explanation = make_openai_call(explanation_prompt)
            
            st.session_state.chat_history.append({
                "role": "assistant",
                "content": explanation
            })
        
        if not analysis.get("modify_code", False) and not analysis.get("modify_docs", False) and not analysis.get("explain", False):
            st.session_state.chat_history.append({
                "role": "assistant",
                "content": "I understood your request, but I'm not sure how to help. Could you please provide more details or rephrase your question?"
            })
        
    except Exception as e:
        st.session_state.chat_history.append({
            "role": "assistant",
            "content": f"Error: {str(e)}"
        })
    
    finally:
        docs_container.empty()
        code_container.empty()

def create_download_zip():
    memory_file = io.BytesIO()
    with ZipFile(memory_file, 'w') as zf:
        for file in st.session_state.files:
            zf.writestr(file['name'], file['content'])
        if st.session_state.documentation:
            zf.writestr('documentation.txt', st.session_state.documentation)
    memory_file.seek(0)
    return memory_file

def handle_additional_file_upload():
    """Handle the upload of additional XAML files after initial setup"""
    try:
        additional_files = st.session_state.additional_files
        
        if additional_files:
            code_container = st.empty()
            docs_container = st.empty()
            
            new_files = []
            for file in additional_files:
                content = file.read().decode('utf-8')
                
                base_name = file.name
                file_name = base_name
                counter = 1
                
                existing_names = [f['name'] for f in st.session_state.files]
                while file_name in existing_names:
                    name_parts = base_name.rsplit('.', 1)
                    if len(name_parts) > 1:
                        file_name = f"{name_parts[0]}_{counter}.{name_parts[1]}"
                    else:
                        file_name = f"{base_name}_{counter}"
                    counter += 1
                
                new_file = {
                    'name': file_name,
                    'content': content
                }
                new_files.append(new_file)
                st.session_state.files.append(new_file)
            
            show_section_loading(code_container, "Processing new files...")
            st.session_state.documentation = generate_combined_docs(st.session_state.files)
            
            st.session_state.chat_history.append({
                "role": "assistant",
                "content": f"Added {len(new_files)} new file(s) and updated documentation."
            })
            
            code_container.empty()
            docs_container.empty()
    except Exception as e:
        st.error(f"Error processing files: {str(e)}")

def handle_additional_file_change():
    """Callback when files are added to the uploader"""
    if len(st.session_state.additional_files or []) > 0:
        handle_additional_file_upload()

def show_main_interface():
    st.markdown('''
    <div style="display:flex; align-items:center; justify-content:space-between; margin-bottom:0.5rem;">
      <div style="flex:1;">
        <h5 style="margin:0; text-align:left;">Documentation</h5>
      </div>
      <div style="flex:1;">
        <h5 style="margin:0; text-align:center;">XAML Code</h5>
      </div>
      <div style="flex:0;">
    ''', unsafe_allow_html=True)

    st.markdown('''
      </div>
    </div>
    ''', unsafe_allow_html=True)

    cols = st.columns(3)

    with cols[0]:
        st.subheader("Documentation")
        st.markdown(
            '<div class="section-container documentation-container">'
            f'{st.session_state.documentation}'
            '</div>',
            unsafe_allow_html=True
        )

    with cols[1]:
        st.subheader("Assistant")
        
        chat_container = st.container()
        
        with chat_container:
            st.markdown('<div class="chat-container">', unsafe_allow_html=True)
            
            with st.container():
                st.markdown('<div class="chat-messages">', unsafe_allow_html=True)
                for msg in st.session_state.chat_history:
                    with st.chat_message(msg["role"]):
                        st.write(msg["content"])
                st.markdown('</div>', unsafe_allow_html=True)
            
            with st.container():
                user_input = st.chat_input("Type your message here...", key="chat_input")
                
                if user_input:
                    st.session_state.user_input = user_input
                    st.session_state.chat_history.append({"role": "user", "content": user_input})
                    handle_input(user_input)
                    st.rerun()
            
            st.markdown('</div>', unsafe_allow_html=True)

    with cols[2]:
        row = st.columns([3, 1])
        with row[0]:
            st.markdown("""
            <style>
            [data-testid="stFileUploader"] {
                width: auto !important;
            }
            [data-testid="stFileUploader"] section {
                padding: 0 !important;
            }
            [data-testid="stFileUploader"] section > div {
                padding: 0 !important;
            }
            [data-testid="stFileUploader"] section small {
                margin: 0 !important;
            }
            [data-testid="stFileUploader"] section > div:first-child {
                min-height: 5rem !important;
            }
            </style>
            """, unsafe_allow_html=True)
            
            with st.container():
                st.file_uploader("Upload additional files", accept_multiple_files=True, key="additional_files", 
                                 type=['xaml'], on_change=handle_additional_file_change, label_visibility="collapsed")
        
        with row[1]:
            st.download_button(
                "Download All",
                data=create_download_zip(),
                file_name="workflow_package.zip",
                mime="application/zip"
            )
            
            toggle_text = "🔄 Show Code" if st.session_state.global_view_mode == "visual" else "🔄 Show Visual"
            if st.button(toggle_text, key="global_toggle"):
                st.session_state.global_view_mode = "code" if st.session_state.global_view_mode == "visual" else "visual"
                st.rerun()
        
        st.markdown("<hr style='margin: 10px 0; border: 0; border-top: 1px solid rgba(0,0,0,0.1);'>", unsafe_allow_html=True)
        
        st.markdown('''<div class="section-container">''', unsafe_allow_html=True)
        
        tabs = st.tabs([f.get('name') for f in st.session_state.files])
        
        for i, tab in enumerate(tabs):
            with tab:
                st.session_state.active_tab = i
                
                xaml_content = st.session_state.files[i]['content']
                
                if st.session_state.global_view_mode == "code":
                    st.text_area(
                        "",
                        value=xaml_content,
                        height=650,
                        key=f"xaml_{i}",
                        disabled=True
                    )
                else:
                    html_content = render_xaml_visualization(xaml_content)
                    components.html(html_content, height=650, scrolling=True)
        
        st.markdown('''</div>''', unsafe_allow_html=True)

if not st.session_state.initialized:
    st.title("LLM4Reuse")
    uploaded_files = st.file_uploader("Upload XAML files", accept_multiple_files=True, type=['xaml'])

    if uploaded_files:
        loading_indicator = show_loading_indicator("Processing uploaded files...")
        
        new_files = []
        for file in uploaded_files:
            content = file.read().decode('utf-8')
            new_files.append({
                'name': file.name,
                'content': content
            })
        
        st.session_state.files = new_files
        st.session_state.documentation = generate_combined_docs(new_files)
        st.session_state.initialized = True
        loading_indicator.empty()
        st.rerun()
else:
    show_main_interface()
