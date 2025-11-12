# Security Policy

## Reporting a Vulnerability

We take the security of SeleniPiLite seriously. If you discover a security vulnerability, please follow these steps:

### How to Report

**Do NOT** open a public issue for security vulnerabilities.

Instead, please report security vulnerabilities by:
- Opening a [Security Advisory](https://github.com/fpc26/SeleniPiLite/security/advisories/new) on GitHub
- Or emailing the maintainer directly (see GitHub profile)

### What to Include

Please include the following information in your report:
- Description of the vulnerability
- Steps to reproduce the issue
- Potential impact of the vulnerability
- Suggested fix (if you have one)
- Your contact information (optional)

### Response Timeline

- We will acknowledge receipt of your report within 48 hours
- We will provide an estimated timeline for a fix within 7 days
- We will notify you when the vulnerability is fixed

## Supported Versions

| Version | Supported          |
| ------- | ------------------ |
| Latest  | :white_check_mark: |
| Older   | :x:                |

We recommend always using the latest version of SeleniPiLite.

## Security Best Practices

When using SeleniPiLite:

1. **Keep dependencies updated**: Regularly update Python packages
   ```bash
   pip install --upgrade -r requirements.txt
   ```

2. **Run with minimal privileges**: Don't run as root unless necessary
   - Use the appropriate GPIO factory (pigpio or lgpio)
   - Add your user to the necessary groups (spi, i2c, gpio)

3. **Network security**: If exposing a web interface (future feature):
   - Use HTTPS/TLS
   - Implement authentication
   - Keep the service on a private network

4. **File permissions**: Ensure configuration files have appropriate permissions
   ```bash
   chmod 644 requirements.txt
   chmod 755 scripts/*.sh
   ```

5. **Virtual environment**: Always use a virtual environment
   ```bash
   python3 -m venv .venv/lunar
   source .venv/lunar/bin/activate
   ```

## Known Security Considerations

- The application requires GPIO/SPI/I2C access on Raspberry Pi
- Touch input is processed locally on the device
- No network communication is performed by default
- No user credentials or sensitive data are stored

## Disclosure Policy

- We will coordinate with you on disclosure timing
- We will credit you in the security advisory (unless you prefer to remain anonymous)
- We will publish a security advisory after the fix is released
