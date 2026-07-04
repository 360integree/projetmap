# Contributing to Codemap

Thank you for your interest in contributing to Codemap! This document provides guidelines and information for contributors.

## Getting Started

### Prerequisites

- Python 3.10 or higher
- Git

### Development Setup

1. **Fork the repository**
   ```bash
   # Fork on GitHub, then clone your fork
   git clone https://github.com/YOUR_USERNAME/projetmap.git
   cd projetmap
   ```

2. **Create a virtual environment**
   ```bash
   python -m venv .venv
   source .venv/bin/activate  # On Windows: .venv\Scripts\activate
   ```

3. **Install in development mode**
   ```bash
   pip install -e ".[dev,full]"
   ```

4. **Verify installation**
   ```bash
   projetmap --help
   pytest --version
   ruff --version
   ```

## Development Workflow

### Branching Strategy

- `main` — stable release branch
- `feat/*` — new features
- `fix/*` — bug fixes
- `docs/*` — documentation changes
- `refactor/*` — code refactoring

### Making Changes

1. **Create a feature branch**
   ```bash
   git checkout -b feat/your-feature-name
   ```

2. **Make your changes**
   - Write code following the project's style
   - Add tests for new functionality
   - Update documentation if needed

3. **Run quality checks**
   ```bash
   # Linting
   ruff check projetmap/
   
   # Formatting
   ruff format projetmap/
   
   # Tests
   pytest
   ```

4. **Commit your changes**
   ```bash
   git add .
   git commit -m "feat: add new feature description"
   ```
   
   Follow [Conventional Commits](https://www.conventionalcommits.org/):
   - `feat:` — new feature
   - `fix:` — bug fix
   - `docs:` — documentation
   - `refactor:` — code refactoring
   - `test:` — adding tests
   - `chore:` — maintenance

5. **Push and create a Pull Request**
   ```bash
   git push origin feat/your-feature-name
   ```

## Code Style

### Python

- Follow PEP 8 (enforced by ruff)
- Use type hints where practical
- Keep functions focused and concise
- Write docstrings for public APIs

### Ruff Configuration

```toml
[tool.ruff]
line-length = 100
target-version = "py310"
```

### Testing

- Write tests for new features and bug fixes
- Aim for meaningful coverage (not just line count)
- Use descriptive test names
- Place tests in `tests/` mirroring source structure

## Pull Request Guidelines

### Before Submitting

- [ ] Code passes `ruff check`
- [ ] Code passes `ruff format --check`
- [ ] All tests pass (`pytest`)
- [ ] New tests added for new functionality
- [ ] Documentation updated (if applicable)
- [ ] Commit messages follow conventions

### PR Description

Include:
- **What** — Summary of changes
- **Why** — Context and motivation
- **How** — Implementation approach (if complex)
- **Testing** — How to verify the changes

### Review Process

1. Maintainers will review your PR
2. Address feedback and make requested changes
3. Once approved, a maintainer will merge your PR

## Reporting Issues

### Bug Reports

Include:
- Python version (`python --version`)
- Operating system
- Codemap version (`pip show projetmap`)
- Steps to reproduce
- Expected vs actual behavior
- Error messages/logs

### Feature Requests

Include:
- Use case description
- Proposed solution (if any)
- Alternatives considered

## Adding Language Support

See `projetmap/behavioral/SCHEMA.md` for the full contract.

1. Create `projetmap/behavioral/extractors/<language>/`
2. Implement an extractor outputting `behavioral_data.json`
3. Register in `projetmap/behavioral/extractors/__init__.py`
4. Add tests in `tests/`

## Code of Conduct

Be respectful, inclusive, and constructive. We're here to build something useful together.

## Questions?

Open a discussion on GitHub or reach out to the maintainers.

Thank you for contributing! 🗺️
