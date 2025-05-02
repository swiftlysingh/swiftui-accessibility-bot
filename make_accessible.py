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
    found_filename_from = None
    found_filename_to = None

    # Find the first '--- ' and '+++ ' lines
    for i, line in enumerate(lines):
        if line.startswith('--- '):
            start_marker_index = i
            # Extract filename from '---' line, removing potential prefixes and timestamp
            match_from = re.match(r'--- (?:a/|b/)?([^\t\n]+)', line)
            if match_from:
                found_filename_from = match_from.group(1).strip()
            # Look for the corresponding '+++ ' line immediately after or separated by whitespace
            for j in range(i + 1, len(lines)):
                if lines[j].startswith('+++ '):
                    plus_marker_index = j
                    # Extract filename from '+++' line
                    match_to = re.match(r'\+\+\+ (?:a/|b/)?([^\t\n]+)', lines[j])
                    if match_to:
                        found_filename_to = match_to.group(1).strip()
                    break
                elif lines[j].strip() != '': # Stop if non-whitespace found before +++
                    break
            break # Found the first potential '---' line

    # Validate found filenames
    if start_marker_index == -1 or plus_marker_index == -1:
        print(f"::error::Could not find '--- ' and '+++ ' lines in the generated output.", file=sys.stderr)
    elif found_filename_from != expected_filename or found_filename_to != expected_filename:
        print(f"::error::Filename mismatch in diff headers. Expected '{expected_filename}', but found '{found_filename_from}' and '{found_filename_to}'.", file=sys.stderr)
        # Exit with error because the patch command will likely fail
        sys.exit(1)
    else:
        # Filenames match, proceed to find hunk header
        # Now, find the first hunk header '@@ ... @@' after the '+++' line
        for i in range(plus_marker_index + 1, len(lines)):
            if lines[i].startswith('@@ '):
                hunk_start_index = i
                break

        if hunk_start_index != -1:
            # Add the CORRECTED '---' and '+++' headers using the expected filename
            diff_lines.append(f'--- {expected_filename}')
            diff_lines.append(f'+++ {expected_filename}')

            # Process lines starting from the first hunk header
            for i in range(hunk_start_index, len(lines)):
                line = lines[i]
                # Check if the line looks like a valid diff line
                if (
                    line.startswith('@@ ') or
                    line.startswith('+') or
                    line.startswith('-') or
                    line.startswith(' ') or
                    line.startswith('\t')
                ):
                    diff_lines.append(line)
                elif line.strip() == '':
                     diff_lines.append(line)
                else:
                    print(f"Stopping diff extraction at line {i+1} (does not match diff format): '{line}'")
                    break
        else:
            print(f"::error::Could not find hunk header '@@ ... @@' after '+++ {expected_filename}' line.", file=sys.stderr)
            # Exit with error as the diff is incomplete
            sys.exit(1)

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
