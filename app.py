import streamlit as st
import streamlit.components.v1 as components
import openai
import os
from zipfile import ZipFile
import io
import re
import json
from xaml_visualizer import render_xaml_visualization

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
    4. Focus on:
       - Overall workflow purpose and flow
       - Dependencies and requirements
       - File interactions
       - Custom implementations
       - Business logic
       - Data flow
       - Inputs/outputs
       - and another relevant information based on the xaml code (Should focus more on the details from code, not general suggestions)
       - Potential errors and exceptions (Should focus more on the details from code, not general suggestions)
       - Possible improvements (Should focus more on the details from code, not general suggestions)
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
                "explain": False,  # Default to explanation if JSON parsing fails
                "file_indices": []
            }

        if analysis.get("modify_code", False):
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
        
        if analysis.get("modify_docs", False):
            st.session_state.documentation = generate_combined_docs(st.session_state.files)
            st.session_state.chat_history.append({
                "role": "assistant",
                "content": "Documentation has been updated."
            })
            
        if analysis.get("explain", False):
            # Generate an explanation based on the user's question
            file_indices = analysis.get("file_indices", [])
            
            # Prepare context for the explanation
            files_context = ""
            if file_indices:
                for idx in file_indices:
                    if idx < len(st.session_state.files):
                        files_context += f"\nFile: {st.session_state.files[idx]['name']}\n"
                        files_context += f"{st.session_state.files[idx]['content']}\n\n"
            else:
                # If no specific files are indicated, provide a summary of all files
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
        
        # If no actions were taken and no explanation was given, provide a default response
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

def create_download_zip():
    memory_file = io.BytesIO()
    with ZipFile(memory_file, 'w') as zf:
        for file in st.session_state.files:
            zf.writestr(file['name'], file['content'])
        if st.session_state.documentation:
            zf.writestr('documentation.txt', st.session_state.documentation)
    memory_file.seek(0)
    return memory_file

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
            '<div class="documentation-container">'
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
            st.subheader("XAML")
        with row[1]:
            st.download_button(
                "Download All",
                data=create_download_zip(),
                file_name="workflow_package.zip",
                mime="application/zip"
            )

        tabs = st.tabs([f.get('name') for f in st.session_state.files])
        for i, tab in enumerate(tabs):
            with tab:
                st.session_state.active_tab = i
                
                file_key = f"view_mode_{i}"
                
                if file_key not in st.session_state.view_mode:
                    st.session_state.view_mode[file_key] = "code"
                
                col1, col2 = st.columns([2, 1])
                with col2:
                    current_mode = st.session_state.view_mode[file_key]
                    toggle_text = "🔄 Visual" if current_mode == "code" else "🔄 Code"
                    
                    if st.button(toggle_text, key=f"toggle_{i}"):
                        st.session_state.view_mode[file_key] = "visual" if current_mode == "code" else "code"
                        st.rerun()
            
                if st.session_state.view_mode[file_key] == "code":
                    st.text_area(
                        "",
                        value=st.session_state.files[i]['content'],
                        height=650,
                        key=f"xaml_{i}",
                        disabled=True
                    )
                else:
                    xaml_content = st.session_state.files[i]['content']
                    html_content = render_xaml_visualization(xaml_content)
                    components.html(html_content, height=650, scrolling=True)

if not st.session_state.initialized:
    st.title("LLM4Reuse")
    uploaded_files = st.file_uploader("Upload XAML files", accept_multiple_files=True, type=['xaml'])

    if uploaded_files:
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
        st.rerun()
else:
    show_main_interface()
