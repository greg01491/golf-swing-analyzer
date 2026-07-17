from golf_sim.main import main


def test_main_runs(capsys):
    main()
    captured = capsys.readouterr()
    assert "hello world" in captured.out
