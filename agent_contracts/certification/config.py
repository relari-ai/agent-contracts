from os import getenv
from pathlib import Path

import yaml
from loguru import logger
from pydantic import BaseModel


class RabbitMQSettings(BaseModel):
    host: str = "localhost"
    port: int = 5672
    username: str
    password: str

    @property
    def url(self):
        return f"amqp://{self.username}:{self.password}@{self.host}:{self.port}"


class RedisSettings(BaseModel):
    host: str = "localhost"
    port: int = 6379
    db: int = 0
    password: str = None

    @property
    def url(self):
        return f"redis://{self.host}:{self.port}/{self.db}"


class KafkaSettings(BaseModel):
    broker: str = "localhost:9094"
    group_id: str = "jaeger-consumer-group"
    topic: str = "jaeger-spans"
    auto_offset_reset: str = "earliest"
    fetch_wait_max_ms: int = 50
    fetch_error_backoff_ms: int = 50
    socket_timeout_ms: int = 1100
    session_timeout_ms: int = 6000
    auto_commit: bool = True

    def to_confluent_config(self):
        return {
            "bootstrap.servers": self.broker,
            "group.id": self.group_id,
            "auto.offset.reset": self.auto_offset_reset,
            "fetch.wait.max.ms": self.fetch_wait_max_ms,
            "fetch.error.backoff.ms": self.fetch_error_backoff_ms,
            "socket.timeout.ms": self.socket_timeout_ms,
            "session.timeout.ms": self.session_timeout_ms,
            "enable.auto.commit": self.auto_commit,
        }


class Settings(BaseModel):
    debug: bool = False
    specifications: str
    kafka: KafkaSettings
    # rabbitmq: RabbitMQSettings
    redis: RedisSettings
    ttl: int = 60 * 10  # 10 minutes
    key: str = "certificates"

    def model_post_init(self, __context):
        override_specs = getenv("RUNTIME_VERIFICATION_SPECS", None)
        if override_specs:
            logger.info(f"Overriding specifications with {override_specs}")
            self.specifications = override_specs

    @classmethod
    def from_yaml(cls, file_path: str) -> "Settings":
        logger.info(f"Loading runtime verification config from {file_path}")
        with Path(file_path).open() as f:
            config_data = yaml.safe_load(f)
        return cls(**config_data)


__RUNTIME_VERIFICATION_CONFIG = getenv("RUNTIME_VERIFICATION_CONFIG", None)
if not __RUNTIME_VERIFICATION_CONFIG:
    raise RuntimeError(
        "Runtime Verification Config is not set, set the environment variable RUNTIME_VERIFICATION_CONFIG"
    )
RuntimeVerificationConfig = Settings.from_yaml(__RUNTIME_VERIFICATION_CONFIG)
