import os
import sys
import re
import tempfile
from openai import OpenAI
import subprocess

INJECTION_PATTERNS = [
    r"ignore.*instructions", r"disregard.*above", r"assistant.*role", r"user.*role",
    r"do not follow", r"@role"
]

def is_potentially_injected(content: str) -> bool:
    return any(re.search(pattern, content, re.IGNORECASE) for pattern in INJECTION_PATTERNS)

def extract_class_name(file_content):
    match = re.search(r'\b(struct|class|enum)\s+(\w+)', file_content)
    return match.group(2) if match else "UnknownClass"

def generate_accessibility_prompt(file_name, class_name, file_content):
    return f"""
You are a senior SwiftUI engineer and expert in iOS accessibility. Your task is to audit the provided SwiftUI view for accessibility issues, but you are only allowed to add the following SwiftUI accessibility modifiers:
- .accessibilityLabel(_:)
- .accessibilityValue(_:)
- .accessibilityHint(_:)
- .accessibilityIdentifier(_:)
- .accessibilityAddTraits(_:)
- .accessibilityRemoveTraits(_:)
- .accessibilitySortPriority(_:)
- .accessibilityHidden(_:)
- .accessibilityElement(children:)
- .accessibilityInputLabels(_:)
- .accessibilityCustomAction(_:)
- .accessibilityRespondsToUserInteraction(_:)
- .accessibilityRepresentation(_:)
- .accessibilityRotorEntry(_:)
- .accessibilityRotor(_:)
- .accessibilityAction(_:)
- .accessibilityAdjustableAction(_:)
- .accessibilityScrollAction(_:)
- .accessibilityFocused(_:)
- .accessibilityShowsLargeContentViewer(_:)
- .accessibilityTextContentType(_:)
- .accessibilityHeading(_:)
- .accessibilityLabeledPair(_:)
- .accessibilityReadingOrder(_:)
- .accessibilityZoomAction(_:)
- .accessibilityInputActions(_:)

**You must not remove, modify, or add any other code, view modifiers, or logic. Only append these accessibility modifiers to existing views as needed.**

## Output Requirements:
- Output only a valid unified diff (diff -u format) for the minimal set of changes needed to add the required accessibility modifiers.
- Do not output any explanations, lists, or commentary—only the diff.
- Do not remove or modify any existing code except to append the allowed accessibility modifiers.

## Provided File to Audit and Refactor:
🔽 SwiftUI view to refactor:
START_OF_FILE
{file_content}
END_OF_FILE
"""

def main():
    swift_file = os.environ.get("INPUT_SWIFT_FILE_PATH")
    api_key = os.environ.get("OPENAI_API_KEY")
    if not swift_file or not api_key:
        print("::error::Missing required environment variables.", file=sys.stderr)
        sys.exit(1)
    if not os.path.isfile(swift_file):
        print(f"::error::File not found: {swift_file}", file=sys.stderr)
        sys.exit(1)
    with open(swift_file, 'r') as file:
        content = file.read()
    if not content.strip():
        print(f"::error::File '{swift_file}' is empty.", file=sys.stderr)
        sys.exit(1)
    class_name = extract_class_name(content)
    prompt = generate_accessibility_prompt(swift_file, class_name, content)
    client = OpenAI(api_key=api_key)
    response = client.chat.completions.create(
        model="gpt-4.1",
        messages=[
            {"role": "system", "content": "You are a senior SwiftUI engineer and expert in iOS accessibility. Only output a valid unified diff (diff -u format) for the minimal set of changes needed to add the required .accessibility* modifiers. Do not output any explanations, lists, or commentary—only the diff. Do not remove or modify any existing code except to append the allowed accessibility modifiers."},
            {"role": "user", "content": prompt}
        ],
        temperature=0.2
    )
    generated_code = response.choices[0].message.content
    print(response.choices)
    print("=== GENERATED DIFF START ===")
    print(generated_code)
    print("=== GENERATED DIFF END ===")

    lines = generated_code.splitlines()
    diff_lines = []
    start_marker_index = -1
    plus_marker_index = -1
    hunk_start_index = -1
    expected_filename = os.path.basename(swift_file)

    # Find the start ('--- ') and plus ('+++ ') markers, allowing for git's a/ b/ prefixes
    for i, line in enumerate(lines):
        if line.startswith('--- '):
            # Basic check to see if it might be the filename we expect, ignoring a/ prefix
            if expected_filename in line:
                start_marker_index = i
                # Look for the corresponding '+++ ' line
                for j in range(i + 1, len(lines)):
                    if lines[j].startswith('+++ '):
                        if expected_filename in lines[j]:
                            plus_marker_index = j
                            break # Found +++
                    elif lines[j].strip() != '': # Stop if non-whitespace found before +++
                        break
                if plus_marker_index != -1:
                    break # Found both --- and +++ for the expected file

    if start_marker_index != -1 and plus_marker_index != -1:
        # Now, find the first hunk header '@@ ... @@' after the '+++' line
        for i in range(plus_marker_index + 1, len(lines)):
            if lines[i].startswith('@@ '):
                hunk_start_index = i
                break

        if hunk_start_index != -1:
            # Add the normalized '---' and '+++' headers
            diff_lines.append(f'--- {expected_filename}')
            diff_lines.append(f'+++ {expected_filename}')

            # Process lines starting from the first hunk header
            for i in range(hunk_start_index, len(lines)):
                line = lines[i]
                # Check if the line looks like a valid diff line (hunk header, add, remove, context)
                # Allow context lines starting with space OR tab
                if (
                    line.startswith('@@ ') or
                    line.startswith('+') or
                    line.startswith('-') or
                    line.startswith(' ') or # Context line starts with a space
                    line.startswith('\t')   # Allow context line starting with a tab
                ):
                    diff_lines.append(line)
                elif line.strip() == '':
                     # Include empty lines only if they are part of the diff content (e.g., between hunks)
                     diff_lines.append(line)
                else:
                    # Stop if we encounter a line that doesn't fit the diff format
                    print(f"Stopping diff extraction at line {i+1} (does not match diff format): '{line}'")
                    break
        else:
            print(f"::error::Could not find hunk header '@@ ... @@' after '+++ {expected_filename}' line.", file=sys.stderr)
    else:
        print(f"::error::Could not find valid '--- {expected_filename}' and '+++ {expected_filename}' lines in the generated output.", file=sys.stderr)

    # Join the filtered lines
    filtered_diff = '\n'.join(diff_lines)
    # Add a newline at the end if filtered_diff is not empty, as patch often requires it
    if filtered_diff and not filtered_diff.endswith('\n'):
        filtered_diff += '\n'

    # Check if the result looks like a minimal valid diff structure
    if not filtered_diff.strip():
        print("::warning::Filtered diff is empty. No changes to apply.", file=sys.stderr)
        sys.exit(0)

    if not filtered_diff.startswith(f'--- {expected_filename}\n+++ {expected_filename}\n'):
        print("::error::Filtered diff does not start with expected headers.", file=sys.stderr)
        print(f"::error::Expected headers: '--- {expected_filename}\n+++ {expected_filename}'", file=sys.stderr)
        print(f"::error::Got:\n{filtered_diff}", file=sys.stderr)
        sys.exit(1)

    # Check for hunk headers if the diff is not just headers
    if len(diff_lines) > 2 and not any(line.startswith('@@') for line in diff_lines):
        print("::warning::Filtered diff does not contain any hunk headers ('@@'). It might be invalid.", file=sys.stderr)

    # Write the filtered diff to a temporary file
    with tempfile.NamedTemporaryFile(mode='w+', delete=False, suffix=".patch") as tmp_patch:
        tmp_patch.write(filtered_diff)
        tmp_patch_path = tmp_patch.name

    # Apply the patch using the patch command-line utility
    swift_file_abspath = os.path.abspath(swift_file)
    root_dir = os.path.dirname(swift_file_abspath)

    patch_command = ['patch', '-p0', '--input', tmp_patch_path]
    print(f"Running patch command: {' '.join(patch_command)} in directory {root_dir}")

    try:
        result = subprocess.run(
            patch_command,
            cwd=root_dir,
            check=True,
            capture_output=True,
            text=True
        )
        print("Patch applied successfully using command!")
    except subprocess.CalledProcessError as e:
        print(f"::error::Failed to apply patch using command: {' '.join(patch_command)}", file=sys.stderr)
        print(f"::error::Return code: {e.returncode}", file=sys.stderr)
        print(f"::error::stdout: {e.stdout}", file=sys.stderr)
        print(f"::error::stderr: {e.stderr}", file=sys.stderr)
        print("::error::Patch content was:", file=sys.stderr)
        print(filtered_diff, file=sys.stderr)
        sys.exit(1)
    except FileNotFoundError:
        print("::error::'patch' command not found. Is it installed in the container?", file=sys.stderr)
        sys.exit(1)
    finally:
        os.remove(tmp_patch_path)

if __name__ == "__main__":
    main()
