import pytest

from pokerbots_cli.main import main


def test_version(capsys):
    with pytest.raises(SystemExit) as exc:
        main(["--version"])
    assert exc.value.code == 0
    assert capsys.readouterr().out.startswith("pb ")


def test_no_args_prints_help(capsys):
    assert main([]) == 0
    assert "usage: pb" in capsys.readouterr().out
