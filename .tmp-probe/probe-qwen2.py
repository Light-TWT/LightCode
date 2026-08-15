import sys

sys.path.insert(0, r"d:\works\pycharm-2025.1.1\Object\lightcode-local\backend")

from app.config.model_provider import build_runtime_config, load_model_provider_config
from app.services.chat_service import _build_chat_system_prompt
from app.services.credential_store import WindowsCredentialManagerProviderCredentialStore
from app.services.model_orchestrator import parse_model_message
from app.services.openai_compatible_provider import OpenAICompatibleProvider

store = WindowsCredentialManagerProviderCredentialStore()
cred = store.get()
config = build_runtime_config(load_model_provider_config(), cred)
provider = OpenAICompatibleProvider(config)

system = _build_chat_system_prompt("unknown")
messages = [
    {"role": "system", "content": system},
    {"role": "user", "content": "这个项目用了哪些技术栈？请按协议输出。"},
]
text = provider.chat(messages)
kind, payload = parse_model_message(text)
print("round1 kind:", kind, "| payload:", payload)

# Simulate round 2: assistant tool_request + tool_result -> model answers.
messages.append({"role": "assistant", "content": text})
tool_result = (
    "[tool_result search_files]\nquery: package.json\nhits: 1\n"
    "0. package.json | line 1 | fileToken: abc123 | snippet: {\\\"name\\\":\\\"frontend\\\"}"
)
messages.append({"role": "user", "content": tool_result})
text2 = provider.chat(messages)
print("=== ROUND2 RAW OUTPUT (repr) ===")
print(repr(text2))
print("=== ROUND2 PARSE ===")
print(parse_model_message(text2))
