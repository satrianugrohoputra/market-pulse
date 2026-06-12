"""Fix indentation of lines 551-598 in app.py from 24 spaces to 12 spaces."""

with open('app.py', 'r', encoding='utf-8') as f:
    lines = f.readlines()

# Lines 551-598 are 0-indexed as 550-597
# They have 24 spaces of indent but should have 12
fixed = []
for i, line in enumerate(lines):
    lineno = i + 1  # 1-indexed
    if 551 <= lineno <= 598:
        # Count current leading spaces
        stripped = line.lstrip(' ')
        current_spaces = len(line) - len(stripped)
        # These lines were over-indented by 12 extra spaces (patch added 12 on top of 12)
        if current_spaces >= 24 and stripped.strip():
            line = ' ' * (current_spaces - 12) + stripped
        elif current_spaces == 0 and not stripped.strip():
            pass  # blank lines keep as-is
    fixed.append(line)

with open('app.py', 'w', encoding='utf-8') as f:
    f.writelines(fixed)

print("Fixed.")
