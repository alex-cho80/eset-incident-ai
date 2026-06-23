# LLM Provider Failure

1. Stop new analysis dispatch if error rate exceeds threshold.
2. Keep collected incidents pending.
3. Fail closed for high/critical incidents.
4. Resume with the same prompt version and evidence IDs.
