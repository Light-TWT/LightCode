import sys

sys.path.insert(0, r"d:\works\pycharm-2025.1.1\Object\lightcode-local\backend")

from app.config.model_provider import build_runtime_config, load_model_provider_config
from app.services.chat_service import _build_chat_system_prompt
from app.services.credential_store import WindowsCredentialManagerProviderCredentialStore
from app.services.model_orchestrator import parse_model_message
from app.services.openai_compatible_provider import OpenAICompatibleProvider

store = WindowsCredentialManagerProviderCredentialStore()
cred = store.get()
print("credential:", cred.provider, "|", cred.model_id, "|", cred.base_url, "| has_key:", bool(cred.api_key))

env_config = load_model_provider_config()
config = build_runtime_config(env_config, cred)
print("config status:", config.status())
print("origin allowlisted:", config.origin_allowlisted)

provider = OpenAICompatibleProvider(config)
messages = [
    {"role": "system", "content": _build_chat_system_prompt("unknown")},
    {"role": "user", "content": "这个项目的技术栈是什么？请按协议输出。"},
]
text = provider.chat(messages)
print("=== RAW OUTPUT (repr) ===")
print(repr(text))
print("=== PARSE ===")
print(parse_model_message(text))
