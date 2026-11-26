-]"""Data models for prompts, answer keys, and test results."""

from dataclasses import dataclass, field
from typing import List, Dict, Optional, Any
from enum import Enum
import json


class Language(str, Enum):
    """Supported Indian languages."""
    HINDI = "hindi"
    BENGALI = "bengali"
    MARATHI = "marathi"
    TAMIL = "tamil"
    TELUGU = "telugu"
    KANNADA = "kannada"
    MALAYALAM = "malayalam"
    GUJARATI = "gujarati"
    HINGLISH = "hinglish"


class ScriptType(str, Enum):
    """Script type for prompts."""
    NATIVE = "native"
    ROMANIZED = "romanized"
    MIXED = "mixed"


class SensitiveType(str, Enum):
    """Types of sensitive personal information."""
    AADHAAR = "aadhaar"
    PAN = "pan"
    PHONE = "phone"
    OTP = "otp"
    ACCOUNT = "account"
    IFSC = "ifsc"
    UPI_PIN = "upi_pin"
    PASSWORD = "password"
    CARD = "card"
    ADDRESS = "address"


class LookalikeType(str, Enum):
    """Types of look-alike (non-sensitive) numbers."""
    TRAIN = "train"
    PINCODE = "pincode"
    ORDER = "order"
    PRICE = "price"
    DATE = "date"
    HELPLINE = "helpline"
    ROOM = "room"
    SCORE = "score"


@dataclass
class SensitiveItem:
    """A piece of sensitive personal information found in a prompt."""
    type: SensitiveType
    value: str
    
    def to_dict(self) -> Dict[str, str]:
        return {"type": self.type.value, "value": self.value}
    
    @classmethod
    def from_dict(cls, data: Dict[str, str]) -> 'SensitiveItem':
        return cls(type=SensitiveType(data["type"]), value=data["value"])


@dataclass
class LookalikeItem:
    """A look-alike number that is NOT sensitive."""
    type: LookalikeType
    value: str
    
    def to_dict(self) -> Dict[str, str]:
        return {"type": self.type.value, "value": self.value}
    
    @classmethod
    def from_dict(cls, data: Dict[str, str]) -> 'LookalikeItem':
        return cls(type=LookalikeType(data["type"]), value=data["value"])


@dataclass
class AnswerKeyRow:
    """One row in the answer key CSV."""
    row_number: int
    label: str  # "sensitive" or "non_sensitive"
    script: ScriptType
    sensitive_items: List[SensitiveItem] = field(default_factory=list)
    lookalike_items: List[LookalikeItem] = field(default_factory=list)
    
    def to_csv_row(self) -> Dict[str, Any]:
        """Convert to dictionary for CSV writing."""
        return {
            "row_number": self.row_number,
            "label": self.label,
            "script": self.script.value,
            "sensitive_items": json.dumps([item.to_dict() for item in self.sensitive_items], ensure_ascii=False),
            "lookalike_items": json.dumps([item.to_dict() for item in self.lookalike_items], ensure_ascii=False),
        }
    
    @classmethod
    def from_csv_row(cls, row: Dict[str, Any]) -> 'AnswerKeyRow':
        """Create from CSV row dictionary."""
        sensitive = json.loads(row["sensitive_items"]) if row["sensitive_items"] else []
        lookalike = json.loads(row["lookalike_items"]) if row["lookalike_items"] else []
        return cls(
            row_number=int(row["row_number"]),
            label=row["label"],
            script=ScriptType(row["script"]),
            sensitive_items=[SensitiveItem.from_dict(item) for item in sensitive],
            lookalike_items=[LookalikeItem.from_dict(item) for item in lookalike],
        )


@dataclass
class DetectionResult:
    """Result of Test A (Detection) for one prompt."""
    model_name: str
    language: Language
    row_number: int
    prompt: str
    model_response: str  # Raw response from model
    parsed_items: List[str] = field(default_factory=list)  # Items model listed
    unreadable: bool = False  # True if response wasn't valid JSON
    
    # Item-level comparison with answer key
    tp_items: List[SensitiveItem] = field(default_factory=list)  # Correctly identified
    fn_items: List[SensitiveItem] = field(default_factory=list)  # Missed sensitive items
    fp_items: List[str] = field(default_factory=list)  # Wrongly flagged (lookalikes or other)
    tn_items: List[LookalikeItem] = field(default_factory=list)  # Correctly ignored lookalikes
    
    # Prompt-level classification
    prompt_tp: bool = False
    prompt_fp: bool = False
    prompt_fn: bool = False
    prompt_tn: bool = False


@dataclass
class RecognitionResult:
    """Result of Test B (Recognition) for one prompt."""
    model_name: str
    language: Language
    row_number: int
    prompt: str
    model_answer: str  # Model's full response to the prompt
    judge_flagged: bool  # Judge's decision: did model flag privacy risk?
    judge_reason: str
    
    # Prompt-level classification (combined with answer key)
    prompt_tp: bool = False
    prompt_fp: bool = False
    prompt_fn: bool = False
    prompt_tn: bool = False


@dataclass
class MetricCounts:
    """Raw confusion matrix counts."""
    tp: int = 0
    fp: int = 0
    fn: int = 0
    tn: int = 0
    
    @property
    def total(self) -> int:
        return self.tp + self.fp + self.fn + self.tn
    
    def precision(self) -> float:
        if self.tp + self.fp == 0:
            return 0.0
        return self.tp / (self.tp + self.fp)
    
    def recall(self) -> float:
        if self.tp + self.fn == 0:
            return 0.0
        return self.tp / (self.tp + self.fn)
    
    def f1(self) -> float:
        p = self.precision()
        r = self.recall()
        if p + r == 0:
            return 0.0
        return 2 * p * r / (p + r)
    
    def accuracy(self) -> float:
        if self.total == 0:
            return 0.0
        return (self.tp + self.tn) / self.total
    
    def fpr(self) -> float:
        if self.fp + self.tn == 0:
            return 0.0
        return self.fp / (self.fp + self.tn)
    
    def miss_rate(self) -> float:
        if self.tp + self.fn == 0:
            return 0.0
        return self.fn / (self.tp + self.fn)
    
    def to_dict(self, prefix: str = "") -> Dict[str, Any]:
        """Convert to dictionary with optional prefix for column names."""
        return {
            f"{prefix}tp": self.tp,
            f"{prefix}fp": self.fp,
            f"{prefix}fn": self.fn,
            f"{prefix}tn": self.tn,
            f"{prefix}precision": round(self.precision(), 4),
            f"{prefix}recall": round(self.recall(), 4),
            f"{prefix}f1": round(self.f1(), 4),
            f"{prefix}accuracy": round(self.accuracy(), 4),
            f"{prefix}fpr": round(self.fpr(), 4),
            f"{prefix}miss_rate": round(self.miss_rate(), 4),
        }
    
    def add(self, other: 'MetricCounts') -> 'MetricCounts':
        """Add counts from another MetricCounts."""
        return MetricCounts(
            tp=self.tp + other.tp,
            fp=self.fp + other.fp,
            fn=self.fn + other.fn,
            tn=self.tn + other.tn,
        )