# Contributing to EAN Reader

Thank you for your interest in contributing to EAN Reader! This document provides guidelines for contributing to the project.

## Code of Conduct

- Be respectful and constructive
- Help others in issues and discussions
- Focus on what's best for the community
- Show empathy towards other contributors

## Before You Start

1. Check [existing issues](https://github.com/swetoast/ha-ean-reader/issues) to avoid duplicates
2. For major changes, open an issue first to discuss
3. Ensure you have a working Home Assistant test environment
4. Familiarize yourself with [Home Assistant integration development](https://developers.home-assistant.io/)

## Development Setup

### Prerequisites

- Home Assistant development environment
- Python 3.11 or higher
- Git

### Local Development

1. Fork the repository
2. Clone your fork:
   ```bash
   git clone https://github.com/YOUR_USERNAME/ha-ean-reader.git
   cd ha-ean-reader
   ```

3. Create a development branch:
   ```bash
   git checkout -b feature/your-feature-name
   ```

4. Install development dependencies:
   ```bash
   pip install -r requirements.txt
   ```

5. Create a symbolic link in your Home Assistant config:
   ```bash
   ln -s $(pwd)/custom_components/ean_reader ~/.homeassistant/custom_components/ean_reader
   ```

6. Restart Home Assistant and test your changes

## Making Changes

### Code Style

- Follow [PEP 8](https://pep8.org/) style guide
- Use meaningful variable and function names
- Add docstrings to functions and classes
- Keep functions focused and small
- Add type hints where possible

### Testing

Before submitting:

1. **Test with real barcodes** - Scan actual products
2. **Test rate limiting** - Scan 15+ products rapidly
3. **Test error cases** - Invalid EANs, network errors, etc.
4. **Test all services** - Verify each service works correctly
5. **Check logs** - No errors or warnings in logs

### OpenFoodFacts API Compliance

When modifying API calls:

- Maintain User-Agent format: `AppName/Version (Email)`
- Respect rate limits (12 req/min conservative limit)
- Handle HTTP 503 gracefully (rate limit exceeded)
- Don't cache products as "unknown" if rate limited
- Test with `openfoodfacts-python` library directly

## Commit Guidelines

### Commit Messages

Use conventional commit format:

```
type(scope): Short description

Longer description if needed

Fixes #123
```

**Types:**
- `feat`: New feature
- `fix`: Bug fix
- `docs`: Documentation changes
- `style`: Code style changes (formatting, etc.)
- `refactor`: Code refactoring
- `test`: Adding tests
- `chore`: Maintenance tasks

**Examples:**
```
feat(services): Add bulk import service for mappings

fix(rate-limit): Handle HTTP 503 without caching as unknown

docs(readme): Update installation instructions for HACS
```

## Pull Request Process

1. **Update documentation** - README, docstrings, comments
2. **Test thoroughly** - Follow testing checklist above
3. **Update manifest** - If dependencies changed
4. **Create PR** with clear description:
   - What problem does it solve?
   - How was it tested?
   - Screenshots (if UI changes)
   - Breaking changes (if any)

5. **Respond to reviews** - Address feedback promptly
6. **Squash commits** - Keep history clean (if requested)

## Issue Guidelines

### Bug Reports

Use the bug report template and include:
- Home Assistant version
- Integration version
- Steps to reproduce
- Expected vs actual behavior
- Relevant logs (with sensitive info removed)
- Example EAN that triggers the bug

### Feature Requests

Use the feature request template and include:
- Clear use case
- Why it's useful
- Proposed implementation (if you have ideas)
- Alternatives considered

## Areas Needing Help

Current priorities:

- [ ] Improve error messages for common issues
- [ ] Add more comprehensive unit tests
- [ ] Support for additional barcode formats
- [ ] Better handling of network timeouts
- [ ] Translations for other languages
- [ ] Integration with more shopping list platforms

## Questions?

- Open a [Discussion](https://github.com/swetoast/ha-ean-reader/discussions) for general questions
- Open an [Issue](https://github.com/swetoast/ha-ean-reader/issues) for bugs or features
- Check existing issues for similar questions

## License

By contributing, you agree that your contributions will be licensed under the MIT License.

## Attribution

When contributing significant changes:
- Add yourself to contributors in README (optional)
- Sign commits if possible (recommended)

Thank you for contributing! 🎉
