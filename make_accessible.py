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
You are a senior SwiftUI engineer and expert in iOS accessibility. Your task is to audit the provided SwiftUI view for accessibility issues, but you are only allowed to add SwiftUI view modifiers that start with `.accessibility` (such as `.accessibilityLabel`, `.accessibilityHint`, `.accessibilityIdentifier`, `.accessibilityAddTraits`, etc.).

**You must not remove, modify, or add any other code, view modifiers, or logic. Only append .accessibility* modifiers to existing views as needed.**

## Task Overview:
First, **identify and list all missing or insufficient .accessibility* modifiers** in the provided SwiftUI view.
- Only consider issues that can be addressed by adding .accessibility* modifiers.
- Ignore all other types of accessibility or code issues.

## Accessibility Refactor Objectives:
After identifying missing .accessibility* modifiers:
1. Regenerate the SwiftUI view, adding only the necessary .accessibility* modifiers to address the issues you found.
2. Do not remove or change any existing code, modifiers, or structure.
3. Do not add any other types of modifiers or code.
4. Add in-line comments explaining each .accessibility* modifier you add.

## Output Requirements:
1. **First**: List all missing or insufficient .accessibility* modifiers found in the original SwiftUI view.
2. **Then**: Return the fully updated SwiftUI code, with only .accessibility* modifiers added and in-line comments for each addition.
3. **Output the updated view ONLY** — do not summarize or add additional commentary after the code.

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
            {"role": "system", "content": "You are a senior SwiftUI engineer and expert in iOS accessibility. First, list all missing or insufficient .accessibility* modifiers found in the provided SwiftUI view. Then, return the fully updated SwiftUI code with only .accessibility* modifiers added and in-line comments explaining each addition. Do not summarize or add commentary after the code."},
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
