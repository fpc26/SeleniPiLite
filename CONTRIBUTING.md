# Contributing to SeleniPiLite

Thank you for your interest in contributing to SeleniPiLite! This document provides guidelines for contributing to the project.

## How to Contribute

### Reporting Issues

- Use the GitHub issue tracker to report bugs or suggest features
- Check if the issue already exists before creating a new one
- Provide clear and detailed information about the issue
- Include steps to reproduce for bug reports
- Include your environment details (Python version, OS, hardware)

### Submitting Changes

1. **Fork the repository** and create a new branch for your changes
   ```bash
   git checkout -b feature/your-feature-name
   ```

2. **Make your changes**
   - Write clear, concise code
   - Follow the existing code style
   - Add comments where necessary
   - Update documentation as needed

3. **Test your changes**
   - Test on desktop using `--backend file`
   - Test on Raspberry Pi if possible
   - Ensure existing functionality still works

4. **Commit your changes**
   - Use clear commit messages
   - Reference related issues in commits
   ```bash
   git commit -m "Add feature: description (fixes #123)"
   ```

5. **Submit a pull request**
   - Provide a clear description of your changes
   - Link to any related issues
   - Be responsive to feedback

## Development Setup

1. Clone the repository:
   ```bash
   git clone https://github.com/fpc26/SeleniPiLite.git
   cd SeleniPiLite
   ```

2. Create a virtual environment:
   ```bash
   python3 -m venv .venv/lunar
   source .venv/lunar/bin/activate
   ```

3. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

4. Test your installation:
   ```bash
   python lunar_pi_skyfield.py --backend file --output test.png
   ```

## Code Style

- Follow PEP 8 guidelines for Python code
- Use meaningful variable and function names
- Add docstrings to functions and classes
- Keep functions focused and modular

## Pull Request Guidelines

- Keep changes focused and minimal
- Update relevant documentation
- Test thoroughly before submitting
- Respond to review feedback promptly
- Squash commits if requested

## Questions?

If you have questions about contributing, feel free to:
- Open an issue with the "question" label
- Check existing issues and discussions
- Review the README.md for project overview

## License

By contributing, you agree that your contributions will be licensed under the MIT License.
