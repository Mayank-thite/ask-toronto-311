import os

ADMIN_DSN = os.getenv("ADMIN_DSN", "postgresql://ask311:ask311@localhost:5432/toronto311")
AGENT_DSN = os.getenv("AGENT_DSN", "postgresql://agent_ro:agent_ro@localhost:5432/toronto311")

# Any OpenAI-compatible chat endpoint works: Ollama, llama.cpp server, vLLM, OpenAI, etc.
LLM_BASE_URL = os.getenv("LLM_BASE_URL", "http://localhost:11434/v1")   # Ollama default
LLM_MODEL = os.getenv("LLM_MODEL", "qwen2.5-coder:7b")
LLM_API_KEY = os.getenv("LLM_API_KEY", "not-needed-for-local")
