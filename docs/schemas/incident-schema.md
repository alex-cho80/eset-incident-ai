# Incident Schema

Normalized incidents contain:

- `external_id`
- `title`
- `severity`
- `detected_at`
- `summary`
- `normalized_payload`

Raw ESET payloads are stored separately and are not sent directly to LLMs or Discord.
