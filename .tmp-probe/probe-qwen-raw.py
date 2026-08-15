import sys

sys.path.insert(0, r"d:\works\pycharm-2025.1.1\Object\lightcode-local\backend")

from app.config.model_provider import build_runtime_config, load_model_provider_config
from app.services.chat_service import _build_chat_system_prompt
from app.services.credential_store import WindowsCredentialManagerProviderCredentialStore
from app.services.openai_compatible_provider import OpenAICompatibleProvider, _to_langchain_messages

store = WindowsCredentialManagerProviderCredentialStore()
cred = store.get()
config = build_runtime_config(load_model_provider_config(), cred)
provider = OpenAICompatibleProvider(config)
llm = provider._llm_client()

system = _build_chat_system_prompt("unknown")
messages = [
    {"role": "system", "content": system},
    {"role": "user", "content": "这个项目的技术栈是什么？请按协议输出。"},
]
ai = llm.invoke(_to_langchain_messages(messages))
print("content type:", type(ai.content).__name__)
print("content repr :", repr(ai.content)[:500])
print("additional_kwargs keys:", list((ai.additional_kwargs or {}).keys()))
print("response_metadata keys:", list((ai.response_metadata or {}).keys()))
