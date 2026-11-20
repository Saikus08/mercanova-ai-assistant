"""The seed command only resets the stock when it is asked to."""

from pathlib import Path

import pytest

from app.scripts import seed


@pytest.fixture
def calls(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> list[bool]:
    dataset = tmp_path / "dataset.xlsx"
    dataset.write_bytes(b"")
    seen: list[bool] = []
    monkeypatch.setattr(seed, "get_session_factory", lambda: object())

    class Settings:
        dataset_path = str(dataset)

    monkeypatch.setattr(seed, "get_settings", lambda: Settings())
    monkeypatch.setattr(seed, "format_summary", lambda catalog: "")
    monkeypatch.setattr(
        seed, "run_seed", lambda path, factory, reset_stock=False: seen.append(reset_stock)
    )
    return seen


def test_the_stock_is_kept_by_default(calls: list[bool]) -> None:
    assert seed.main([]) == 0
    assert calls == [False]


def test_the_stock_is_reset_only_with_the_flag(calls: list[bool]) -> None:
    assert seed.main(["--reset-stock"]) == 0
    assert calls == [True]
