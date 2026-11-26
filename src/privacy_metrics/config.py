"""Configuration management for the privacy metrics project."""

import yaml
from pathlib import Path
from typing import Dict, Any, List, Optional
from dataclasses import dataclass


@dataclass
class OpenRouterConfig:
    """OpenRouter API configuration."""
    base_url: str
    models: List[Dict[str, str]]  # List of {id, name}


@dataclass
class SarvamConfig:
    """Sarvam API configuration."""
    base_url: str
    model_id: str
    model_name: str


@dataclass
class JudgeConfig:
    """Judge model configuration for Test B."""
    provider: str  # "openrouter" or "sarvam"
    model_id: str
    model_name: str


@dataclass
class DatasetConfig:
    """Dataset generation configuration."""
    languages: List[str]
    prompts_per_language: int
    sensitive_ratio: float
    romanized_ratio: float
    review_sample_ratio: float


@dataclass
class TestConfig:
    """Test execution configuration."""
    detection_instruction: str
    max_concurrent_requests: int
    max_retries: int
    retry_wait_seconds: int
    timeout_seconds: int


@dataclass
class CostConfig:
    """Cost control configuration."""
    budget_usd: float
    openrouter_cost_per_1m: Dict[str, float]
    sarvam_cost_per_1m: Dict[str, float]


@dataclass
class OutputConfig:
    """Output file paths configuration."""
    results_dir: str
    database_file: str
    excel_file: str
    html_report: str
    detection_answers: str
    recognition_answers: str


@dataclass
class Config:
    """Main configuration container."""
    openrouter: OpenRouterConfig
    sarvam: SarvamConfig
    judge: JudgeConfig
    dataset: DatasetConfig
    test: TestConfig
    cost: CostConfig
    output: OutputConfig


class ConfigLoader:
    """Loads and manages configuration from YAML file."""
    
    def __init__(self, config_path: str = "config.yaml"):
        self.config_path = Path(config_path)
        self._config: Optional[Config] = None
    
    def load(self) -> Config:
        """Load configuration from YAML file."""
        if not self.config_path.exists():
            raise FileNotFoundError(f"Config file not found: {self.config_path}")
        
        with open(self.config_path, 'r', encoding='utf-8') as f:
            data = yaml.safe_load(f)
        
        self._config = Config(
            openrouter=OpenRouterConfig(**data['openrouter']),
            sarvam=SarvamConfig(**data['sarvam']),
            judge=JudgeConfig(**data['judge']),
            dataset=DatasetConfig(**data['dataset']),
            test=TestConfig(**data['test']),
            cost=CostConfig(**data['cost']),
            output=OutputConfig(**data['output']),
        )
        return self._config
    
    @property
    def config(self) -> Config:
        """Get loaded config, loading if necessary."""
        if self._config is None:
            return self.load()
        return self._config


# Global config loader instance
config_loader = ConfigLoader()


def get_config() -> Config:
    """Get the global configuration instance."""
    return config_loader.config