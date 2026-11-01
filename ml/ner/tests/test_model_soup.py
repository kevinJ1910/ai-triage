import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import make_bundle  # noqa: E402
from model_soup import (  # noqa: E402
    export_soup_checkpoint,
    greedy_soup,
    load_checkpoint_weights,
    main as soup_cli_main,
    make_tensor,
    read_safetensors,
    tensor_flat_list,
    uniform_soup,
    write_safetensors,
)


def _assert_close(actual, expected, tol: float = 1e-5) -> None:
    a = tensor_flat_list(actual)
    assert len(a) == len(expected)
    for x, y in zip(a, expected):
        assert abs(x - y) <= tol


class TestSafetensorsRoundtripAndUniformSoup:
    def test_safetensors_roundtrip_preserves_float_and_int_buffers(self, tmp_path):
        tensors = {
            "roberta.encoder.layer.0.weight": make_tensor([0.25, -1.5, 3.0, 0.0], shape=(2, 2), dtype="F32"),
            "roberta.embeddings.position_ids": make_tensor([0, 1, 2, 3], shape=(1, 4), dtype="I64"),
        }
        st_path = write_safetensors(tmp_path / "model.safetensors", tensors, metadata={"format": "pt"})
        loaded = read_safetensors(st_path)
        assert set(loaded.keys()) == set(tensors.keys())
        _assert_close(loaded["roberta.encoder.layer.0.weight"], [0.25, -1.5, 3.0, 0.0])
        assert tensor_flat_list(loaded["roberta.embeddings.position_ids"]) == [0, 1, 2, 3]

    def test_uniform_soup_averages_floats_and_rejects_mismatched_shapes(self):
        sd1 = {
            "w": make_tensor([1.0, 3.0], shape=(2,), dtype="F32"),
            "pos": make_tensor([0, 1], shape=(2,), dtype="I64"),
        }
        sd2 = {
            "w": make_tensor([3.0, 5.0], shape=(2,), dtype="F32"),
            "pos": make_tensor([0, 1], shape=(2,), dtype="I64"),
        }
        merged = uniform_soup([sd1, sd2])
        _assert_close(merged["w"], [2.0, 4.0])
        assert tensor_flat_list(merged["pos"]) == [0, 1]

        with pytest.raises(ValueError, match="Forma incompatible"):
            uniform_soup([sd1, {"w": make_tensor([1.0, 2.0, 3.0], shape=(3,), dtype="F32"), "pos": sd1["pos"]}])


class TestGreedySoupAndCli:
    def test_greedy_soup_improves_over_single_best_and_skips_harmful_checkpoint(self, tmp_path):
        target = [2.0, 2.0]

        def eval_fn(sd):
            vals = tensor_flat_list(sd["w"])
            sq_err = sum((v - t) ** 2 for v, t in zip(vals, target))
            return float(1.0 - sq_err / 10.0)

        # fold_a (score ~0.959) supera a fold_b (score ~0.926), y su promedio [1.9, 2.05] sube a ~0.99875;
        # fold_bad esta lejos -> empeora el promedio y debe ser descartado por greedy_soup
        candidates = [
            ("fold_bad", {"w": make_tensor([-4.0, -4.0], shape=(2,), dtype="F32")}),
            ("fold_b", {"w": make_tensor([1.3, 2.5], shape=(2,), dtype="F32")}),
            ("fold_a", {"w": make_tensor([2.5, 1.6], shape=(2,), dtype="F32")}),
        ]
        result = greedy_soup(candidates, eval_fn)
        assert result.selected == ["fold_a", "fold_b"]
        assert result.best_score > max(result.individual_scores.values())
        assert result.best_score > 0.998

        ref_dir = tmp_path / "fold_a"
        ref_dir.mkdir()
        (ref_dir / "config.json").write_text('{"architectures": ["RobertaForTokenClassification"]}', encoding="utf-8")
        (ref_dir / "ner_labels.json").write_text('["O", "B-SINTOMA"]', encoding="utf-8")
        out_dir = export_soup_checkpoint(result, tmp_path / "soup_out", reference_checkpoint_dir=ref_dir)
        assert (out_dir / "model.safetensors").exists()
        assert (out_dir / "config.json").exists()
        assert (out_dir / "ner_labels.json").exists()
        manifest = json.loads((out_dir / "soup_manifest.json").read_text(encoding="utf-8"))
        assert manifest["selected_checkpoints"] == ["fold_a", "fold_b"]
        reloaded = load_checkpoint_weights(out_dir)
        _assert_close(reloaded["w"], [1.9, 2.05])

    def test_cli_forbids_test_split_in_greedy_mode_and_supports_uniform(self, tmp_path):
        c1, c2 = tmp_path / "c1", tmp_path / "c2"
        write_safetensors(c1 / "model.safetensors", {"w": make_tensor([1.0, 2.0], shape=(2,), dtype="F32")})
        write_safetensors(c2 / "model.safetensors", {"w": make_tensor([3.0, 4.0], shape=(2,), dtype="F32")})
        (c1 / "config.json").write_text("{}", encoding="utf-8")

        with pytest.raises(SystemExit):
            soup_cli_main(["--mode", "greedy", "--checkpoints", str(c1), str(c2), "--split", "test"])

        out = tmp_path / "uniform_out"
        res = soup_cli_main(["--mode", "uniform", "--checkpoints", str(c1), str(c2), "--output", str(out)])
        assert res.mode == "uniform"
        _assert_close(load_checkpoint_weights(out)["w"], [2.0, 3.0])

    def test_make_bundle_includes_model_soup(self):
        assert "model_soup.py" in make_bundle.FILES
        assert make_bundle.FILES["model_soup.py"].exists()
