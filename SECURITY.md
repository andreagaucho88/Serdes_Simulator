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

Do not expose the current server directly to an untrusted network. A hosted
deployment must add, at minimum:

- authenticated sessions and authorization;
- per-user state isolation;
- upload size and parser limits;
- CPU/time quotas for simulations and experiments;
- CSRF/origin controls and secure proxy headers;
- audit logging and dependency monitoring.

No credentials, private agent notes, or developer-specific filesystem paths
should be committed to the repository.
