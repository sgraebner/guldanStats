
from __future__ import annotations
import json, os
from pydantic_settings import BaseSettings
from pydantic import Field, field_validator
from typing import List, Optional, Any

class ShopwareInstance(BaseSettings):
    name: str
    base_url: str
    client_id: str
    client_secret: str

class AmazonAccount(BaseSettings):
    name: str
    region: str  # 'eu', 'na', 'fe'
    marketplace_ids: str  # comma separated
    lwa_client_id: str
    lwa_client_secret: str
    refresh_token: str
    role_arn: str

class EbayAccount(BaseSettings):
    name: str
    environment: str  # 'production' or 'sandbox'
    app_id: str
    cert_id: str
    redirect_uri: str
    refresh_token: str

class Settings(BaseSettings):
    ENV: str = "production"
    TZ: str = "Europe/Berlin"

    RUN_HOUR: int = 3
    RUN_MINUTE: int = 30
    BACKFILL_DAYS: int = 90

    GOOGLE_SPREADSHEET_ID: str
    GOOGLE_SHEET_TAB: str = "Tägliche Kennzahlen"
    GOOGLE_SERVICE_ACCOUNT_JSON: Optional[str] = None
    GOOGLE_SERVICE_ACCOUNT_FILE: Optional[str] = None

    OPENAI_API_KEY: str
    OPENAI_MODEL: str = "gpt-5-nano"

    ALERT_EMAIL_TO: Optional[str] = None
    ALERT_EMAIL_FROM: Optional[str] = None
    SMTP_HOST: Optional[str] = None
    SMTP_PORT: int = 587
    SMTP_USER: Optional[str] = None
    SMTP_PASSWORD: Optional[str] = None
    SMTP_USE_TLS: bool = True

    SHOPWARE6_INSTANCES: List[ShopwareInstance] = Field(default_factory=list)
    GETMYINVOICES_API_KEY: Optional[str] = None

    GOOGLE_ADS_DEVELOPER_TOKEN: Optional[str] = None
    GOOGLE_ADS_CLIENT_ID: Optional[str] = None
    GOOGLE_ADS_CLIENT_SECRET: Optional[str] = None
    GOOGLE_ADS_REFRESH_TOKEN: Optional[str] = None
    GOOGLE_ADS_CUSTOMER_IDS: Optional[str] = None  # comma list

    AMAZON_ACCOUNTS: List[AmazonAccount] = Field(default_factory=list)

    EBAY_ACCOUNTS: List[EbayAccount] = Field(default_factory=list)

    @field_validator("SHOPWARE6_INSTANCES", mode="before")
    @classmethod
    def parse_sw6(cls, v: Any):
        if isinstance(v, str):
            return json.loads(v)
        return v

    @field_validator("AMAZON_ACCOUNTS", mode="before")
    @classmethod
    def parse_amz(cls, v: Any):
        if isinstance(v, str):
            return json.loads(v)
        return v

    @field_validator("EBAY_ACCOUNTS", mode="before")
    @classmethod
    def parse_ebay(cls, v: Any):
        if isinstance(v, str):
            return json.loads(v)
        return v

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = False
