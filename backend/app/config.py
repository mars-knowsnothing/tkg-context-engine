from pydantic_settings import BaseSettings
from typing import Optional

class Settings(BaseSettings):
    # API Settings
    app_name: str = "TKG Context Engine"
    debug: bool = False
    
    # Database Settings
    database_url: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/tkg_context"
    
    # Redis Settings  
    redis_url: str = "redis://localhost:6379"
    
    # FalkorDB Settings
    falkordb_host: str = "localhost"
    falkordb_port: int = 6380
    falkordb_password: str = "falkordb"
    falkordb_graph_name: str = "tkg_knowledge_graph"
    
    # OpenAI Settings
    openai_api_key: str = "sk-test-dummy-key"
    openai_model: str = "gpt-4"
    
    # Graphiti Settings
    graphiti_llm_provider: str = "openai"
    
    # Security
    secret_key: str = "your-secret-key-change-in-production"
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 30
    
    class Config:
        env_file = ".env"

settings = Settings()