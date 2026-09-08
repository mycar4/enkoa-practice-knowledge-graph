with open('app_dart_trace_dashboard.py', 'r', encoding='utf-8') as f:
    lines = f.readlines()

for i in range(700, min(len(lines), 760)):
    print(f"{i+1}: {repr(lines[i])}")
