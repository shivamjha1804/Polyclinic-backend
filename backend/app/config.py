from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    SUPABASE_URL: str
    SUPABASE_ANON_KEY: str
    SUPABASE_SERVICE_KEY: str
    SUPABASE_DB_URL: str

    OPENAI_API_KEY: str
    ASSEMBLYAI_API_KEY: str 
    VOYAGE_API_KEY: str

    LANGFUSE_PUBLIC_KEY: str = ""
    LANGFUSE_SECRET_KEY: str = ""
    LANGFUSE_HOST: str = "https://cloud.langfuse.com"

    MODEL_PRIMARY: str = "gpt-4o"
    MODEL_FAST: str = "gpt-4o-mini"
    EMBED_MODEL: str = "voyage-3"

    ENV: str = "dev"

    INTERNAL_TOKEN: str
    ANALYTICS_DB_URL: str

settings = Settings()
