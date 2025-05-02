import sys
import re

def apply_patch(swift_file, patch_file):
    with open(swift_file, 'r') as f:
        lines = f.readlines()
    with open(patch_file, 'r') as f:
        patch = f.read().splitlines()

    # Parse patch instructions
    insertions = []
    pattern = re.compile(r"After line (\\d+), add:")
    i = 0
    while i < len(patch):
        match = pattern.match(patch[i])
        if match:
            line_num = int(match.group(1))
            i += 1
            code_to_insert = []
            while i < len(patch) and not patch[i].startswith("After line"):
                code_to_insert.append(patch[i] + '\\n')
                i += 1
            insertions.append((line_num, code_to_insert))
        else:
            i += 1

    # Apply insertions in reverse order to not mess up line numbers
    for line_num, code in reversed(insertions):
        lines[line_num:line_num] = code

    with open(swift_file, 'w') as f:
        f.writelines(lines)

if __name__ == '__main__':
    if len(sys.argv) != 3:
        print('Usage: python apply_patch.py <swift_file> <patch_file>')
        sys.exit(1)
    apply_patch(sys.argv[1], sys.argv[2])