# ReAct AI Agent Studio

A production-grade, highly-extensible ReAct (Reasoning + Acting) AI Agent built in Python. This agent is capable of solving complex, multi-step tasks by dynamically planning, selecting, and executing external tools (web search, weather API, secure AST-based math evaluations, and safe file operations). 

The application offers two interfaces:
1. **Interactive CLI**: Featuring beautiful styled traces (thoughts, tool runs, and results) powered by the `rich` library.
2. **Glassmorphic Web Studio**: A stunning web dashboard (FastAPI + SSE) featuring live-updating execution graphs, visual progress trackers, and real-time Human-in-the-Loop approval popups for file operations.

---

## 🌟 Key Features

- **ReAct Execution Engine**: Alternates reasoning steps (`Thoughts`), tool executions (`Actions`), and response captures (`Observations`) in a loop.
- **Pre-execution Planning Phase**: Performs high-level roadmap creation prior to loop entry to guide the agent towards target goals.
- **Five Specialized Tools**:
  1. **get_weather**: Fetches real-time weather summaries from `wttr.in`.
  2. **calculate**: Safely parses and evaluates mathematical expressions using Python's Abstract Syntax Tree (`ast`), shielding the host from `eval()` injection vulnerabilities.
  3. **search_web**: Searches DuckDuckGo for context retrieval.
  4. **read_file**: Safely reads local files within authorized workspace boundaries, shielding against directory traversal attacks.
  5. **write_file**: Safely writes files inside the workspace boundaries (triggers Human-in-the-Loop check).
- **Human-in-the-Loop (HITL)**: Prompts the operator for approval before committing side-effect actions (like writing files).
- **Self-Healing / Error Recovery**: Passes exceptions and runtime tool failures back to the LLM as observations, allowing it to correct its parameters and retry.
- **API Agnostic**: Supports both **Google Gemini** (using standard or OpenAI-compatible client) and **OpenAI** APIs.

---

## 📂 Project Structure

```
├── agent/
│   ├── __init__.py
│   ├── core.py          # Main ReAct loop engine (run_agent)
│   ├── llm.py           # Unified client wrapping Gemini and OpenAI
│   └── tools.py         # 5 functional tools, schemas, and safety controls
├── web/
│   ├── templates/
│   │   └── index.html   # Glassmorphic dashboard UI
│   └── app.py           # FastAPI server using Server-Sent Events (SSE)
├── tests/
│   ├── test_agent.py       # Unit tests for tools and AST parser
│   └── test_react_loop.py  # Integration tests for ReAct loop steps
├── .env.example         # Template for keys and config
├── requirements.txt     # Third-party dependencies
├── Dockerfile           # App containerization
├── docker-compose.yml   # Multi-container orchestration
├── main.py              # CLI entrypoint
└── README.md            # Documentation
```

---

## 🚀 Setup & Execution

### Prerequisites
- Python 3.12+
- Gemini API Key (or OpenAI API Key)

### Local Development Setup

1. **Clone the Repository** (or enter the workspace):
   ```bash
   cd React-Ai-agent
   ```

2. **Configure Environment Variables**:
   Copy `.env.example` to `.env` and fill in your API key(s):
   ```bash
   cp .env.example .env
   ```
   Open `.env` and enter your preferred provider and API key:
   ```env
   LLM_PROVIDER=gemini
   GEMINI_API_KEY=AIzaSy...
   ```

3. **Initialize Virtual Environment & Install Dependencies**:
   ```bash
   python3 -m venv .venv
   source .venv/bin/activate
   pip install -r requirements.txt
   ```

---

### Running the CLI Mode

Run the CLI tool using Python. You will be prompted to enter a task if none is provided via command-line arguments:

```bash
# Run with interactive terminal prompt
python main.py

# Run with direct argument
python main.py "Find the current weather in Paris and calculate what 5 factorial is."

# Run with custom max-steps limits
python main.py "What is the weather in Tokyo?" --max-steps 5
```

---

### Running the Web Dashboard Mode

Start the FastAPI application:

```bash
python -m uvicorn web.app:app --reload --port 8000
```

Open [http://localhost:8000](http://localhost:8000) in your web browser. 

- Enter a query in the text area (e.g. *"Search the web for what is the capital of France, check its current weather, and write a summary to capital_report.txt"*).
- Watch the agent run step-by-step.
- When the agent tries to write to the file, a **Security Approval Popup** will prompt you to **Approve** or **Deny** the action.

---

### Containerization (Docker)

You can containerize and run the entire Web Dashboard using Docker Compose.

1. **Build and start the container**:
   ```bash
   docker-compose up --build
   ```
2. **Access the Web Dashboard**:
   Go to [http://localhost:8000](http://localhost:8000).

---

## 🧪 Verification & Testing

Verify code correctness and tool safety rules by executing our unit and integration tests:

```bash
python -m unittest discover -s tests
```

---

## 🧠 Example ReAct Flows

### Multi-Tool Sequencing Prompt:
> *"What's the weather in Tokyo, and what is its current temperature squared?"*

1. **Plan**:
   - Call `get_weather` with `Tokyo` to find the current temperature.
   - Extract the numerical value.
   - Call `calculate` with `{temp} ** 2` to square it.
   - Respond with the final answer.
2. **Step 1 (Thought)**: "I need to fetch the weather for Tokyo to get its temperature."
3. **Step 1 (Action)**: Calls `get_weather(city="Tokyo")`.
4. **Step 1 (Observation)**: returns `"Tokyo: 🌡️ +20°C 🌤️ Partly cloudy"`
5. **Step 2 (Thought)**: "The temperature is +20 degrees. I will extract 20 and compute 20 squared."
6. **Step 2 (Action)**: Calls `calculate(expression="20 ** 2")`.
7. **Step 2 (Observation)**: returns `"400"`
8. **Step 3 (Thought)**: "I have the weather and the math calculation complete. I can now write the final output."
9. **Step 3 (Final Response)**: "The weather in Tokyo is +20°C. The temperature squared is 400."
