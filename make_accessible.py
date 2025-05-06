import os
import sys
import re
import difflib
from openai import OpenAI

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
- Output **only** the complete, modified Swift file content enclosed in a single Markdown code block like this:
```swift
[Your modified Swift code here]
```
- Do not output any explanations, lists, commentary, or diffs—only the final Swift code block.
- Ensure the output is valid Swift code.

## Provided File to Audit and Refactor:
🔽 SwiftUI view to refactor:
START_OF_FILE
{file_content}
END_OF_FILE
"""

def extract_swift_code(llm_output):
    """Extracts Swift code from a Markdown code block."""
    match = re.search(r'```swift\n(.*?)```', llm_output, re.DOTALL)
    if match:
        return match.group(1).strip()
    else:
        print("::warning::Could not find Markdown Swift code block. Attempting to use entire LLM output.", file=sys.stderr)
        return llm_output.strip()

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
        original_content = file.read()

    if not original_content.strip():
        print(f"::error::File '{swift_file}' is empty.", file=sys.stderr)
        sys.exit(1)

    class_name = extract_class_name(original_content)
    prompt = generate_accessibility_prompt(swift_file, class_name, original_content)
    client = OpenAI(api_key=api_key)
    response = client.chat.completions.create(
        model="gpt-4.1",
        messages=[
            {"role": "system", "content": "You are a senior SwiftUI engineer and expert in iOS accessibility. Only output the complete, modified Swift file content enclosed in a single Markdown code block (```swift ... ```). Do not output any explanations, lists, commentary, or diffs. Ensure the output is valid Swift code."},
            {"role": "user", "content": prompt}
        ],
        temperature=0.2
    )
    llm_response_content = response.choices[0].message.content

    print("=== LLM Raw Response Start ===")
    print(llm_response_content)
    print("=== LLM Raw Response End ===")

    modified_content = extract_swift_code(llm_response_content)
    if not modified_content:
        print("::error::Could not extract Swift code from LLM response.", file=sys.stderr)
        print(f"::debug::LLM response was:\n{llm_response_content}", file=sys.stderr)
        sys.exit(1)

    original_lines = original_content.splitlines(keepends=True)
    modified_lines = modified_content.splitlines(keepends=True)

    matcher = difflib.SequenceMatcher(None, original_lines, modified_lines)
    final_lines = []
    has_changes = False

    for tag, i1, i2, j1, j2 in matcher.get_opcodes():
        if tag == 'equal':
            final_lines.extend(original_lines[i1:i2])
        elif tag == 'insert':
            final_lines.extend(modified_lines[j1:j2])
            has_changes = True
        elif tag == 'delete':
            final_lines.extend(original_lines[i1:i2])
            print(f"::debug::Ignoring LLM suggested deletion at original lines {i1+1}-{i2}", file=sys.stderr)
        elif tag == 'replace':
            final_lines.extend(original_lines[i1:i2])
            print(f"::debug::Ignoring LLM suggested replacement at original lines {i1+1}-{i2}", file=sys.stderr)

    final_content = "".join(final_lines)

    if has_changes and final_content != original_content:
        print(f"::notice::Applying accessibility additions to {swift_file}")
        try:
            with open(swift_file, 'w') as file:
                file.write(final_content)
            print(f"Successfully updated {swift_file} with additions only.")
            sys.exit(0)
        except IOError as e:
            print(f"::error::Failed to write updated content to {swift_file}: {e}", file=sys.stderr)
            sys.exit(1)
    elif has_changes and final_content == original_content:
        print(f"::notice::LLM suggested changes for {swift_file}, but they involved deletions or replacements which were ignored. No additions applied.")
        sys.exit(1)
    else:
        print(f"::notice::LLM did not suggest any additions for {swift_file}. No changes applied.")
        sys.exit(1)

if __name__ == "__main__":
    main()
