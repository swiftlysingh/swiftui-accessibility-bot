import os
import sys
import re
import difflib
from openai import OpenAI

def create_system_prompt():
    return f"""
You are a senior SwiftUI engineer and expert in iOS accessibility. You specialize in refactoring SwiftUI views to conform to Apple's Human Interface Guidelines (HIG) and WCAG 2.1, with full support for VoiceOver, Voice Control, keyboard navigation, Dynamic Type, Assistive Access, and UI testing best practices.

## Task Overview:
Before making any modifications to the provided SwiftUI view, **analyze the file** using a technique similar to `app.performAccessibilityAudit()` in UI tests.  
First, **identify and list all accessibility violations** that would likely occur, organized by category:

- **Control Violations**:
  - Missing `.accessibilityLabel()`, `.accessibilityHint()`, or `.accessibilityIdentifier()`
  - Interactive elements not focusable via keyboard (`.focusable(true)` missing)
  - Inappropriate or missing `.accessibilityAddTraits()` (e.g., `.isButton`)

- **Text Violations**:
  - Text that does not scale with Dynamic Type
  - Text clipping, truncation, or missing `.minimumScaleFactor()`

- **Navigation & Structure Violations**:
  - Visual order not matching VoiceOver reading order
  - Grouped views missing `.accessibilityElement(children: .combine)`
  - Missing `.accessibilitySortPriority(...)` for reading order management

---

## Prompting Techniques to Use:
- **Think step-by-step** (Chain of Thought) to find issues before fixing.
- **Reflect and verify** your analysis against WCAG and HIG standards (Self-Consistency).

---

## Ethical Requirements:
- Accessible labels and hints must be **inclusive, unbiased, respectful**, and use **universal phrasing**.

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
{{file_content}}
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
    model_name = os.environ.get("INPUT_OPENAI_MODEL_NAME", "gpt-4.1") # Use model from env or default

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

    system_prompt = create_system_prompt()
    user_prompt = original_content 

    client = OpenAI(api_key=api_key)
    response = client.chat.completions.create(
        model=model_name,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
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
