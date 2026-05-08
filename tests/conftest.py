"""Test compatibility helpers for minimal environments."""

from __future__ import annotations

import asyncio
import inspect
from collections.abc import Generator
from typing import Any

import pytest


def pytest_addoption(parser: pytest.Parser) -> None:
    """Accept pytest-asyncio configuration when that plugin is not installed."""
    parser.addini("asyncio_mode", "asyncio compatibility mode", default="auto")


def pytest_configure(config: pytest.Config) -> None:
    """Register the asyncio marker when pytest-asyncio is unavailable."""
    config.addinivalue_line("markers", "asyncio: run async tests on the default event loop")


@pytest.hookimpl(tryfirst=True)
def pytest_pyfunc_call(pyfuncitem: pytest.Function) -> bool | None:
    """Run coroutine tests marked with ``pytest.mark.asyncio`` without extra plugins."""
    if "asyncio" not in pyfuncitem.keywords:
        return None
    testfunction = pyfuncitem.obj
    if not inspect.iscoroutinefunction(testfunction):
        return None
    signature = inspect.signature(testfunction)
    kwargs: dict[str, Any] = {
        name: pyfuncitem.funcargs[name]
        for name in signature.parameters
        if name in pyfuncitem.funcargs
    }
    asyncio.run(testfunction(**kwargs))
    return True


@pytest.fixture
def event_loop() -> Generator[asyncio.AbstractEventLoop]:
    """Provide an event loop fixture compatible with older async tests."""
    loop = asyncio.new_event_loop()
    try:
        yield loop
    finally:
        loop.close()
