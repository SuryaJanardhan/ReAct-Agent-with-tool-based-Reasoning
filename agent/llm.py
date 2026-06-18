import os
import json
from typing import List, Dict, Any, Optional
from dotenv import load_dotenv
from openai import OpenAI

# Load environment variables
load_dotenv()

class ToolCall:
    """Represents a tool call requested by the LLM."""
    def __init__(self, name: str, input_args: dict):
        self.name = name
        self.input = input_args

    def __repr__(self):
        return f"ToolCall(name='{self.name}', input={self.input})"

class LLMResponse:
    """Standardized response from the LLM wrapper."""
    def __init__(self, stop_reason: str, content: str, tool_use_block: Optional[ToolCall] = None):
        self.stop_reason = stop_reason  # "end_turn" or "tool_use"
        self.content = content or ""     # The model's thought or reasoning text
        self.tool_use_block = tool_use_block

    def final_text(self) -> str:
        return self.content

    def __repr__(self):
        return f"LLMResponse(stop_reason='{self.stop_reason}', content='{self.content[:40]}...', tool={self.tool_use_block})"


class LLMClient:
    """Unified client wrapper to support OpenAI and Google Gemini."""
    def __init__(self):
        self.provider = os.getenv("LLM_PROVIDER", "gemini").lower()
        
        if self.provider == "openai":
            self.api_key = os.getenv("OPENAI_API_KEY")
            self.model = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
            if not self.api_key:
                raise ValueError("OPENAI_API_KEY environment variable is missing.")
            self.client = OpenAI(api_key=self.api_key)
            
        elif self.provider == "gemini":
            self.api_key = os.getenv("GEMINI_API_KEY")
            self.model = os.getenv("GEMINI_MODEL", "gemini-1.5-flash")
            if not self.api_key:
                raise ValueError("GEMINI_API_KEY environment variable is missing.")
            # Use Gemini's OpenAI compatibility layer
            self.client = OpenAI(
                api_key=self.api_key,
                base_url="https://generativelanguage.googleapis.com/v1beta/openai"
            )
        else:
            # Fallback to check if we can try native Gemini or throw
            raise ValueError(f"Unsupported LLM_PROVIDER '{self.provider}'. Must be 'gemini' or 'openai'.")

    def call(self, messages: List[Dict[str, str]], tools: List[Dict[str, Any]]) -> LLMResponse:
        """Sends chat history and tool schemas to the LLM and parses the response."""
        try:
            # Format tools for the OpenAI schema
            formatted_tools = []
            for t in tools:
                formatted_tools.append({
                    "type": "function",
                    "function": {
                        "name": t["function"]["name"],
                        "description": t["function"]["description"],
                        "parameters": t["function"]["parameters"]
                    }
                })

            # Call the completion API
            response = self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                tools=formatted_tools if formatted_tools else None,
                tool_choice="auto" if formatted_tools else None,
                temperature=0.2  # Lower temperature for more deterministic tool usage
            )

            message = response.choices[0].message
            content = message.content or ""
            
            # Check if there is a tool call request
            if message.tool_calls:
                tool_call_info = message.tool_calls[0].function
                tool_name = tool_call_info.name
                
                try:
                    tool_args = json.loads(tool_call_info.arguments)
                except json.JSONDecodeError:
                    tool_args = {}
                    
                tool_call = ToolCall(name=tool_name, input_args=tool_args)
                return LLMResponse(
                    stop_reason="tool_use",
                    content=content,
                    tool_use_block=tool_call
                )
            
            # If no tool calls, it is a final response
            return LLMResponse(
                stop_reason="end_turn",
                content=content
            )

        except Exception as e:
            # Return a graceful error inside an LLMResponse
            raise RuntimeError(f"LLM API Call failed: {str(e)}")
