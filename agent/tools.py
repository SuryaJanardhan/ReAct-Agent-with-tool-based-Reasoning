import ast
import operator
import os
import requests
from typing import Dict, Any, Callable

# Initialize DuckDuckGo Search client dynamically
try:
    from duckduckgo_search import DDGS
except ImportError:
    DDGS = None

# Base directory for safe file I/O (workspace root)
WORKSPACE_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))

# =====================================================================
# 1. Tool: get_weather
# =====================================================================
def get_weather(city: str) -> str:
    """Get the current weather conditions for a given city."""
    if not city:
        return "Error: City name is required."
    try:
        # Clean city name and call wttr.in
        clean_city = city.strip().replace(" ", "+")
        # Format 3 is a single-line summary, format 4 is detailed text
        url = f"https://wttr.in/{clean_city}?format=4"
        response = requests.get(url, timeout=10)
        if response.status_code == 200:
            return response.text.strip()
        else:
            # Try a fallback format
            fallback_url = f"https://wttr.in/{clean_city}?format=3"
            response = requests.get(fallback_url, timeout=10)
            if response.status_code == 200:
                return response.text.strip()
            return f"Error: Unable to fetch weather for '{city}' (Status code: {response.status_code})."
    except Exception as e:
        return f"Error: Exception occurred while fetching weather: {str(e)}"

# =====================================================================
# 2. Tool: calculate (Safe Math Parser using AST)
# =====================================================================
class SafeEval:
    # Allowed operators
    operators = {
        ast.Add: operator.add,
        ast.Sub: operator.sub,
        ast.Mult: operator.mul,
        ast.Div: operator.truediv,
        ast.FloorDiv: operator.floordiv,
        ast.Mod: operator.mod,
        ast.Pow: operator.pow,
        ast.USub: operator.neg,
        ast.UAdd: operator.pos,
    }

    @classmethod
    def evaluate(cls, expression: str) -> str:
        """Safely evaluates a mathematical expression without eval()."""
        try:
            # Remove whitespace and validate characters to prevent malicious parsing
            expr_str = expression.strip()
            if not expr_str:
                return "Error: Empty expression."
            
            node = ast.parse(expr_str, mode='eval')
            result = cls._eval(node.body)
            return str(result)
        except Exception as e:
            return f"Error: Invalid or dangerous mathematical expression: {str(e)}"

    @classmethod
    def _eval(cls, node):
        if isinstance(node, ast.Constant):
            if isinstance(node.value, (int, float)):
                return node.value
            raise TypeError(f"Literal type {type(node.value)} not supported")
        elif isinstance(node, ast.BinOp):
            op_type = type(node.op)
            if op_type not in cls.operators:
                raise TypeError(f"Operator {op_type.__name__} not supported")
            left = cls._eval(node.left)
            right = cls._eval(node.right)
            # Prevent DivisionByZero or huge exponent computations (denial of service)
            if op_type == ast.Pow and (right > 1000 or left > 1000):
                raise ValueError("Exponentiation values too large")
            if op_type in (ast.Div, ast.FloorDiv, ast.Mod) and right == 0:
                raise ZeroDivisionError("Division by zero")
            return cls.operators[op_type](left, right)
        elif isinstance(node, ast.UnaryOp):
            op_type = type(node.op)
            if op_type not in cls.operators:
                raise TypeError(f"Unary operator {op_type.__name__} not supported")
            operand = cls._eval(node.operand)
            return cls.operators[op_type](operand)
        else:
            raise TypeError(f"AST node type {type(node).__name__} not supported")

def calculate(expression: str) -> str:
    """Evaluates a mathematical expression safely."""
    return SafeEval.evaluate(expression)

# =====================================================================
# 3. Tool: search_web
# =====================================================================
def search_web(query: str) -> str:
    """Returns top web search results for a query."""
    if not query:
        return "Error: Search query is required."
    
    if DDGS is None:
        return "Error: 'duckduckgo_search' library is not installed."
        
    try:
        results = []
        with DDGS() as ddgs:
            # Fetch text results
            ddgs_generator = ddgs.text(query, max_results=5)
            for r in ddgs_generator:
                results.append(f"Title: {r.get('title')}\nLink: {r.get('href')}\nSnippet: {r.get('body')}\n")
        
        if not results:
            return "No results found."
        return "\n---\n".join(results)
    except Exception as e:
        return f"Error: Exception occurred during web search: {str(e)}"

# =====================================================================
# 4. Tool: read_file
# =====================================================================
def _is_safe_path(path: str) -> bool:
    """Checks if a path is safe to read/write, avoiding directory traversal."""
    abs_path = os.path.abspath(path)
    # Ensure it resides inside the WORKSPACE_ROOT
    return abs_path.startswith(WORKSPACE_ROOT)

def read_file(path: str) -> str:
    """Reads the contents of a local text file and returns it as a string."""
    if not path:
        return "Error: File path is required."
    
    # Clean the path to locate it relative to workspace root if it's a relative path
    target_path = path if os.path.isabs(path) else os.path.join(WORKSPACE_ROOT, path)
    
    if not _is_safe_path(target_path):
        return f"Error: Access denied. Path '{path}' is outside the authorized workspace."
        
    if not os.path.exists(target_path):
        return f"Error: File '{path}' does not exist."
        
    if os.path.isdir(target_path):
        return f"Error: '{path}' is a directory, not a file."
        
    try:
        with open(target_path, 'r', encoding='utf-8') as f:
            return f.read()
    except Exception as e:
        return f"Error: Unable to read file: {str(e)}"

# =====================================================================
# 5. Tool: write_file (Requires HITL Confirmation)
# =====================================================================
# A global variable or callback to handle HITL verification.
# In core loop, if this tool is called, the hook intercepts it.
hitl_callback: Callable[[str, Dict[str, Any]], bool] = None

def write_file(path: str, content: str) -> str:
    """Writes content to a local text file."""
    if not path:
        return "Error: File path is required."
        
    target_path = path if os.path.isabs(path) else os.path.join(WORKSPACE_ROOT, path)
    
    if not _is_safe_path(target_path):
        return f"Error: Access denied. Path '{path}' is outside the authorized workspace."
        
    try:
        # Create directory if it doesn't exist
        os.makedirs(os.path.dirname(target_path), exist_ok=True)
        with open(target_path, 'w', encoding='utf-8') as f:
            f.write(content)
        return f"Success: Content written to '{path}' ({len(content)} characters)."
    except Exception as e:
        return f"Error: Unable to write file: {str(e)}"

# =====================================================================
# Tool Definitions (JSON Schemas) for LLMs
# =====================================================================
TOOL_SCHEMAS = [
    {
        "type": "function",
        "function": {
            "name": "get_weather",
            "description": "Get the current weather conditions for a specific city.",
            "parameters": {
                "type": "object",
                "properties": {
                    "city": {
                        "type": "string",
                        "description": "The name of the city, e.g., 'Tokyo' or 'San Francisco'"
                    }
                },
                "required": ["city"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "calculate",
            "description": "Safely evaluates a mathematical expression. Supports +, -, *, /, **, %, and parentheses.",
            "parameters": {
                "type": "object",
                "properties": {
                    "expression": {
                        "type": "string",
                        "description": "The mathematical expression to evaluate, e.g. '2 * (3 + 4)' or '5**2'"
                    }
                },
                "required": ["expression"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "search_web",
            "description": "Search the web for a query and return snippets of search results.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "The web search query, e.g., 'GitHub Copilot Workspace features'"
                    }
                },
                "required": ["query"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "read_file",
            "description": "Reads the contents of a local text file in the workspace directory.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "The relative path to the file inside the workspace, e.g. 'data.txt'"
                    }
                },
                "required": ["path"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "write_file",
            "description": "Writes text content to a local file in the workspace directory. Requires confirmation.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "The relative path to the file inside the workspace, e.g. 'output.txt'"
                    },
                    "content": {
                        "type": "string",
                        "description": "The content to write into the file"
                    }
                },
                "required": ["path", "content"]
            }
        }
    }
]

# Map names to actual callable Python functions
TOOL_FUNCTIONS: Dict[str, Callable] = {
    "get_weather": get_weather,
    "calculate": calculate,
    "search_web": search_web,
    "read_file": read_file,
    "write_file": write_file
}
