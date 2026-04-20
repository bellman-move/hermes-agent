from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest
import yaml
from PIL import Image, ImageChops, ImageDraw

REPO_ROOT = Path(__file__).resolve().parents[1]
EP001_DIR = REPO_ROOT / "docs/plans/orbi-trend-webnovel-webtoon-20260417/webtoon/ep001"
ANALYZER = EP001_DIR / "analyze_balloon_zones.py"
RENDERER = EP001_DIR / "render_balloons.py"
UTILS_PATH = EP001_DIR / "balloon_layout_utils.py"
SOURCE_MANIFEST = EP001_DIR / "generated_fal_manifest_v3.json"
LETTERING = EP001_DIR / "lettering_script.yaml"
SCROLL_PLAN = EP001_DIR / "scroll_plan.yaml"
INPUT_DIR = EP001_DIR / "generated_fal_v3"


def _load_ep001_utils():
    spec = importlib.util.spec_from_file_location("ep001_balloon_layout_utils", UTILS_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Unable to load EP001 utils from {UTILS_PATH}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _load_ep001_renderer():
    renderer_dir = str(EP001_DIR)
    if renderer_dir not in sys.path:
        sys.path.insert(0, renderer_dir)
    spec = importlib.util.spec_from_file_location("ep001_render_balloons", RENDERER)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Unable to load EP001 renderer from {RENDERER}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


EP001_UTILS = _load_ep001_utils()
EP001_RENDERER = _load_ep001_renderer()
load_font = EP001_UTILS.load_font
speech_text_safe_box = EP001_UTILS.speech_text_safe_box
render_shape = EP001_RENDERER.render_shape


def _load_yaml(path: Path) -> dict:
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def _load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _assert_norm_rect(rect: dict) -> None:
    assert 0.0 <= rect["x"] <= 1.0
    assert 0.0 <= rect["y"] <= 1.0
    assert 0.0 < rect["w"] <= 1.0
    assert 0.0 < rect["h"] <= 1.0
    assert rect["x"] + rect["w"] <= 1.0001
    assert rect["y"] + rect["h"] <= 1.0001


def _measure_text_bbox(
    draw: ImageDraw.ImageDraw,
    font_path: str | None,
    font_size: int,
    lines: list[str],
) -> tuple[int, int]:
    font = load_font(font_path, font_size)
    text = "\n".join(lines)
    spacing = max(7, int(font_size * 0.34))
    bbox = draw.multiline_textbbox((0, 0), text, font=font, spacing=spacing, align="center")
    return bbox[2] - bbox[0], bbox[3] - bbox[1]


def _masked_diff_intensity(
    baseline_image: Image.Image,
    rendered_image: Image.Image,
    tail_points: list[list[int]],
    exclude_box: list[int] | None = None,
) -> int:
    diff = ImageChops.difference(baseline_image.convert("RGBA"), rendered_image.convert("RGBA")).convert("L")
    mask = Image.new("L", rendered_image.size, 0)
    mask_draw = ImageDraw.Draw(mask)
    mask_draw.polygon([tuple(point) for point in tail_points], fill=255)
    if exclude_box is not None:
        mask_draw.rectangle(tuple(exclude_box), fill=0)
    masked_diff = ImageChops.multiply(diff, mask)
    histogram = masked_diff.histogram()
    return sum(histogram[1:])


def _replay_panel_render(
    source_image: Image.Image,
    placements: list[dict[str, object]],
    font_path: str | None,
    suppressed_tail_ids: set[str] | None = None,
) -> Image.Image:
    replay = source_image.convert("RGBA").copy()
    suppressed_tail_ids = suppressed_tail_ids or set()
    for placement in placements:
        tail_points = placement["tail_points"]
        if placement["id"] in suppressed_tail_ids:
            tail_points = None
        render_shape(
            replay,
            SimpleNamespace(
                speaker=placement["speaker"],
                template=placement["template"],
                box=tuple(placement["box"]),
                lines=list(placement["lines"]),
                font_size=placement["font_size"],
                inner_box=tuple(placement["inner_box"]),
                tail_points=[tuple(point) for point in tail_points] if tail_points else None,
            ),
            font_path,
        )
    return replay


@pytest.fixture(scope="module")
def generated_artifacts(tmp_path_factory: pytest.TempPathFactory) -> dict[str, Path]:
    tmp_dir = tmp_path_factory.mktemp("balloon-pipeline")
    analysis_path = tmp_dir / "balloon_analysis_ep001.yaml"
    output_dir = tmp_dir / "generated_fal_v3_ballooned"
    subprocess.run(
        [
            sys.executable,
            str(ANALYZER),
            "--manifest",
            str(SOURCE_MANIFEST),
            "--lettering",
            str(LETTERING),
            "--scroll-plan",
            str(SCROLL_PLAN),
            "--output",
            str(analysis_path),
        ],
        check=True,
        cwd=REPO_ROOT,
    )
    subprocess.run(
        [
            sys.executable,
            str(RENDERER),
            "--input-dir",
            str(INPUT_DIR),
            "--analysis",
            str(analysis_path),
            "--lettering",
            str(LETTERING),
            "--scroll-plan",
            str(SCROLL_PLAN),
            "--output-dir",
            str(output_dir),
            "--compose-longscroll",
        ],
        check=True,
        cwd=REPO_ROOT,
    )
    return {
        "analysis": analysis_path,
        "output_dir": output_dir,
        "placement_manifest": output_dir / "placement_manifest.json",
        "longscroll": output_dir / "ep001_ballooned_longscroll.png",
    }


@pytest.fixture(scope="module")
def analysis(generated_artifacts: dict[str, Path]) -> dict:
    return _load_yaml(generated_artifacts["analysis"])


@pytest.fixture(scope="module")
def placement_manifest(generated_artifacts: dict[str, Path]) -> dict:
    return _load_json(generated_artifacts["placement_manifest"])


@pytest.fixture(scope="module")
def analysis_panels_by_id(analysis: dict) -> dict[str, dict]:
    return {panel["panel_id"]: panel for panel in analysis["panels"]}


@pytest.fixture(scope="module")
def placements_by_id(placement_manifest: dict) -> dict[str, dict]:
    mapping: dict[str, dict] = {}
    for panel in placement_manifest["panels"]:
        for placement in panel["placements"]:
            mapping[placement["id"]] = placement
    return mapping


def test_analysis_yaml_has_required_episode_and_source_paths(analysis: dict) -> None:
    assert analysis["episode"] == "ep001"
    assert analysis["analysis_version"] == "v2"
    assert {"analysis_version", "source", "panels"} <= analysis.keys()
    assert analysis["source"]["manifest"].endswith("generated_fal_manifest_v3.json")
    assert analysis["source"]["lettering"].endswith("lettering_script.yaml")
    assert analysis["source"]["scroll_plan"].endswith("scroll_plan.yaml")
    assert "generated_fal_v3" in analysis["source"]["default_input_dir"]


def test_ep001_utils_are_loaded_from_filesystem_path() -> None:
    assert UTILS_PATH.exists()
    assert Path(EP001_UTILS.__file__).resolve() == UTILS_PATH.resolve()
    assert EP001_UTILS.load_font is load_font
    assert EP001_UTILS.speech_text_safe_box is speech_text_safe_box


def test_analysis_covers_all_eight_fal_v3_panels(analysis: dict) -> None:
    panel_ids = [panel["panel_id"] for panel in analysis["panels"]]
    assert panel_ids == [f"p{index:02d}" for index in range(1, 9)]
    for panel in analysis["panels"]:
        assert {
            "panel_id",
            "image_path",
            "panel_mode",
            "overlay_tracks",
            "safe_zones",
            "forbidden_zones",
            "speaker_points",
            "speaker_anchors",
            "speaker_local_zones",
            "panel_overrides",
            "render_hints",
        } <= panel.keys()
        assert "generated_fal_v3/" in panel["image_path"]
        assert "generated_panels/" not in panel["image_path"]


def test_analysis_geometry_is_normalized_and_bounded(analysis: dict) -> None:
    for panel in analysis["panels"]:
        for zone in panel["safe_zones"]:
            _assert_norm_rect(zone)
        for zone in panel["forbidden_zones"]:
            _assert_norm_rect(zone)
        for zone in panel["speaker_local_zones"]:
            _assert_norm_rect(zone)
            assert 0.0 <= zone["confidence"] <= 1.0
            assert zone["priority"] >= 0
        for point in panel["speaker_points"]:
            assert 0.0 <= point["x"] <= 1.0
            assert 0.0 <= point["y"] <= 1.0
        for anchor in panel["speaker_anchors"]:
            assert 0.0 <= anchor["x"] <= 1.0
            assert 0.0 <= anchor["y"] <= 1.0
            assert 0.0 <= anchor["confidence"] <= 1.0
            assert anchor["priority"] >= 0


def test_panel_modes_and_tracks_match_ep001_story_intent(analysis_panels_by_id: dict[str, dict]) -> None:
    assert analysis_panels_by_id["p03"]["panel_mode"] != "dialogue"
    assert "screen_ui" in analysis_panels_by_id["p03"]["overlay_tracks"]
    assert analysis_panels_by_id["p04"]["panel_mode"] != "dialogue"
    assert "chat_ui" in analysis_panels_by_id["p04"]["overlay_tracks"]
    assert analysis_panels_by_id["p05"]["panel_mode"] != "dialogue"
    assert "screen_ui" in analysis_panels_by_id["p05"]["overlay_tracks"]
    assert analysis_panels_by_id["p07"]["panel_mode"] != "dialogue"
    assert {"screen_ui", "caption"} <= set(analysis_panels_by_id["p07"]["overlay_tracks"])
    assert {"chat_ui", "dialogue", "caption"} <= set(analysis_panels_by_id["p08"]["overlay_tracks"])


def test_render_hints_and_attachment_contract_cover_required_panels(analysis_panels_by_id: dict[str, dict]) -> None:
    p02 = analysis_panels_by_id["p02"]
    p06 = analysis_panels_by_id["p06"]
    p08 = analysis_panels_by_id["p08"]

    assert p02["render_hints"]["item_templates"]["l01"] == "speech"
    assert p06["render_hints"]["item_templates"]["l03"] == "speech"
    assert p08["render_hints"]["item_templates"]["l05"] == "chat_ui"
    assert p08["render_hints"]["item_templates"]["l06"] == "speech"
    assert p08["render_hints"]["item_templates"]["p08_caption_04"] == "caption"

    for panel in (p02, p06, p08):
        assert panel["render_hints"]["allow_tail"] is True
        assert panel["speaker_anchors"]
        assert panel["speaker_local_zones"]
        assert panel["panel_overrides"]["placement_order_policy"] == "hybrid_ranked"
        assert panel["render_hints"]["tail_policy"]["mode"] == "edge_select"
        assert panel["render_hints"]["item_overrides"]


def test_override_precedence_contract_is_explicit(analysis_panels_by_id: dict[str, dict]) -> None:
    p02_item = analysis_panels_by_id["p02"]["render_hints"]["item_overrides"]["l01"]
    p06_tail = analysis_panels_by_id["p06"]["render_hints"]["tail_overrides"]["l03"]
    p08_item = analysis_panels_by_id["p08"]["render_hints"]["item_overrides"]["l06"]

    assert p02_item["preferred_zone_ids"][0] == "p02_mother_upper_right"
    assert "speech_top_left" in p02_item["disallowed_zone_ids"]
    assert p06_tail["speaker_anchor_id"] == "mother_mouth_primary"
    assert analysis_panels_by_id["p08"]["render_hints"]["tail_overrides"]["l06"]["entry_edge"] == "bottom"
    assert p08_item["force_anchor_id"] == "mother_mouth_primary"


def test_renderer_artifacts_use_ballooned_v3_paths(generated_artifacts: dict[str, Path], placement_manifest: dict) -> None:
    assert generated_artifacts["output_dir"].name == "generated_fal_v3_ballooned"
    assert generated_artifacts["placement_manifest"].exists()
    assert generated_artifacts["longscroll"].exists()
    assert placement_manifest["longscroll"].endswith("generated_fal_v3_ballooned/ep001_ballooned_longscroll.png")
    assert Path(placement_manifest["analysis_path"]).exists()
    assert "generated_fal_v3" in placement_manifest["input_dir"]
    assert "generated_panels" not in placement_manifest["input_dir"]


def test_manifest_contains_required_attachment_metadata(placement_manifest: dict, placements_by_id: dict[str, dict]) -> None:
    assert {"l01", "l02", "l03", "l04", "l05", "l06", "p01_caption_01", "p03_caption_02", "p07_caption_03", "p08_caption_04"} <= placements_by_id.keys()
    for placement in placements_by_id.values():
        assert {
            "candidate_class",
            "resolved_anchor_id",
            "resolved_anchor_role",
            "selected_zone_score",
            "score_breakdown",
            "tail_entry_edge",
            "tail_cross_ratio",
            "fallback_reason",
            "lines",
            "review_reasons",
            "rejected_candidates",
        } <= placement.keys()
    assert placements_by_id["l02"]["bubble_kind"] == "chat"
    assert placements_by_id["l04"]["bubble_kind"] == "note"
    assert placements_by_id["p08_caption_04"]["bubble_kind"] == "caption"


def test_final_boxes_stay_within_panel_bounds_and_overlap_budget(placement_manifest: dict) -> None:
    threshold = placement_manifest["forbidden_overlap_threshold"]
    manual_review_panels = 0
    for panel in placement_manifest["panels"]:
        width, height = panel["size"]
        if panel["manual_review_required"]:
            manual_review_panels += 1
            assert panel["manual_review_reasons"]
        for placement in panel["placements"]:
            left, top, right, bottom = placement["box"]
            assert 0 <= left < right <= width
            assert 0 <= top < bottom <= height
            if placement["selected_with_warning"]:
                assert placement["warning_reason"] is not None
            else:
                assert placement["max_forbidden_overlap"] <= threshold + 1e-9
            assert placement["tail_cross_ratio"] >= 0.0
            for metric in placement["overlap_metrics"]:
                assert metric["ratio"] >= 0.0
    assert manual_review_panels >= 1


def test_speech_text_fits_inside_safe_box(generated_artifacts: dict[str, Path], placement_manifest: dict) -> None:
    font_path = placement_manifest["font_path"]
    for panel in placement_manifest["panels"]:
        image = Image.open(panel["output"]).convert("RGBA")
        draw = ImageDraw.Draw(image)
        for placement in panel["placements"]:
            if placement["template"] != "speech":
                continue
            assert placement["lines"]
            text_w, text_h = _measure_text_bbox(draw, font_path, placement["font_size"], placement["lines"])
            safe_box = speech_text_safe_box(tuple(placement["inner_box"]))
            assert text_w <= (safe_box[2] - safe_box[0])
            assert text_h <= (safe_box[3] - safe_box[1])


def test_ranked_speech_candidates_prefer_speaker_local_when_valid(placements_by_id: dict[str, dict]) -> None:
    p02 = placements_by_id["l01"]
    p06 = placements_by_id["l03"]
    assert p02["candidate_class"] == "speaker_local"
    assert p02["zone_id"] == "p02_mother_upper_right"
    assert any(candidate["zone_id"] == "speech_top_right" for candidate in p02["rejected_candidates"])
    assert p06["candidate_class"] == "speaker_local"
    assert p06["zone_id"] == "p06_mother_upper_right"
    assert any(candidate["zone_id"] == "speech_top_right" for candidate in p06["rejected_candidates"])


def test_tail_routing_provenance_matches_resolved_anchor_and_policy(placements_by_id: dict[str, dict]) -> None:
    p02 = placements_by_id["l01"]
    p06 = placements_by_id["l03"]
    p08 = placements_by_id["l06"]

    assert p02["resolved_anchor_id"] == "mother_mouth_primary"
    assert p02["resolved_anchor_role"] == "mouth"
    assert p02["tail_entry_edge"] == "bottom"
    assert p02["tail_points"][-1]
    assert p02["tail_cross_ratio"] <= 0.02
    assert not p02["review_reasons"]

    assert p06["resolved_anchor_id"] == "mother_mouth_primary"
    assert p06["tail_entry_edge"] == "bottom"
    assert p06["tail_points"][-1]
    assert p06["tail_cross_ratio"] <= 0.015

    assert p08["resolved_anchor_id"] == "mother_mouth_primary"
    assert p08["tail_entry_edge"] == "bottom"


def test_p02_attachment_specific_expectations(placements_by_id: dict[str, dict]) -> None:
    placement = placements_by_id["l01"]
    assert placement["zone_id"] in {"p02_mother_upper_right", "speech_top_right", "speech_upper_mid"}
    assert placement["resolved_anchor_id"] == "mother_mouth_primary"
    assert any(candidate["zone_id"] == "speech_top_right" for candidate in placement["rejected_candidates"])


def test_p06_attachment_specific_expectations(placements_by_id: dict[str, dict]) -> None:
    placement = placements_by_id["l03"]
    assert placement["zone_id"] == "p06_mother_upper_right"
    assert placement["candidate_class"] == "speaker_local"
    assert placement["tail_entry_edge"] == "bottom"
    assert placement["fallback_reason"] is None


def test_p08_mixed_mode_expectations(analysis_panels_by_id: dict[str, dict], placements_by_id: dict[str, dict]) -> None:
    assert analysis_panels_by_id["p08"]["render_hints"]["item_templates"]["l05"] == "chat_ui"
    assert analysis_panels_by_id["p08"]["render_hints"]["item_templates"]["p08_caption_04"] == "caption"

    assert placements_by_id["l05"]["bubble_kind"] == "chat"
    assert placements_by_id["p08_caption_04"]["bubble_kind"] == "caption"
    assert placements_by_id["l06"]["bubble_kind"] == "speech"
    assert placements_by_id["l06"]["candidate_class"] == "speaker_local"
    assert placements_by_id["l06"]["fallback_reason"] is None
    assert placements_by_id["l06"]["tail_cross_ratio"] <= 0.02
    assert not placements_by_id["l06"]["review_reasons"]


def test_p08_speech_manifest_lines_fit_safe_box(
    generated_artifacts: dict[str, Path],
    placement_manifest: dict,
    placements_by_id: dict[str, dict],
) -> None:
    p08 = placements_by_id["l06"]
    image = Image.open(generated_artifacts["output_dir"] / "p08.png").convert("RGBA")
    draw = ImageDraw.Draw(image)
    assert p08["lines"]
    text_w, text_h = _measure_text_bbox(draw, placement_manifest["font_path"], p08["font_size"], p08["lines"])
    safe_box = speech_text_safe_box(tuple(p08["inner_box"]))
    assert text_w <= (safe_box[2] - safe_box[0])
    assert text_h <= (safe_box[3] - safe_box[1])
    assert p08["bubble_kind"] == "speech"
    assert p08["candidate_class"] == "speaker_local"
    assert p08["fallback_reason"] is None
    assert p08["tail_cross_ratio"] <= 0.02


def test_speech_tail_pixels_are_rendered_in_output_panels(placement_manifest: dict) -> None:
    expected_tail_ids = {"l01", "l03", "l06"}
    font_path = placement_manifest["font_path"]

    for panel in placement_manifest["panels"]:
        source_image = Image.open(panel["source"]).convert("RGBA")
        rendered_image = Image.open(panel["output"]).convert("RGBA")
        replayed_image = _replay_panel_render(source_image, panel["placements"], font_path)
        assert not ImageChops.difference(replayed_image.convert("RGB"), rendered_image.convert("RGB")).getbbox()
        for placement in panel["placements"]:
            if placement["id"] not in expected_tail_ids:
                continue
            assert placement["template"] == "speech"
            assert placement["tail_points"]
            no_tail_image = _replay_panel_render(
                source_image,
                panel["placements"],
                font_path,
                suppressed_tail_ids={placement["id"]},
            )
            changed_pixels = _masked_diff_intensity(
                baseline_image=no_tail_image,
                rendered_image=rendered_image,
                tail_points=placement["tail_points"],
            )
            assert changed_pixels > 0, f"Speech tail for {placement['id']} was not rendered"
