"""user_data contract: root identity, choke pins, no-op desktop, web bridge.

The web-bridge tests fake the page environment exactly as the probe
found it (doc 46 phase 2): a ``platform`` module whose ``window`` holds
the injected ``sh46`` IndexedDB shim, with methods taking a callback
that fires synchronously. Awaiting JS promises directly aborts the
interpreter build, so the callback bridge is the contract.
"""
from __future__ import annotations

from tests.support.asyncutil import run

import sys
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

from src.spacehack import display_config, saveload, user_data


def test_spacehack_root_is_the_logical_path_on_every_platform(tmp_path):
    # the root itself is platform-independent; only the sync layer branches
    with mock.patch.object(Path, "home", return_value=tmp_path):
        assert user_data.spacehack_root() == tmp_path / ".spacehack"


def test_saves_and_config_ride_the_user_data_choke(tmp_path):
    with mock.patch.object(Path, "home", return_value=tmp_path):
        root = user_data.spacehack_root()
        assert saveload._saves_dir() == root / "saves"
        assert saveload._saves_dir().is_dir()
        assert display_config.default_config_path() == root / "config.toml"


def test_dev_quicksave_path_rides_the_saves_choke(tmp_path):
    from src.spacehack import dev_mode

    with mock.patch.object(Path, "home", return_value=tmp_path):
        assert dev_mode._quicksave_path() == saveload._saves_dir() / "quicksave.json"


def test_sync_persistence_is_a_no_op_on_desktop(monkeypatch, tmp_path):
    monkeypatch.setattr(user_data, "_is_web", lambda: False)
    assert user_data.sync_persistence(tmp_path / "whatever.json") is None


def test_restore_is_a_no_op_on_desktop():
    assert run(user_data.restore()) is None


def _fake_shim(store: dict):
    """A stand-in for window.sh46: get/keys keep the callback bridge
    (restore runs in the main await chain); put/remove take an OPTIONAL
    callback because sync_persistence fires them with none."""

    class Shim:
        @staticmethod
        def put(name, text, cb=None):
            store[name] = text
            if cb:
                cb(True)

        @staticmethod
        def get(name, cb):
            cb(store.get(name))

        @staticmethod
        def remove(name, cb=None):
            store.pop(name, None)
            if cb:
                cb(True)

        @staticmethod
        def keys(cb):
            cb(sorted(store))

    return Shim()


def _install_web_env(monkeypatch, tmp_path, store):
    monkeypatch.setattr(user_data, "_is_web", lambda: True)
    fake_platform = SimpleNamespace(window=SimpleNamespace(sh46=_fake_shim(store)))
    monkeypatch.setitem(sys.modules, "platform", fake_platform)
    monkeypatch.setattr(Path, "home", lambda: tmp_path)


def test_sync_persistence_pushes_writes_and_deletes(monkeypatch, tmp_path):
    store: dict = {}
    _install_web_env(monkeypatch, tmp_path, store)

    target = user_data.spacehack_root() / "saves" / "autosave.json"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text('{"v": 1}')
    user_data.sync_persistence(target)

    assert store == {"saves/autosave.json": '{"v": 1}'}

    target.unlink()
    user_data.sync_persistence(target)

    assert store == {}  # written, pushed, then deleted remotely


def test_sync_persistence_pushes_the_written_payload(monkeypatch, tmp_path):
    store: dict = {}
    _install_web_env(monkeypatch, tmp_path, store)

    target = user_data.spacehack_root() / "config.toml"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text("window_width = 1600\n")
    user_data.sync_persistence(target)

    assert store == {"config.toml": "window_width = 1600\n"}


def test_sync_persistence_ignores_paths_outside_the_root(monkeypatch, tmp_path):
    store: dict = {}
    _install_web_env(monkeypatch, tmp_path, store)

    user_data.sync_persistence(Path("/etc/passwd"))

    assert store == {}


def test_restore_materializes_persisted_files(monkeypatch, tmp_path):
    store = {
        "saves/autosave.json": '{"ctx": true}',
        "config.toml": "window_width = 1280\n",
    }
    _install_web_env(monkeypatch, tmp_path, store)

    run(user_data.restore())

    root = tmp_path / ".spacehack"
    assert (root / "saves" / "autosave.json").read_text() == '{"ctx": true}'
    assert (root / "config.toml").read_text() == "window_width = 1280\n"


def test_delete_save_flushes_the_remote_remove_on_web(monkeypatch, tmp_path):
    """On web the remote remove IS the delete (MEMFS starts empty each
    boot, so the FileNotFoundError branch is the normal path)."""
    store = {"saves/autosave.json": '{"ctx": true}'}
    _install_web_env(monkeypatch, tmp_path, store)

    saveload.delete_save()

    assert store == {}


def test_restore_without_a_shim_is_a_no_op(monkeypatch, tmp_path):
    monkeypatch.setattr(user_data, "_is_web", lambda: True)
    fake_platform = SimpleNamespace(window=SimpleNamespace())
    monkeypatch.setitem(sys.modules, "platform", fake_platform)
    monkeypatch.setattr(Path, "home", lambda: tmp_path)

    assert run(user_data.restore()) is None
    assert not (tmp_path / ".spacehack").exists()
