import os
from dotenv import load_dotenv

load_dotenv()


class Config:
    RAPIDAPI_KEY: str = os.getenv("RAPIDAPI_KEY", "")
    PROXYCURL_API_KEY: str = os.getenv("PROXYCURL_API_KEY", "")
    SERPAPI_KEY: str = os.getenv("SERPAPI_KEY", "")
    PRODUCTHUNT_API_TOKEN: str = os.getenv("PRODUCTHUNT_API_TOKEN", "")
    DATABASE_URL: str = os.getenv("DATABASE_URL", "sqlite:///founders.db")
    MIN_SCORE_THRESHOLD: int = int(os.getenv("MIN_SCORE_THRESHOLD", "40"))
    # Must be explicitly set to "true" to protect limited SerpAPI quota
    GOOGLE_DORKER_ENABLED: bool = os.getenv("GOOGLE_DORKER_ENABLED", "false").lower() == "true"
    # Cross-platform profile lookup for HN/PH founders (also uses SerpAPI quota)
    SOCIAL_LOOKUP_ENABLED: bool = os.getenv("SOCIAL_LOOKUP_ENABLED", "false").lower() == "true"

    # Derived: path for SQLite file
    @property
    def sqlite_path(self) -> str:
        url = self.DATABASE_URL
        if url.startswith("sqlite:///"):
            return url[len("sqlite:///"):]
        return "founders.db"


config = Config()
