with open('src/privacy_metrics/metrics_calculator.py', 'r', encoding='utf-8') as f:
    content = f.read()

# Fix the metrics_to_table function
old = '''    html = "<table><tr>" + "".join(f"<th>{c}</th>" for c in columns) + "</tr>"
        for key, counts in metrics.items():
            html += "<tr>"
            html += f"<td>{key}</td>"
            for col in columns[1:]:
                val = getattr(counts, col.lower().replace(" ", "_"))
                if callable(val):
                    val = val()
                html += f"<td>{val:.4f if isinstance(val, float) else val}</td>"
            html += "</tr>"
        html += "</table>"
        return html'''

new = '''    html = "<table><tr>" + "".join(f"<th>{c}</th>" for c in columns) + "</tr>"
        for key, counts in metrics.items():
            html += "<tr>"
            html += f"<td>{key}</td>"
            for col in columns[1:]:
                val = getattr(counts, col.lower().replace(" ", "_"))
                if callable(val):
                    val = val()
                if isinstance(val, float):
                    html += f"<td>{val:.4f}</td>"
                else:
                    html += f"<td>{val}</td>"
            html += "</tr>"
        html += "</table>"
        return html'''

if old in content:
    content = content.replace(old, new)
    with open('src/privacy_metrics/metrics_calculator.py', 'w', encoding='utf-8') as f:
        f.write(content)
    print('Fixed metrics_to_table')
else:
    print('Could not find the method to replace')
    # Try to find it
    idx = content.find('html = "<table><tr>"')
    if idx >= 0:
        print('Found at:', idx)
        print(content[idx:idx+300])

print('Done')