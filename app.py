import os
import openai
from flask import Flask, request, render_template, jsonify, send_file
import shutil
import io

app = Flask(__name__)
app.secret_key = "some-secret-key"

UPLOAD_FOLDER = "LLM4Reuse/temp_uploads"
current_xaml_file = os.path.join(UPLOAD_FOLDER, "current_workflow.xaml")
current_doc_file = os.path.join(UPLOAD_FOLDER, "current_documentation.txt")

openai.api_key = "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"

@app.route("/", methods=["GET"])
def main_page():
    return render_template("index.html")

@app.route("/", methods=["POST"])
def upload_files():
    if not os.path.exists(UPLOAD_FOLDER):
        os.makedirs(UPLOAD_FOLDER)

    files = request.files.getlist("files")
    for f in files:
        if f.filename.lower().endswith('.xaml'):
            f.save(current_xaml_file)
            
            with open(current_xaml_file, 'r', encoding='utf-8') as xf:
                xaml_content = xf.read()
            
            documentation = generate_docs(xaml_content)
            with open(current_doc_file, 'w', encoding='utf-8') as df:
                df.write(documentation)
            
            return jsonify({
                "status": "ok",
                "xaml_code": xaml_content,
                "documentation": documentation
            })

    return jsonify({"error": "No XAML file uploaded"}), 400

@app.route("/extend_code", methods=["POST"])
def extend_code():   
    if not current_xaml_file or not os.path.exists(current_xaml_file):
        return {"error": "No XAML file available"}, 400

    data = request.json or {}
    user_prompt = data.get("prompt", "").strip()

    with open(current_xaml_file, "r", encoding="utf-8") as xf:
        current_xaml = xf.read()

    if user_prompt:
        updated_code = extend_xaml(current_xaml, user_prompt)
        with open(current_xaml_file, "w", encoding="utf-8") as xf:
            xf.write(updated_code)
        return {"xaml_code": updated_code}

    return {"xaml_code": current_xaml}

@app.route("/generate_docs", methods=["POST"])
def generate_docs_api():  
    if not current_xaml_file or not os.path.exists(current_xaml_file):
        return {"error": "No XAML file available"}, 400

    with open(current_xaml_file, "r", encoding="utf-8") as xf:
        current_xaml = xf.read()
    
    new_doc = generate_docs(current_xaml)
    with open(current_doc_file, "w", encoding="utf-8") as df:
        df.write(new_doc)
    
    return {"documentation": new_doc}

@app.route("/confirm", methods=["POST"])
def confirm():
    if not current_xaml_file or not os.path.exists(current_xaml_file):
        return {"error": "No files to confirm"}, 400

    folder_name = "confirmed_files"
    if not os.path.exists(folder_name):
        os.makedirs(folder_name)

    shutil.copy2(current_xaml_file, os.path.join(folder_name, "workflow.xaml"))
    if current_doc_file and os.path.exists(current_doc_file):
        shutil.copy2(current_doc_file, os.path.join(folder_name, "documentation.txt"))

    return {"status": "confirmed"}

@app.route("/download_pdf", methods=["GET"])
def download_pdf():
    if current_doc_file and os.path.exists(current_doc_file):
        return send_file(current_doc_file, 
                        as_attachment=True,
                        download_name="documentation.txt",
                        mimetype="text/plain")
    
    return "No documentation available", 404

def extend_xaml(current_xaml, user_prompt):
    prompt_text = f"""
        You are an advanced UiPath RPA developer.
        Do not remove any attributes from the XAML file that are used in the body. For example, if scg is used in the body, the attribute should also remain in the activity, as the reference is used.
        Integrate these changes into XAML. Return only the complete, updated code in plain-text.
        You have the following current UiPath XAML code:
        {current_xaml}

        The user wants changes or enhancements based on the following instructions:
        {user_prompt}
        """

    resp = openai.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role": "user", "content": prompt_text}],
        max_tokens=10000,
        temperature=0.1,
    )
    return resp.choices[0].message.content.strip().replace("```xml", "").replace("```", "")

def generate_docs(xaml_code):
    prompt_text = f"""
        You are an expert in documenting UiPath workflows in extreme detail.
        Given the following XAML code, produce a thorough, step-by-step documentation.
        Include all libraries or packages used, how each activity and element works, the purpose of this RPA workflow, expected inputs/outputs:
        {xaml_code}

        Return only the documentation text."""
    
    resp = openai.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role": "user", "content": prompt_text}],
        max_tokens=10000,
        temperature=0.3
    )
    return resp.choices[0].message.content.strip()

if __name__ == "__main__":
    app.run(debug=True)
