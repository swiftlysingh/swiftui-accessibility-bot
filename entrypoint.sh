#!/bin/sh -l
set -e

export OPENAI_API_KEY="${INPUT_OPENAI_API_KEY:-$INPUT_OPENAI-API-KEY}"
export GITHUB_TOKEN="${INPUT_GITHUB_TOKEN:-$INPUT_GITHUB-TOKEN}"

# Find all SwiftUI view files (simple heuristic)
FILES=$(find . -name '*.swift' | xargs grep -l 'import SwiftUI' | xargs grep -l 'struct .*: View')

MODIFIED=0

for file in $FILES; do
  export INPUT_SWIFT_FILE_PATH="$file"
  if OUTPUT=$(python /app/make_accessible.py); then
    echo "$OUTPUT" > "$file"
    MODIFIED=$((MODIFIED+1))
  else
    echo "::warning::Failed to process $file"
  fi

done

if [ "$MODIFIED" -gt 0 ]; then
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
