# Security policy

## Supported version

The current <code>0.1.x</code> line receives security fixes.

## Reporting a vulnerability

Do not open a public issue for a vulnerability. Use GitHub's private
**Security → Report a vulnerability** flow for this repository and include:

- affected version or commit;
- reproduction steps;
- expected impact;
- any proposed mitigation.

## Deployment boundary

Lab PRO is designed to bind to localhost and operate as a single-user
educational workbench. Its API does not provide authentication, authorization,
multi-tenant isolation, or public-service resource quotas.

The local server binds only to `127.0.0.1`, rejects non-loopback Host headers
and cross-origin state mutations, limits all request bodies to 16 MiB, and
limits Touchstone text to 8 MiB. WebSocket origins are restricted to loopback
hosts as well.

Do not expose the current server directly to an untrusted network. A hosted
deployment must add, at minimum:

- authenticated sessions and authorization;
- per-user state isolation;
- deployment-specific upload and parser limits;
- CPU/time quotas for simulations and experiments;
- CSRF/origin controls for the public URL and secure proxy headers;
- audit logging and dependency monitoring.

No credentials, private agent notes, or developer-specific filesystem paths
should be committed to the repository.
