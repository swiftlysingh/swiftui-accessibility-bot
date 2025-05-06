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
  if python /app/make_accessible.py; then
    echo "Accessibility patch applied for $file"
    MODIFIED=$((MODIFIED+1))
  else
    echo "::warning::Failed to process or apply patch to $file"
  fi
done

if [ "$MODIFIED" -gt 0 ]; then
  git config --global --add safe.directory /github/workspace
  git config --global user.name "github-actions[bot]"
  gi  #!/bin/sh -l
  set -e
  
  # ... (environment variable checks and exports) ...
  
  export OPENAI_API_KEY="$INPUT_OPENAI_API_KEY"
  export GITHUB_TOKEN="$INPUT_GITHUB_TOKEN"
  
  # Find all SwiftUI files
  FILES=$(find . -name '*.swift' | xargs grep -l 'import SwiftUI')
  echo "SwiftUI files found: $FILES"
  
  MODIFIED_FILES_LIST=""
  MODIFIED_COUNT=0
  
  for file in $FILES; do
    export INPUT_SWIFT_FILE_PATH="$file"
    # Use exit code to check if make_accessible.py made changes (exits 0 if changes applied)
    if python /app/make_accessible.py; then
      echo "Accessibility additions applied to $file"
      MODIFIED_FILES_LIST="$MODIFIED_FILES_LIST- $file\n"
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
  
    # Construct PR Body
    PR_TITLE="🤖 Apply AI Accessibility Improvements"
    PR_BODY=$(cat <<-EOF
  **Summary:**
  
  This PR automatically applies accessibility improvements suggested by an AI model.
  
  **Files Modified ($MODIFIED_COUNT):**
  $MODIFIED_FILES_LIST
  
  **Diff:**
  \`\`\`diff
  $DIFF_CONTENT
  \`\`\`
  EOF
  )
  
    # Create Pull Request using GitHub CLI
    echo "Creating Pull Request..."
    # Use GITHUB_TOKEN for authentication with gh cli
    echo "$GITHUB_TOKEN" | gh auth login --with-token
    gh pr create \
      --base "$(git remote show origin | grep 'HEAD branch' | cut -d' ' -f3)" \
      --head "$BRANCH" \
      --title "$PR_TITLE" \
      --body "$PR_BODY" \
      --repo "$GITHUB_REPOSITORY"
  
    echo "Pull Request created successfully."
    echo "branch-name=$BRANCH" >> $GITHUB_OUTPUT
  else
    echo "No files were modified. Skipping PR creation."
    echo "branch-name=" >> $GITHUB_OUTPUT # Ensure output is set even if no branch
  fi
  
  echo "files-modified=$MODIFIED_COUNT" >> $GITHUB_OUTPUT
  t config --global user.email "github-actions[bot]@users.noreply.github.com"
  BRANCH="bot/a11y-apply-$(date +%s)"
  git checkout -b "$BRANCH"
  git add .
  git commit -m "feat(bot): Apply AI-suggested accessibility improvements"
  git push "https://x-access-token:$INPUT_GITHUB_TOKEN@github.com/$GITHUB_REPOSITORY.git" "$BRANCH"
  echo "branch-name=$BRANCH" >> $GITHUB_OUTPUT
fi

echo "files-modified=$MODIFIED" >> $GITHUB_OUTPUT
