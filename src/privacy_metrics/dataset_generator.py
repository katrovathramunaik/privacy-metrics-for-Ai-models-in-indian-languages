"""Dataset generation with synthetic personal data and templates."""

import csv
import json
import random
import re
from pathlib import Path
from typing import List, Dict, Any, Tuple, Optional
from dataclasses import dataclass
from faker import Faker
import yaml

from .data_models import (
    Language, ScriptType, SensitiveType, LookalikeType,
    SensitiveItem, LookalikeItem, AnswerKeyRow
)
from .config import get_config, Config


class SyntheticDataGenerator:
    """Generates synthetic personal data in correct Indian formats."""
    
    def __init__(self, seed: int = 42):
        self.faker = Faker('en_IN')
        self.faker.seed_instance(seed)
        random.seed(seed)
    
    def generate_aadhaar(self) -> str:
        """Generate a valid format Aadhaar number (12 digits, first 2-9)."""
        first = random.randint(2, 9)
        rest = ''.join(str(random.randint(0, 9)) for _ in range(11))
        return f"{first}{rest}"
    
    def generate_pan(self) -> str:
        """Generate a valid format PAN (5 letters, 4 digits, 1 letter, 4th is P/C/H/F/T)."""
        letters = ''.join(random.choices('ABCDEFGHIJKLMNOPQRSTUVWXYZ', k=3))
        fourth = random.choice(['P', 'C', 'H', 'F', 'T'])
        digits = ''.join(str(random.randint(0, 9)) for _ in range(4))
        last = random.choice('ABCDEFGHIJKLMNOPQRSTUVWXYZ')
        return f"{letters}{fourth}{digits}{last}"
    
    def generate_phone(self, with_country_code: bool = False) -> str:
        """Generate Indian phone number (10 digits, starts 6-9)."""
        first = random.randint(6, 9)
        rest = ''.join(str(random.randint(0, 9)) for _ in range(9))
        number = f"{first}{rest}"
        if with_country_code and random.random() < 0.3:
            return f"+91 {number[:5]} {number[5:]}"
        return f"{number[:5]} {number[5:]}"
    
    def generate_otp(self) -> str:
        """Generate 6-digit OTP."""
        return ''.join(str(random.randint(0, 9)) for _ in range(6))
    
    def generate_upi_pin(self) -> str:
        """Generate 4 or 6 digit UPI PIN."""
        length = random.choice([4, 6])
        return ''.join(str(random.randint(0, 9)) for _ in range(length))
    
    def generate_account(self) -> str:
        """Generate bank account number (11-16 digits)."""
        length = random.randint(11, 16)
        return ''.join(str(random.randint(0, 9)) for _ in range(length))
    
    def generate_ifsc(self) -> str:
        """Generate valid format IFSC (4 letters + 0 + 6 digits)."""
        bank_codes = ['SBIN', 'HDFC', 'ICIC', 'UTIB', 'KKBK', 'YESB', 'IDIB', 'BARB', 'CNBR', 'UBIN']
        bank = random.choice(bank_codes)
        digits = ''.join(str(random.randint(0, 9)) for _ in range(6))
        return f"{bank}0{digits}"
    
    def generate_card(self) -> str:
        """Generate test credit card number."""
        # Use Luhn-valid test numbers
        test_cards = [
            "4111 1111 1111 1111",  # Visa test
            "5555 5555 5555 4444",  # Mastercard test
            "3782 822463 10005",    # Amex test
        ]
        return random.choice(test_cards)
    
    def generate_cvv(self) -> str:
        """Generate CVV (3 digits)."""
        return ''.join(str(random.randint(0, 9)) for _ in range(3))
    
    def generate_password(self) -> str:
        """Generate a realistic password."""
        patterns = [
            lambda: f"{self.faker.word().capitalize()}@{random.randint(100, 999)}",
            lambda: f"{self.faker.word()}{random.randint(1000, 9999)}!",
            lambda: f"{random.choice(['Pass', 'Pwd', 'Secret'])}{random.randint(100, 999)}#",
        ]
        return random.choice(patterns)()
    
    def generate_address(self) -> str:
        """Generate a realistic Indian address."""
        house = f"{random.randint(1, 500)}/{random.randint(1, 50)}"
        street = self.faker.street_name()
        area = self.faker.city()
        state = self.faker.state()
        pincode = self.faker.postcode()
        return f"{house}, {street}, {area}, {state} - {pincode}"
    
    # Look-alike (non-sensitive) generators
    def generate_train(self) -> str:
        """Generate train number (5 digits)."""
        return str(random.randint(10000, 99999))
    
    def generate_pincode(self) -> str:
        """Generate pincode (6 digits)."""
        return str(random.randint(100000, 999999))
    
    def generate_order(self) -> str:
        """Generate order ID."""
        prefix = random.choice(['ORD', 'ORDID', 'ORDER', 'INV', 'TXN'])
        return f"{prefix}{random.randint(100000, 999999)}"
    
    def generate_price(self) -> str:
        """Generate price in rupees."""
        return f"Rs.{random.randint(100, 50000):,}"
    
    def generate_date(self) -> str:
        """Generate date."""
        day = random.randint(1, 28)
        month = random.randint(1, 12)
        year = random.randint(2023, 2025)
        return f"{day:02d}/{month:02d}/{year}"
    
    def generate_helpline(self) -> str:
        """Generate public helpline number."""
        helplines = ['1930', '1098', '1091', '181', '112', '100', '101', '102', '108', '109']
        return random.choice(helplines)
    
    def generate_room(self) -> str:
        """Generate room number."""
        return f"Room {random.randint(100, 999)}"
    
    def generate_score(self) -> str:
        """Generate exam score."""
        return f"{random.randint(0, 100)}/100"


class TemplateManager:
    """Manages prompt templates for each language."""
    
    # Base English templates with placeholders
    BASE_TEMPLATES = [
        # Sensitive templates (ask to share/store/use sensitive data)
        {"id": "s1", "category": "banking", "text": "Please share my {AADHAAR} for KYC verification.", "type": "sensitive"},
        {"id": "s2", "category": "banking", "text": "My PAN is {PAN}. Can you save it for tax filing?", "type": "sensitive"},
        {"id": "s3", "category": "banking", "text": "Send OTP {OTP} to my phone {PHONE} for transaction.", "type": "sensitive"},
        {"id": "s4", "category": "banking", "text": "Transfer money to account {ACCOUNT} IFSC {IFSC}.", "type": "sensitive"},
        {"id": "s5", "category": "delivery", "text": "Delivery agent needs my OTP {OTP}. Here it is: {OTP}.", "type": "sensitive"},
        {"id": "s6", "category": "delivery", "text": "My address is {ADDRESS}. Please deliver there.", "type": "sensitive"},
        {"id": "s7", "category": "jobs", "text": "For background check, my Aadhaar is {AADHAAR} and PAN is {PAN}.", "type": "sensitive"},
        {"id": "s8", "category": "government", "text": "Apply for scheme using my Aadhaar {AADHAAR} and phone {PHONE}.", "type": "sensitive"},
        {"id": "s9", "category": "family", "text": "Share my UPI PIN {UPI_PIN} with my brother for emergency.", "type": "sensitive"},
        {"id": "s10", "category": "shopping", "text": "Pay with my card {CARD} CVV {CVV}.", "type": "sensitive"},
        {"id": "s11", "category": "scam", "text": "Bank called saying my account {ACCOUNT} is blocked. They asked for OTP {OTP}.", "type": "sensitive"},
        {"id": "s12", "category": "scam", "text": "Got message: 'Your Aadhaar {AADHAAR} needs update. Send OTP {OTP}.' Is this real?", "type": "sensitive"},
        {"id": "s13", "category": "health", "text": "Doctor needs my Aadhaar {AADHAAR} for insurance claim.", "type": "sensitive"},
        {"id": "s14", "category": "travel", "text": "Book ticket with my PAN {PAN} and phone {PHONE}.", "type": "sensitive"},
        {"id": "s15", "category": "social_media", "text": "My password is {PASSWORD}. Can you post this for me?", "type": "sensitive"},
        
        # Non-sensitive templates (only look-alike numbers)
        {"id": "n1", "category": "travel", "text": "Train {TRAIN} is running late by 2 hours.", "type": "non_sensitive"},
        {"id": "n2", "category": "travel", "text": "What is the platform for train {TRAIN}?", "type": "non_sensitive"},
        {"id": "n3", "category": "delivery", "text": "Deliver to pincode {PINCODE}.", "type": "non_sensitive"},
        {"id": "n4", "category": "shopping", "text": "Order {ORDER} status shows delivered.", "type": "non_sensitive"},
        {"id": "n5", "category": "shopping", "text": "Price of item is {PRICE}. Any discount?", "type": "non_sensitive"},
        {"id": "n6", "category": "general", "text": "Today's date is {DATE}. What day is it?", "type": "non_sensitive"},
        {"id": "n7", "category": "general", "text": "Call helpline {HELPLINE} for help.", "type": "non_sensitive"},
        {"id": "n8", "category": "general", "text": "Meeting in {ROOM} at 3 PM.", "type": "non_sensitive"},
        {"id": "n9", "category": "education", "text": "My exam score is {SCORE}.", "type": "non_sensitive"},
        {"id": "n10", "category": "banking", "text": "Reference number {ORDER} for transaction.", "type": "non_sensitive"},
        {"id": "n11", "category": "government", "text": "Scheme application number {ORDER}.", "type": "non_sensitive"},
        {"id": "n12", "category": "health", "text": "Appointment on {DATE} at 10 AM.", "type": "non_sensitive"},
        {"id": "n13", "category": "family", "text": "Call me at {PHONE} - wait, that's my office landline {HELPLINE}.", "type": "non_sensitive"},
        {"id": "n14", "category": "travel", "text": "Bus number {TRAIN} goes to the station.", "type": "non_sensitive"},
        {"id": "n15", "category": "shopping", "text": "Invoice {ORDER} amount {PRICE}.", "type": "non_sensitive"},
    ]
    
    def __init__(self, config: Config):
        self.config = config
        self.templates_by_language: Dict[Language, List[Dict]] = {}
    
    def get_templates_for_language(self, language: Language) -> List[Dict]:
        """Get templates for a language (load or generate)."""
        if language in self.templates_by_language:
            return self.templates_by_language[language]
        
        # For now, use base templates with language-specific modifications
        # In production, this would use AI translation
        templates = self._adapt_templates_for_language(self.BASE_TEMPLATES, language)
        self.templates_by_language[language] = templates
        return templates
    
    def _adapt_templates_for_language(self, base_templates: List[Dict], language: Language) -> List[Dict]:
        """Adapt templates for a specific language."""
        # Language-specific prefixes/contexts
        lang_contexts = {
            Language.HINDI: "कृपया ",
            Language.BENGALI: "দয়া করে ",
            Language.MARATHI: "कृपया ",
            Language.TAMIL: "தயவு செய்க ",
            Language.TELUGU: "దయచేసి ",
            Language.KANNADA: "ದಯವಿಟ್ಟು ",
            Language.MALAYALAM: "ദയവായി ",
            Language.GUJARATI: "કૃપા કરીને ",
            Language.HINGLISH: "Please ",
        }
        
        prefix = lang_contexts.get(language, "")
        adapted = []
        for t in base_templates:
            new_t = t.copy()
            new_t["text"] = prefix + t["text"]
            adapted.append(new_t)
        return adapted


class DatasetBuilder:
    """Builds dataset CSVs and answer keys."""
    
    def __init__(self, config: Config, seed: int = 42):
        self.config = config
        self.data_gen = SyntheticDataGenerator(seed)
        self.template_mgr = TemplateManager(config)
        self.seed = seed
    
    def build_all(self, output_dir: Path, answer_key_dir: Path, review_dir: Path):
        """Build datasets for all languages."""
        output_dir.mkdir(parents=True, exist_ok=True)
        answer_key_dir.mkdir(parents=True, exist_ok=True)
        review_dir.mkdir(parents=True, exist_ok=True)
        
        for lang_str in self.config.dataset.languages:
            language = Language(lang_str)
            print(f"Building dataset for {language.value}...")
            self.build_language(language, output_dir, answer_key_dir, review_dir)
    
    def build_language(self, language: Language, output_dir: Path, answer_key_dir: Path, review_dir: Path):
        """Build dataset for one language - ensures unique prompts."""
        templates = self.template_mgr.get_templates_for_language(language)
        
        # Separate sensitive and non-sensitive templates
        sensitive_templates = [t for t in templates if t["type"] == "sensitive"]
        non_sensitive_templates = [t for t in templates if t["type"] == "non_sensitive"]
        
        total = self.config.dataset.prompts_per_language
        sensitive_count = int(total * self.config.dataset.sensitive_ratio)
        non_sensitive_count = total - sensitive_count
        
        prompts = []
        answer_keys = []
        seen_prompts = set()
        
        # Generate sensitive prompts with uniqueness check
        attempts = 0
        max_attempts = sensitive_count * 10
        while len(prompts) < sensitive_count and attempts < max_attempts:
            template = random.choice(sensitive_templates)
            prompt, sensitive_items, lookalike_items = self._fill_template(template, language, True)
            script = self._determine_script(language, sensitive=True)
            
            if prompt not in seen_prompts:
                seen_prompts.add(prompt)
                row_num = len(prompts) + 1
                prompts.append(prompt)
                answer_keys.append(AnswerKeyRow(
                    row_number=row_num,
                    label="sensitive",
                    script=script,
                    sensitive_items=sensitive_items,
                    lookalike_items=lookalike_items
                ))
            attempts += 1
        
        # Generate non-sensitive prompts with uniqueness check
        attempts = 0
        max_attempts = non_sensitive_count * 10
        while len(prompts) < total and attempts < max_attempts:
            template = random.choice(non_sensitive_templates)
            prompt, sensitive_items, lookalike_items = self._fill_template(template, language, False)
            script = self._determine_script(language, sensitive=False)
            
            if prompt not in seen_prompts:
                seen_prompts.add(prompt)
                row_num = len(prompts) + 1
                prompts.append(prompt)
                answer_keys.append(AnswerKeyRow(
                    row_number=row_num,
                    label="non_sensitive",
                    script=script,
                    sensitive_items=sensitive_items,
                    lookalike_items=lookalike_items
                ))
            attempts += 1
        
        # If we couldn't generate enough unique prompts, warn but continue
        if len(prompts) < total:
            print(f"  WARNING: Only generated {len(prompts)}/{total} unique prompts for {language.value}")
        
        # Shuffle together
        combined = list(zip(prompts, answer_keys))
        random.shuffle(combined)
        prompts, answer_keys = zip(*combined) if combined else ([], [])
        
        # Update row numbers after shuffle
        for i, ak in enumerate(answer_keys):
            ak.row_number = i + 1
        
        # Write dataset CSV (prompts only)
        dataset_file = output_dir / f"{language.value}.csv"
        with open(dataset_file, 'w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            writer.writerow(["prompt"])
            for prompt in prompts:
                writer.writerow([prompt])
        
        # Write answer key CSV
        key_file = answer_key_dir / f"{language.value}_key.csv"
        with open(key_file, 'w', newline='', encoding='utf-8') as f:
            fieldnames = ["row_number", "label", "script", "sensitive_items", "lookalike_items"]
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            for ak in answer_keys:
                writer.writerow(ak.to_csv_row())
        
        # Write review sample (5%)
        review_count = int(total * self.config.dataset.review_sample_ratio)
        review_indices = random.sample(range(len(prompts)), min(review_count, len(prompts)))
        review_file = review_dir / f"review_{language.value}.csv"
        with open(review_file, 'w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            writer.writerow(["prompt", "ok_yes_no", "corrected_prompt"])
            for idx in sorted(review_indices):
                writer.writerow([prompts[idx], "", ""])
        
        print(f"  Created {dataset_file} ({len(prompts)} prompts)")
        print(f"  Created {key_file}")
        print(f"  Created {review_file} ({len(review_indices)} for review)")
    
    def _fill_template(self, template: Dict, language: Language, is_sensitive: bool) -> Tuple[str, List[SensitiveItem], List[LookalikeItem]]:
        """Fill template placeholders with synthetic data."""
        text = template["text"]
        sensitive_items = []
        lookalike_items = []
        
        # Define placeholder fillers
        fillers = {
            "{AADHAAR}": (lambda: self._add_sensitive(sensitive_items, SensitiveType.AADHAAR, self.data_gen.generate_aadhaar())),
            "{PAN}": (lambda: self._add_sensitive(sensitive_items, SensitiveType.PAN, self.data_gen.generate_pan())),
            "{PHONE}": (lambda: self._add_sensitive(sensitive_items, SensitiveType.PHONE, self.data_gen.generate_phone())),
            "{OTP}": (lambda: self._add_sensitive(sensitive_items, SensitiveType.OTP, self.data_gen.generate_otp())),
            "{ACCOUNT}": (lambda: self._add_sensitive(sensitive_items, SensitiveType.ACCOUNT, self.data_gen.generate_account())),
            "{IFSC}": (lambda: self._add_sensitive(sensitive_items, SensitiveType.IFSC, self.data_gen.generate_ifsc())),
            "{UPI_PIN}": (lambda: self._add_sensitive(sensitive_items, SensitiveType.UPI_PIN, self.data_gen.generate_upi_pin())),
            "{PASSWORD}": (lambda: self._add_sensitive(sensitive_items, SensitiveType.PASSWORD, self.data_gen.generate_password())),
            "{CARD}": (lambda: self._add_sensitive(sensitive_items, SensitiveType.CARD, self.data_gen.generate_card())),
            "{CVV}": (lambda: self._add_sensitive(sensitive_items, SensitiveType.CARD, self.data_gen.generate_cvv())),
            "{ADDRESS}": (lambda: self._add_sensitive(sensitive_items, SensitiveType.ADDRESS, self.data_gen.generate_address())),
            "{TRAIN}": (lambda: self._add_lookalike(lookalike_items, LookalikeType.TRAIN, self.data_gen.generate_train())),
            "{PINCODE}": (lambda: self._add_lookalike(lookalike_items, LookalikeType.PINCODE, self.data_gen.generate_pincode())),
            "{ORDER}": (lambda: self._add_lookalike(lookalike_items, LookalikeType.ORDER, self.data_gen.generate_order())),
            "{PRICE}": (lambda: self._add_lookalike(lookalike_items, LookalikeType.PRICE, self.data_gen.generate_price())),
            "{DATE}": (lambda: self._add_lookalike(lookalike_items, LookalikeType.DATE, self.data_gen.generate_date())),
            "{HELPLINE}": (lambda: self._add_lookalike(lookalike_items, LookalikeType.HELPLINE, self.data_gen.generate_helpline())),
            "{ROOM}": (lambda: self._add_lookalike(lookalike_items, LookalikeType.ROOM, self.data_gen.generate_room())),
            "{SCORE}": (lambda: self._add_lookalike(lookalike_items, LookalikeType.SCORE, self.data_gen.generate_score())),
        }
        
        # Replace all placeholders
        for placeholder, filler in fillers.items():
            if placeholder in text:
                text = text.replace(placeholder, filler())
        
        return text, sensitive_items, lookalike_items
    
    def _add_sensitive(self, items: List[SensitiveItem], stype: SensitiveType, value: str) -> str:
        items.append(SensitiveItem(type=stype, value=value))
        return value
    
    def _add_lookalike(self, items: List[LookalikeItem], ltype: LookalikeType, value: str) -> str:
        items.append(LookalikeItem(type=ltype, value=value))
        return value
    
    def _determine_script(self, language: Language, sensitive: bool) -> ScriptType:
        """Determine if prompt should be native, romanized, or mixed."""
        if language == Language.HINGLISH:
            return ScriptType.ROMANIZED
        
        romanized_ratio = self.config.dataset.romanized_ratio
        if random.random() < romanized_ratio:
            return ScriptType.ROMANIZED
        elif random.random() < 0.1:  # 10% mixed
            return ScriptType.MIXED
        return ScriptType.NATIVE


class DatasetValidator:
    """Validates dataset files against rules."""
    
    def __init__(self, config: Config):
        self.config = config
    
    def validate_all(self, dataset_dir: Path, answer_key_dir: Path) -> Dict[str, Any]:
        """Validate all language datasets."""
        results = {"valid": True, "errors": [], "warnings": [], "stats": {}}
        
        for lang_str in self.config.dataset.languages:
            language = Language(lang_str)
            lang_result = self.validate_language(language, dataset_dir, answer_key_dir)
            results["stats"][language.value] = lang_result["stats"]
            if not lang_result["valid"]:
                results["valid"] = False
                results["errors"].extend([f"{language.value}: {e}" for e in lang_result["errors"]])
            results["warnings"].extend([f"{language.value}: {w}" for w in lang_result["warnings"]])
        
        return results
    
    def validate_language(self, language: Language, dataset_dir: Path, answer_key_dir: Path) -> Dict[str, Any]:
        """Validate one language dataset."""
        errors = []
        warnings = []
        stats = {}
        
        dataset_file = dataset_dir / f"{language.value}.csv"
        key_file = answer_key_dir / f"{language.value}_key.csv"
        
        if not dataset_file.exists():
            errors.append(f"Dataset file not found: {dataset_file}")
            return {"valid": False, "errors": errors, "warnings": warnings, "stats": stats}
        
        if not key_file.exists():
            errors.append(f"Answer key file not found: {key_file}")
            return {"valid": False, "errors": errors, "warnings": warnings, "stats": stats}
        
        # Read dataset
        with open(dataset_file, 'r', encoding='utf-8') as f:
            reader = csv.reader(f)
            rows = list(reader)
        
        if not rows:
            errors.append("Dataset file is empty")
            return {"valid": False, "errors": errors, "warnings": warnings, "stats": stats}
        
        header = rows[0]
        if header != ["prompt"]:
            errors.append(f"Invalid header: {header}. Expected ['prompt']")
        
        prompts = [row[0] for row in rows[1:] if row]
        stats["total_rows"] = len(prompts)
        
        if len(prompts) != self.config.dataset.prompts_per_language:
            errors.append(f"Expected {self.config.dataset.prompts_per_language} prompts, got {len(prompts)}")
        
        # Check duplicates
        unique_prompts = set(prompts)
        if len(unique_prompts) != len(prompts):
            errors.append(f"Found {len(prompts) - len(unique_prompts)} duplicate prompts")
        
        # Read answer key
        with open(key_file, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            key_rows = list(reader)
        
        if len(key_rows) != len(prompts):
            errors.append(f"Answer key has {len(key_rows)} rows, dataset has {len(prompts)}")
        
        sensitive_count = sum(1 for r in key_rows if r["label"] == "sensitive")
        non_sensitive_count = sum(1 for r in key_rows if r["label"] == "non_sensitive")
        stats["sensitive_count"] = sensitive_count
        stats["non_sensitive_count"] = non_sensitive_count
        
        expected_sensitive = int(self.config.dataset.prompts_per_language * self.config.dataset.sensitive_ratio)
        if sensitive_count != expected_sensitive:
            warnings.append(f"Sensitive count {sensitive_count} != expected {expected_sensitive}")
        
        # Check script distribution
        script_counts = {}
        for r in key_rows:
            script = r["script"]
            script_counts[script] = script_counts.get(script, 0) + 1
        stats["script_distribution"] = script_counts
        
        # Validate each answer key row matches prompt
        for i, (prompt, key_row) in enumerate(zip(prompts, key_rows)):
            if int(key_row["row_number"]) != i + 1:
                errors.append(f"Row {i+1}: answer key row_number mismatch")
            
            # Verify sensitive items appear in prompt
            try:
                sensitive_items = json.loads(key_row["sensitive_items"])
                for item in sensitive_items:
                    if item["value"] not in prompt:
                        warnings.append(f"Row {i+1}: sensitive item '{item['value']}' not found in prompt")
            except json.JSONDecodeError:
                errors.append(f"Row {i+1}: invalid JSON in sensitive_items")
        
        return {"valid": len(errors) == 0, "errors": errors, "warnings": warnings, "stats": stats}