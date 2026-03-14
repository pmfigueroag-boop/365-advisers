# 365 Advisers — Security Controls & Compliance
## SOC2 Type II Relevant Controls

### Document Control
| Property | Value |
|---|---|
| **Version** | 1.0 |
| **Classification** | Internal |
| **Last Reviewed** | 2026-03-13 |
| **Owner** | Platform Security Team |

---

## 1. Access Control (CC6.1 - CC6.3)

### Authentication
- [x] **JWT-based authentication** with configurable expiration (default 8h)
- [x] **Role-Based Access Control** (RBAC) with 3 tiers: VIEWER, ANALYST, ADMIN
- [x] **Bcrypt password hashing** (12 rounds, adaptive cost factor)
- [x] **SHA-256 → bcrypt migration** path for existing credentials
- [ ] **Identity Provider integration** (Auth0/Okta) — roadmap Q2 2026
- [ ] **Multi-Factor Authentication** — roadmap Q2 2026

### Authorization
- [x] Role hierarchy enforcement (ADMIN > ANALYST > VIEWER)
- [x] Endpoint-level RBAC with FastAPI dependencies
- [x] `AUTH_ENABLED` kill switch for emergency access

### Session Management
- [x] JWT tokens with configurable expiration
- [x] Token-based stateless authentication
- [ ] Refresh token rotation — roadmap

---

## 2. Audit & Accountability (CC7.1 - CC7.3)

### Audit Trail
- [x] **Full request audit logging** via middleware
- [x] Fields captured: user, method, path, status, duration, IP, user-agent
- [x] **In-memory ring buffer** (1000 events) for real-time monitoring
- [x] **Database persistence** (AuditLog table) for compliance retention
- [x] Admin API: `GET /api/audit/recent`, `GET /api/audit/stats`
- [x] High-frequency endpoints excluded (health checks)

### Monitoring
- [x] **OpenTelemetry** tracing with span-level LLM call instrumentation
- [x] **Cost tracking** with daily budgets and automated alerts
- [x] **Health checks**: `/health` (6 subsystems), `/health/live`, `/health/ready`

---

## 3. Data Protection (CC6.5 - CC6.7)

### Input Validation
- [x] **Ticker sanitization** — regex validation, format enforcement
- [x] **Anti-prompt injection** — 14 detection patterns for LLM inputs
- [x] **Text sanitization** — control character removal, length limits
- [x] **Recursive data sanitization** — nested dict/list cleaning
- [x] Data markers (`[USER_DATA_START]`/`[USER_DATA_END]`) for injection neutralization

### Encryption
- [x] **TLS 1.3** enforced at reverse proxy (Nginx)
- [x] **HSTS** with preload (63072000 seconds)
- [x] mTLS configuration prepared for inter-service communication
- [x] **Security headers**: CSP, X-Frame-Options, X-Content-Type-Options

### Secrets Management
- [x] **SecretsManager** abstraction (env, Vault, AWS backends)
- [x] Environment variable isolation in containers
- [x] Kubernetes Secrets integration in deployment manifests
- [ ] Automated secret rotation — roadmap

---

## 4. Infrastructure Security (CC6.6 - CC6.8)

### Container Security
- [x] **Multi-stage Docker builds** (minimal attack surface)
- [x] **Non-root containers** (runAsUser: 1000)
- [x] Resource limits enforced (CPU/memory caps)
- [x] Read-only root filesystem capable

### Network Security
- [x] **Kubernetes NetworkPolicy** (Zero Trust)
  - Backend only accepts traffic from frontend + ingress
  - Egress restricted to Redis + external APIs (443)
- [x] Rate limiting at multiple layers (Nginx + application middleware)
- [x] CORS restricted to specific origins

### Auto-Scaling & Availability
- [x] **HorizontalPodAutoscaler** (2-8 replicas)
  - Scale up: 70% CPU or 80% memory
  - Scale down stabilization: 5 minutes
- [x] **Liveness, readiness, and startup probes**
- [x] Rolling update deployment strategy

---

## 5. Change Management (CC8.1)

### CI/CD Pipeline
- [x] **GitHub Actions** automated pipeline
  - Lint → Test → Docker Build → Integration verify
- [x] Automated test suite (99+ tests)
- [x] **Alembic** database migration versioning

### Schema Versioning
- [x] Database models with bounded context separation
- [x] Alembic migration environment configured
- [x] Forward/backward migration support

---

## 6. Cost Controls (CC5.3)

### LLM Budget Management
- [x] Per-model cost tracking (Flash: $0.15/1M input, Pro: $1.25/1M input)
- [x] Configurable daily budget (`DAILY_LLM_BUDGET_USD`)
- [x] Alert at 80% threshold
- [x] **Auto-downgrade** Pro → Flash when budget exceeded
- [x] Real-time cost monitoring API (`GET /api/costs`)

---

## Compliance Readiness Matrix

| SOC2 Criteria | Status | Coverage |
|---|---|---|
| CC6.1 Logical Access | ✅ Implemented | JWT + RBAC + bcrypt |
| CC6.3 Role Management | ✅ Implemented | 3-tier hierarchy |
| CC6.5 Data Protection | ✅ Implemented | TLS + input validation |
| CC6.6 System Security | ✅ Implemented | Container hardening + NetworkPolicy |
| CC7.1 Detection | ✅ Implemented | OTEL + audit trail |
| CC7.2 Monitoring | ✅ Implemented | Health checks + cost tracking |
| CC8.1 Change Management | ✅ Implemented | CI/CD + Alembic |
| CC5.3 Cost Controls | ✅ Implemented | Budget + auto-downgrade |
