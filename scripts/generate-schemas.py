#!/usr/bin/env python3
"""
Generate JSON Schema inputSchema for all MCP tools in server.py
and update manifest.json with the schemas.
"""

import ast
import json
import re
from pathlib import Path
from typing import Any

# Paths
SCRIPT_DIR = Path(__file__).parent
PROJECT_ROOT = SCRIPT_DIR.parent
SERVER_PY = PROJECT_ROOT / "mcpb" / "src" / "accountingqb" / "server.py"
MANIFEST_JSON = PROJECT_ROOT / "mcpb" / "manifest.json"


def python_type_to_json_schema(type_name: str) -> dict:
    """Convert Python type annotation to JSON Schema type."""
    mapping = {
        "str": {"type": "string"},
        "int": {"type": "integer"},
        "float": {"type": "number"},
        "bool": {"type": "boolean"},
    }
    return mapping.get(type_name, {"type": "string"})


def extract_tools_from_ast(source_code: str) -> list[dict]:
    """Parse server.py and extract all @mcp.tool decorated functions."""
    tree = ast.parse(source_code)
    tools = []

    for node in ast.walk(tree):
        if not isinstance(node, ast.AsyncFunctionDef):
            continue

        # Check for @mcp.tool decorator
        is_mcp_tool = False
        annotations = {}
        for decorator in node.decorator_list:
            if isinstance(decorator, ast.Call):
                if isinstance(decorator.func, ast.Attribute):
                    if decorator.func.attr == "tool":
                        is_mcp_tool = True
                        # Extract annotations kwarg
                        for kw in decorator.keywords:
                            if kw.arg == "annotations":
                                if isinstance(kw.value, ast.Dict):
                                    for k, v in zip(kw.value.keys, kw.value.values):
                                        if isinstance(k, ast.Constant) and isinstance(v, ast.Constant):
                                            annotations[k.value] = v.value
            elif isinstance(decorator, ast.Attribute):
                if decorator.attr == "tool":
                    is_mcp_tool = True

        if not is_mcp_tool:
            continue

        # Extract function info
        func_name = node.name
        docstring = ast.get_docstring(node) or ""

        # Extract parameters
        params = []
        defaults_offset = len(node.args.args) - len(node.args.defaults)

        for i, arg in enumerate(node.args.args):
            if arg.arg == "self":
                continue

            param = {
                "name": arg.arg,
                "type": "str",  # default
                "required": True,
                "default": None,
            }

            # Get type annotation
            if arg.annotation:
                if isinstance(arg.annotation, ast.Name):
                    param["type"] = arg.annotation.id
                elif isinstance(arg.annotation, ast.Constant):
                    param["type"] = str(arg.annotation.value)

            # Check for default value
            default_idx = i - defaults_offset
            if default_idx >= 0 and default_idx < len(node.args.defaults):
                default_node = node.args.defaults[default_idx]
                param["required"] = False
                if isinstance(default_node, ast.Constant):
                    param["default"] = default_node.value
                elif isinstance(default_node, ast.Num):  # Python 3.7 compat
                    param["default"] = default_node.n
                elif isinstance(default_node, ast.Str):  # Python 3.7 compat
                    param["default"] = default_node.s

            params.append(param)

        tools.append({
            "name": func_name,
            "docstring": docstring,
            "params": params,
            "annotations": annotations,
        })

    return tools


def generate_input_schema(tool: dict) -> dict | None:
    """Generate JSON Schema inputSchema for a tool."""
    params = tool["params"]

    if not params:
        # No parameters - return empty schema
        return {
            "type": "object",
            "properties": {},
            "required": []
        }

    properties = {}
    required = []

    for param in params:
        prop = python_type_to_json_schema(param["type"])

        # Add description from parameter name
        prop["description"] = param["name"].replace("_", " ").title()

        # Add default if present
        if param["default"] is not None:
            prop["default"] = param["default"]

        properties[param["name"]] = prop

        if param["required"]:
            required.append(param["name"])

    schema = {
        "type": "object",
        "properties": properties,
    }

    if required:
        schema["required"] = required

    return schema


def update_manifest(tools: list[dict], strip_schemas: bool = False) -> None:
    """Update manifest.json with inputSchema for each tool."""
    with open(MANIFEST_JSON, "r") as f:
        manifest = json.load(f)

    # Create lookup from extracted tools
    tool_lookup = {t["name"]: t for t in tools}

    # Update each tool in manifest
    updated_count = 0
    for manifest_tool in manifest.get("tools", []):
        tool_name = manifest_tool.get("name")

        # Strip schemas if requested (for mcpb compatibility)
        if strip_schemas:
            manifest_tool.pop("inputSchema", None)
            manifest_tool.pop("annotations", None)
            updated_count += 1
            continue

        if tool_name in tool_lookup:
            extracted = tool_lookup[tool_name]

            # Generate and add inputSchema
            schema = generate_input_schema(extracted)
            if schema:
                manifest_tool["inputSchema"] = schema

            # Add annotations if present
            if extracted["annotations"]:
                manifest_tool["annotations"] = extracted["annotations"]

            updated_count += 1

    # Write updated manifest
    with open(MANIFEST_JSON, "w") as f:
        json.dump(manifest, f, indent=2)

    action = "stripped schemas from" if strip_schemas else "updated with inputSchema"
    print(f"{action.capitalize()} {updated_count} tools")
    print(f"Manifest written to: {MANIFEST_JSON}")


def main():
    import sys
    strip_mode = "--strip" in sys.argv

    print("Reading server.py...")
    source_code = SERVER_PY.read_text()

    print("Extracting tool definitions...")
    tools = extract_tools_from_ast(source_code)
    print(f"Found {len(tools)} tools")

    if strip_mode:
        print("Stripping inputSchema/annotations from manifest.json (mcpb compatibility)...")
        update_manifest(tools, strip_schemas=True)
    else:
        print("Updating manifest.json with inputSchema...")
        update_manifest(tools)

    print("Done!")


if __name__ == "__main__":
    main()
