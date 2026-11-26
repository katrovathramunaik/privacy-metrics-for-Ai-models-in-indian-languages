with open('run.py', 'r', encoding='utf-8') as f:
    content = f.read()

content = content.replace('[green]✓[/green]', '[green]OK[/green]')
content = content.replace('[red]✗[/red]', '[red]FAIL[/red]')

with open('run.py', 'w', encoding='utf-8') as f:
    f.write(content)

print('Fixed checkmarks')