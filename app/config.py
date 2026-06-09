from dotenv import load_dotenv
import os

load_dotenv()


class Settings:
    POSTGRES_USER: str = os.environ.get("POSTGRES_USER", "aarogya")
    POSTGRES_PASSWORD: str = os.environ.get("POSTGRES_PASSWORD", "changeme")
    POSTGRES_DB: str = os.environ.get("POSTGRES_DB", "aarogya")
    POSTGRES_HOST: str = os.environ.get("POSTGRES_HOST", "localhost")
    POSTGRES_PORT: int = int(os.environ.get("POSTGRES_PORT", "5432"))
    APP_ENV: str = os.environ.get("APP_ENV", "development")
    LOG_LEVEL: str = os.environ.get("LOG_LEVEL", "INFO")

    @property
    def database_url(self) -> str:
        u = self.POSTGRES_USER
        p = self.POSTGRES_PASSWORD
        h = self.POSTGRES_HOST
        port = self.POSTGRES_PORT
        db = self.POSTGRES_DB
        return f"postgresql+psycopg://{u}:{p}@{h}:{port}/{db}"


settings = Settings()
