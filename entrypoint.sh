#!/bin/sh -l
set -e

# Debug: print environment variable presence
if [ -z "$INPUT_OPENAI_API_KEY" ]; then
  echo "::error::OPENAI_API_KEY is not set!"
else
  echo "OPENAI_API_KEY is set."
fi
# GITHUB_TOKEN is an environment variable automatically provided by GitHub Actions
if [ -z "$INPUT_GITHUB_TOKEN" ]; then 
  echo "::error::GITHUB_TOKEN is not set! This should be automatically provided by GitHub Actions."
else
  echo "GITHUB_TOKEN is set."
fi

export OPENAI_API_KEY="$INPUT_OPENAI_API_KEY"
export GH_TOKEN="$INPUT_GITHUB_TOKEN" # GH_TOKEN is used by gh cli, set it from the default GITHUB_TOKEN
export INPUT_OPENAI_MODEL_NAME="${INPUT_OPENAI_MODEL_NAME:-gpt-4.1}" # Pass model name to script
export INPUT_PROCESS_CHANGED_FILES_ONLY="${INPUT_PROCESS_CHANGED_FILES_ONLY:-false}" # Pass changed files flag to script

# Find SwiftUI files
if [ "$INPUT_PROCESS_CHANGED_FILES_ONLY" = "true" ]; then
  echo "Processing only changed Swift files from the last commit."
  # Get files changed in the last commit, filter by .swift extension, and ensure they exist and contain 'import SwiftUI'
  # Ensure git commands run in the correct directory and handle cases where no files were changed.
  # Fetch enough history to be able to diff HEAD^
  git fetch --depth=2 || echo "Fetch failed, proceeding with local history. This might fail if history is too shallow."
  FILES=$(git diff --name-only HEAD^ HEAD -- '*.swift' | xargs -I {} sh -c 'test -f "$1" && grep -q "import SwiftUI" "$1" && echo "$1"' _ {} || echo "")
  if [ -z "$FILES" ]; then
    echo "No changed Swift files containing 'import SwiftUI' found in the last commit."
  else
    echo "Changed SwiftUI files to process: $FILES"
  fi
else
  echo "Processing all SwiftUI files in the repository."
  FILES=$(find . -name '*.swift' | xargs grep -l 'import SwiftUI')
  if [ -z "$FILES" ]; then
    echo "No SwiftUI files found in the repository."
  fi
fi

echo "SwiftUI files to process: $FILES"

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

  # Set PR title with previous commit message (before bot commit)
  # HEAD is now the bot's commit. HEAD~1 is the commit before the bot's.
  PREV_COMMIT_MSG=$(git log --pretty=format:%s HEAD~1 -1)
  PR_TITLE="[Accessibility-Bot] Update accessibility for: $PREV_COMMIT_MSG"

  # Construct PR Body
  # MODIFIED_FILES_FOR_PR_BODY already contains formatted list of files
  # DIFF_CONTENT was captured from 'git diff --staged' before the commit
  PR_BODY_SUMMARY_TEXT="The following files were modified by the accessibility bot:\n$MODIFIED_FILES_FOR_PR_BODY"

  PR_BODY_CONTENT_FILE=$(mktemp)
  {
    echo "$PR_BODY_SUMMARY_TEXT"
    echo ""
    echo "<details><summary>View changes</summary>"
    echo ""
    echo "\`\`\`diff"
    echo "$DIFF_CONTENT"
    echo "\`\`\`"
    echo ""
    echo "</details>"
  } > "$PR_BODY_CONTENT_FILE"

  # Determine base branch more reliably
  BASE_BRANCH_NAME=$(git symbolic-ref refs/remotes/origin/HEAD | sed 's@^refs/remotes/origin/@@' 2>/dev/null)
  if [ -z "$BASE_BRANCH_NAME" ]; then
    echo "::warning::Could not determine base branch using 'git symbolic-ref'. Trying fallback: 'git remote show origin | grep HEAD | awk \\'{print \\$NF\\}''. "
    BASE_BRANCH_NAME=$(git remote show origin | grep 'HEAD branch' | awk '{print $NF}')
  fi
  
  if [ -z "$BASE_BRANCH_NAME" ]; then
    echo "::error::Could not determine the base branch name. Exiting."
    rm "$PR_BODY_CONTENT_FILE" # Clean up temp file
    exit 1
  fi
  echo "Base branch for PR: $BASE_BRANCH_NAME"
  echo "Head branch for PR: $BRANCH"

  gh pr create \
    --base "$BASE_BRANCH_NAME" \
    --head "$BRANCH" \
    --title "$PR_TITLE" \
    --body-file "$PR_BODY_CONTENT_FILE" # Corrected to --body-file
  
  rm "$PR_BODY_CONTENT_FILE" # Clean up the temporary file

  echo "Pull Request created successfully."
  echo "branch-name=$BRANCH" >> "$GITHUB_OUTPUT"
else
  echo "No files were modified. Skipping PR creation."
  echo "branch-name=" >> "$GITHUB_OUTPUT" # Ensure output is set even if no branch
fi

echo "files-modified=$MODIFIED_COUNT" >> "$GITHUB_OUTPUT"
