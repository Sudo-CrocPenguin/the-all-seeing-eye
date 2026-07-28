from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]


def test_linux_systemd_unit_preserves_graceful_shutdown() -> None:
    unit_template = (
        ROOT_DIR / "agent/deploy/linux/all-seeing-eye-agent.service.template"
    ).read_text(encoding="utf-8")

    assert "EnvironmentFile={{ENV_FILE}}" in unit_template
    assert "ExecStart={{INSTALL_DIR}}/.venv/bin/python -m agent.app.cli" in unit_template
    assert "KillSignal=SIGTERM" in unit_template
    assert "Restart=always" in unit_template


def test_windows_installer_uses_visible_service_wrapper() -> None:
    installer = (ROOT_DIR / "agent/deploy/windows/install-service.ps1").read_text(
        encoding="utf-8",
    )

    assert "agent.app.windows_service" in installer
    assert "AllSeeingEyeAgent" in installer
    assert "AGENT_TOKEN=$AgentToken" in installer
    assert "AgentToken es obligatorio" in installer


def test_linux_installer_does_not_start_without_agent_token() -> None:
    installer = (ROOT_DIR / "agent/deploy/linux/install-systemd.sh").read_text(
        encoding="utf-8",
    )

    assert "AGENT_TOKEN no esta configurado" in installer
    assert "systemctl restart" in installer
