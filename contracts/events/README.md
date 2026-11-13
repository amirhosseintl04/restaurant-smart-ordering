# contracts/events

One JSON Schema per domain event plus the shared event envelope of SAD 7.1 (`event_id`,
`event_type`, `event_version`, `occurred_at`, `producer`, `tenant_id`, `correlation_id`, `data`).
Event names are past tense and routing keys follow `<aggregate>.<event>` (SAD 7.3); schemas
evolve only under the rules of SAD 7.4 and follow the conventions of SAD 11.1.
Schemas are approved before any publisher or consumer code is written.
