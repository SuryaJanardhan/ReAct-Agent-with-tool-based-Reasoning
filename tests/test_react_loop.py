import unittest
from unittest.mock import patch, MagicMock
from agent.core import run_agent, AgentEventHandler
from agent.llm import LLMResponse, ToolCall

class MockEventHandler(AgentEventHandler):
    def __init__(self):
        self.plan_created = None
        self.steps = []
        self.thoughts = []
        self.actions = []
        self.observations = []
        self.completed = None
        self.timed_out = False
        self.errors = []
        self.hitl_count = 0

    def on_plan_created(self, plan: str):
        self.plan_created = plan

    def on_step_start(self, step: int, max_steps: int):
        self.steps.append(step)

    def on_thought(self, step: int, thought: str):
        self.thoughts.append((step, thought))

    def on_action(self, step: int, tool_name: str, tool_input: dict):
        self.actions.append((step, tool_name, tool_input))

    def on_hitl_request(self, tool_name: str, tool_input: dict) -> bool:
        self.hitl_count += 1
        return True  # Auto approve

    def on_observation(self, step: int, observation: str):
        self.observations.append((step, observation))

    def on_complete(self, final_answer: str):
        self.completed = final_answer

    def on_timeout(self, max_steps: int):
        self.timed_out = True

    def on_error(self, error_msg: str):
        self.errors.append(error_msg)


class TestReactLoop(unittest.TestCase):

    @patch('agent.core.LLMClient')
    def test_react_loop_successful_sequence(self, MockLLMClient):
        # Setup mock client responses
        mock_instance = MockLLMClient.return_value
        
        # Sequence of mocked responses from LLM
        # 1. Planning call (step=0): returns plan text
        # 2. Step 1 call: returns get_weather tool call
        # 3. Step 2 call: returns calculate tool call
        # 4. Step 3 call: returns final answer
        mock_instance.call.side_effect = [
            LLMResponse(stop_reason="end_turn", content="Plan: 1. Get weather for Tokyo. 2. Calculate degrees warmer."),
            LLMResponse(stop_reason="tool_use", content="I will fetch weather for Tokyo first.", 
                        tool_use_block=ToolCall(name="get_weather", input_args={"city": "Tokyo"})),
            LLMResponse(stop_reason="tool_use", content="Now I will compute the math calculation.", 
                        tool_use_block=ToolCall(name="calculate", input_args={"expression": "20 + 5"})),
            LLMResponse(stop_reason="end_turn", content="The final temperature is 25 degrees.")
        ]

        handler = MockEventHandler()
        result = run_agent(
            task="Find weather in Tokyo and add 5.",
            max_steps=5,
            enable_planning=True,
            event_handler=handler
        )

        # Check results
        self.assertEqual(result, "The final temperature is 25 degrees.")
        self.assertEqual(handler.plan_created, "Plan: 1. Get weather for Tokyo. 2. Calculate degrees warmer.")
        self.assertEqual(len(handler.steps), 4)  # step 0 (planning), step 1, step 2, step 3
        self.assertEqual(handler.steps, [0, 1, 2, 3])
        self.assertEqual(handler.completed, "The final temperature is 25 degrees.")
        self.assertEqual(len(handler.errors), 0)

        # Verify calls
        self.assertEqual(mock_instance.call.call_count, 4)

    @patch('agent.core.LLMClient')
    def test_react_loop_max_steps_timeout(self, MockLLMClient):
        # Setup mock client returning tool calls indefinitely to trigger timeout
        mock_instance = MockLLMClient.return_value
        mock_instance.call.return_value = LLMResponse(
            stop_reason="tool_use",
            content="Thinking...",
            tool_use_block=ToolCall(name="calculate", input_args={"expression": "2+2"})
        )

        handler = MockEventHandler()
        result = run_agent(
            task="Infinite loops testing.",
            max_steps=3,
            enable_planning=False,
            event_handler=handler
        )

        # Verify timeout occurred
        self.assertTrue(handler.timed_out)
        self.assertIn("Max steps", result)
        self.assertEqual(handler.steps, [1, 2, 3])
        self.assertIsNone(handler.completed)

if __name__ == "__main__":
    unittest.main()
