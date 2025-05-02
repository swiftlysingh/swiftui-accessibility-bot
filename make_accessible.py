import os
import sys
import re
from openai import OpenAI

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

## Task Overview:
First, **identify and list all missing or insufficient accessibility modifiers** in the provided SwiftUI view (from the list above).
- Only consider issues that can be addressed by adding the listed accessibility modifiers.
- Ignore all other types of accessibility or code issues.

## Accessibility Refactor Objectives:
After identifying missing accessibility modifiers:
1. For each required modifier, output a unified diff
2. Only output the minimal set of changes needed, in the order they should be applied.
3. Do not output the full file, do not remove or modify any existing code, and do not add any other commentary.

## Output Requirements:
- Only output the minimal patch as described above.

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
        model="gpt-4-0125-preview",
        messages=[
            {"role": "system", "content": "You are a senior SwiftUI engineer and expert in iOS accessibility. First, list all missing or insufficient .accessibility* modifiers found in the provided SwiftUI view. Then, return the minimal patch-style instructions for adding the required .accessibility* modifiers, specifying the line number after which each modifier should be inserted and the code to insert. Do not output the full file, remove any code, or add commentary."},
            {"role": "user", "content": prompt}
        ],
        temperature=0.2,
        max_tokens=3000
    )
    generated_code = response.choices[0].message.content
    if not generated_code or is_potentially_injected(generated_code):
        print("::error::LLM output invalid or potentially injected.", file=sys.stderr)
        sys.exit(1)
    print(generated_code)

if __name__ == "__main__":
    main()
