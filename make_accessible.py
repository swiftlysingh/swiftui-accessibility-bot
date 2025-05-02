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
    start_index = -1
    plus_index = -1
    expected_filename = os.path.basename(swift_file)

    # Find the start of the diff ('--- <filename>')
    for i, line in enumerate(lines):
        if line.startswith('--- '):
            start_index = i
            # Look for the '+++ <filename>' line immediately after or separated by whitespace
            for j in range(i + 1, len(lines)):
                if lines[j].startswith('+++ '):
                    plus_index = j
                    break
                elif lines[j].strip() != '':  # Stop if non-whitespace found before +++
                    print(f"Non-whitespace line found between '---' and '+++': '{lines[j]}'")
                    break
            break  # Found the first potential '---'

    if start_index != -1 and plus_index != -1:
        # Add the normalized '---' line
        diff_lines.append(f'--- {expected_filename}')
        # Add the normalized '+++' line
        diff_lines.append(f'+++ {expected_filename}')

        # Process lines after '+++'
        for i in range(plus_index + 1, len(lines)):
            line = lines[i]
            # Check if the line looks like a valid diff line (hunk header, add, remove, context, or empty)
            if (
                line.startswith('@@') or
                line.startswith('+') or
                line.startswith('-') or
                line.startswith(' ') or
                line.strip() == ''  # Allow empty lines within the diff context/hunks
            ):
                diff_lines.append(line)
            else:
                # Stop if we encounter a line that doesn't fit the diff format
                # This handles cases where the LLM adds commentary after the diff block
                print(f"Stopping diff extraction at line {i+1} (does not match diff format): '{line}'")
                break
    else:
        print(f"::error::Could not find valid '--- {expected_filename}' and '+++ {expected_filename}' lines in the generated output.", file=sys.stderr)
        # Proceeding with empty diff_lines will cause the next check to fail cleanly

    # Join the filtered lines
    filtered_diff = '\n'.join(diff_lines)
    # Add a newline at the end if filtered_diff is not empty, as patch often requires it
    if filtered_diff:
        filtered_diff += '\n'

    # Check if the result looks like a minimal valid diff structure
    if not filtered_diff.strip():
        print("::warning::Filtered diff is empty. No changes to apply.", file=sys.stderr)
        # Exit cleanly if no diff was generated or extracted
        sys.exit(0)

    if not filtered_diff.startswith(f'--- {expected_filename}\n+++ {expected_filename}\n'):
        print("::error::Filtered diff does not start with expected headers.", file=sys.stderr)
        print(f"::error::Expected headers: '--- {expected_filename}\n+++ {expected_filename}'", file=sys.stderr)
        print(f"::error::Got:\n{filtered_diff}", file=sys.stderr)
        sys.exit(1)

    # Check for hunk headers if the diff is not just headers
    if len(diff_lines) > 2 and not any(line.startswith('@@') for line in diff_lines):
        print("::warning::Filtered diff does not contain any hunk headers ('@@'). It might be invalid.", file=sys.stderr)
        # Decide whether to proceed or exit based on requirements. For now, allow it but warn.

    # Write the filtered diff to a temporary file
    # Use a specific suffix for clarity
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
