# contracts/openapi

One OpenAPI 3.1 specification per service (public and internal endpoints, `/health/*`).
Contracts are written and approved before the code that implements them (SAD 7.4, 11.1);
API conventions such as RFC 9457 errors and `correlation_id` follow SAD 11.1.
