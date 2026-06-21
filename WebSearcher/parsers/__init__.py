"""Parse-pipeline package: parse_serp plus its component machinery.

`parse_serp` is intentionally *not* re-exported here. The package mixes two
layers -- leaf modules (`component`, `component_list`, `component_types`,
`components/`) that `extractors` and `classifiers` import, and the orchestrator
(`parsers.parse_serp`) that depends on `extractors`. Re-exporting `parse_serp` from
this `__init__` would make importing any leaf eagerly pull the orchestrator and
create a circular import. Consumers import it by real path instead:
`from WebSearcher.parsers.parse_serp import parse_serp` (and `WebSearcher.parse_serp`).
"""
