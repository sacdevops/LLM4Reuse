import re
from bs4 import BeautifulSoup

COMPONENTS = {
    "Assign": "📝",
    "MessageBox": "💬",
    "ReadTextFile": "📄",
    "Comment": "💡",
    "Sequence": "🔽",
    "If": "↔️",
    "If.Then": "✅",
    "If.Else": "❌",
    "ReadCsvFile": "👓",
    "WriteCsvFile": "📝",
    "AppendCsvFile": "📝",
    "Click": "🐭",
    "TypeInto": "💬",
    "InvokeWorkflowFile": "↗️"
}

def get_icon_for_node(node_name):
    return COMPONENTS.get(node_name, "🔧")

def is_base64_image(value):
    if not isinstance(value, str):
        return False
    
    base64_patterns = [
        r'^data:image/[a-zA-Z]+;base64,',
        r'^iVBOR',
        r'^/9j/',
        r'^R0lGOD',
        r'^UEs'
    ]
    
    for pattern in base64_patterns:
        if re.search(pattern, value):
            return True
    
    if len(value) > 100 and re.match(r'^[A-Za-z0-9+/]+={0,2}$', value):
        return True
    
    return False

def parse_xaml_to_dict(xaml_string):
    try:
        soup = BeautifulSoup(xaml_string, 'xml')
        root = soup.find('Activity')
        
        if not root:
            return {"error": "No Activity element found in the XAML"}
        
        sequence = root.find('Sequence')
        if not sequence:
            sequence = root
            
        return process_node(sequence)
    except Exception as e:
        return {"error": f"Error parsing XAML: {str(e)}"}

def process_node(node):
    try:
        node_name = node.name
        if ':' in node_name:
            node_name = node_name.split(':')[-1]
        
        display_name = node.get('DisplayName', '')
        annotation = None
        
        for attr_name, attr_value in node.attrs.items():
            if 'Annotation.AnnotationText' in attr_name:
                annotation = attr_value
                break
        
        attributes = []
        base64_images = []
        
        for attr_name, attr_value in node.attrs.items():
            if (attr_name != 'DisplayName' and 
                not attr_name.startswith('sap:') and 
                not attr_name.startswith('sap2010:') and
                not attr_name.startswith('WorkflowViewStateService') and
                attr_value != '{x:Null}'):
                
                if is_base64_image(attr_value):
                    img_format = "png"
                    if attr_value.startswith("data:image/"):
                        base64_images.append({"name": attr_name, "value": attr_value})
                    else:
                        base64_images.append({
                            "name": attr_name, 
                            "value": f"data:image/{img_format};base64,{attr_value}"
                        })
                else:
                    attributes.append({"name": attr_name, "value": attr_value})
        
        main_attributes = []
        main_args = []
        in_args = []
        out_args = []
        arguments_table = []
        is_unsupported = node_name not in COMPONENTS
        
        children = []
        
        for child in node.find_all(recursive=False):
            child_name = child.name
            
            if (child_name.startswith('WorkflowViewStateService.ViewState') or
                child_name in ['Variables', 'Sequence.Variables']):
                continue
                
            if '.Body' in child_name:
                for body_child in child.find_all(recursive=False):
                    children.append(process_node(body_child))
                continue
                
            if '.Argument' in child_name:
                arg_info = {
                    "type": child_name.split('.')[-2],
                    "argType": "",
                    "name": "",
                    "value": ""
                }
                
                for arg_child in child.find_all(recursive=False, limit=1):
                    arg_info["argType"] = arg_child.name.split(':')[-1] if ':' in arg_child.name else arg_child.name
                    arg_info["name"] = arg_child.get('Name', '')
                    
                    if arg_child.has_attr('x:TypeArguments'):
                        arg_info["value"] = arg_child.get('x:TypeArguments', '')
                
                arguments_table.append(arg_info)
                continue
                
            children.append(process_node(child))
        
        if node_name == "Assign":
            assign_to = node.find("Assign.To")
            assign_value = node.find("Assign.Value")
            if assign_to:
                main_args.append({"name": "Assign To", "value": assign_to.text.strip() if assign_to.text else ""})
            if assign_value:
                main_args.append({"name": "Assign Value", "value": assign_value.text.strip() if assign_value.text else ""})
            children = []
            
        elif node_name in ["MessageBox", "Comment"]:
            message_text = node.get('Text', 'No Message')
            main_args.append({"name": "Text", "value": message_text})
            attributes = [attr for attr in attributes if attr["name"] != "Text"]
            
        elif node_name == "ReadTextFile":
            file_name = node.get('FileName', 'FILE NOT SELECTED')
            main_args.append({"name": "File Name", "value": file_name})
            attributes = [attr for attr in attributes if attr["name"] != "FileName"]
            
        elif node_name == "TypeInto":
            text = node.get('Text', 'Text not Specified')
            main_args.append({"name": "Text", "value": text})
            attributes = [attr for attr in attributes if attr["name"] != "Text"]
            children = []
            
        elif node_name == "If":
            condition = node.get('Condition', 'Condition not Specified')
            main_args.append({"name": "Condition", "value": condition})
            attributes = [attr for attr in attributes if attr["name"] != "Condition"]
            
        elif node_name == "ReadCsvFile":
            file_path = node.get('FilePath', 'FilePath not Specified')
            main_args.append({"name": "FilePath", "value": file_path})
            attributes = [attr for attr in attributes if attr["name"] != "FilePath"]
            
            data_table = node.get('DataTable', 'Output not Specified')
            main_args.append({"name": "Output to", "value": data_table})
            attributes = [attr for attr in attributes if attr["name"] != "DataTable"]
            
        elif node_name == "WriteCsvFile" or node_name == "AppendCsvFile":
            file_path = node.get('FilePath', 'FilePath not Specified')
            main_args.append({"name": "Write to what file", "value": file_path})
            attributes = [attr for attr in attributes if attr["name"] != "FilePath"]
            
            data_table = node.get('DataTable', 'Datatable not Specified')
            main_args.append({"name": "Write from", "value": data_table})
            attributes = [attr for attr in attributes if attr["name"] != "DataTable"]
            
        elif node_name == "InvokeWorkflowFile":
            workflow_file = node.get('WorkflowFileName', 'Workflow not Specified')
            main_args.append({"name": "Workflow", "value": workflow_file})
            attributes = [attr for attr in attributes if attr["name"] != "WorkflowFileName"]
            
            args_node = node.find("InvokeWorkflowFile.Arguments")
            if args_node:
                for arg in args_node.find_all(recursive=False):
                    key = arg.get('x:Key', 'Unnamed')
                    arg_type = arg.get('x:TypeArguments', 'Unknown')
                    
                    if 'InArgument' in arg.name:
                        in_args.append(f"{arg_type}: {key}")
                    elif 'OutArgument' in arg.name:
                        out_args.append(f"{arg_type}: {key}")
            children = []
            
        elif node_name == "Click":
            children = []
        
        return {
            "nodeName": node_name,
            "displayName": display_name,
            "annotation": annotation,
            "attributes": attributes,
            "mainAttributes": main_attributes,
            "mainArgs": main_args,
            "inArgs": in_args,
            "outArgs": out_args,
            "children": children,
            "isUnsupported": is_unsupported,
            "argumentsTable": arguments_table,
            "base64Images": base64_images
        }
    except Exception as e:
        return {"nodeName": "Error", "error": str(e), "children": []}

def generate_visual_html(node, depth=0):
    try:
        icon = get_icon_for_node(node.get("nodeName", "Unknown"))
        
        attributes_html = ""
        if node.get("attributes"):
            attributes_html = f'<div class="arguments">{"".join([f"<div><strong>{attr.get("name")}</strong>: {attr.get("value")}</div>" for attr in node.get("attributes", [])])}</div>'
        
        main_arg_html = ""
        if node.get("mainArgs"):
            main_arg_items = "".join([
                f'<div class="main-arg-item">'
                f'<span class="main-arg-label"><strong>{arg.get("name")}</strong>:</span>'
                f'<div class="main-arg-value">{arg.get("value")}</div>'
                f'</div>' 
                for arg in node.get("mainArgs", [])
            ])
            main_arg_html = f'<div class="main-arg">{main_arg_items}</div>'
        
        annotation_html = f'<div class="annotation">{node.get("annotation")}</div>' if node.get("annotation") else ""
        
        warning_icon = '&nbsp;<span class="warning-icon" title="This Activity is not supported by this code preview and may be displayed incorrectly">⚠️</span>' if node.get("isUnsupported", False) else ""
        
        main_attribute_html = "".join([f'<div class="main-attributes"><strong>{attr.get("name")}</strong>: {attr.get("value")}</div>' for attr in node.get("mainAttributes", [])])
        
        arguments_table_html = ""
        if node.get("argumentsTable") and len(node.get("argumentsTable")) > 0:
            arguments_table_html = f'''
                <div class="arguments-table">
                    <table>
                        <tr>
                            <th>Argument Type</th>
                            <th>Name</th>
                            <th>Type</th>
                        </tr>
                        {''.join([
                            f'<tr><td>{arg.get("argType", "")}</td><td><strong>{arg.get("name", "")}</strong></td><td>{arg.get("value", "")}</td></tr>'
                            for arg in node.get("argumentsTable", [])
                        ])}
                    </table>
                </div>
            '''
        
        workflow_args_html = ""
        if node.get("inArgs") or node.get("outArgs"):
            in_args_html = "<br>".join(node.get("inArgs", [])) or "-"
            out_args_html = "<br>".join(node.get("outArgs", [])) or "-"
            
            workflow_args_html = f'''
                <div class="workflow-arguments">
                    <table>
                        <tr>
                            <th>In</th>
                            <th>Out</th>
                        </tr>
                        <tr>
                            <td>{in_args_html}</td>
                            <td>{out_args_html}</td>
                        </tr>
                    </table>
                </div>
            '''
        
        base64_images_html = ""
        if node.get("base64Images") and len(node.get("base64Images")) > 0:
            images_content = "".join([
                f'<div class="base64-image-container">'
                f'<div class="image-name"><strong>{img.get("name")}</strong>:</div>'
                f'<img src="{img.get("value")}" alt="Base64 encoded image" class="base64-image">'
                f'</div>'
                for img in node.get("base64Images", [])
            ])
            base64_images_html = f'<div class="base64-images">{images_content}</div>'
        
        children_html = ""
        for child in node.get("children", []):
            children_html += generate_visual_html(child, depth + 1)
        
        return f'''
            <div class="component" style="margin-left: {depth * 1}px; margin-right: 0px; width: calc(100% - {depth * 1}px);">
                <div class="header">{icon} {node.get("nodeName", "Unknown")}{f' ({node["displayName"]})' if node.get("displayName") else ""}{warning_icon}</div>
                {annotation_html}
                {main_attribute_html}
                {main_arg_html}
                {arguments_table_html}
                {workflow_args_html}
                {base64_images_html}
                {attributes_html}
                <div class="children">{children_html}</div>
            </div>
        '''
    except Exception as e:
        return f'<div class="error">Error rendering node: {str(e)}</div>'

def get_xaml_visualization_css():
    return """
    <style>
        .xaml-visualization {
            font-family: "Source Sans Pro", sans-serif;
            font-size: 12px;
            background-color: rgb(14, 17, 23);
            color: #ddd;
            padding: 15px;
            border-radius: 8px;
            overflow-y: auto;
            box-shadow: 0px 4px 8px rgba(0, 0, 0, 0.3);
        }
        
        .component, .arguments, .main-arg, .annotation, 
        .workflow-arguments, .arguments-table, .main-arg-value, 
        .arguments div, td, th {
            word-wrap: break-word;
            overflow-wrap: break-word;
            word-break: break-word;
            white-space: normal;
        }
        
        .component {
            border: 1px solid #444;
            padding: 4px;
            margin: 2px 0;
            border-radius: 8px;
            background-color: #1c1f26;
            box-shadow: 0px 2px 4px rgba(0, 0, 0, 0.4);
            transition: all 0.2s ease-in-out;
            position: relative;
            box-sizing: border-box;
        }
        
        .component:hover {
            box-shadow: 0px 3px 8px rgba(0, 0, 0, 0.6);
            border-color: #666;
        }
        
        .header {
            font-weight: 600;
            font-size: 14px;
            background: linear-gradient(135deg, #2a5b98, #1a3e6e);
            color: white;
            padding: 8px;
            border-radius: 6px;
            display: flex;
            align-items: center;
            gap: 8px;
            width: 100%;
            box-sizing: border-box;
            margin-bottom: 6px;
            justify-content: space-between;
        }
        
        .header span:first-child {
            flex-grow: 1;
        }
        
        .children {
            border-left: 2px solid #444;
            padding-left: 2px;
            margin-top: 2px;
        }
        
        .arguments, .main-arg, .annotation, .workflow-arguments, .arguments-table {
            margin: 4px 0;
            padding: 4px;
            border-radius: 6px;
            font-size: 12px;
        }
        
        .arguments {
            border-left: 3px solid #0078D7;
            background: #112233;
        }
        
        .arguments:before {
            content: "🏷️ Arguments";
            font-weight: bold;
            display: block;
            margin-bottom: 2px;
            color: #4ca3ff;
            font-size: 12px;
        }
        
        .arguments div {
            margin: 2px 0;
            padding-left: 10px;
            font-size: 12px;
        }
        
        .annotation {
            border-left: 5px solid #4CAF50;
            background: #1b2d1b;
            font-style: italic;
            color: #b4e0b4;
            font-size: 12px;
        }
        
        .annotation:before {
            content: "💡 Annotation";
            font-weight: bold;
            display: block;
            margin-bottom: 6px;
            color: #74d774;
            font-size: 12px;
        }
        
        .main-arg {
            display: flex;
            flex-wrap: wrap;
            gap: 4px;
            border-left: 5px solid #00aaff;
            background: #1b2b3b;
            max-width: 100%;
            box-sizing: border-box;
        }
        
        .main-arg:before {
            content: "📊 Main Arguments";
            font-weight: bold;
            display: block;
            margin-bottom: 8px;
            color: #8cc4ff;
            width: 100%;
            font-size: 12px;
        }
        
        .main-arg-item {
            display: flex;
            flex-direction: column;
            flex: 1 1 45%;
            min-width: 150px;
        }
        
        .main-arg-label {
            font-weight: bold;
            margin-bottom: 6px;
            color: #98c1ff;
            font-size: 12px;
        }
        
        .main-arg-value {
            width: 100%;
            padding: 4px;
            border: 1px solid #555;
            border-radius: 6px;
            background: #2c2f36;
            text-align: left;
            box-shadow: inset 0px 1px 3px rgba(0, 0, 0, 0.3);
            box-sizing: border-box;
            font-size: 12px;
            max-width: 100%;
        }
        
        .warning-icon {
            color: #ffcc00;
            font-size: 14px;
            margin-left: auto;
            cursor: help;
        }
        
        .arguments-table {
            background: #1b263b;
            border-left: 5px solid #00a8cc;
            padding: 12px;
        }
        
        .arguments-table:before {
            content: "📋 Arguments";
            font-weight: bold;
            display: block;
            margin-bottom: 8px;
            color: #66d9ff;
            font-size: 12px;
        }
        
        .arguments-table table {
            width: 100%;
            border-collapse: collapse;
            border-spacing: 0;
            border-radius: 8px;
            overflow: hidden;
            margin-top: 8px;
            font-size: 12px;
        }
        
        .arguments-table th {
            font-weight: bold;
            color: #66d9ff;
            padding: 10px;
            text-align: left;
            background-color: #1a3a5a;
            font-size: 12px;
        }
        
        .arguments-table td {
            padding: 8px;
            border-bottom: 1px solid #444;
            background-color: #1c1f26;
            text-align: left;
            font-size: 12px;
            max-width: 33%;
        }
        
        .arguments-table tr:last-child td {
            border-bottom: none;
        }
        
        .workflow-arguments {
            background: #1b3b22;
            border-left: 5px solid #68d700;
            padding: 15px;
        }
        
        .workflow-arguments table {
            width: 100%;
            border-collapse: collapse;
            border-spacing: 0;
            border-radius: 8px;
            overflow: hidden;
            margin-top: 8px;
            font-size: 12px;
        }
        
        .workflow-arguments th {
            font-weight: bold;
            color: #7cff02;
            padding: 12px;
            text-align: left;
            background-color: #2f4f25;
            font-size: 12px;
        }
        
        .workflow-arguments td {
            padding: 10px;
            border-bottom: 1px solid #444;
            background-color: #1c1f26;
            text-align: left;
            font-size: 12px;
        }
        
        .workflow-arguments tr:last-child td {
            border-bottom: none;
        }
        
        .workflow-arguments:before {
            content: "🔗 Workflow Arguments";
            font-weight: bold;
            display: block;
            margin-bottom: 10px;
            color: #68d700;
            font-size: 12px;
        }
        
        .arguments strong, .main-arg-label strong, .arguments-table td strong {
            color: #88ccff;
        }
        
        .error {
            background-color: #42211f;
            color: #ff6b6b;
            padding: 15px;
            border-radius: 6px;
            margin: 10px 0;
            border-left: 5px solid #ff3333;
            font-size: 12px;
        }
        
        .base64-images {
            margin: 4px 0;
            padding: 8px;
            border-radius: 6px;
            border-left: 5px solid #d66bff;
            background: #2b1f36;
            font-size: 12px;
        }
        
        .base64-images:before {
            content: "🖼️ Embedded Images";
            font-weight: bold;
            display: block;
            margin-bottom: 8px;
            color: #d66bff;
            font-size: 12px;
        }
        
        .base64-image-container {
            margin: 8px 0;
            padding: 8px;
            background: #1c1f26;
            border-radius: 4px;
            border: 1px solid #444;
        }
        
        .image-name {
            margin-bottom: 6px;
            font-size: 12px;
        }
        
        .image-name strong {
            color: #d66bff;
        }
        
        .base64-image {
            width: 100%;
            max-width: 100%;
            height: auto;
            border-radius: 4px;
            border: 1px solid #555;
            display: block;
        }
        
        .view-toggle-container {
            text-align: right;
            margin-bottom: 10px;
        }
        
        .view-toggle-button {
            background: linear-gradient(135deg, #2a5b98, #1a3e6e);
            color: white;
            border: none;
            border-radius: 4px;
            padding: 8px 12px;
            cursor: pointer;
            transition: all 0.2s;
            font-weight: bold;
            font-size: 12px;
        }
        
        .view-toggle-button:hover {
            background: linear-gradient(135deg, #3a6ca8, #2a4f7e);
            box-shadow: 0 2px 5px rgba(0,0,0,0.2);
        }
    </style>
    """

def render_xaml_visualization(xaml_content):
    xaml_dict = parse_xaml_to_dict(xaml_content)
    
    if "error" in xaml_dict:
        return f'<div class="error">Failed to parse XAML: {xaml_dict["error"]}</div>'
    
    html_content = generate_visual_html(xaml_dict)
    
    css = get_xaml_visualization_css()
    full_html = f'{css}<div class="xaml-visualization">{html_content}</div>'
    
    return full_html
