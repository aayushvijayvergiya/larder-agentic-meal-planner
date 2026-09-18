from larder.config import Settings
from larder.llm.base import LLM
from larder.llm.fake import FakeLLM


def get_llm(settings: Settings) -> LLM:
    if settings.llm_provider == "groq":
        from larder.llm.groq import GroqLLM  # imported lazily so the fake path has no langchain import cost

        return GroqLLM(settings)
    return FakeLLM()
