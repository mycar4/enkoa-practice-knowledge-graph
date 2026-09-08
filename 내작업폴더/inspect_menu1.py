with open('app_dart_trace_dashboard.py', 'r', encoding='utf-8') as f:
    lines = f.readlines()

# Look around line 700 to 750
menu1_idx = -1
for i, l in enumerate(lines):
    if "메뉴 1: 상장사 지배구조" in l:
        menu1_idx = i
        break

print("menu1_idx:", menu1_idx)
# print preceding 40 lines
for idx in range(menu1_idx - 45, menu1_idx):
    print(f"{idx+1}: {lines[idx].rstrip()[:80]}")
