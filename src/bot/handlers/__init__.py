"""Handlers package."""

from aiogram import Dispatcher

from src.bot.handlers.start import register_start_handlers


def register_handlers(dp: Dispatcher) -> None:
    """Register all handlers to dispatcher."""
    register_start_handlers(dp)