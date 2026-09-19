# Deployment Preparation

## Supported runtime

The validated runtime is Python 3.13 on a minimal Debian-based container. Production deployment requires an approved environment, HTTPS termination, explicit trusted origins and hosts, and externally managed secrets.

## Build and local verification

```sh
docker build --tag audit-verification-system:local .
docker compose config
docker compose up --detach --build
docker compose ps
curl --fail http://127.0.0.1:8000/health/live
curl --fail http://127.0.0.1:8000/health/ready
```

Run `./scripts/validate.sh` outside the container before review. The CI workflow repeats the quality gate and build validation.

## Runtime security

The image runs as the unprivileged `audit` user, disables Python bytecode, excludes the active ledger and secrets from image context, drops Linux capabilities in Compose, prevents privilege escalation, and uses a read-only root filesystem with a limited temporary filesystem.

## Environment contract

Create `.env` outside version control from `.env.example`. Supply approved password verifier material, session secret, allowed origins, trusted hosts, and deployment settings. Never bake `.env` or accepted credentials into an image layer.

## Ledger storage

Compose mounts `./backend/audit_repo` explicitly at `/app/backend/audit_repo`. Back up the ledger before upgrades. The container image must never contain active ledger business records.

## Startup and shutdown

Use `docker compose up --detach --build` to start and `docker compose down` to stop. Confirm both health endpoints after every startup. A failed readiness check must block traffic and trigger ledger investigation.

## Backup and restore

Stop mutation traffic, copy the ledger and backup files with metadata preserved, calculate SHA-256 hashes, and store copies in an approved protected location. Restore only a verified backup while the service is stopped, then run readiness and the comprehensive quality gate.

## Upgrade and rollback

Build the candidate image, run the complete quality gate, back up the ledger, start the candidate against a copied ledger, and verify health. Roll back to the previous image and verified ledger backup if readiness or integrity validation fails.

## Deployment boundary

These artifacts prepare deployment only. They do not authorize production deployment, public exposure, proxy trust, secret provisioning, or automatic merging.
