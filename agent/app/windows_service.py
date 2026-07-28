import importlib
from dataclasses import dataclass
from typing import Any

from agent.app.config import AgentSettings
from agent.app.runner import AgentConfigurationError, AgentRunner
from agent.app.transport import AgentTransportError

WINDOWS_SERVICE_NAME = "AllSeeingEyeAgent"
WINDOWS_SERVICE_DISPLAY_NAME = "The All Seeing Eye Agent"
WINDOWS_SERVICE_DESCRIPTION = "Agente corporativo autorizado de auditoria de red."


@dataclass(frozen=True, slots=True)
class PyWin32Modules:
    win32event: Any
    win32service: Any
    win32serviceutil: Any
    servicemanager: Any


def load_pywin32_modules() -> PyWin32Modules:
    try:
        return PyWin32Modules(
            win32event=importlib.import_module("win32event"),
            win32service=importlib.import_module("win32service"),
            win32serviceutil=importlib.import_module("win32serviceutil"),
            servicemanager=importlib.import_module("servicemanager"),
        )
    except ImportError as exc:
        raise RuntimeError(
            "pywin32 es obligatorio para instalar el agente como Windows Service. "
            'Instala el extra con: python -m pip install -e ".[windows-service]"',
        ) from exc


def build_windows_service_class(modules: PyWin32Modules) -> type[Any]:
    service_framework: Any = modules.win32serviceutil.ServiceFramework

    class AllSeeingEyeAgentService(service_framework):  # type: ignore[misc]
        _svc_name_ = WINDOWS_SERVICE_NAME
        _svc_display_name_ = WINDOWS_SERVICE_DISPLAY_NAME
        _svc_description_ = WINDOWS_SERVICE_DESCRIPTION

        def __init__(self, args: list[str]) -> None:
            modules.win32serviceutil.ServiceFramework.__init__(self, args)
            self._runner: AgentRunner | None = None

        def SvcStop(self) -> None:
            self.ReportServiceStatus(modules.win32service.SERVICE_STOP_PENDING)
            if self._runner is not None:
                self._runner.request_stop()

        def SvcDoRun(self) -> None:
            modules.servicemanager.LogInfoMsg(f"{WINDOWS_SERVICE_DISPLAY_NAME} iniciado")
            try:
                settings = AgentSettings.from_environment()
                self._runner = AgentRunner(settings)
                self._runner.run_forever()
            except (AgentConfigurationError, AgentTransportError, ValueError) as exc:
                modules.servicemanager.LogErrorMsg(
                    f"{WINDOWS_SERVICE_DISPLAY_NAME} fallo: {exc}",
                )
                raise
            finally:
                modules.servicemanager.LogInfoMsg(f"{WINDOWS_SERVICE_DISPLAY_NAME} detenido")

    return AllSeeingEyeAgentService


def main() -> None:
    modules = load_pywin32_modules()
    service_class = build_windows_service_class(modules)
    modules.win32serviceutil.HandleCommandLine(service_class)


if __name__ == "__main__":
    main()
