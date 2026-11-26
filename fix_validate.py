with open('run.py', 'r', encoding='utf-8') as f:
    content = f.read()

content = content.replace('[green]✓ All validation', '[green]OK All validation')

with open('run.py', 'w', encoding='utf-8') as f:
    f.write(content)

print('Fixed')