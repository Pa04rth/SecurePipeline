# Threat model

A STRIDE analysis of the SecurePipe pipeline itself — not of the FastAPI sample application. The aim is to make explicit what an attacker would try to do against this platform, which control in the system is supposed to stop them, and which risks are accepted because the mitigation lives outside the project's scope.

This is a one-page document on purpose. A threat model that nobody reads is worse than no threat model at all.

---

## Scope

**In scope.** Everything in the CI/CD path from a developer commit through to a running pod, plus the runtime and observability controls that watch it. Specifically: GitHub Actions workflows, the build and signing chain, the Kubernetes admission and runtime controllers, Vault and External Secrets Operator, Argo CD, the observability stack, and the network segmentation policies.

**Out of scope.** Identity provider compromise (GitHub account takeover), GitHub itself as a service, AWS as a service, supply chain compromise of the open-source tools used (Trivy, Kyverno, etc.), physical compromise of the cluster nodes, and any business-logic vulnerabilities in the FastAPI sample app — those belong to a separate application threat model.

---

## Assets worth protecting

| Asset                                                         | Why it matters                                                    |
| ------------------------------------------------------------- | ----------------------------------------------------------------- |
| Source code on `main`                                         | The trust root for everything downstream                          |
| `GITHUB_TOKEN` and per-workflow OIDC tokens                   | Can publish to GHCR, comment on PRs, sign images                  |
| The cosign signing identity (workflow path)                   | Forging it means images become indistinguishable from real builds |
| The Kyverno `ClusterPolicy`                                   | The last gate before a bad image runs                             |
| Vault root token and stored secrets                           | Game over for application credentials                             |
| Argo CD's git read credentials and its `signatureKeys` config | Bypassing them lets unsigned deployments through                  |
| The cluster's API server                                      | Compromise means the platform is owned                            |
| Falco's event stream                                          | An attacker who can silence it can operate undetected             |
| Loki log retention                                            | Tamper-evident audit relies on it                                 |

---

## Trust boundaries

There are five boundaries where authority changes hands. Each is a candidate for attack.

1. **Developer machine → GitHub.** Crossed via SSH or HTTPS + GPG-signed commits.
2. **GitHub Actions runner → external services.** Crossed by OIDC tokens (cosign + Sigstore) and `GITHUB_TOKEN` (GHCR push, PR comments).
3. **Git repository → Argo CD.** Crossed by Argo CD's polling of the repo on `main`.
4. **Argo CD → Kubernetes API.** Crossed by the in-cluster RBAC the controller uses.
5. **Kubernetes API → individual pods.** Crossed by admission controllers (Kyverno) and runtime sandbox controls.

---

## STRIDE

### Spoofing

| Threat                                                                       | Control                                                                                                                                                              |
| ---------------------------------------------------------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Attacker forges commits on `main` pretending to be a contributor             | GPG-signed commits enforced by Argo CD's `AppProject.signatureKeys`; only known keys (developer + GitHub web-flow merge key) are accepted                            |
| Attacker forges a container image pretending to come from the build workflow | cosign keyless signing tied to the workflow's OIDC identity; Kyverno's `verifyImages` keyless attestor matches on the exact workflow path regex                      |
| Attacker spoofs a pod identity to Vault                                      | Vault's Kubernetes auth method calls `TokenReview` against the Kubernetes API to validate the ServiceAccount JWT — forgery would require compromising the API server |
| Compromised dev pushes from a different machine without their key            | Mitigated only partially — GitHub branch protection rules requiring signed commits close this entirely                                                               |

### Tampering

| Threat                                                                     | Control                                                                                                                                                             |
| -------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Attacker modifies a workflow file on a PR branch to disable security scans | GitHub Actions `workflow_run` triggers always read workflow definitions from the default branch — changes on PR branches do not take effect for cross-workflow jobs |
| Attacker swaps the image at the registry between sign and deploy           | cosign verifies the image digest, not the tag; the signature is invalidated by any byte change                                                                      |
| Operator runs `kubectl edit` to bypass policy                              | Argo CD's `automated.selfHeal: true` reverts manual changes within ~30 seconds and Falco logs the action                                                            |
| Attacker tampers with the Vault stored secret                              | Vault's audit log records every write with timestamp, identity, and source — visible in Loki                                                                        |
| Attacker modifies the Kyverno policy                                       | Mutating policies requires cluster admin; Falco's audit rule catches CRD modifications (rule available but disabled by default in this build)                       |

### Repudiation

| Threat                                                                  | Control                                                                                                                             |
| ----------------------------------------------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------- |
| A contributor denies authoring a commit that introduced a vulnerability | Signed commits + git history + Sigstore Rekor transparency log together give cryptographic non-repudiation                          |
| The team disputes which deployment caused a regression                  | Argo CD records every sync with the source commit SHA; cross-referenced with Loki controller logs                                   |
| Nobody can determine who read a particular secret                       | Vault audit log (enabled to file in dev; recommended to ship to Loki in production) records every read with the requesting identity |

### Information disclosure

| Threat                                                           | Control                                                                                                                             |
| ---------------------------------------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------- |
| Secret committed to source code                                  | Gitleaks pre-merge gate; `.gitleaksignore` fingerprints documented per case                                                         |
| Secret embedded in a Kubernetes manifest in git                  | External Secrets Operator pattern enforces secrets stay in Vault — no `kind: Secret` lives in the repo                              |
| Secret baked into a container image layer                        | SBOM published via Syft makes layers inspectable; not directly enforced — accepted residual risk (see below)                        |
| GITHUB_TOKEN exfiltrated by malicious PR code via `workflow_run` | `persist-credentials: false` on checkout + `if:` block gating against fork PRs + same-repo workflow_run trigger only                |
| Loki retains sensitive log lines                                 | Application-level redaction is out of scope; Loki retention is configurable, and Calico NetworkPolicies restrict who can query Loki |
| Falco events sent to Slack contain secret values                 | Falco rules use field selectors that exclude payload content by default                                                             |

### Denial of service

| Threat                                               | Control                                                                                                                           |
| ---------------------------------------------------- | --------------------------------------------------------------------------------------------------------------------------------- |
| Attacker spams PRs to consume GitHub Actions minutes | `concurrency:` groups per workflow cancel in-progress runs on the same ref; branch protection on the repo limits the spam surface |
| Compromised pod tries to exhaust node resources      | Deployment manifests set CPU and memory `limits`; NetworkPolicy `egress` rules prevent outbound abuse                             |
| Attacker targets Vault to deny credential issuance   | Calico NetworkPolicy isolates the Vault namespace; only the application and ESO can reach it on port 8200                         |
| Falco's event volume overwhelms the alert sink       | Falco's `outputs_queue` and the `minimumpriority: warning` filter in Falcosidekick drop noise before it reaches Slack             |

### Elevation of privilege

| Threat                                                                                         | Control                                                                                                                                                                                    |
| ---------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| Attacker escapes the application container to the host                                         | Pod runs with `readOnlyRootFilesystem: true`, `runAsNonRoot: true`, all capabilities dropped, `allowPrivilegeEscalation: false`                                                            |
| Compromised app pod reads its own ServiceAccount token to call the Kubernetes API              | Custom Falco rule `SecurePipe App Reading Service Account Token` fires at runtime; default-deny NetworkPolicy blocks outbound to the API server unless explicitly allowed                  |
| ESO ServiceAccount used to read secrets it should not                                          | Vault role `app` binds the SA to a single policy with read-only access to `secret/data/app`                                                                                                |
| Pull-request code in a forked repo executes inside a privileged workflow context (pwn-request) | Consolidate workflow's `if:` block restricts runs to `head_repository.full_name == github.repository`; the `nosemgrep:` for `workflow-run-target-code-checkout` documents why this is safe |
| Kyverno is bypassed via a deliberately mutated request                                         | Kyverno runs in `enforce` mode with `mutateDigest: false` to prevent silent rewrites                                                                                                       |

---

## Review

This document should be revisited any time a new component is added to the platform, any time an existing control is changed, or every six months at minimum. Each entry above is dated by the commit that introduces it. Threat models that are not maintained become misleading rather than absent.
