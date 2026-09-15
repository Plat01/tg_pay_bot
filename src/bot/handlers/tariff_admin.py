"""Admin handlers for managing tariffs (/tariffs, /add_tariff).

Tariffs are stored in the tariff_settings table; every change refreshes the
in-memory cache, so buttons and texts update without restarting the bot.
"""

import logging

from aiogram import Dispatcher
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import Message

from src.bot.constants import Commands
from src.config import settings
from src.services.tariff import (
    TRIAL_TARIFF,
    TariffService,
    TariffValidationError,
    build_button_label,
    validate_tariff_field,
)

logger = logging.getLogger(__name__)

CONFIRM_ANSWERS = ("да", "yes", "y", "д", "+")

# Field menu of the edit flow: number -> (field name, prompt)
EDIT_FIELDS = {
    "1": ("price", "Введите новую цену в рублях (например, 249 или 249.50):"),
    "2": ("days", "Введите новую длительность подписки в днях:"),
    "3": ("devices", "Введите количество устройств:"),
    "4": ("duration_text", "Введите текст длительности (например, «1 месяц»):"),
    "5": ("label", "Введите название типа подписки (например, «Месячная»):"),
    "6": (
        "max_grant_days",
        "Введите максимальное число дней ручной выдачи для этого тарифа "
        "или «-», если тариф покрывает всё сверху:",
    ),
}

# Steps of the add flow: (field, prompt)
ADD_STEPS = [
    (
        "tariff_type",
        "Введите код тарифа латиницей (например, half_year). "
        "Он используется в кнопках и в записях о подписках:",
    ),
    ("price", "Введите цену в рублях (например, 999):"),
    ("days", "Введите длительность подписки в днях:"),
    ("devices", "Введите количество устройств:"),
    ("duration_text", "Введите текст длительности (например, «6 месяцев»):"),
    ("label", "Введите название типа подписки (например, «Полугодовая»):"),
]


class TariffEditStates(StatesGroup):
    """States for the /tariffs edit flow."""

    waiting_for_tariff = State()
    waiting_for_field = State()
    waiting_for_value = State()
    waiting_for_confirmation = State()


class TariffAddStates(StatesGroup):
    """States for the /add_tariff flow."""

    waiting_for_value = State()
    waiting_for_confirmation = State()


def _is_admin(message: Message) -> bool:
    """Check that the message comes from an admin."""
    if not message.from_user:
        return False
    return str(message.from_user.id) in settings.admin_id_list


async def _deny(message: Message, command: str) -> None:
    """Report missing permissions."""
    user_id = message.from_user.id if message.from_user else "unknown"
    logger.warning(f"Non-admin user {user_id} tried to access {command} command")
    await message.answer("❌ У вас нет прав для выполнения этой команды.")


def _format_value(field: str, value: object) -> str:
    """Format a field value for display."""
    if field == "price":
        return f"{int(value)} ₽" if float(value) == int(float(str(value))) else f"{value} ₽"
    if field == "days":
        return f"{value} дн."
    if field == "max_grant_days":
        return "всё сверху" if value is None else f"до {value} дн."
    return str(value)


def _format_tariff(index: int, entry: dict) -> str:
    """Format one tariff for the list."""
    status = "✅" if entry["is_active"] else "🚫 выключен"
    grant = (
        "всё сверху" if entry["max_grant_days"] is None else f"до {entry['max_grant_days']} дн."
    )
    return (
        f"<b>{index}. {entry['tariff_type']}</b> — {entry['name']} {status}\n"
        f"   💰 {int(entry['price'])} ₽ | ⏱ {entry['days']} дн. | 📱 {entry['devices']}\n"
        f"   🏷 {entry['label']}\n"
        f"   🎁 ручная выдача: {grant}"
    )


async def _tariff_list_text(header: str) -> tuple[str, list[dict]]:
    """Build the tariff list text and the ordered tariffs behind it."""
    tariffs = await TariffService().list_tariffs()
    lines = [header, ""]
    lines += [_format_tariff(index, entry) for index, entry in enumerate(tariffs, start=1)]
    return "\n".join(lines), tariffs


async def cmd_tariffs(message: Message, state: FSMContext) -> None:
    """Admin command to view and edit tariffs."""
    if not _is_admin(message):
        await _deny(message, "tariffs")
        return

    text, tariffs = await _tariff_list_text("💼 <b>Тарифы</b>")

    await state.set_state(TariffEditStates.waiting_for_tariff)
    await state.update_data(tariff_types=[entry["tariff_type"] for entry in tariffs])
    await message.answer(
        f"{text}\n\n"
        "Введите номер тарифа для изменения.\n"
        "Новый тариф — /add_tariff, выход — /cancel",
        parse_mode="HTML",
    )

    admin_id = message.from_user.id if message.from_user else "unknown"
    logger.info(f"Admin {admin_id} opened tariffs list ({len(tariffs)} tariffs)")


async def process_tariff_choice(message: Message, state: FSMContext) -> None:
    """Process tariff number input."""
    if not message.text:
        await message.answer("❌ Пожалуйста, отправьте номер тарифа.")
        return

    data = await state.get_data()
    tariff_types: list[str] = data.get("tariff_types", [])

    try:
        index = int(message.text.strip())
        tariff_type = tariff_types[index - 1]
        if index < 1:
            raise IndexError
    except (ValueError, IndexError):
        await message.answer("❌ Введите номер тарифа из списка выше:")
        return

    entry = await TariffService().get_tariff_data(tariff_type)
    if not entry:
        await message.answer("❌ Тариф не найден, откройте список заново: /tariffs")
        await state.clear()
        return

    await state.update_data(tariff_type=tariff_type)
    await state.set_state(TariffEditStates.waiting_for_field)

    toggle_text = "Выключить" if entry["is_active"] else "Включить"
    await message.answer(
        f"⚙️ <b>Тариф {tariff_type}</b> — {entry['name']}\n\n"
        f"<b>1</b> — Цена ({int(entry['price'])} ₽)\n"
        f"<b>2</b> — Длительность ({entry['days']} дн.)\n"
        f"<b>3</b> — Устройств ({entry['devices']})\n"
        f"<b>4</b> — Текст длительности («{entry['duration_text']}»)\n"
        f"<b>5</b> — Название типа («{entry['name']}»)\n"
        f"<b>6</b> — Макс. дней ручной выдачи ("
        f"{'всё сверху' if entry['max_grant_days'] is None else entry['max_grant_days']})\n"
        f"<b>7</b> — {toggle_text} тариф\n"
        f"<b>8</b> — Удалить тариф\n\n"
        "Введите номер поля или /cancel:",
        parse_mode="HTML",
    )


async def process_field_choice(message: Message, state: FSMContext) -> None:
    """Process field number input."""
    if not message.text:
        await message.answer("❌ Пожалуйста, отправьте номер поля.")
        return

    choice = message.text.strip()
    data = await state.get_data()
    tariff_type = data["tariff_type"]

    if choice in EDIT_FIELDS:
        field, prompt = EDIT_FIELDS[choice]
        await state.update_data(field=field)
        await state.set_state(TariffEditStates.waiting_for_value)
        await message.answer(prompt)
        return

    entry = await TariffService().get_tariff_data(tariff_type)
    if not entry:
        await message.answer("❌ Тариф не найден, откройте список заново: /tariffs")
        await state.clear()
        return

    if choice == "7":
        new_state = not entry["is_active"]
        await state.update_data(action="toggle", new_value=new_state)
        await state.set_state(TariffEditStates.waiting_for_confirmation)
        action_text = "включить" if new_state else "выключить"
        hint = (
            ""
            if new_state
            else "\n\nВыключенный тариф пропадёт из меню оплаты, "
            "но выданные подписки продолжат работать."
        )
        await message.answer(
            f"⚠️ Подтвердите: {action_text} тариф <b>{tariff_type}</b>?{hint}\n\n(да/нет)",
            parse_mode="HTML",
        )
        return

    if choice == "8":
        if tariff_type == TRIAL_TARIFF:
            await message.answer(
                "❌ Тариф trial удалить нельзя — он используется при выдаче тестового периода. "
                "Его можно только изменить или выключить (пункт 7)."
            )
            return

        await state.update_data(action="delete")
        await state.set_state(TariffEditStates.waiting_for_confirmation)
        await message.answer(
            f"⚠️ Удалить тариф <b>{tariff_type}</b>?\n\n"
            "Выданные по нему подписки продолжат работать, но в их карточках вместо названия "
            "останется код тарифа. Если тариф просто больше не продаётся — лучше выключить его "
            "(пункт 7).\n\n(да/нет)",
            parse_mode="HTML",
        )
        return

    await message.answer("❌ Введите номер поля от 1 до 8:")


async def process_field_value(message: Message, state: FSMContext) -> None:
    """Process new value input and ask for confirmation."""
    if not message.text:
        await message.answer("❌ Пожалуйста, отправьте значение.")
        return

    data = await state.get_data()
    field = data["field"]
    tariff_type = data["tariff_type"]

    try:
        value = validate_tariff_field(field, message.text)
    except TariffValidationError as e:
        await message.answer(f"❌ {e}\n\nПопробуйте снова или /cancel:")
        return

    entry = await TariffService().get_tariff_data(tariff_type)
    if not entry:
        await message.answer("❌ Тариф не найден, откройте список заново: /tariffs")
        await state.clear()
        return

    old_value = entry["name"] if field == "label" else entry[field]

    preview_entry = {**entry, field: value}
    preview_label = build_button_label(
        preview_entry["duration_text"], preview_entry["devices"], preview_entry["price"]
    )

    warning = ""
    if field == "price":
        warning = (
            "\n\n⚠️ Счета, выставленные по старой цене, останутся с прежней суммой — "
            "при оплате пользователь получит именно тот тариф, который выбирал."
        )
    elif field == "days":
        warning = (
            "\n\n⚠️ Новая длительность применится только к будущим покупкам, "
            "уже выданные подписки не изменятся."
        )

    await state.update_data(action="update", new_value=value)
    await state.set_state(TariffEditStates.waiting_for_confirmation)
    await message.answer(
        f"⚠️ <b>Подтверждение изменения</b>\n\n"
        f"Тариф: <b>{tariff_type}</b>\n"
        f"Поле: {field}\n"
        f"Было: {_format_value(field, old_value)}\n"
        f"Станет: {_format_value(field, value)}\n\n"
        f"Кнопка будет выглядеть так:\n{preview_label}{warning}\n\n"
        f"Подтвердите (да/нет):",
        parse_mode="HTML",
    )


async def process_edit_confirmation(message: Message, state: FSMContext) -> None:
    """Apply a confirmed tariff change."""
    if not message.text:
        await message.answer("❌ Пожалуйста, отправьте текст.")
        return

    if message.text.strip().lower() not in CONFIRM_ANSWERS:
        await state.clear()
        await message.answer("❌ Изменение отменено.")
        return

    data = await state.get_data()
    tariff_type = data["tariff_type"]
    action = data.get("action")
    admin_id = message.from_user.id if message.from_user else "unknown"

    await state.clear()
    service = TariffService()

    try:
        if action == "delete":
            deleted = await service.delete_tariff(tariff_type)
            if not deleted:
                await message.answer("❌ Тариф не найден.")
                return
            logger.info(f"Admin {admin_id} deleted tariff {tariff_type}")
            await message.answer(f"✅ Тариф <b>{tariff_type}</b> удалён.", parse_mode="HTML")
            return

        if action == "toggle":
            new_value = data["new_value"]
            await service.set_active(tariff_type, new_value)
            logger.info(f"Admin {admin_id} set tariff {tariff_type} active={new_value}")
            state_text = "включён" if new_value else "выключен"
            await message.answer(
                f"✅ Тариф <b>{tariff_type}</b> {state_text}.", parse_mode="HTML"
            )
            return

        field = data["field"]
        value = data["new_value"]
        entry = await service.update_tariff(tariff_type, field, value)
        logger.info(f"Admin {admin_id} changed tariff {tariff_type}.{field} to {value}")
        await message.answer(
            f"✅ <b>Тариф обновлён</b>\n\n"
            f"{tariff_type}: {field} = {_format_value(field, value)}\n"
            f"Кнопка: {entry['label']}",
            parse_mode="HTML",
        )

    except TariffValidationError as e:
        await message.answer(f"❌ {e}")
    except Exception as e:
        logger.error(f"Error applying tariff change: {e}")
        await message.answer(f"❌ Не удалось применить изменение: {e}")


async def cmd_add_tariff(message: Message, state: FSMContext) -> None:
    """Admin command to add a new tariff."""
    if not _is_admin(message):
        await _deny(message, "add_tariff")
        return

    await state.set_state(TariffAddStates.waiting_for_value)
    await state.update_data(step=0, fields={})

    field, prompt = ADD_STEPS[0]
    await message.answer(
        f"➕ <b>Новый тариф</b> (шаг 1 из {len(ADD_STEPS)})\n\n{prompt}\n\nОтмена — /cancel",
        parse_mode="HTML",
    )

    admin_id = message.from_user.id if message.from_user else "unknown"
    logger.info(f"Admin {admin_id} started add_tariff process")


async def process_add_tariff_value(message: Message, state: FSMContext) -> None:
    """Collect new tariff fields step by step."""
    if not message.text:
        await message.answer("❌ Пожалуйста, отправьте значение.")
        return

    data = await state.get_data()
    step = data["step"]
    fields = dict(data["fields"])
    field, _ = ADD_STEPS[step]

    try:
        value = validate_tariff_field(field, message.text)
    except TariffValidationError as e:
        await message.answer(f"❌ {e}\n\nПопробуйте снова или /cancel:")
        return

    if field == "tariff_type" and await TariffService().get_tariff_data(value):
        await message.answer(f"❌ Тариф с кодом {value} уже существует. Введите другой код:")
        return

    fields[field] = value
    step += 1

    if step < len(ADD_STEPS):
        next_field, prompt = ADD_STEPS[step]
        await state.update_data(step=step, fields=fields)
        await message.answer(
            f"➕ <b>Новый тариф</b> (шаг {step + 1} из {len(ADD_STEPS)})\n\n{prompt}",
            parse_mode="HTML",
        )
        return

    await state.update_data(step=step, fields=fields)
    await state.set_state(TariffAddStates.waiting_for_confirmation)

    preview_label = build_button_label(fields["duration_text"], fields["devices"], fields["price"])
    await message.answer(
        f"⚠️ <b>Подтверждение нового тарифа</b>\n\n"
        f"Код: <b>{fields['tariff_type']}</b>\n"
        f"Название: {fields['label']}\n"
        f"Цена: {int(fields['price'])} ₽\n"
        f"Длительность: {fields['days']} дн.\n"
        f"Устройств: {fields['devices']}\n"
        f"Ручная выдача: до {fields['days']} дн.\n\n"
        f"Кнопка в меню оплаты:\n{preview_label}\n\n"
        f"Создать тариф? (да/нет)",
        parse_mode="HTML",
    )


async def process_add_tariff_confirmation(message: Message, state: FSMContext) -> None:
    """Create the new tariff after confirmation."""
    if not message.text:
        await message.answer("❌ Пожалуйста, отправьте текст.")
        return

    if message.text.strip().lower() not in CONFIRM_ANSWERS:
        await state.clear()
        await message.answer("❌ Создание тарифа отменено.")
        return

    data = await state.get_data()
    fields = data["fields"]
    admin_id = message.from_user.id if message.from_user else "unknown"

    await state.clear()

    try:
        entry = await TariffService().create_tariff(fields)
    except TariffValidationError as e:
        await message.answer(f"❌ {e}")
        return
    except Exception as e:
        logger.error(f"Error creating tariff: {e}")
        await message.answer(f"❌ Не удалось создать тариф: {e}")
        return

    logger.info(f"Admin {admin_id} created tariff {fields['tariff_type']}")
    await message.answer(
        f"✅ <b>Тариф создан</b>\n\n"
        f"Код: {entry['tariff_type']}\n"
        f"Кнопка: {entry['label']}\n\n"
        f"Он уже доступен пользователям в меню оплаты.",
        parse_mode="HTML",
    )


def register_tariff_admin_handlers(dp: Dispatcher) -> None:
    """Register tariff admin handlers."""
    dp.message.register(cmd_tariffs, Command(Commands.TARIFFS))
    dp.message.register(cmd_add_tariff, Command(Commands.ADD_TARIFF))

    dp.message.register(process_tariff_choice, TariffEditStates.waiting_for_tariff)
    dp.message.register(process_field_choice, TariffEditStates.waiting_for_field)
    dp.message.register(process_field_value, TariffEditStates.waiting_for_value)
    dp.message.register(process_edit_confirmation, TariffEditStates.waiting_for_confirmation)

    dp.message.register(process_add_tariff_value, TariffAddStates.waiting_for_value)
    dp.message.register(process_add_tariff_confirmation, TariffAddStates.waiting_for_confirmation)

    logger.info("Tariff admin handlers registered")
