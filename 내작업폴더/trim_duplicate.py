with open('app_dart_trace_dashboard.py', 'r', encoding='utf-8') as f:
    lines = f.readlines()

# find the duplicate section around line 700
# 701 is '</style>\n', 702 is '    """, unsafe_allow_html=True)\n'
# 703 is '    canvas_bg = "#0e1117"\n'
# line 741 is '    canvas_font = "#ffffff"\n'

cut_start = -1
cut_end = -1
for i in range(695, 710):
    if 'canvas_bg = "#0e1117"' in lines[i]:
        cut_start = i
        break

for i in range(cut_start, cut_start + 50):
    if 'canvas_font = "#ffffff"' in lines[i]:
        cut_end = i + 1  # include this line
        break

print(f"Cutting lines {cut_start+1} to {cut_end}")
print("Start line content:", repr(lines[cut_start]))
print("End line content:", repr(lines[cut_end-1]))

new_lines = lines[:cut_start] + [
    '    canvas_bg = "#0e1117"\n',
    '    canvas_font = "#ffffff"\n'
] + lines[cut_end:]

with open('app_dart_trace_dashboard.py', 'w', encoding='utf-8') as f:
    f.writelines(new_lines)

print("Trimmed duplicate css block successfully!")

# Now verify AST
import ast
ast.parse("".join(new_lines))
print("*** AST PARSING VERIFIED: NO SYNTAX ERRORS! ***")
