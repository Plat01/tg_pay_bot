"""Handlers package."""

from aiogram import Dispatcher

from src.bot.handlers.start import register_start_handlers
from src.bot.handlers.deposit import register_deposit_handlers


def register_handlers(dp: Dispatcher) -> None:
    """Register all handlers to dispatcher."""
    register_start_handlers(dp)
    register_deposit_handlers(dp)