# Security Policy

## Supported versions

The project is pre-1.0. Security fixes land on the `main` branch and, when one
exists, the latest tagged release.

## Reporting a vulnerability

Please **do not** open a public issue for security problems. Report privately:

- Email / DM to the maintainer (see GitHub profile), or
- GitHub's private vulnerability reporting form on this repository.

Please include:
- Affected command / flow and version,
- Steps to reproduce,
- Impact (e.g. arbitrary code execution, brick risk, data loss, credential exposure).

We aim to acknowledge reports within 72 hours and will coordinate disclosure.

## Scope & expectations

This tool intentionally performs low-level USB / bootloader operations. By its
nature it can wipe or brick a device. That is documented behaviour, not a
vulnerability. We care about:

- Exploits that run untrusted code beyond the intended operation,
- Bypassing safety confirmations / device checks in a way that harms users,
- Shipping proprietary blobs or secrets in the repository,
- Anything that leaks a user's device data or credentials.

Please operate only on devices you own or are authorized to service.