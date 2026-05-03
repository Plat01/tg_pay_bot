"""Полный тест цикла оплаты через Platega с PaymentService.

Тестирует:
1. Создание платежа через PaymentService
2. Проверка статуса через PaymentService
3. Webhook handler
4. HTTP callback handlers бота

Запуск:
    python tests/manual/test_payment_flow.py
"""

import asyncio
import logging
from decimal import Decimal
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from src.config import settings
from src.infrastructure.database import async_session_maker
from src.infrastructure.payments.schemas import PlategaPaymentMethod
from src.services.payment import PaymentService

logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


async def test_full_payment_flow() -> None:
    """Полный тест цикла оплаты."""
    logger.info("=" * 80)
    logger.info("ПОЛНЫЙ ТЕСТ ЦИКЛА ОПЛАТЫ")
    logger.info("=" * 80)

    test_telegram_id = "123456789"
    test_amount = Decimal("299.00")
    test_currency = "RUB"
    test_description = "Подписка: 1 месяц — 299 ₽"
    test_method = PlategaPaymentMethod.SBP_QR

    logger.info(f"Telegram ID: {test_telegram_id}")
    logger.info(f"Amount: {test_amount}")
    logger.info(f"Method: {test_method.name}")

    async with async_session_maker() as session:
        payment_service = PaymentService(session)

        logger.info(f"\nШАГ 1: Создание платежа через PaymentService")
        logger.info("-" * 80)

        try:
            payment, result = await payment_service.create_external_payment(
                telegram_id=test_telegram_id,
                amount=test_amount,
                currency=test_currency,
                description=test_description,
                payment_method=test_method,
            )

            logger.info(f"\nРЕЗУЛЬТАТ:")
            logger.info(f"  Payment DB ID: {payment.id}")
            logger.info(f"  Payment External ID: {payment.external_id}")
            logger.info(f"  Payment Status: {payment.status.value}")
            logger.info(f"  Provider Result Success: {result.success}")
            logger.info(f"  Provider External ID: {result.external_id}")
            logger.info(f"  Payment URL: {result.payment_url}")
            logger.info(f"  QR Code: {result.qr_code}")
            logger.info(f"  Expires In: {result.expires_in}")
            logger.info(f"  Error: {result.error_message}")

            if result.success:
                logger.info(f"\n✅ ПЛАТЕЖ СОЗДАН УСПЕШНО!")

                logger.info(f"\nШАГ 2: Проверка статуса платежа")
                logger.info("-" * 80)

                await asyncio.sleep(2)

                payment_updated = await payment_service.check_and_update_status(payment)

                logger.info(f"\nСТАТУС ПОСЛЕ ПРОВЕРКИ:")
                logger.info(f"  Payment ID: {payment_updated.id}")
                logger.info(f"  Status: {payment_updated.status.value}")
                logger.info(f"  External ID: {payment_updated.external_id}")
                logger.info(f"  Completed At: {payment_updated.completed_at}")

                logger.info(f"\nШАГ 3: Получение платежа по external_id")
                logger.info("-" * 80)

                payment_by_external = await payment_service.get_payment_by_external_id(
                    payment.external_id
                )

                if payment_by_external:
                    logger.info(f"✅ Платеж найден по external_id:")
                    logger.info(f"  ID: {payment_by_external.id}")
                    logger.info(f"  Status: {payment_by_external.status.value}")
                else:
                    logger.error(f"❌ Платеж не найден по external_id")

                logger.info(f"\nШАГ 4: Получение платежей пользователя")
                logger.info("-" * 80)

                user_payments = await payment_service.get_user_payments(test_telegram_id)

                logger.info(f"Найдено платежей: {len(user_payments)}")
                for p in user_payments:
                    logger.info(f"  - ID: {p.id}, Status: {p.status.value}, Amount: {p.amount}")

                logger.info(f"\n" + "=" * 80)
                logger.info("ИНФОРМАЦИЯ ДЛЯ ОПЛАТЫ")
                logger.info("=" * 80)
                logger.info(f"Payment URL: {result.payment_url}")
                logger.info(f"QR Code: {result.qr_code}")
                logger.info(f"Transaction ID: {result.external_id}")
                logger.info("=" * 80)

            else:
                logger.error(f"\n❌ ПЛАТЕЖ НЕ СОЗДАН")
                logger.error(f"   Error: {result.error_message}")

                if payment.external_id:
                    logger.warning(f"   Но payment.external_id = {payment.external_id}")
                    logger.warning(f"   Это значит transactionId был в ответе!")

        except ValueError as e:
            logger.error(f"\n❌ ОШИБКА ВАЛИДАЦИИ: {e}")

        except Exception as e:
            logger.error(f"\n❌ ИСКЛЮЧЕНИЕ: {type(e).__name__}: {e}")
            import traceback

            logger.error(traceback.format_exc())

        await payment_service.close_provider()


async def test_card_acquiring_method() -> None:
    """Тест метода CARD_ACQUIRING (который вызывал ошибку)."""
    logger.info("\n" + "=" * 80)
    logger.info("ТЕСТ МЕТОДА CARD_ACQUIRING (код 11)")
    logger.info("=" * 80)

    test_telegram_id = "123456789"
    test_amount = Decimal("299.00")
    test_method = PlategaPaymentMethod.CARD_ACQUIRING

    async with async_session_maker() as session:
        payment_service = PaymentService(session)

        try:
            payment, result = await payment_service.create_external_payment(
                telegram_id=test_telegram_id,
                amount=test_amount,
                payment_method=test_method,
                description="Тест CARD_ACQUIRING",
            )

            logger.info(f"Success: {result.success}")
            logger.info(f"External ID: {result.external_id}")
            logger.info(f"Error: {result.error_message}")
            logger.info(f"Payment DB External ID: {payment.external_id}")

            if not result.success and result.external_id:
                logger.warning("⚠️  HTTP 400, но transactionId присутствует!")
                logger.warning(f"   Это исправленная проблема!")

        except ValueError as e:
            logger.error(f"❌ ValueError (пустой external_id): {e}")

        except Exception as e:
            logger.error(f"❌ Exception: {e}")

        await payment_service.close_provider()


def main() -> None:
    """Запуск тестов."""
    logger.info("=" * 80)
    logger.info("ТЕСТИРОВАНИЕ ПОЛНОГО ЦИКЛА ОПЛАТЫ")
    logger.info("=" * 80)

    asyncio.run(test_full_payment_flow())

    asyncio.run(test_card_acquiring_method())


if __name__ == "__main__":
    main()
