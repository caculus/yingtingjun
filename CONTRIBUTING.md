# Contributing

Thank you for helping with Yingtingjun.

You do not need to be a programmer to contribute. Bug reports, installer feedback, documentation edits, UI wording, and learning-feature ideas are all useful.

[繁體中文](CONTRIBUTING.zh-TW.md)

## Ways to help

- Report a bug or a confusing installer step
- Improve docs (`README.md`, `docs/`)
- Translate or polish player UI copy
- Make the install flow clearer or more reliable
- Add tests that do not require real ASR or translation models
- Improve learning features such as notes, dictionary lookup, and partial re-transcription

Please do **not** commit personal recordings, transcripts, notes, or `HANDOFF.md`. Those stay local.

## Report a bug

Open a GitHub issue and include:

- Platform and CPU architecture (`macOS Apple Silicon`, `Windows x64`, `Linux ARM64`, …)
- Installer or source-based setup
- What you did
- What you expected
- What actually happened
- Relevant terminal or player log output

Use [Troubleshooting](docs/troubleshooting.md) first if the problem looks like a known install issue.

## Development setup

Start here:

- [Installation](docs/installation.md)
- [Development](docs/development.md)

Quick notes:

- macOS: `requirements.txt`
- Windows: `requirements-windows.txt` and `scripts/install_windows.ps1`
- Linux: `requirements-linux.txt` and `scripts/install_linux.sh`
- Do not compile `speakrs` on Windows or Linux
- Tests should stay local and lightweight: `python -m pytest`

## Pull requests

- Keep the change focused on one issue
- Match the existing style of nearby files
- If you change install or packaging behavior, say how you smoke-tested it
- If you only change docs or copy, say so in the PR

## Language

English and Traditional Chinese are both welcome in issues, PRs, and UI copy.
