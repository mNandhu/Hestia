# Data Model: Hestia

## Entities

### Service
- id (string)
- name (string)
- strategy (string)
- machine_selector (string)  # rule key to choose machine
- health_endpoint (string, optional)
- warmup_seconds (int, optional)
- auth_required (bool, default=false)
- created_at (datetime)
- updated_at (datetime)

### Machine
- id (string)
- name (string)
- role (enum: local|remote|hpc)
- capabilities (json)  # CPU/GPU/memory tags
- address (string)
- status (enum: available|unavailable)
- created_at (datetime)
- updated_at (datetime)

### RoutingRule
- id (string)
- name (string)
- match (json)  # criteria (service type, size)
- target_machine_role (string)
- priority (int)

### Activity
- id (string)
- service_id (string)
- last_used_at (datetime)
- state (enum: hot|cold|starting|stopping)
- idle_timeout_seconds (int)

### AuthKey
- id (string)
- name (string)
- hashed_key (string)
- scopes (json)
- created_at (datetime)
- disabled (bool)

## Relationships
- Service 1—N Activity (historical), latest state tracked in Activity.state
- Service N—1 Machine (current placement)
- RoutingRule influences Service→Machine selection
- AuthKey applies to API access; dashboard uses username/password (outside model scope)

## Validation Rules
- If health_endpoint absent, warmup_seconds must be provided
- idle_timeout_seconds > 0
- routing rule priority unique within ruleset
