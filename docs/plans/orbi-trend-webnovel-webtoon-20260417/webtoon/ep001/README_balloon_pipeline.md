# Balloon Pipeline

This episode-local pipeline keeps `generated_fal_v3` as the source art baseline and adds lettering as a separate postprocess pass.

## Inputs

- `generated_fal_manifest_v3.json`
- `lettering_script.yaml`
- `scroll_plan.yaml`
- `generated_fal_v3/*.png`

## Outputs

- `balloon_analysis_ep001.yaml`
- `generated_fal_v3_ballooned/*.png`
- `generated_fal_v3_ballooned/placement_manifest.json`
- `generated_fal_v3_ballooned/ep001_ballooned_longscroll.png`

## Run

The repo environment is `.venv`:

```bash
source .venv/bin/activate
```

Generate the analysis artifact:

```bash
python docs/plans/orbi-trend-webnovel-webtoon-20260417/webtoon/ep001/analyze_balloon_zones.py \
  --manifest docs/plans/orbi-trend-webnovel-webtoon-20260417/webtoon/ep001/generated_fal_manifest_v3.json \
  --lettering docs/plans/orbi-trend-webnovel-webtoon-20260417/webtoon/ep001/lettering_script.yaml \
  --scroll-plan docs/plans/orbi-trend-webnovel-webtoon-20260417/webtoon/ep001/scroll_plan.yaml \
  --output docs/plans/orbi-trend-webnovel-webtoon-20260417/webtoon/ep001/balloon_analysis_ep001.yaml
```

Render the separate lettering pass:

```bash
python docs/plans/orbi-trend-webnovel-webtoon-20260417/webtoon/ep001/render_balloons.py \
  --input-dir docs/plans/orbi-trend-webnovel-webtoon-20260417/webtoon/ep001/generated_fal_v3 \
  --analysis docs/plans/orbi-trend-webnovel-webtoon-20260417/webtoon/ep001/balloon_analysis_ep001.yaml \
  --lettering docs/plans/orbi-trend-webnovel-webtoon-20260417/webtoon/ep001/lettering_script.yaml \
  --scroll-plan docs/plans/orbi-trend-webnovel-webtoon-20260417/webtoon/ep001/scroll_plan.yaml \
  --output-dir docs/plans/orbi-trend-webnovel-webtoon-20260417/webtoon/ep001/generated_fal_v3_ballooned \
  --compose-longscroll
```

## Inspect And Edit

- `balloon_analysis_ep001.yaml` is intentionally human-editable.
- Tweak `safe_zones`, `speaker_local_zones`, `speaker_anchors`, `panel_overrides`, or `render_hints.item_overrides` on a hard panel, then rerun the renderer only.
- `placement_manifest.json` records the chosen zone, candidate class, resolved anchor, tail edge, score breakdown, rejected candidates, overlap metrics, and any `manual_review_required` panels.
- Manual review is now expected whenever a speech placement falls back to a generic zone, loses its anchor, or keeps a least-bad tail that still crosses protected art.

## Force Manual Review

- Set `render_hints.manual_review: true` on a panel to force review.
- Add a note under `render_hints.manual_review_reasons` explaining why the panel should not auto-approve.
- Lower or raise `render_hints.forbidden_overlap_threshold` only when the protected-region budget has been reviewed against the panel art.
- If a speech bubble must break the normal attachment policy, document it with `render_hints.tail_overrides` or `render_hints.item_overrides` instead of silently reordering generic zones.
