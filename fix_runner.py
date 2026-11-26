with open('src/privacy_metrics/runner.py', 'r', encoding='utf-8') as f:
    content = f.read()

content = content.replace('keys[(key.language, key.row_number)] = key', 'keys[(lang, key.row_number)] = key')

with open('src/privacy_metrics/runner.py', 'w', encoding='utf-8') as f:
    f.write(content)

print('Fixed runner.py')