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

def parse_xaml_to_dict(xaml_string):
    """Parse XAML string to a Python dictionary"""
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
    """Process an XML node and its children into a dictionary"""
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
        for attr_name, attr_value in node.attrs.items():
            if (attr_name != 'DisplayName' and 
                not attr_name.startswith('sap:') and 
                not attr_name.startswith('sap2010:') and
                not attr_name.startswith('WorkflowViewStateService') and
                attr_value != '{x:Null}'):
                attributes.append({"name": attr_name, "value": attr_value})
        
        main_attributes = []
        main_args = []
        in_args = []
        out_args = []
        is_unsupported = node_name not in COMPONENTS
        
        children = []
        for child in node.find_all(recursive=False):
            if (not child.name.startswith('WorkflowViewStateService.ViewState') and
                child.name not in ['Variables', 'Sequence.Variables']):
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
            "isUnsupported": is_unsupported
        }
    except Exception as e:
        return {"nodeName": "Error", "error": str(e), "children": []}

def generate_visual_html(node, depth=0):
    """Generate HTML for the visual representation of a XAML node"""
    try:
        icon = get_icon_for_node(node.get("nodeName", "Unknown"))
        
        attributes_html = ""
        if node.get("attributes"):
            attributes_html = f'<div class="arguments">{"".join([f"<div>{attr.get('name')}: {attr.get('value')}</div>" for attr in node.get("attributes", [])])}</div>'
        
        main_arg_html = ""
        if node.get("mainArgs"):
            main_arg_items = "".join([
                f'<div class="main-arg-item">'
                f'<span class="main-arg-label">{arg.get("name")}:</span>'
                f'<div class="main-arg-value">{arg.get("value")}</div>'
                f'</div>' 
                for arg in node.get("mainArgs", [])
            ])
            main_arg_html = f'<div class="main-arg">{main_arg_items}</div>'
        
        annotation_html = f'<div class="annotation">{node.get("annotation")}</div>' if node.get("annotation") else ""
        warning_html = f'<div class="warning">This Activity is not supported by this code preview and may be displayed incorrectly.</div>' if node.get("isUnsupported", False) else ""
        
        main_attribute_html = "".join([f'<div class="main-attributes">{attr.get("name")}: {attr.get("value")}</div>' for attr in node.get("mainAttributes", [])])
        
        arguments_table = ""
        if node.get("inArgs") or node.get("outArgs"):
            in_args_html = "<br>".join(node.get("inArgs", [])) or "-"
            out_args_html = "<br>".join(node.get("outArgs", [])) or "-"
            
            arguments_table = f'''
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
        
        children_html = ""
        for child in node.get("children", []):
            children_html += generate_visual_html(child, depth + 1)
        
        return f'''
            <div class="component" style="margin-left: {depth * 20}px;">
                <div class="header">{icon} {node.get("nodeName", "Unknown")}{f' ({node["displayName"]})' if node.get("displayName") else ""}</div>
                {annotation_html}
                {main_attribute_html}
                {main_arg_html}
                {arguments_table}
                {attributes_html}
                {warning_html}
                <div class="children">{children_html}</div>
            </div>
        '''
    except Exception as e:
        return f'<div class="error">Error rendering node: {str(e)}</div>'

def get_xaml_visualization_css():
    """Return the CSS for styling the XAML visualization"""
    return """
    <style>
        .xaml-visualization {
            font-family: "Source Sans Pro", sans-serif;
            background-color: rgb(14, 17, 23);
            color: #ddd;
            padding: 15px;
            border-radius: 8px;
            overflow-y: auto;
            height: 650px;
            box-shadow: 0px 4px 8px rgba(0, 0, 0, 0.3);
        }
        
        .component {
            border: 1px solid #444;
            padding: 10px;
            margin: 8px 5px;
            border-radius: 8px;
            background-color: #1c1f26;
            box-shadow: 0px 3px 6px rgba(0, 0, 0, 0.4);
            transition: all 0.2s ease-in-out;
            position: relative;
            max-width: 98%;
            box-sizing: border-box;
        }
        
        .component:hover {
            box-shadow: 0px 5px 12px rgba(0, 0, 0, 0.6);
            border-color: #666;
        }
        
        .header {
            font-weight: 600;
            background: linear-gradient(135deg, #2a5b98, #1a3e6e);
            color: white;
            padding: 12px;
            border-radius: 6px;
            font-size: 16px;
            display: flex;
            align-items: center;
            gap: 8px;
            width: 100%;
            box-sizing: border-box;
            margin-bottom: 8px;
        }
        
        .children {
            border-left: 2px solid #444;
            padding-left: 5px;
            margin-top: 10px;
        }
        
        .arguments, .main-arg, .annotation, .workflow-arguments {
            margin: 10px 0;
            padding: 12px;
            border-radius: 6px;
        }
        
        .arguments {
            border-left: 5px solid #0078D7;
            background: #112233;
        }
        
        .arguments:before {
            content: "🏷️ Arguments";
            font-weight: bold;
            display: block;
            margin-bottom: 6px;
            color: #4ca3ff;
        }
        
        .arguments div {
            margin: 4px 0;
            padding-left: 10px;
        }
        
        .annotation {
            border-left: 5px solid #4CAF50;
            background: #1b2d1b;
            font-style: italic;
            color: #b4e0b4;
        }
        
        .annotation:before {
            content: "💡 Annotation";
            font-weight: bold;
            display: block;
            margin-bottom: 6px;
            color: #74d774;
        }
        
        .main-arg {
            display: flex;
            flex-wrap: wrap;
            gap: 10px;
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
            font-size: 14px;
            color: #98c1ff;
        }
        
        .main-arg-value {
            width: 100%;
            padding: 8px;
            border: 1px solid #555;
            border-radius: 6px;
            background: #2c2f36;
            font-size: 14px;
            text-align: left;
            box-shadow: inset 0px 1px 3px rgba(0, 0, 0, 0.3);
            overflow-wrap: break-word;
            box-sizing: border-box;
        }
        
        .warning {
            border-left: 5px solid #d9534f;
            background-color: #2a1a1a;
            color: #d9534f;
            padding: 10px;
            margin: 10px 0;
            border-radius: 6px;
            font-weight: bold;
        }
        
        .warning:before {
            content: "⚠️ Warning";
            display: block;
            margin-bottom: 5px;
        }
        
        /* Workflow Arguments */
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
        }
        
        .workflow-arguments th {
            font-weight: bold;
            font-size: 14px;
            color: #7cff02;
            padding: 12px;
            text-align: left;
            background-color: #2f4f25;
        }
        
        .workflow-arguments td {
            padding: 10px;
            border-bottom: 1px solid #444;
            background-color: #1c1f26;
            text-align: left;
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
            font-size: 16px;
        }
        
        /* Error message */
        .error {
            background-color: #42211f;
            color: #ff6b6b;
            padding: 15px;
            border-radius: 6px;
            margin: 10px 0;
            border-left: 5px solid #ff3333;
        }
        
        /* Toggle button styling */
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
        }
        
        .view-toggle-button:hover {
            background: linear-gradient(135deg, #3a6ca8, #2a4f7e);
            box-shadow: 0 2px 5px rgba(0,0,0,0.2);
        }
    </style>
    """

def render_xaml_visualization(xaml_content):
    """Render the visual representation of XAML content"""
    xaml_dict = parse_xaml_to_dict(xaml_content)
    
    if "error" in xaml_dict:
        return f'<div class="error">Failed to parse XAML: {xaml_dict["error"]}</div>'
    
    html_content = generate_visual_html(xaml_dict)
    
    css = get_xaml_visualization_css()
    full_html = f'{css}<div class="xaml-visualization">{html_content}</div>'
    
    return full_html
