with open('src/privacy_metrics/dataset_generator.py', 'r', encoding='utf-8') as f:
    content = f.read()

content = content.replace('₹', 'Rs.')

with open('src/privacy_metrics/dataset_generator.py', 'w', encoding='utf-8') as f:
    f.write(content)

print('Fixed rupee symbol')