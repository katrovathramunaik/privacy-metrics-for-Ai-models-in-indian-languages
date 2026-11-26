with open('run.py', 'r', encoding='utf-8') as f:
    content = f.read()

content = content.replace('[red]✗ No detection', '[red]FAIL No detection')
content = content.replace('[red]✗ No recognition', '[red]FAIL No recognition')

with open('run.py', 'w', encoding='utf-8') as f:
    f.write(content)

print('Fixed checkmarks')