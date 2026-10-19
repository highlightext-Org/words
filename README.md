# words
A collection of keywords, phrases, and terminology used by Highlighter to identify and highlight important information during financial research and analysis.

## Build the master data file

Requires Python 3.9+ with no third-party dependencies. From this directory:

```sh
python3 scripts/build_master.py
```

This reads JSON, CSV, and TXT files recursively in `sources/` and atomically writes
`master.json`. Source files are never modified. Custom paths are supported:

```sh
python3 scripts/build_master.py --sources /path/to/sources --output /path/to/master.json
python3 -m unittest discover -s tests -v
```

The single JSON output contains:

- `profiles`: one master record per connected set of explicit identities, with
  canonical `x_handle` (lowercase, no `@`), `x_url`, wallets, profile URLs,
  normalized `fields`, `conflicts`, and original `observations` with provenance.
- `holdings`: wallet/token/snapshot observations linked by `profile_id`, with
  numeric metrics and original values. Percentages use percentage points
  (`1.12%` becomes `1.12`); currency symbols and K/M/B/T suffixes are expanded.
  The source meaning of `final` is retained without assuming a financial definition.
- `keywords`: whitespace/case-normalized keyword entries, retaining all original
  variants and their profile settings. Regex entries have `match_mode: "regex"`
  and preserve exact pattern text instead of normalizing whitespace or case.
- `settings`: complete Keyword Glow settings, including empty profiles.
- `sources`, `summary`, and `warnings`: file hashes, reconciliation counts, and
  invalid identity/number values requiring review.

### Source transformations

| Export | Transformation |
| --- | --- |
| X Profile Scout JSON | `handle` / `profileUrl` → X identity; camelCase metadata → snake_case |
| Pump following CSV | `x_handle` / `x_url` → X identity; Pump profile address → case-sensitive wallet; concatenated follower text → number |
| Pump Holder Lab JSON | Flatten snapshot rows; `x` → X identity; wallet → profile link; retain mint/time/price/URL for each holding |
| Profile audit CSV (both versions) | `profile_url` → website identity; yes/no → booleans; semicolon contact/platform lists → arrays; absent fields remain absent |
| Keyword Glow JSON | Combine matching keyword text while preserving profile membership, colors, enabled states, and settings |
| Regex TXT (one pattern per line) | Preserve each nonblank line verbatim as a regex keyword, with source filename and line number; combine exact duplicates while retaining every origin |
| Keyword CSV (`keyword` column, optional `category`) | Normalize literal keyword whitespace/case for merging; preserve original text, category, all raw columns, and source row in variants |

To add sources, drop supported exports anywhere under `sources/` and rerun
`python3 scripts/build_master.py`. Filenames do not affect format detection.
Every run rebuilds from all current sources rather than appending to the previous
master, so rerunning does not accumulate entries. Duplicate copies contribute
source references, not extra master keywords. Keep original sources in place;
removing a file removes its contribution on the next build. Summary counts show
literal/regex totals, keyword observations, and how many were merged as duplicates.
Keyword CSVs require a nonempty `keyword` in every row; `category` is optional.
Quoted commas and UTF-8 BOMs are supported. Duplicate/empty headers and malformed
rows fail the build rather than silently dropping data.

Every `.txt` source is treated as a UTF-8 (optional BOM) regex list. Blank lines
are ignored; other lines must compile with Python's `re` module. Patterns have
no added flags, colors, enabled states, or profile assignments. Regex variants
contain `keyword` and `origin`; profile fields are absent because these lists
do not export profiles. Consumers must use regex matching for entries marked
`match_mode: "regex"`; entries without that marker retain literal keyword behavior.
Regexes are deduplicated by exact text, separately from literal keywords. Overlapping
patterns and alternative spellings remain intact. Invalid patterns stop the build
with the source filename and line number before the existing master is replaced.

Matching uses exact normalized X handles, case-sensitive wallets, or canonical
profile URLs, including transitive links across files. URL schemes/hosts and
trailing slashes are normalized; query strings/fragments are removed. Display
names, Pump handles, shared email/phone values, and social platform names are
not sufficient identity evidence. Records without an identity stay separate.
The script does not infer that a Pump display name is an X handle.

Scalar fields use the latest nonempty observation by checked/scanned/snapshot/
export timestamp (ISO timestamps as exported); ties use source/location order.
Contact/platform arrays are unioned. Distinct scalar or array values remain in
`conflicts`, and every original row remains in `observations`. A component with
multiple X handles has a null canonical `x_handle` and lists all candidates for
review rather than selecting one. Explicit exported links are evidence, not
independent verification of ownership or handle history.

Holdings are deduplicated only when profile, snapshot metadata (excluding export
time), and raw values match. Balances are never summed across snapshots or tokens.
Source locations for repeated observations are retained. Output is deterministic
for unchanged inputs. IDs are derived from the preferred identity and may change
when new sources reveal a different identity or connect previously separate groups.
Unknown JSON/CSV schemas and malformed input stop the build before replacing the
existing master; add an explicit adapter for new export formats.

## Published data and local sources

[`master.json`](master.json) is tracked in Git and linked from [`index.html`](index.html).
It contains the combined profile, contact, wallet, keyword, and settings data.
Original exports in `sources/` remain ignored by Git and stay local.

## Community tier — free open-source tools

The Community tier is **free ($0)**: use the open-source tools without a
subscription or purchase. Company-owned software and associated technical
documentation are available under the [MIT License](LICENSE), including its
**AS IS / no-warranty / no-liability** provisions. Community support is best
effort; maintenance and updates are not guaranteed.

Read [license scope and software disclaimer](DISCLAIMER.md) before use. The
software license does not grant rights in branding, third-party material,
personal information, or generated datasets. Test suitability, verify results,
and keep backups. Liability exclusions apply only to the extent permitted by law.
Paid plans and custom services are separate from Community software rights.
