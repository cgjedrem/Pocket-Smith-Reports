---
name: api-design
description: 'API design guidelines covering REST conventions, response shapes, input validation, authentication, versioning, rate limiting, and pagination. Use when designing, implementing, or reviewing API endpoints for any HTTP/REST project. Do not use for frontend UI conventions, database schema design, or GraphQL/gRPC-specific patterns.'
---

# API Design Guidelines

## REST Conventions
- Use plural nouns for resources: `/users`, `/posts`, `/comments`
- Use HTTP methods correctly: GET (read), POST (create), PUT (replace), PATCH (update), DELETE (remove)
- Nest sub-resources: `/users/:id/posts`
- Use query params for filtering: `/posts?status=published&author=123`
- Return proper status codes: 200, 201, 204, 400, 401, 403, 404, 409, 422, 500

## Response Shape

### Success Response
```json
{
  "data": {},
  "error": null,
  "meta": { "page": 1, "total": 42 }
}
```

### Error Response
```json
{
  "data": null,
  "error": {
    "code": "VALIDATION_ERROR",
    "message": "Human-readable message",
    "details": [{ "field": "email", "message": "Invalid format" }]
  }
}
```

## Input Validation
- Validate all input at the API boundary — before it reaches business logic
- Return 422 with field-level error details for validation failures
- Sanitize strings to prevent injection
- Enforce size limits on all inputs
- Use the project's existing validation library (Zod, Joi, etc.)

## Authentication
- Use the project's existing auth mechanism
- Apply auth middleware at the router level — not per-handler
- Return 401 for missing/invalid credentials
- Return 403 for insufficient permissions
- Never roll custom auth unless the project has none

## Versioning
- Follow the project's existing versioning strategy
- If none exists, prefer URL path versioning: `/api/v1/resource`
- Do not mix versioning strategies in the same project

## Rate Limiting
- Apply rate limiting to all public endpoints
- Use the project's existing rate limiting solution
- Return 429 with `Retry-After` header when rate limited

## Pagination
- Use cursor-based pagination for large datasets
- Use offset-based pagination only for small, stable datasets
- Return pagination metadata in the `meta` field