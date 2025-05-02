#!/bin/sh -l
set -e

# Debug: print environment variable presence
if [ -z "$INPUT_OPENAI_API_KEY" ]; then
  echo "::error::INPUT_OPENAI_API_KEY is not set!"
else
  echo "INPUT_OPENAI_API_KEY is set."
fi
if [ -z "$INPUT_GITHUB_TOKEN" ]; then
  echo "::error::INPUT_GITHUB_TOKEN is not set!"
else
  echo "INPUT_GITHUB_TOKEN is set."
fi

export OPENAI_API_KEY="$INPUT_OPENAI_API_KEY"
export GITHUB_TOKEN="$INPUT_GITHUB_TOKEN"

# Find all SwiftUI files that import SwiftUI and have a struct/class/enum (more inclusive)
FILES=$(find . -name '*.swift' | xargs grep -l 'import SwiftUI')

echo "SwiftUI files found: $FILES"

MODIFIED=0

for file in $FILES; do
  export INPUT_SWIFT_FILE_PATH="$file"
  if python /app/make_accessible.py > patch.txt; then
    if python /app/apply_patch.py "$file" patch.txt; then
      MODIFIED=$((MODIFIED+1))
    else
      echo "::warning::Failed to apply patch to $file"
    fi
  else
    echo "::warning::Failed to process $file"
  fi

done

if [ "$MODIFIED" -gt 0 ]; then
  git config --global --add safe.directory /github/workspace
  git config --global user.name "github-actions[bot]"
  git config --global user.email "github-actions[bot]@users.noreply.github.com"
  BRANCH="bot/a11y-apply-$(date +%s)"
  git checkout -b "$BRANCH"
  git add .
  git commit -m "feat(bot): Apply AI-suggested accessibility improvements"
  git push "https://x-access-token:$INPUT_GITHUB_TOKEN@github.com/$GITHUB_REPOSITORY.git" "$BRANCH"
  echo "branch-name=$BRANCH" >> $GITHUB_OUTPUT
fi

echo "files-modified=$MODIFIED" >> $GITHUB_OUTPUT
