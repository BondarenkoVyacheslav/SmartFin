# LLM (ProxyAPI)

This app is wired to a single provider and a single model:

- Provider: ProxyAPI (OpenAI-compatible)
- Base URL (default): https://api.proxyapi.ru/openai/v1
- Endpoint: /chat/completions
- Fixed model: ChatGPT 5.2 (model_id: gpt-5.2-chat-latest)

Configuration (env):

- PROXY_API_KEY (preferred) or PROXYAPI_KEY
- LLM_PROXYAPI_BASE_URL (optional override)
- LLM_PROXYAPI_TIMEOUT_S (optional, default 30)
- LLM_PROXYAPI_MAX_RETRIES (optional, default 2)
