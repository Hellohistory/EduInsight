# app/core/config.py

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # 通过 model_config 指定从 .env 文件读取
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # DeepSeek API 配置
    DEEPSEEK_API_KEY: str
    DEEPSEEK_MODEL: str = "deepseek-chat"
    DEEPSEEK_BASE_URL: str = "https://api.deepseek.com"

    # 可以在这里添加其他项目配置，例如数据库URL等
    # DATABASE_URL: str


# 创建一个全局可用的配置实例
settings = Settings()