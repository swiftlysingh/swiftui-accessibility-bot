#!/bin/sh -l
set -e

# Debug: print environment variable presence
if [ -z "$INPUT_OPENAI_API_KEY" ]; then
  echo "::error::OPENAI_API_KEY is not set!"
else
  echo "OPENAI_API_KEY is set."
fi
# Correctly check for INPUT_GITHUB_TOKEN
if [ -z "$INPUT_GITHUB_TOKEN" ]; then
  echo "::error::GITHUB_TOKEN is not set!"
else
  echo "GITHUB_TOKEN is set."
fi

export OPENAI_API_KEY="$INPUT_OPENAI_API_KEY"
export GITHUB_TOKEN="$INPUT_GITHUB_TOKEN"

# Find all SwiftUI files
FILES=$(find . -name '*.swift' | xargs grep -l 'import SwiftUI')
echo "SwiftUI files found: $FILES"

MODIFIED_FILES_FOR_PR_BODY="" # Changed variable name for clarity
MODIFIED_COUNT=0

for file in $FILES; do
  export INPUT_SWIFT_FILE_PATH="$file"
  # Use exit code to check if make_accessible.py made changes (exits 0 if changes applied)
  if python /app/make_accessible.py; then
    echo "Accessibility additions applied to $file"
    if [ -z "$MODIFIED_FILES_FOR_PR_BODY" ]; then
      MODIFIED_FILES_FOR_PR_BODY="- $file"
    else
      # Append with a literal newline character for proper Markdown list formatting
      MODIFIED_FILES_FOR_PR_BODY="$MODIFIED_FILES_FOR_PR_BODY\n- $file"
    fi
    MODIFIED_COUNT=$((MODIFIED_COUNT+1))
  else
    # make_accessible.py exits 1 if no changes or only ignored changes were made
    echo "No applicable accessibility additions found for $file"
  fi
done

if [ "$MODIFIED_COUNT" -gt 0 ]; then
  git config --global --add safe.directory /github/workspace
  git config --global user.name "github-actions[bot]"
  git config --global user.email "github-actions[bot]@users.noreply.github.com"
  BRANCH="bot/a11y-apply-$(date +%s)"
  git checkout -b "$BRANCH"
  git add . # Add all changes made by the python script

  # Generate the diff *after* adding changes
  DIFF_CONTENT=$(git diff --staged) # Get diff of staged changes

  git commit -m "feat(bot): Apply AI-suggested accessibility improvements"
  git push "https://x-access-token:$GITHUB_TOKEN@github.com/$GITHUB_REPOSITORY.git" "$BRANCH"

  # Create Pull Request using GitHub CLI
  echo "Creating Pull Request..."

  PR_BODY_FILE=$(mktemp)
  # Safely print the summary and diff to the temporary file
  printf "%s\n\n%s" "$PR_BODY_SUMMARY" "$PR_BODY_DIFF" > "$PR_BODY_FILE"

  gh pr create \
    --base "$(git remote show origin | grep 'HEAD branch' | cut -d' ' -f3)" \
    --head "$BRANCH" \
    --title "$PR_TITLE" \
    --body-file "$PR_BODY_FILE" \
    --repo "$GITHUB_REPOSITORY"
  
  rm "$PR_BODY_FILE" # Clean up the temporary file

  echo "Pull Request created successfully."
  echo "branch-name=$BRANCH" >> "$GITHUB_OUTPUT"
else
  echo "No files were modified. Skipping PR creation."
  echo "branch-name=" >> "$GITHUB_OUTPUT" # Ensure output is set even if no branch
fi

echo "files-modified=$MODIFIED_COUNT" >> "$GITHUB_OUTPUT"
