import json
from typing import Dict, Any, List, Callable, Optional
from agent.llm import LLMClient, LLMResponse, ToolCall
from agent.tools import TOOL_SCHEMAS, TOOL_FUNCTIONS

SYSTEM_PROMPT = """You are a highly capable ReAct (Reasoning + Acting) AI Agent.
Your goal is to solve the user's task by reasoning step-by-step and executing external tools.

Process:
1. Analyze the task and make a plan.
2. In each step:
   - Formulate a Thought: Explain what you are doing, what you have learned, and why you need a tool.
   - Take an Action: Request a tool call with precise arguments.
   - Receive an Observation: The agent system will run the tool and show you the result.
3. Use the observations to refine your thoughts and actions.
4. When you have successfully completed the task, output the final answer directly without calling any tools.

Guidelines:
- Error Recovery: If a tool call fails, analyze the error message in the Observation, correct your parameters (e.g. fix spelling, correct math expressions), and try again or use a different tool.
- Do not make up information; always rely on tool observations where needed.
- If you cannot complete the task, explain why in your final response.
"""

class AgentEventHandler:
    """Interface for handling real-time execution events."""
    def on_plan_created(self, plan: str):
        pass

    def on_step_start(self, step: int, max_steps: int):
        pass

    def on_thought(self, step: int, thought: str):
        pass

    def on_action(self, step: int, tool_name: str, tool_input: dict):
        pass

    def on_hitl_request(self, tool_name: str, tool_input: dict) -> bool:
        """Return True to proceed, False to abort."""
        return True

    def on_observation(self, step: int, observation: str):
        pass

    def on_complete(self, final_answer: str):
        pass

    def on_timeout(self, max_steps: int):
        pass

    def on_error(self, error_msg: str):
        pass


def run_agent(
    task: str,
    max_steps: int = 10,
    enable_planning: bool = True,
    event_handler: Optional[AgentEventHandler] = None
) -> str:
    """Runs the ReAct agent loop for a given task."""
    handler = event_handler or AgentEventHandler()
    
    try:
        # Initialize client
        llm = LLMClient()
    except Exception as e:
        error_msg = f"Failed to initialize LLM client: {str(e)}"
        handler.on_error(error_msg)
        return error_msg

    # Prepare chat history
    messages: List[Dict[str, str]] = [
        {"role": "system", "content": SYSTEM_PROMPT}
    ]

    # --- STRETCH GOAL: Planning Step ---
    if enable_planning:
        try:
            handler.on_step_start(0, max_steps)
            plan_prompt = (
                f"You are preparing to solve this task: '{task}'\n"
                f"Create a high-level step-by-step plan detailing what tools you will use and "
                f"what you need to discover. Output ONLY the plan."
            )
            plan_response = llm.call(
                messages=[
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": plan_prompt}
                ],
                tools=[]  # No tools for planning, just generate text
            )
            plan = plan_response.final_text()
            handler.on_plan_created(plan)
            # Add plan to conversation history so the agent remembers its goal
            messages.append({"role": "user", "content": f"Here is the plan we will follow:\n{plan}\n\nTask: {task}"})
        except Exception as e:
            handler.on_error(f"Planning step failed: {str(e)}. Continuing without plan...")
            messages.append({"role": "user", "content": task})
    else:
        messages.append({"role": "user", "content": task})

    # --- ReAct Execution Loop ---
    for step in range(1, max_steps + 1):
        handler.on_step_start(step, max_steps)
        
        try:
            # Call LLM with the tool definitions and conversation history
            response = llm.call(messages, tools=TOOL_SCHEMAS)
        except Exception as e:
            error_msg = f"LLM Error at Step {step}: {str(e)}"
            handler.on_error(error_msg)
            return error_msg

        # Extract thought if present
        thought = response.content.strip()
        if thought:
            handler.on_thought(step, thought)

        # Decision Point: Final Answer (end_turn) vs Action (tool_use)
        if response.stop_reason == "end_turn":
            final_answer = response.final_text()
            handler.on_complete(final_answer)
            return final_answer

        elif response.stop_reason == "tool_use":
            tool_call = response.tool_use_block
            if not tool_call:
                error_msg = "Error: stop_reason was tool_use but no tool_use_block found."
                handler.on_error(error_msg)
                return error_msg

            handler.on_action(step, tool_call.name, tool_call.input)

            # Check for HITL (Human-in-the-loop) side-effect confirmation
            # write_file is a side-effect tool
            proceed = True
            if tool_call.name == "write_file":
                proceed = handler.on_hitl_request(tool_call.name, tool_call.input)

            if not proceed:
                observation = "Observation: Action cancelled by user."
                handler.on_observation(step, observation)
                
                # Format response for the next turn
                # Construct mock assistant messages containing the call details
                assistant_msg = {
                    "role": "assistant",
                    "content": response.content or "Let me call the tool.",
                    "tool_calls": [
                        {
                            "id": f"call_{step}",
                            "type": "function",
                            "function": {
                                "name": tool_call.name,
                                "arguments": json.dumps(tool_call.input)
                            }
                        }
                    ]
                }
                messages.append(assistant_msg)
                
                # Append observation
                messages.append({
                    "role": "tool",
                    "tool_call_id": f"call_{step}",
                    "name": tool_call.name,
                    "content": "Error: Tool execution cancelled by user confirmation."
                })
                continue

            # Execute the tool
            observation = ""
            if tool_call.name not in TOOL_FUNCTIONS:
                observation = f"Error: Tool '{tool_call.name}' is not registered."
            else:
                try:
                    # Run target tool
                    func = TOOL_FUNCTIONS[tool_call.name]
                    # Pass argument dictionary using unpacking
                    observation = func(**tool_call.input)
                except TypeError as te:
                    observation = f"Error: Incorrect arguments for tool '{tool_call.name}'. {str(te)}"
                except Exception as e:
                    observation = f"Error: Tool execution failed: {str(e)}"

            handler.on_observation(step, observation)

            # Append the assistant response with tool call metadata
            assistant_msg = {
                "role": "assistant",
                "content": response.content or "",
                "tool_calls": [
                    {
                        "id": f"call_{step}",
                        "type": "function",
                        "function": {
                            "name": tool_call.name,
                            "arguments": json.dumps(tool_call.input)
                        }
                    }
                ]
            }
            messages.append(assistant_msg)

            # Append the observation response
            messages.append({
                "role": "tool",
                "tool_call_id": f"call_{step}",
                "name": tool_call.name,
                "content": observation
            })

    # If loop completes without stop_reason = end_turn, we timed out
    handler.on_timeout(max_steps)
    return f"Max steps ({max_steps}) reached without completing the task."
