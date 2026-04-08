"""Bot message texts.

All user-facing message texts are centralized here
for easy editing and future localization support.
"""

from src.config import settings


class Texts:
    """All bot message texts."""

    # Start command - new welcome message as per image
    START_WELCOME = (
        f"👋 <b>Привет, Дорогой друг!</b>\n\n"
        f"<b>{settings.bot_name}</b> – включил и забыл.\n"
        "✅ Неограниченный трафик\n"
        "💰 Доступные тарифы\n"
        "📶 Много разных локаций\n"
        "🚀 Мгновенная активация\n"
        "💸 Партнерская программа с пассивным доходом!\n\n"
        "━━━━━━━━━━━━━━━━━━━━\n"
        "📌 <b>Ваша подписка:</b> {subscription_status}\n"
        "📅 <b>До:</b> {subscription_end}\n"
        "━━━━━━━━━━━━━━━━━━━━\n\n"
        "Нажмите <b>💳 Оплатить</b> чтобы активировать подписку 👇"
    )

    START_NEW_USER = START_WELCOME

    START_EXISTING_USER = START_WELCOME

    START_MAIN_MENU = START_WELCOME

    # Info menu - message text
    INFO_MENU_TEXT = "ℹ️ <b>Инфо</b>\n\nВыберите раздел:"

    # Info message (old - kept for reference)
    INFO_TEXT = (
        f"ℹ️ <b>О сервисе {settings.bot_name}</b>\n\n"
        f"<b>{settings.bot_name}</b> – включил и забыл.\n"
        "✅ Неограниченный трафик\n"
        "💰 Доступные тарифы\n"
        "📶 Много разных локаций\n"
        "🚀 Мгновенная активация\n"
        "💸 Партнерская программа с пассивным доходом!\n\n"
        "Используйте меню для управления подпиской."
    )

    # Profile message
    PROFILE_TEXT = (
        "💼 <b>Ваш профиль</b>\n\n"
        "👤 <b>Пользователь:</b> {username}\n"
        "📅 <b>Действует до:</b> {subscription_end}\n"
        "⏳ <b>Осталось:</b> {time_left}\n"
        "📱 <b>Лимит устройств:</b> {device_limit}\n"
        "🏷 <b>Тип подписки:</b> {subscription_type}\n"
        "💰 <b>Баланс:</b> {balance} ₽"
    )

    PROFILE_NO_SUBSCRIPTION = (
        "💼 <b>Ваш профиль</b>\n\n"
        "👤 <b>Пользователь:</b> {username}\n"
        "❌ <b>Подписка:</b> не активна\n"
        "💰 <b>Баланс:</b> {balance} ₽\n\n"
        "Нажмите <b>💳 Оплатить</b> для покупки подписки."
    )

    # Pay message
    PAY_TEXT = (
        "💳 <b>Оплата подписки</b>\n\n"
        "Выберите тарифный план:\n\n"
        "• 1 месяц — 299 ₽\n"
        "• 3 месяца — 799 ₽\n"
        "• 12 месяцев — 2499 ₽\n\n"
        "Для покупки выберите тариф."
    )

    # Support message
    SUPPORT_TEXT = (
        "Для того, чтобы мы быстро вас нашли, "
        "скопируйте ваш ID заранее и отправьте в "
        "поддержку с проблемой, которая у вас "
        "случилась.\n\n"
        "📋 <b>Ваш ID для копирования:</b>\n\n"
        "<code>Вот мой ID {user_id}</code>\n\n"
        "👇 Нажмите на текст выше, чтобы "
        "скопировать ваш ID, затем перейдите в "
        "поддержку."
    )

    # Bonuses message
    BONUSES_TEXT = (
        "🎁 <b>Бонусы</b>\n\n"
        "Приглашайте друзей и получайте бонусы!\n\n"
        "Нажмите <b>👥 Пригласить друга</b> чтобы получить вашу реферальную ссылку."
    )

    # Invite friend message (replaces Connect message)
    CONNECT_TEXT = (
        "👥 <b>Пригласите друга и получите бонусы!</b>\n\n"
        "• Новый пользователь получает: <b>5 ₽</b> при первом пополнении от 120 ₽\n"
        "• Вы получаете при первом пополнении реферала: <b>10 ₽</b>\n"
        "• Комиссия с каждого пополнения реферала: <b>20%</b>\n\n"
        "🔗 <b>Ваша реферальная ссылка:</b>\n"
        "{referral_link}"
    )

    # Balance
    BALANCE_INFO = (
        "💰 <b>Ваш баланс</b>\n\nСумма: {balance} ₽\nРеферальный код: <code>{referral_code}</code>"
    )
    BALANCE_DEPOSIT_PROMPT = (
        "💳 <b>Пополнение баланса</b>\n\n"
        "Выберите сумму или используйте команду <code>/deposit &lt;rub&gt;</code>"
    )
    BALANCE_ZERO = "💰 Ваш баланс: 0.00 ₽\n\nИспользуйте /deposit для пополнения."

    # Deposit
    DEPOSIT_START = (
        "💳 <b>Пополнение баланса</b>\n\n"
        "Минимальная сумма: {min_amount} ₽\n\n"
        "Выберите сумму или введите вручную:"
    )
    DEPOSIT_AMOUNT_SELECTED = (
        "💰 <b>Пополнение баланса</b>\n\nСумма: {amount} ₽\n\nВыберите способ оплаты:"
    )
    DEPOSIT_AMOUNT_PROMPT = "Введите сумму пополнения (минимум {min_amount} ₽):"
    DEPOSIT_METHOD_SELECT = "Выберите способ оплаты:"
    DEPOSIT_CREATING = "⏳ Создаю платеж..."
    DEPOSIT_SUCCESS = (
        "✅ Платёж создан!\n\n"
        "Сумма: {amount:.2f} ₽\n"
        "Способ: {method}\n\n"
        "Нажмите кнопку ниже для оплаты."
    )
    DEPOSIT_PENDING = "⏳ Платёж ожидает оплаты.\n\nСумма: {amount:.2f} ₽"
    DEPOSIT_COMPLETED = "✅ Платёж успешно завершен!\n\nСумма: {amount:.2f} ₽ зачислена на баланс."
    DEPOSIT_FAILED = "❌ Платёж не удался. Попробуйте снова."
    DEPOSIT_CANCELLED = "❌ Пополнение отменено."
    DEPOSIT_INVALID_AMOUNT = "❌ Неверная сумма. Введите число от {min_amount} до {max_amount} ₽."
    DEPOSIT_MIN_AMOUNT_ERROR = (
        "❌ Минимальная сумма пополнения: {min_amount} ₽\nВведите другую сумму:"
    )
    DEPOSIT_INVALID_FORMAT = "❌ Неверный формат суммы.\nВведите число, например: 500 или 1000"
    DEPOSIT_HISTORY_EMPTY = "История платежей пуста."
    DEPOSIT_HISTORY_TITLE = "📋 История платежей:\n\n"

    # Referral
    REFERRAL_INFO = (
        "👥 <b>Реферальная программа</b>\n\n"
        "• Новый пользователь получает: <b>5 ₽</b> при первом пополнении от 120 ₽\n"
        "• Вы получаете при первом пополнении реферала: <b>10 ₽</b>\n"
        "• Комиссия с каждого пополнения реферала: <b>20%</b>\n\n"
        "🤖 <b>Ссылка на бота:</b>\n"
        "{bot_link}?start={referral_code}\n\n"
        "🆔 <b>Ваш код:</b> <code>{referral_code}</code>\n\n"
        "📢 Приглашайте друзей и зарабатывайте!"
    )
    # Text for sharing referral link (sent when user clicks "Отправить приглашение")
    REFERRAL_SHARE = (
        "🎉 <b>Присоединяйся к VPN сервису!</b>\n\n"
        "💎 При первом пополнении от 120 ₽ ты получишь <b>5 ₽</b> бонусом на баланс!\n\n"
        "🚀 Быстрое подключение\n"
        "🌍 Серверы по всему миру\n"
        "🔒 Надежная защита\n\n"
        "👇 Переходи по ссылке:\n"
        "{referral_link}"
    )
    REFERRAL_LINK = "🔗 Ваша реферальная ссылка:\n\n{link}"
    REFERRAL_STATS_EMPTY = "У вас пока нет рефералов."

    # Errors
    ERROR_GENERIC = "❌ Произошла ошибка. Попробуйте позже."
    ERROR_NOT_REGISTERED = "❌ Вы не зарегистрированы.\nИспользуйте /start для регистрации."
    ERROR_PAYMENT_NOT_FOUND = "❌ Платёж не найден."
    ERROR_BALANCE = "❌ Ошибка получения баланса"

    # Deposit messages
    DEPOSIT_PROMPT = "💳 <b>Пополнение баланса</b>\n\nДля пополнения используйте команду /deposit"

    # Subscription messages
    TRIAL_SUBSCRIPTION = (
        "🧪 <b>Тестовый период</b>\n\n"
        "Вы можете активировать тестовую подписку на 3 дня.\n\n"
        "Для активации нажмите кнопку ниже."
    )
    TRIAL_PROPOSAL = (
        "🧪 <b>Тестовый период</b>\n\n"
        "Хотите начать 3-дневный тестовый период?\n\n"
        "Это позволит вам бесплатно попробовать наш VPN сервис."
    )
    TRIAL_ACTIVATED = (
        "✅ <b>Тестовый период активирован!</b>\n\n"
        "🎉 Ваша подписка активна на 3 дня.\n\n"
        "🔗 <b>Ваша VPN ссылка:</b>\n"
        "<code>{vpn_link}</code>\n\n"
        "👇 Нажмите на ссылку выше, чтобы скопировать её."
    )
    TRIAL_ALREADY_USED = (
        "❌ <b>Тестовый период уже использован</b>\n\n"
        "Вы уже активировали тестовый период ранее.\n\n"
        "Для покупки подписки нажмите <b>💳 Оплатить</b>."
    )
    BUY_SUBSCRIPTION = (
        "💎 <b>Купить подписку</b>\n\n"
        "Выберите тарифный план:\n\n"
        "• 1 месяц — 299 ₽\n"
        "• 3 месяца — 799 ₽\n"
        "• 12 месяцев — 2499 ₽\n\n"
        "Для покупки выберите тариф."
    )

    # Cancel
    CANCELLED = "❌ Операция отменена."

    # Help
    HELP_TEXT = (
        "📖 <b>Справка по командам:</b>\n\n"
        "/start — регистрация\n"
        "/balance — баланс\n"
        "/deposit — пополнить баланс\n"
        "/referral — реферальная программа\n"
        "/help — эта справка"
    )

    # Payment flow texts
    PAYMENT_METHOD_SELECT = (
        "💳 <b>Выберите способ оплаты</b>\n\n"
        "Сумма: {amount} ₽\n"
        "Тариф: {tariff_label}\n\n"
        "Выберите удобный способ оплаты:"
    )

    PAYMENT_CREATED = (
        "✅ <b>Платёж создан!</b>\n\n"
        "💰 Сумма: {amount} ₽\n"
        "💳 Способ: {method_name}\n"
        "📋 ID платежа: #{payment_id}\n\n"
        "🔗 <b>Для оплаты:</b>\n"
        "1. Нажмите кнопку «Перейти к оплате»\n"
        "2. Оплатите на сайте платежной системы\n"
        "3. Вернитесь и нажмите «Я оплатил»\n\n"
        "⏰ <b>Важно:</b> Нажмите «Я оплатил» после завершения оплаты!"
    )

    PAYMENT_PENDING_CHECK = "⏳ <b>Проверка статуса платежа...</b>\n\nПодождите, проверяем оплату."

    PAYMENT_PENDING_RESULT = (
        "⏳ <b>Платеж еще не завершен</b>\n\n"
        "Если вы уже оплатили, подождите несколько минут и попробуйте снова.\n\n"
        "💡 Нажмите «Я оплатил» для повторной проверки."
    )

    PAYMENT_SUCCESS_RESULT = (
        "✅ <b>Оплата успешно завершена!</b>\n\n"
        "🎉 Подписка активирована!\n"
        "📅 Длительность: {duration} дней\n\n"
        "🔗 <b>Ваша VPN ссылка:</b>\n"
        "<code>{vpn_link}</code>\n\n"
        "👇 Нажмите на ссылку выше, чтобы скопировать её."
    )

    PAYMENT_FAILED_RESULT = (
        "❌ <b>Платеж не прошел</b>\n\n"
        "Причина: {reason}\n\n"
        "Попробуйте оплатить снова или выберите другой способ оплаты."
    )

    PAYMENT_CANCELLED_RESULT = "🚫 <b>Платёж отменён</b>\n\nВы можете попробовать оплатить снова."

    PAYMENT_ALREADY_ACTIVE = (
        "✅ <b>У вас уже есть активная подписка</b>\n\n"
        "📅 Действует до: {end_date}\n\n"
        "Новая подписка будет добавлена к текущей."
    )


def format_text(template: str, **kwargs) -> str:
    """Format text template with given parameters.

    Args:
        template: Text template from Texts class.
        **kwargs: Parameters to substitute.

    Returns:
        Formatted text string.
    """
    return template.format(**kwargs)
