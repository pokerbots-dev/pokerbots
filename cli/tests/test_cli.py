import pytest

from pokerbots_cli.main import main


def test_version(capsys):
    with pytest.raises(SystemExit) as exc:
        main(["--version"])
    assert exc.value.code == 0
    assert capsys.readouterr().out.startswith("pb ")


def test_init_then_test(tmp_path, capsys):
    bot = tmp_path / "mybot"
    assert main(["init", str(bot)]) == 0
    assert main(["test", str(bot), "--games", "3", "--seed", "1"]) == 0
    assert "errors      0" in capsys.readouterr().out


def test_docs_plain(capsys):
    assert main(["docs", "--plain"]) == 0
    assert "min_raise" in capsys.readouterr().out
