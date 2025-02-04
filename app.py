import os
import uuid
import openai
from flask import Flask, request, session, render_template, jsonify, send_file
import shutil
import io

app = Flask(__name__)
app.secret_key = "some-secret-key"

openai.api_key = "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"

@app.route("/", methods=["GET"])
def main_page():
    return render_template("index.html")

@app.route("/", methods=["POST"])
def upload_files():
    files = request.files.getlist("files")
    if not os.path.exists("temp_uploads"):
        os.mkdir("temp_uploads")

    saved_paths = []
    for f in files:
        filename = f"{uuid.uuid4()}_{f.filename}"
        path = os.path.join("temp_uploads", filename)
        f.save(path)
        saved_paths.append(path)

    session["uploaded_files"] = saved_paths
    xaml_code = load_xaml(saved_paths)

    xaml_path = os.path.join("temp_uploads", f"{uuid.uuid4()}.xaml")
    with open(xaml_path, "w", encoding="utf-8") as xf:
        xf.write(xaml_code)
    session["xaml_path"] = xaml_path

    documentation = generate_docs(xaml_code)
    doc_path = os.path.join("temp_uploads", f"{uuid.uuid4()}.txt")
    with open(doc_path, "w", encoding="utf-8") as df:
        df.write(documentation)
    session["doc_path"] = doc_path

    session["chat_history"] = []
    return jsonify({
        "status": "ok",
        "xaml_code": xaml_code,
        "documentation": documentation
    })

@app.route("/extend_code", methods=["POST"])
def extend_code():
    if "xaml_path" not in session:
        return {"error": "No code in session"}, 400

    data = request.json or {}
    user_prompt = data.get("prompt", "").strip()
    xaml_path = session["xaml_path"]

    with open(xaml_path, "r", encoding="utf-8") as xf:
        current_xaml = xf.read()

    if user_prompt:
        chat_history = session.get("chat_history", [])
        chat_history.append(("user", user_prompt))
        updated_code = extend_xaml(current_xaml, user_prompt)
        with open(xaml_path, "w", encoding="utf-8") as xf:
            xf.write(updated_code)
        chat_history.append(("assistant", "Code updated."))
        session["chat_history"] = chat_history
        return {"xaml_code": updated_code}

    return {"xaml_code": current_xaml}

@app.route("/generate_docs", methods=["POST"])
def generate_docs_api():
    if "xaml_path" not in session:
        return {"error": "No code available"}, 400

    xaml_path = session["xaml_path"]
    with open(xaml_path, "r", encoding="utf-8") as xf:
        current_xaml = xf.read()
    new_doc = generate_docs(current_xaml)
    doc_path = os.path.join("temp_uploads", f"{uuid.uuid4()}_doc.txt")
    with open(doc_path, "w", encoding="utf-8") as df:
        df.write(new_doc)
    session["doc_path"] = doc_path
    return {"documentation": new_doc}

@app.route("/confirm", methods=["POST"])
def confirm():
    if "uploaded_files" not in session:
        return {"error": "No uploaded files in session"}, 400

    doc_path = session.get("doc_path")
    folder_name = f"confirmed_{uuid.uuid4()}"
    os.mkdir(folder_name)
    for path in session["uploaded_files"]:
        filename = os.path.basename(path)
        shutil.move(path, os.path.join(folder_name, filename))
    if doc_path:
        shutil.move(doc_path, os.path.join(folder_name, "generated_documentation.txt"))
    session.clear()
    return {"status": "confirmed"}

@app.route("/download_pdf", methods=["GET"])
def download_pdf():
    doc_path = session.get("doc_path")
    if doc_path and os.path.exists(doc_path):
        with open(doc_path, "r", encoding="utf-8") as f:
            content = f.read().encode("utf-8")
    else:
        content = "No documentation.".encode("utf-8")
    return send_file(io.BytesIO(content), as_attachment=True, download_name="documentation.txt", mimetype="text/plain")

def load_xaml(paths):
    result = []
    for p in paths:
        if p.lower().endswith(".xaml"):
            with open(p, "r", encoding="utf-8") as f:
                result.append(f.read())
    return "\n".join(result)

def extend_xaml(current_xaml, user_prompt):
    prompt_text = f"""
        You are an advanced UiPath RPA developer.
        You have the following current UiPath XAML code:
        {current_xaml}

        The user wants changes or enhancements based on the following instructions:
        {user_prompt}

        Please integrate these changes into the XAML. Return only the complete, updated code without any additionals."""

    resp = openai.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role": "user", "content": prompt_text}],
        max_tokens=10000,
        temperature=0.3,
    )
    return resp.choices[0].message.content.strip()

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
