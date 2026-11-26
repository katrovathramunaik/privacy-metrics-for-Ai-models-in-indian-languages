with open('src/privacy_metrics/dataset_generator.py', 'r', encoding='utf-8') as f:
    content = f.read()

# Find and replace the build_language method
old_method = '''    def build_language(self, language: Language, output_dir: Path, answer_key_dir: Path, review_dir: Path):
        """Build dataset for one language."""
        templates = self.template_mgr.get_templates_for_language(language)
        
        # Separate sensitive and non-sensitive templates
        sensitive_templates = [t for t in templates if t["type"] == "sensitive"]
        non_sensitive_templates = [t for t in templates if t["type"] == "non_sensitive"]
        
        total = self.config.dataset.prompts_per_language
        sensitive_count = int(total * self.config.dataset.sensitive_ratio)
        non_sensitive_count = total - sensitive_count
        
        prompts = []
        answer_keys = []
        
        # Generate sensitive prompts
        for i in range(sensitive_count):
            template = random.choice(sensitive_templates)
            prompt, sensitive_items, lookalike_items = self._fill_template(template, language, True)
            script = self._determine_script(language, sensitive=True)
            
            row_num = len(prompts) + 1
            prompts.append(prompt)
            answer_keys.append(AnswerKeyRow(
                row_number=row_num,
                label="sensitive",
                script=script,
                sensitive_items=sensitive_items,
                lookalike_items=lookalike_items
            ))
        
        # Generate non-sensitive prompts
        for i in range(non_sensitive_count):
            template = random.choice(non_sensitive_templates)
            prompt, sensitive_items, lookalike_items = self._fill_template(template, language, False)
            script = self._determine_script(language, sensitive=False)
            
            row_num = len(prompts) + 1
            prompts.append(prompt)
            answer_keys.append(AnswerKeyRow(
                row_number=row_num,
                label="non_sensitive",
                script=script,
                sensitive_items=sensitive_items,
                lookalike_items=lookalike_items
            ))
        
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
        review_indices = random.sample(range(total), review_count)
        review_file = review_dir / f"review_{language.value}.csv"
        with open(review_file, 'w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            writer.writerow(["prompt", "ok_yes_no", "corrected_prompt"])
            for idx in sorted(review_indices):
                writer.writerow([prompts[idx], "", ""])
        
        print(f"  Created {dataset_file} ({len(prompts)} prompts)")
        print(f"  Created {key_file}")
        print(f"  Created {review_file} ({review_count} for review)")'''

new_method = '''    def build_language(self, language: Language, output_dir: Path, answer_key_dir: Path, review_dir: Path):
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
        print(f"  Created {review_file} ({len(review_indices)} for review)")'''

if old_method in content:
    content = content.replace(old_method, new_method)
    with open('src/privacy_metrics/dataset_generator.py', 'w', encoding='utf-8') as f:
        f.write(content)
    print("Fixed build_language method")
else:
    print("Could not find the method to replace")
    # Print first 100 chars of old_method to debug
    print("Looking for:", old_method[:100])

print("Done")