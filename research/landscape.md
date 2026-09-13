# Landscape notes

## Binner — binner.io / github.com/replaysMike/Binner (checked 2026-09-05)

Open-source (GPL-3.0) electronic parts inventory system; self-hosted (Windows/Linux/RPi/Docker,
free, unlimited parts) plus paid cloud at binner.io. Features: part lookup automation against
DigiKey/Mouser/Arrow/Octopart/Nexar/TME, barcode scanning, Dymo label printing, distributor
order importing, datasheet retrieval, nested categories, CSV/Excel export, custom fields,
KiCad HTTP Library support.

**No photo or AI identification of any kind** — intake is manual entry, barcode scan, or
part-number API lookup. Verdict: Binner is the strongest player in the *store/browse/organize*
half and confirms KICKOFF's landscape claim: nothing on the market does
bulk-photo-of-a-pile → identified inventory. That capture/identify front-end remains
Parts Pile's differentiator; Binner starts from a part number, we start from a photo.

Update (Ben, 2026-09-05): Binner also sells a physical smart-storage solution — bins that
light up when you ask "where is this part," i.e. they're investing in the *retrieval* end
(find the part you know you have). Notable: that hardware is only as useful as the inventory
data behind it, and their intake is still manual/barcode. Photo-based bulk intake feeds
exactly the layer their hardware depends on. Their bets: retrieval + organization. Our bet:
intake + identification. No collision; the seams line up.

Implications for us:
- Positioning: complement as much as competitor — "point camera at pile" is the intake step
  Binner lacks. A Binner-compatible CSV export (their import format) would make Parts Pile a
  feeder for Binner users at near-zero cost; consider at M6 (optional, not committed).
- Their feature list (datasheet retrieval, distributor lookup) is the natural post-Phase-1
  direction our spec_url field gestures at — but explicitly out of scope for Phase 1 per
  KICKOFF (no distributor API integration).
- Don't compete on inventory-management depth (labels, BOM, multi-user); our browse UI stays
  minimal and phone-first.
