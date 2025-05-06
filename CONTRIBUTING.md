# Contributing to MT5Linux

Thank you for considering contributing to MT5Linux! This document provides guidelines and instructions for contributing to the project.

## Code of Conduct

By participating in this project, you agree to abide by our code of conduct: be respectful, considerate, and collaborative.

## How Can I Contribute?

### Reporting Bugs

- Check if the bug has already been reported in the [Issues](https://github.com/lucas-campagna/mt5linux/issues)
- Use the bug report template when creating a new issue
- Include detailed steps to reproduce the bug
- Include information about your environment (OS, Python version, Wine version, etc.)

### Suggesting Enhancements

- Check if the enhancement has already been suggested in the [Issues](https://github.com/lucas-campagna/mt5linux/issues)
- Use the feature request template when creating a new issue
- Clearly describe the enhancement and its benefits
- If possible, provide examples of how the enhancement would work

### Pull Requests

1. Fork the repository
2. Create a new branch for your feature or bugfix
3. Make your changes
4. Run the tests to ensure they pass
5. Submit a pull request

## Development Setup

1. Clone the repository:
   ```bash
   git clone https://github.com/lucas-campagna/mt5linux.git
   cd mt5linux
   ```

2. Install development dependencies:
   ```bash
   pip install -e ".[dev]"
   ```

3. Set up pre-commit hooks:
   ```bash
   pre-commit install
   ```

## Testing

Run the tests with pytest:
```bash
pytest
```

For more comprehensive testing:
```bash
make test-all
```

## Coding Standards

- Follow PEP 8 style guidelines
- Use Google-style docstrings
- Write tests for new features
- Keep functions and methods small and focused
- Use type hints where appropriate

## Documentation

- Update the documentation when changing functionality
- Use clear and concise language
- Include examples where appropriate

## Commit Messages

- Use the present tense ("Add feature" not "Added feature")
- Use the imperative mood ("Move cursor to..." not "Moves cursor to...")
- Reference issues and pull requests where appropriate

## Versioning

We use [Semantic Versioning](https://semver.org/). Please ensure your changes are appropriately versioned.

## License

By contributing to MT5Linux, you agree that your contributions will be licensed under the project's MIT license.