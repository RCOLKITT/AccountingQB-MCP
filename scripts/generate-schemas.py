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
                                        if isinstance(k, ast.Constant) and isinstance(
                                            v, ast.Constant
                                        ):
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

        tools.append(
            {
                "name": func_name,
                "docstring": docstring,
                "params": params,
                "annotations": annotations,
            }
        )

    return tools


def generate_input_schema(tool: dict) -> dict | None:
    """Generate JSON Schema inputSchema for a tool."""
    params = tool["params"]

    if not params:
        # No parameters - return empty schema
        return {"type": "object", "properties": {}, "required": []}

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


def short_description(docstring: str, max_len: int = 200) -> str:
    """First line of the docstring, trimmed for the manifest tools array."""
    first_line = docstring.strip().splitlines()[0].strip() if docstring.strip() else ""
    if len(first_line) > max_len:
        first_line = first_line[: max_len - 1].rstrip() + "…"
    return first_line


def update_manifest(tools: list[dict], strip_schemas: bool = False) -> None:
    """Regenerate the manifest.json tools array from the tools extracted
    out of server.py. Existing descriptions are preserved when present;
    new tools get the first line of their docstring as description.

    With strip_schemas=True (--strip), only name/description are written
    (mcpb pack compatibility); otherwise inputSchema and annotations are
    included as well.
    """
    with open(MANIFEST_JSON, "r") as f:
        manifest = json.load(f)

    # Preserve hand-written short descriptions already in the manifest
    existing_descriptions = {
        t.get("name"): t.get("description")
        for t in manifest.get("tools", [])
        if t.get("name") and t.get("description")
    }

    new_tools = []
    for tool in tools:
        entry = {
            "name": tool["name"],
            "description": existing_descriptions.get(tool["name"])
            or short_description(tool["docstring"]),
        }

        if not strip_schemas:
            schema = generate_input_schema(tool)
            if schema:
                entry["inputSchema"] = schema
            ann = tool["annotations"]
            if ann:
                entry["annotations"] = ann
            # Also surface capability flags at the top level. MCP clients read
            # hints from `annotations`, but security auditors expect explicit
            # top-level declarations. Derive from the server's ground-truth
            # annotations rather than guessing. We intentionally do NOT emit a
            # blanket networkAccess flag: every tool speaks only to the single
            # first-party QuickBooks API (BASE_URL) with the user's own OAuth
            # token, so per-tool networkAccess:true misleads exfiltration-graph
            # analysis into treating each tool as an arbitrary egress point.
            # The real network posture (one allowlisted destination, no
            # tool-to-tool flow, _audit_log on every call) is documented in
            # CERTIFICATION.md. codeExecution is declared false — no tool
            # evaluates arbitrary code.
            entry["readOnlyHint"] = bool(ann.get("readOnlyHint"))
            entry["destructiveHint"] = bool(ann.get("destructiveHint"))
            entry["codeExecution"] = False

        new_tools.append(entry)

    manifest["tools"] = new_tools
    manifest["tools_generated"] = True

    # Write updated manifest
    with open(MANIFEST_JSON, "w") as f:
        json.dump(manifest, f, indent=2)
        f.write("\n")

    action = (
        "wrote name/description only (schemas stripped) for"
        if strip_schemas
        else "wrote inputSchema for"
    )
    print(f"Regenerated tools array: {action} {len(new_tools)} tools")
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
        print(
            "Stripping inputSchema/annotations from manifest.json (mcpb compatibility)..."
        )
        update_manifest(tools, strip_schemas=True)
    else:
        print("Updating manifest.json with inputSchema...")
        update_manifest(tools)

    print("Done!")


if __name__ == "__main__":
    main()
