# Security Policy

## Supported Versions

We actively support the following versions with security updates:

| Version | Supported          |
| ------- | ------------------ |
| 7.x.x   | :white_check_mark: |
| 6.x.x   | :x:                |
| < 6.0   | :x:                |

## Reporting a Vulnerability

We take security vulnerabilities seriously. If you discover a security issue, please report it responsibly.

### How to Report

1. **Do NOT** create a public GitHub issue for security vulnerabilities
2. Email the maintainer directly or use GitHub's private vulnerability reporting feature
3. Include as much detail as possible:
   - Description of the vulnerability
   - Steps to reproduce
   - Potential impact
   - Suggested fix (if any)

### What to Expect

- **Acknowledgment**: We will acknowledge receipt within 48 hours
- **Assessment**: We will assess the vulnerability within 7 days
- **Resolution**: Critical vulnerabilities will be addressed within 30 days
- **Disclosure**: We will coordinate disclosure timing with you

### Security Best Practices for Users

1. **API Key Security**
   - Never commit your `.env` file to version control
   - Use environment variables in CI/CD instead of hardcoded values
   - Rotate API keys periodically

2. **File Permissions**
   - The application creates files with `0600` permissions (owner read/write only)
   - Ensure your config directory has appropriate permissions

3. **Remote Domains**
   - When using `DOMAINS_URL`, consider enabling hash verification with `DOMAINS_HASH_URL`
   - Only use trusted HTTPS URLs

4. **Docker**
   - The Docker image runs as non-root user
   - Don't mount sensitive host directories

## Security Features

This project includes several security features:

- **Secure file permissions**: All sensitive files are created with `0600` mode
- **Input validation**: Domain names, URLs, and configuration values are validated
- **Rate limiting**: Built-in rate limiter prevents API abuse
- **Audit logging**: All actions are logged for accountability
- **Hash verification**: Optional SHA256 verification for remote domains
- **No shell injection**: Uses `shlex.quote()` for shell command construction

## Dependencies

We regularly scan dependencies for vulnerabilities using:
- `safety` - Python dependency vulnerability scanner
- `bandit` - Python security linter
- Dependabot - Automated dependency updates

## Acknowledgments

We appreciate responsible disclosure from security researchers. Contributors who report valid security issues will be acknowledged here (with permission).
