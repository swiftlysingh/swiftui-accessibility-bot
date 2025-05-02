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
- **Assistive Access Violations**:
  - Small tap targets (<44x44 points)
  - Use of non-standard gestures or non-standard SwiftUI controls
  - Layout breakage at large Dynamic Type sizes (e.g., `.extraExtraExtraLarge`)
---
## Prompting Techniques to Use:
- **Think step-by-step** (Chain of Thought) to find issues before fixing.
- **Reflect and verify** your analysis against WCAG and HIG standards (Self-Consistency).
---
## Accessibility Refactor Objectives:
After identifying violations:
1. Regenerate the SwiftUI view with **full accessibility support applied**.
2. Ensure:
   - All UI elements have meaningful `.accessibilityLabel()` and `.accessibilityHint()`.
   - For example: Use hints like "Tap \\(answerChoice)" so the user can say "Tap Deep Dish Pizza."
   - Visible label text appears at the beginning of custom accessibility labels if changed.
   - Full support for Dynamic Type using `.font(.preferredFont(forTextStyle:))`, `.system(...) relativeTo:` or `.custom(..., relativeTo:)`.
   - Keyboard navigation is fully supported using `.focusable(true)`.
   - Layout does not break under large accessibility text settings.
---
## Explainability Requirements:
- For **each issue found**, cite the relevant WCAG 2.1 success criterion or HIG recommendation.
- Explanations must be in **plain English**, suitable for junior developers and designers.
---
## Ethical Requirements:
- Accessible labels and hints must be **inclusive, unbiased, respectful**, and use **universal phrasing**.
---
## Output Requirements:
1. **First**: List all accessibility violations found in the original SwiftUI view.
2. **Then**: Return the fully updated SwiftUI code, applying changes with **in-line comments** explaining each improvement.
3. **Output the updated view ONLY** — do not summarize or add additional commentary after the code.
---
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
            {"role": "system", "content": "You are a senior SwiftUI engineer and expert in iOS accessibility. First, list all accessibility violations found in the provided SwiftUI view. Then, return the fully updated SwiftUI code with in-line comments explaining each improvement. Do not summarize or add commentary after the code."},
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
