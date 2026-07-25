# report/

The chaptered write-up lands here (Phase 5). Same rule as the World Economy
Lab next door: **no claim enters the report unless it is computed in this repo**
from collected primary evidence — every number traceable to a `signals` row and
every row traceable to the artifact it came from.

## The PII rule for figures

`report/figures/*.png` is gitignored. Figures here are derived from one real
person's data, and the difference between "aggregate" and "identifying" is
thinner than it looks — a bits-by-surface bar chart is safe, a timeline of your
own location signals is not.

To publish a figure, review it, then force it past the ignore:

```bash
git add -f report/figures/bits-by-surface.png
```
