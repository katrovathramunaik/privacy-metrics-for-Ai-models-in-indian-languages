with open('run.py', 'r', encoding='utf-8') as f:
    content = f.read()

content = content.replace('[green]✓ Detection', '[green]OK Detection')
content = content.replace('[green]✓ Recognition', '[green]OK Recognition')
content = content.replace('[green]✓ Metrics', '[green]OK Metrics')

with open('run.py', 'w', encoding='utf-8') as f:
    f.write(content)

print('Fixed checkmarks')