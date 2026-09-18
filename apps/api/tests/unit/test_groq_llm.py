from larder.config import Settings
from larder.llm.factory import get_llm

DB = "postgresql+asyncpg://x"


def test_factory_picks_fake_without_key():
    s = Settings(database_url=DB, groq_api_key="", llm_provider=None)
    assert s.llm_provider == "fake"
    assert get_llm(s).name == "fake"


def test_factory_picks_groq_with_key():
    s = Settings(database_url=DB, groq_api_key="k", llm_provider=None)
    assert s.llm_provider == "groq"
    assert get_llm(s).name == "groq:openai/gpt-oss-120b"


def test_checkpoint_url_is_derived():
    s = Settings(database_url="postgresql+asyncpg://u:p@h:5432/db")
    assert s.checkpoint_database_url == "postgresql://u:p@h:5432/db"
