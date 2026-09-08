with open('app_dart_trace_dashboard.py', 'r', encoding='utf-8') as f:
    lines = f.readlines()

menu1_idx = -1
for i, l in enumerate(lines):
    if "메뉴 1: 상장사 지배구조" in l:
        menu1_idx = i
        break

# 704 is '    canvas_font = "#ffffff"\n'
# Let's find index where first 'canvas_font = "#ffffff"' is around 700
first_cf = -1
for i in range(695, 715):
    if 'canvas_font = "#ffffff"' in lines[i]:
        first_cf = i
        break

print(f"first_cf is line {first_cf+1}: {repr(lines[first_cf])}")
print(f"menu1 is line {menu1_idx+1}: {repr(lines[menu1_idx])}")

# Delete from first_cf + 1 up to menu1_idx - 2 (keeping 2 empty lines)
clean_lines = lines[:first_cf+1] + ["\n\n"] + lines[menu1_idx:]

with open('app_dart_trace_dashboard.py', 'w', encoding='utf-8') as f:
    f.writelines(clean_lines)

print("Saved clean file!")

import ast
ast.parse("".join(clean_lines))
print("*** AST PARSING 100% SUCCESSFUL! NO ERRORS AT ALL! ***")
