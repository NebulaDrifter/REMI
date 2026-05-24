# AWS Cloud Deployment

**Status: v1.1 — not yet implemented.**

This directory will hold the Terraform modules and Lambda packaging for the
AWS deployment of REMI.

## Planned Architecture

```
Internet
   │
   ▼
CloudFront (TLS, WAF, edge caching)
   │
   ├─→ S3 (static frontend assets)
   │
   └─→ API Gateway (REST API with usage plan)
            │
            ▼
       Lambda (FastAPI + Mangum wrapper)
            │
            ├─→ DynamoDB (people, interactions, open_loops, audit_log)
            ├─→ S3 (audio storage, KMS-encrypted, 7-day lifecycle)
            └─→ Secrets Manager (API keys)
```

## Why Not in v1.0

See `DECISIONS.md` item 10 (Local-First Build Sequence). Local-first is
sequencing, not scope cut. v1.1 will ship.

## Planned v1.1 Phases

Per `BUILD_PLAN.md`:

- **Phase 10**: Terraform modules — DynamoDB, S3, IAM, Secrets Manager, KMS
- **Phase 11**: DynamoDB storage adapter implementation
- **Phase 12**: S3 blob adapter implementation
- **Phase 13**: Mangum wrapper + Lambda packaging
- **Phase 14**: API Gateway + CloudFront + WAF Terraform
- **Phase 15**: CloudWatch alarms, GuardDuty enablement
- **Phase 16**: Frontend deploy to S3 + CloudFront
- **Phase 17**: Migration scripts (local → cloud, if needed)

## Future Files

```
deployments/aws/
├── lambda_handler.py        # Mangum wrapper for FastAPI app
└── terraform/
    ├── main.tf
    ├── variables.tf
    ├── outputs.tf
    ├── providers.tf
    ├── backend.tf
    └── modules/
        ├── dynamodb/
        ├── s3/
        ├── lambda/
        ├── api_gateway/
        ├── cloudfront/
        └── iam/
```

Do not implement these in v1.0.
