from pathlib import Path

from jaknastredni import fetch_all


def test_stahni_catches_exception_and_continues(caplog):
    def boom():
        raise RuntimeError("network is down")

    fetch_all._stahni("test krok", boom)  # nesmí propagovat výjimku
    assert "test krok selhalo" in caplog.text


def test_stahni_calls_function_with_args():
    calls = []
    fetch_all._stahni("ok", lambda a, b, kw=None: calls.append((a, b, kw)), 1, 2, kw="x")
    assert calls == [(1, 2, "x")]


def test_fetch_all_calls_every_source_with_expected_ranges(monkeypatch, tmp_path):
    calls = {"msmt": 0, "mz": [], "jpz_old": [], "jpz_new": [], "csi": 0, "infoabsolvent": 0}

    monkeypatch.setattr(fetch_all.msmt, "download", lambda raw_dir: calls.__setitem__("msmt", calls["msmt"] + 1))
    monkeypatch.setattr(fetch_all.cermat_mz, "download",
                         lambda rok, obdobi, raw_dir: calls["mz"].append((rok, obdobi)))
    monkeypatch.setattr(fetch_all.cermat_jpz_old, "download",
                         lambda rok, raw_dir: calls["jpz_old"].append(rok))
    monkeypatch.setattr(fetch_all.cermat_jpz, "download",
                         lambda rok, kolo, soubor, raw_dir: calls["jpz_new"].append((rok, kolo, soubor)))
    monkeypatch.setattr(fetch_all.csi, "download", lambda raw_dir: calls.__setitem__("csi", calls["csi"] + 1))

    fetch_all.fetch_all(tmp_path, rok_do=2026, skip_infoabsolvent=True, skip_atlas=True)

    assert calls["msmt"] == 1
    assert calls["csi"] == 1
    assert (2015, "j") in calls["mz"] and (2026, "jap") in calls["mz"]
    assert len(calls["mz"]) == (2026 - 2015 + 1) * 2
    assert calls["jpz_old"] == list(range(2017, 2024))
    assert (2024, 1, "vysledky") in calls["jpz_new"]
    assert (2026, 2, "kapacity") in calls["jpz_new"]
    assert len(calls["jpz_new"]) == (2026 - 2024 + 1) * 2 * 3


def test_fetch_all_skip_infoabsolvent(monkeypatch, tmp_path):
    for mod, name in [(fetch_all.msmt, "download"), (fetch_all.cermat_mz, "download"),
                       (fetch_all.cermat_jpz_old, "download"), (fetch_all.cermat_jpz, "download"),
                       (fetch_all.csi, "download")]:
        monkeypatch.setattr(mod, name, lambda *a, **kw: None)

    called = []
    monkeypatch.setattr(fetch_all.infoabsolvent, "check_robots_allows", lambda *a, **kw: called.append("robots"))
    monkeypatch.setattr(fetch_all.infoabsolvent, "fetch_raw", lambda *a, **kw: called.append("fetch_raw"))

    fetch_all.fetch_all(tmp_path, rok_do=2015, skip_infoabsolvent=True, skip_atlas=True)
    assert called == []


def test_fetch_all_skip_atlas(monkeypatch, tmp_path):
    for mod, name in [(fetch_all.msmt, "download"), (fetch_all.cermat_mz, "download"),
                       (fetch_all.cermat_jpz_old, "download"), (fetch_all.cermat_jpz, "download"),
                       (fetch_all.csi, "download")]:
        monkeypatch.setattr(mod, name, lambda *a, **kw: None)

    called = []
    monkeypatch.setattr(fetch_all.atlas, "check_robots_allows", lambda *a, **kw: called.append("robots"))
    monkeypatch.setattr(fetch_all.atlas, "fetch_raw", lambda *a, **kw: called.append("fetch_raw"))

    fetch_all.fetch_all(tmp_path, rok_do=2015, skip_infoabsolvent=True, skip_atlas=True)
    assert called == []


def test_fetch_all_calls_atlas_when_not_skipped(monkeypatch, tmp_path):
    for mod, name in [(fetch_all.msmt, "download"), (fetch_all.cermat_mz, "download"),
                       (fetch_all.cermat_jpz_old, "download"), (fetch_all.cermat_jpz, "download"),
                       (fetch_all.csi, "download")]:
        monkeypatch.setattr(mod, name, lambda *a, **kw: None)
    monkeypatch.setattr(fetch_all.infoabsolvent, "check_robots_allows", lambda *a, **kw: None)
    monkeypatch.setattr(fetch_all.infoabsolvent, "fetch_raw", lambda *a, **kw: None)

    called = []
    monkeypatch.setattr(fetch_all.atlas, "check_robots_allows", lambda *a, **kw: called.append("robots"))
    monkeypatch.setattr(fetch_all.atlas, "fetch_raw", lambda *a, **kw: called.append("fetch_raw"))

    fetch_all.fetch_all(tmp_path, rok_do=2015, skip_infoabsolvent=False, skip_atlas=False)
    assert called == ["robots", "fetch_raw"]
