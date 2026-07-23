# Contributing to IntelliScrape

Thanks for your interest in contributing! IntelliScrape is built by the community, for the community.

## Ways to Contribute

### 1. Anti-Bot Bypass Patterns

Found a way to bypass a new anti-bot system? We'd love to add it.

```
anti_detection/
└── bypasses/
    ├── cloudflare.py
    ├── akamai.py
    └── ...
```

### 2. CAPTCHA Solving Techniques

Know how to solve a new CAPTCHA type? Add it to:

```
challenges/
└── captcha.py
```

### 3. Proxy Provider Integrations

Use a proxy service? Add integration for:

```
proxy/
└── providers/
    ├── brightdata.py
    ├── scraperapi.py
    └── ...
```

### 4. Bug Fixes

Found a bug? Open an issue or submit a PR.

### 5. Documentation

Help us improve docs, examples, or tutorials.

## Getting Started

1. Fork the repo
2. Create a branch: `git checkout -b my-feature`
3. Make your changes
4. Run tests: `pytest`
5. Submit a PR

## Code Style

- Use type hints
- Follow PEP 8
- Add docstrings to public functions
- Keep it readable

## Testing

```bash
# Install dev dependencies
pip install intelliscrape[dev]

# Run tests
pytest

# Run with verbose output
pytest -v
```

## Questions?

Open a [Discussion](https://github.com/GuixJoy/IntelliScrape/discussions) on GitHub.
