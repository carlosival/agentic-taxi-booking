import ast
import json
import os
import re
from typing import Dict, Any, Optional
import logging

logger = logging.getLogger(__name__)

def get_secret(name: str, default: str | None = None) -> str | None:
    """
    Reads a secret from Docker secrets if available,
    otherwise falls back to a normal environment variable.
    """
    file_path = os.getenv(f"{name}_FILE")
    if file_path and os.path.exists(file_path):
        with open(file_path, "r") as f:
            return f.read().strip()
    return os.getenv(name, default)


def json_parser(json_str: str) -> Optional[Dict[str, Any]]:
            """
            Try to parse a JSON string to Dict.
            If it fails, attempt to extract the first {...} block.
            If that also fails, try to parse it as a Python literal.
            """
            try:
                # First try: normal JSON parsing
                json_dict = json.loads(json_str)
                if isinstance(json_dict, dict):
                    return json_dict
                else:
                    raise ValueError("Top-level JSON is not an object")
            
            except json.JSONDecodeError:
                # Second try: extract first {...} using regex
                match = re.search(r'\{.*\}', json_str, re.DOTALL)
                if match:
                    try:
                        json_dict = json.loads(match.group(0))
                        if isinstance(json_dict, dict):
                            return json_dict
                    except json.JSONDecodeError:
                        pass  # Continue to literal_eval fallback

                # Third try: attempt to parse as Python literal
                try:
                    python_dict = ast.literal_eval(json_str)
                    if isinstance(python_dict, dict):
                        # Convert to JSON-compatible: ensure keys are strings etc.
                        json_string = json.dumps(python_dict)
                        json_dict = json.loads(json_string)
                        return json_dict
                except (ValueError, SyntaxError):
                    pass

            # If everything fails, return a fallback
            logger.warning(f"JSON parsing failed for: {json_str[:100]}...")
            return None