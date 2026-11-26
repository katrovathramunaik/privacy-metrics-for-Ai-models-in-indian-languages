with open('run.py', 'r', encoding='utf-8') as f:
    content = f.read()

content = content.replace('[yellow]⚠[/yellow]', '[yellow]WARN[/yellow]')

with open('run.py', 'w', encoding='utf-8') as f:
    f.write(content)

print('Fixed warning symbol')