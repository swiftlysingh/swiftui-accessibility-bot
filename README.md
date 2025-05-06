# swiftui-accessibility-bot

This GitHub Action automatically reviews and applies accessibility improvements to your SwiftUI views using OpenAI's language models. It then creates a pull request with the suggested changes.

## Features

-   **Automated Accessibility Improvements**: Leverages LLMs to identify and suggest accessibility enhancements for your SwiftUI code.
-   **Customizable OpenAI Model**: Specify the OpenAI model you want to use (e.g., `gpt-4`, `gpt-4.1`, `gpt-4-turbo`). Defaults to `gpt-4.1`.
-   **Process Specific Files**:
    -   Process all SwiftUI files in the repository.
    -   Process only SwiftUI files that were changed in the current commit.
-   **Pull Request Creation**: Automatically creates a pull request with the applied changes.

## Inspiration

This project was inspired by the talk and work of Allison McEntire on accessibility. You can find more about her insights here: [gist.github.com/allisonpaigemcentire](https://gist.github.com/allisonpaigemcentire/719b856796d599e9d758e8a1343b5bd8).

## Important Considerations

-   **Code Modification**: This bot directly modifies your codebase by applying accessibility improvements. It is **highly recommended** that you carefully review all changes proposed in the pull requests created by this bot before merging them.
-   **Model Behavior**: The quality and nature of the suggestions depend on the OpenAI model used. While the bot aims to apply only additive accessibility modifiers, always verify the changes.

## Prerequisites

1.  **OpenAI API Key**: You need an OpenAI API key with access to the desired models. This key should be stored as a secret in your GitHub repository (e.g., `OPENAI_API_KEY`).
2.  **GitHub Token**: The action uses a GitHub token to create branches and pull requests. The default `GITHUB_TOKEN` provided by GitHub Actions usually has the necessary permissions.

## Permissions Required

For this action to function correctly, it needs permissions to:
-   Read repository contents.
-   Write repository contents (to commit changes and push a new branch).
-   Create pull requests.

You may need to adjust your repository's settings to grant these permissions to GitHub Actions. Navigate to your repository's `Settings > Actions > General` and ensure that "Workflow permissions" are set to "Read and write permissions". If you restrict the default `GITHUB_TOKEN` permissions, you might need to provide a token with sufficient scopes.

## Usage

To use this action in your workflow, add a step similar to the following:

```yaml
name: SwiftUI Accessibility Check

on: [push] # Or your preferred trigger

jobs:
  accessibility-bot:
    runs-on: ubuntu-latest
    permissions:
      contents: write      # Required to push new branches
      pull-requests: write # Required to create PRs
    steps:
      - uses: actions/checkout@v4
        with:
          # fetch-depth: 0 is recommended to fetch all history.
          # This is crucial if using `process_changed_files_only: true` 
          # or if your action needs to reliably determine the base branch for PRs.
          fetch-depth: 0 

      - name: Run SwiftUI Accessibility Bot
        uses: your-username/swiftui-accessibility-bot@v1 # Replace with your action's path or version
        env:
          GH_TOKEN: ${{ github.token }} # Pass the GitHub token for PR creation and push
        with:
          openai_api_key: ${{ secrets.OPENAI_API_KEY }}
          # Optional: Specify a different OpenAI model
          # openai_model_name: 'gpt-4-turbo'
          # Optional: Process only files changed in the current commit
          # process_changed_files_only: true
```

### Inputs

Refer to the `action.yml` file for a complete list of inputs and their descriptions.

-   `openai_api_key` (required): Your OpenAI API key.
-   `openai_model_name` (optional): The OpenAI model to use. Defaults to `gpt-4.1`.
-   `process_changed_files_only` (optional): Set to `true` to only process files changed in the current commit. Defaults to `false`.

### Outputs

-   `branch-name`: The name of the branch created with the accessibility improvements.
-   `files-modified`: The number of files modified by the bot.

## Contributing

Contributions are welcome! Please open an issue or submit a pull request.

## License

This project is licensed under the MIT License.