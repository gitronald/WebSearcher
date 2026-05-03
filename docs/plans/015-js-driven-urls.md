---
status: done
branch:
created: 2026-02-22T17:16:14-08:00
completed:
pr:
---

# JS-Driven URL Collection

## Context

Some SERP components have URLs that aren't available in static HTML because they're resolved through JavaScript click handlers.

## Known Cases

### Shopping ads (hotels sub_type)

`shopping_ads` with hotels sub_type have `href="#"` placeholders. The actual hotel website URLs are resolved through Google's booking flow via JS click events.

### Locations

`locations` components only have `/travel/search?...` relative paths pointing to Google's travel search. The actual destination URLs aren't in the static HTML.

### Reference SERP

"hotels in manhattan" (`5898b04fb534`, `data/demo-ws-v0.6.8a0/html/hotels_in_manhattan.html`)

## Possible Approaches

- Intercept network requests during collection (e.g., Selenium network logging, CDP `Network.requestWillBeSent`)
- Post-process relative paths into absolute Google URLs (partial fix, not the real destination)
- Flag these URLs as unresolvable in parsed output so downstream consumers know they're placeholders
