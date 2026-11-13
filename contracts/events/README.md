# contracts/events

One JSON Schema (draft 2020-12) per domain event plus the shared event envelope of SAD 7.1
(`event_id`, `event_type`, `event_version`, `occurred_at`, `producer`, `tenant_id`,
`correlation_id`, `data`). Event names are past tense and routing keys follow
`<aggregate>.<event>` (SAD 7.3); schemas evolve only under the rules of SAD 7.4 and follow the
conventions of SAD 11.1. Schemas are approved before any publisher or consumer code is written.

## Files

| File | Content |
| --- | --- |
| `envelope.schema.json` | The envelope of SAD 7.1. Closed (`additionalProperties: false`) |
| `common.schema.json` | Shared definitions: `id`, `money`, `channel`, `customer_ref`, `order_status`, `order_line` |
| `<EventType>.schema.json` | One per event: the envelope (`allOf`) with `event_type`, `event_version` and `producer` fixed and `data` defined |
| `examples/<EventType>.json` | A full sample message; CI validates it against `<EventType>.schema.json`. `examples/OrderCreated.json` is the sample of SAD 7.1 |
| `registry.json` | Machine-readable SAD 7.2 and 7.3: routing key, producer and consumers per event, queues and bindings, retry queues and DLQ |

Schemas carry no `$id`, so the relative `$ref`s resolve against the file location.

## Event list (SAD 7.2, 7.3)

| Event | Routing key | Producer | Consumers |
| --- | --- | --- | --- |
| `RestaurantRegistered` | `restaurant.registered` | Restaurant | Catalog, Order |
| `RestaurantSuspended` | `restaurant.suspended` | Restaurant | Catalog, Order |
| `CustomerRegistered` | `customer.registered` | Identity | Analytics |
| `MenuItemUpdated` | `catalog.menu_item_updated` | Catalog | Conversation |
| `MenuItemAvailabilityChanged` | `catalog.menu_item_availability_changed` | Catalog | Conversation |
| `PromotionActivated` | `catalog.promotion_activated` | Catalog | Conversation |
| `PromotionExpired` | `catalog.promotion_expired` | Catalog | Conversation |
| `OrderCreated` | `order.created` | Order | Notification, Analytics |
| `OrderUpdated` | `order.updated` | Order | Notification, Analytics |
| `OrderStatusChanged` | `order.status_changed` | Order | Notification, Analytics |
| `OrderCancelled` | `order.cancelled` | Order | Notification, Analytics |
| `SuggestionShown` | `suggestion.shown` | Conversation | Analytics |
| `SuggestionAccepted` | `suggestion.accepted` | Conversation | Analytics |
| `SuggestionDeclined` | `suggestion.declined` | Conversation | Analytics |

## Rules for publishers and consumers

- **`data` is open, the envelope is closed.** Adding an optional field to `data` is backward
  compatible and keeps `event_version` (SAD 7.4 rule 1), so consumers ignore fields they do not
  know. A breaking change gets a new `event_version` and a new schema file
  `<EventType>.v<N>.schema.json`, published in parallel with the old one (SAD 7.4 rule 2).
- **`tenant_id` is on every event** (SAD 8.2). For `restaurant.*` events it equals
  `data.restaurant_id`.
- **Identifiers are opaque strings** (`common.schema.json#/$defs/id`); only `event_id` is a UUID.
- **Money is an integer amount in Toman** (SAD 11.1). Events carry no `currency` field.
- **Time is ISO-8601 in UTC** with the `Z` suffix.
- **State-transfer events may arrive out of order** because of the retry queues. A consumer
  ignores a `catalog.*` event whose `occurred_at` is older than the last one it applied to the
  same entity and field group; the full rebuild of SAD 8.3 repairs anything else.
- **One source per projection field** (SAD 8.3): `MenuItemUpdated` never carries availability.
  Catalog publishes `MenuItemAvailabilityChanged` on every availability change and when an item
  is created; a projection row with no availability yet counts as unavailable.
- **Cancelling publishes `OrderCancelled` only**, never an additional `OrderStatusChanged`.
- Publishing goes through the transactional outbox (SAD 6.3, ADR-10); consumers are idempotent
  on `event_id` through `processed_events`.

## Validation

```bash
uvx check-jsonschema --check-metaschema contracts/events/*.schema.json
uvx check-jsonschema --schemafile contracts/events/OrderCreated.schema.json \
    contracts/events/examples/OrderCreated.json
```
