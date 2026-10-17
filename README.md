# words
A collection of keywords, phrases, and terminology used by Highlighter to identify and highlight important information during financial research and analysis.

## Build the master data file

Requires Python 3.9+ with no third-party dependencies. From this directory:

```sh
python3 scripts/build_master.py
```

This reads JSON and CSV files recursively in `sources/` and atomically writes
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
  variants and their profile settings.
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
