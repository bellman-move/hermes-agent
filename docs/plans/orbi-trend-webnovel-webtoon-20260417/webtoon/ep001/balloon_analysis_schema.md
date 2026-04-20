# Balloon Analysis Schema

`balloon_analysis_ep001.yaml` is the editable contract between the analyzer and the renderer.

## Top-Level Fields

- `episode`: episode id such as `ep001`
- `analysis_version`: schema version string
- `source.manifest`: source fal manifest path
- `source.lettering`: lettering script path
- `source.scroll_plan`: scroll plan path
- `source.default_input_dir`: default renderer input directory
- `panels[]`: one entry per source panel

## Panel Fields

- `panel_id`: `p01`-style id
- `image_path`: source panel image path
- `panel_mode`: dominant strategy
  - `dialogue`
  - `caption`
  - `chat_ui`
  - `screen_ui`
  - `silent`
- `overlay_tracks`: active content types for the panel
  - `dialogue`
  - `caption`
  - `chat_ui`
  - `screen_ui`
  - `silent`
- `narrative_role`: block-purpose string from `scroll_plan.yaml`
- `shot`: shot hint from `generated_fal_manifest_v3.json`
- `reading_order`: ordered lettering item ids
- `safe_zones[]`: normalized candidate placement regions
- `forbidden_zones[]`: normalized protected regions
- `speaker_points[]`: normalized tail anchors for spoken dialogue
- `speaker_anchors[]`: richer anchor contract with role, priority, and preferred tail side
- `speaker_local_zones[]`: speaker/item-local preferred speech regions
- `panel_overrides`: panel-level attachment policy
- `render_hints`: renderer policy overrides

## Geometry Contract

All rectangles are normalized to the source panel:

```yaml
x: 0.0-1.0
y: 0.0-1.0
w: 0.0-1.0
h: 0.0-1.0
```

Rules:

- `0.0 <= x, y <= 1.0`
- `0.0 < w, h <= 1.0`
- `x + w <= 1.0`
- `y + h <= 1.0`

Points use:

```yaml
x: 0.0-1.0
y: 0.0-1.0
```

## Safe Zone Fields

- `id`: stable candidate id
- `kind`: one of `speech`, `caption`, `chat_ui`, `screen_note`
- `x`, `y`, `w`, `h`: normalized rectangle
- `confidence`: analyzer score in `0.0-1.0`
- `rationale`: human-readable explanation
- `background_metrics`: image-derived luminance/edge summary

## Forbidden Zone Fields

- `id`: stable protected-region id
- `kind`: one of `face`, `hand`, `screen_region`, `key_prop`, `focal_center`
- `x`, `y`, `w`, `h`: normalized rectangle
- `confidence`: analyzer confidence in `0.0-1.0`
- `source`: `composition_rule`, `shot_heuristic`, or `panel_override`

## Speaker Point Fields

- `speaker`: normalized speaker id
- `anchor_id`: stable anchor name
- `x`, `y`: normalized point
- `confidence`: analyzer confidence
- `source`: heuristic provenance

## Speaker Anchor Fields

- `speaker`: normalized speaker id
- `anchor_id`: stable anchor name
- `role`: anchor role such as `mouth`
- `x`, `y`: normalized point
- `confidence`: analyzer confidence
- `source`: provenance such as `panel_override`
- `priority`: higher value wins when multiple anchors exist
- `preferred_tail_side`: default tail edge hint

## Speaker Local Zone Fields

- `id`: stable candidate id
- `kind`: placement kind, currently speech-oriented
- `speaker`: intended speaker
- `item_id`: optional lettering item id override
- `zone_ref`: generic zone this local zone refines
- `x`, `y`, `w`, `h`: normalized rectangle
- `placement_side`: coarse composition tag
- `priority`: higher value wins within local candidates
- `confidence`: analyzer confidence
- `rationale`: human-readable note
- `source`: provenance such as `panel_override`

## Panel Overrides

- `placement_order_policy`: placement ranking mode
- `generic_speech_fallback_allowed`: whether generic safe zones remain valid for speech
- `generic_fallback_margin`: score margin required before a generic candidate may beat a valid local candidate
- `attachment_review_threshold`: confidence floor before a generic fallback is considered suspicious

## Render Hints

- `default_template`: dominant template fallback
- `item_templates`: map of lettering item id to template
  - `speech`
  - `caption`
  - `chat_ui`
  - `screen_note`
- `allow_tail`: whether tailed speech is allowed in this panel
- `manual_review`: explicit review flag
- `manual_review_reasons[]`: machine-readable reasons
- `compactness`: `compact` or `balanced`
- `max_balloons`: expected placement count cap
- `forbidden_overlap_threshold`: maximum placement overlap ratio against protected regions
- `item_overrides`: per-item placement override map
  - `preferred_zone_ids[]`
  - `disallowed_zone_ids[]`
  - `force_anchor_id`
  - `max_font_size`
  - `min_font_size`
  - `max_text_width`
  - `max_text_height`
  - `box_horizontal_align`
  - `box_vertical_align`
  - `box_offset_x`
  - `box_offset_y`
  - `force_manual_review`
- `tail_policy`: panel-level tail routing policy
  - `mode`
  - `anchor_preference`
  - `min_clearance_from_forbidden`
  - `max_cross_ratio`
- `tail_overrides`: per-item tail overrides
  - `entry_edge`
  - `speaker_anchor_id`
  - `bend_point`

## Renderer Invariants

- Every final placement box must stay inside the panel bounds.
- `chat_ui` items must not fall back to generic speech balloons on chat-first panels.
- `screen_note` items must render as note/screen cards, not speech balloons.
- Renderer must report rejected candidate reasons in `placement_manifest.json`.
- Renderer must expose per-placement forbidden-overlap metrics and flag `manual_review_required` when fallback placement exceeds the threshold.
- Speech placement must rank viable candidates instead of exiting on the first passing generic zone.
- Speech placements in the manifest must record `candidate_class`, resolved anchor info, score breakdown, tail edge, tail cross ratio, fallback reason, and rejected candidates.

## Precedence And Fallback

Placement ownership:

1. `render_hints.item_overrides`
2. `panel_overrides`
3. generic renderer defaults

Anchor ownership:

1. `render_hints.tail_overrides[item_id].speaker_anchor_id`
2. `render_hints.item_overrides[item_id].force_anchor_id`
3. highest-priority matching `speaker_anchors[]`
4. legacy `speaker_points[]`

Tail ownership:

1. `render_hints.tail_overrides[item_id].entry_edge`
2. `render_hints.tail_policy`
3. renderer `speaker_facing_edge` fallback

Fallback behavior:

- If a speech item has no local zone, mark panel review with `missing_speaker_local_zone`.
- If no anchor exists, keep the placement tail-less and mark `missing_speaker_anchor`.
- If generic fallback wins while a local candidate existed, preserve the fallback reason in the manifest and mark panel review.
- If every eligible tail route exceeds `tail_policy.max_cross_ratio`, keep the least-bad route and mark `tail_crosses_forbidden_region`.
