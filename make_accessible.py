import os
import sys
import re
import tempfile
from openai import OpenAI
import patch

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

    # Filter out lines that are not part of a valid unified diff
    diff_lines = []
    in_diff = False
    expected_filename = os.path.basename(swift_file)
    for line in generated_code.splitlines():
        # Normalize diff headers to match the actual filename
        if line.startswith('--- '):
            in_diff = True
            # Handle both '--- a/filename' and '--- filename'
            if line.startswith('--- a/'):
                line = f'--- {expected_filename}'
            else:
                line = f'--- {expected_filename}'
        elif line.startswith('+++ '):
            # Handle both '+++ b/filename' and '+++ filename'
            if line.startswith('+++ b/'):
                line = f'+++ {expected_filename}'
            else:
                line = f'+++ {expected_filename}'
        if in_diff:
            # Only allow valid diff lines or context lines
            if (
                line.startswith('--- ') or line.startswith('+++ ') or
                line.startswith('@@') or
                line.startswith('+') or
                line.startswith('-') or
                line.startswith(' ') or
                line.strip() == ''
            ):
                diff_lines.append(line)
    # Join the filtered lines
    filtered_diff = '\n'.join(diff_lines)

    if not filtered_diff.strip().startswith('---'):
        print("::error::OpenAI did not return a valid unified diff.", file=sys.stderr)
        sys.exit(1)


    # Write the filtered diff to a temporary file
    with tempfile.NamedTemporaryFile(mode='w+', delete=False) as tmp_patch:
        tmp_patch.write(filtered_diff)
        tmp_patch_path = tmp_patch.name

    # Apply the patch
    pset = patch.fromfile(tmp_patch_path)
    if not pset:
        print("::error::Failed to parse generated patch.", file=sys.stderr)
        sys.exit(1)
    root_dir = os.path.dirname(os.path.abspath(swift_file))
    if pset.apply(root=root_dir):
        print("Patch applied successfully!")
    else:
        print("::error::Failed to apply patch.", file=sys.stderr)
        sys.exit(1)

if __name__ == "__main__":
    main()
