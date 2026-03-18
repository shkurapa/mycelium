"""
Metrics dashboard commands for Mycelium CLI.

Wraps ClawMetry to provide real-time observability for OpenClaw agents:
  - Token usage and cost tracking
  - Agent session monitoring
  - Live message flow visualization
  - System health checks

Requires the `metrics` extra: pip install mycelium-cli[metrics]
"""

import json as json_module
import os
import shutil
import signal
import subprocess
import sys
from pathlib import Path

import typer

from mycelium.error_handler import print_error

app = typer.Typer(help="Agent metrics dashboard (powered by ClawMetry)")

_PID_FILE = Path.home() / ".mycelium" / "metrics.pid"
_DEFAULT_PORT = 8900
_DEFAULT_HOST = "127.0.0.1"


def _check_clawmetry() -> bool:
    """Return True if clawmetry is importable."""
    try:
        import clawmetry  # noqa: F401
        return True
    except ImportError:
        return False


def _is_running() -> tuple[bool, int | None]:
    """Check if the metrics dashboard is running. Returns (running, pid)."""
    if not _PID_FILE.exists():
        return False, None
    try:
        data = json_module.loads(_PID_FILE.read_text())
        pid = int(data["pid"]) if isinstance(data, dict) else int(data)
        os.kill(pid, 0)
        return True, pid
    except (ValueError, KeyError, ProcessLookupError, PermissionError):
        _PID_FILE.unlink(missing_ok=True)
        return False, None


def _get_port() -> int:
    """Read the port the running dashboard was started on, or return the default."""
    if _PID_FILE.exists():
        try:
            data = json_module.loads(_PID_FILE.read_text())
            if isinstance(data, dict) and "port" in data:
                return int(data["port"])
        except (ValueError, json_module.JSONDecodeError):
            pass
    return _resolve_port(None)


def _get_host() -> str:
    """Read the host the running dashboard was started on, or return the default."""
    if _PID_FILE.exists():
        try:
            data = json_module.loads(_PID_FILE.read_text())
            if isinstance(data, dict) and "host" in data:
                return str(data["host"])
        except (ValueError, json_module.JSONDecodeError):
            pass
    return _resolve_host(None)


def _find_clawmetry() -> str | None:
    """Locate the clawmetry binary — check the current interpreter's bin dir first (for pipx/venv)."""
    venv_bin = Path(sys.executable).parent / "clawmetry"
    if venv_bin.exists():
        return str(venv_bin)
    return shutil.which("clawmetry")


def _resolve_port(port: int | None) -> int:
    return port or int(os.getenv("MYCELIUM_METRICS_PORT", str(_DEFAULT_PORT)))


def _resolve_host(host: str | None) -> str:
    return host or os.getenv("MYCELIUM_METRICS_HOST", _DEFAULT_HOST)


def _display_host(host: str) -> str:
    """Return a hostname suitable for display URLs (0.0.0.0 → localhost)."""
    return "localhost" if host == "0.0.0.0" else host


@app.callback()
def metrics_main(ctx: typer.Context) -> None:
    """Agent metrics dashboard — token usage, costs, sessions, and live flow."""


@app.command("start")
def start(
    ctx: typer.Context,
    port: int | None = typer.Option(None, "--port", "-p", help=f"Dashboard port (default: {_DEFAULT_PORT})"),
    host: str | None = typer.Option(None, "--host", help=f"Bind address (default: {_DEFAULT_HOST}, use 0.0.0.0 for remote access)"),
    workspace: str | None = typer.Option(None, "--workspace", "-w", help="OpenClaw workspace path (auto-detected)"),
    otel: bool = typer.Option(False, "--otel", help="Enable built-in OTLP receiver for richer token metrics"),
    foreground: bool = typer.Option(False, "--fg", help="Run in foreground instead of background"),
) -> None:
    """
    Start the metrics dashboard.

    Launches ClawMetry to monitor OpenClaw agent activity. Auto-detects the
    OpenClaw workspace at ~/.openclaw unless overridden with --workspace.

    With --otel, the dashboard also acts as a lightweight OTLP receiver.
    Point OpenClaw's diagnostics-otel plugin at http://localhost:<port> to
    get real token counts and cost calculations.

    Use --host 0.0.0.0 to make the dashboard accessible from other machines.

    Examples:
        mycelium metrics start                    # background, default port
        mycelium metrics start --fg               # foreground (Ctrl+C to stop)
        mycelium metrics start --otel             # with OTLP receiver
        mycelium metrics start --port 9100        # custom port
        mycelium metrics start --host 0.0.0.0     # allow remote access
    """
    try:
        if not _check_clawmetry():
            typer.secho("  ✗ ClawMetry not installed.", fg=typer.colors.RED)
            typer.echo("")
            typer.echo("  Install with:")
            typer.secho("    pip install 'mycelium-cli[metrics]'", fg=typer.colors.CYAN)
            typer.echo("  or:")
            typer.secho("    pip install clawmetry", fg=typer.colors.CYAN)
            raise typer.Exit(1)

        running, existing_pid = _is_running()
        if running:
            typer.secho(f"  Metrics dashboard already running (PID {existing_pid}).", fg=typer.colors.YELLOW)
            typer.echo(f"  → http://{_display_host(_get_host())}:{_get_port()}")
            typer.echo("  Use 'mycelium metrics stop' to stop it first.")
            return

        resolved_port = _resolve_port(port)
        resolved_host = _resolve_host(host)
        url_host = _display_host(resolved_host)

        clawmetry_bin = _find_clawmetry()
        if not clawmetry_bin:
            typer.secho("  ✗ 'clawmetry' command not found.", fg=typer.colors.RED)
            typer.echo("    Reinstall: pip install 'mycelium-cli[metrics]'")
            raise typer.Exit(1)

        cmd = [clawmetry_bin, "--port", str(resolved_port), "--host", resolved_host]
        if workspace:
            cmd += ["--workspace", workspace]

        if foreground:
            typer.secho(f"  Starting metrics dashboard on {resolved_host}:{resolved_port}...", fg=typer.colors.GREEN)
            typer.echo(f"  → http://{url_host}:{resolved_port}")
            typer.echo("  Press Ctrl+C to stop.")
            typer.echo("")

            env = os.environ.copy()
            if otel:
                env["CLAWMETRY_OTEL"] = "1"

            try:
                subprocess.run(cmd, env=env, check=False)
            except KeyboardInterrupt:
                typer.echo("\n  Dashboard stopped.")
            return

        env = os.environ.copy()
        if otel:
            env["CLAWMETRY_OTEL"] = "1"

        proc = subprocess.Popen(
            cmd,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            env=env,
            start_new_session=True,
        )

        _PID_FILE.parent.mkdir(parents=True, exist_ok=True)
        _PID_FILE.write_text(json_module.dumps({"pid": proc.pid, "port": resolved_port, "host": resolved_host}))

        typer.secho(f"  ✓ Metrics dashboard started (PID {proc.pid})", fg=typer.colors.GREEN)
        typer.echo(f"  → http://{url_host}:{resolved_port}")
        if otel:
            typer.echo(f"  OTLP receiver enabled on port {resolved_port}")

    except typer.Exit:
        raise
    except Exception as e:
        verbose = ctx.obj.get("verbose", False) if ctx.obj else False
        print_error(e, verbose=verbose)
        raise typer.Exit(1) from None


@app.command("stop")
def stop(ctx: typer.Context) -> None:
    """Stop the metrics dashboard."""
    try:
        running, pid = _is_running()
        if not running:
            typer.echo("  Metrics dashboard is not running.")
            return

        os.kill(pid, signal.SIGTERM)
        _PID_FILE.unlink(missing_ok=True)
        typer.secho("  ✓ Metrics dashboard stopped.", fg=typer.colors.GREEN)

    except Exception as e:
        verbose = ctx.obj.get("verbose", False) if ctx.obj else False
        print_error(e, verbose=verbose)


@app.command("status")
def metrics_status(ctx: typer.Context) -> None:
    """Show metrics dashboard status."""
    try:
        json_output = ctx.obj.get("json", False) if ctx.obj else False
        running, pid = _is_running()
        installed = _check_clawmetry()

        port = _get_port()
        url_host = _display_host(_get_host())

        if json_output:
            typer.echo(json_module.dumps({
                "installed": installed,
                "running": running,
                "pid": pid,
                "url": f"http://{url_host}:{port}" if running else None,
            }))
            return

        if not installed:
            typer.secho("  ✗ ClawMetry not installed", fg=typer.colors.RED)
            typer.echo("    Install: pip install 'mycelium-cli[metrics]'")
            return

        if running:
            typer.secho(f"  ✓ Metrics dashboard running (PID {pid})", fg=typer.colors.GREEN)
            typer.echo(f"    → http://{url_host}:{port}")
        else:
            typer.secho("  ~ Metrics dashboard not running", fg=typer.colors.YELLOW)
            typer.echo("    Start: mycelium metrics start")

    except Exception as e:
        verbose = ctx.obj.get("verbose", False) if ctx.obj else False
        print_error(e, verbose=verbose)


@app.command("open")
def open_dashboard(ctx: typer.Context) -> None:
    """Open the metrics dashboard in the default browser."""
    try:
        import webbrowser

        running, _ = _is_running()
        if not running:
            typer.secho("  Metrics dashboard is not running.", fg=typer.colors.YELLOW)
            typer.echo("  Start it first: mycelium metrics start")
            raise typer.Exit(1)

        url = f"http://{_display_host(_get_host())}:{_get_port()}"
        webbrowser.open(url)
        typer.echo(f"  Opened {url}")

    except typer.Exit:
        raise
    except Exception as e:
        verbose = ctx.obj.get("verbose", False) if ctx.obj else False
        print_error(e, verbose=verbose)
