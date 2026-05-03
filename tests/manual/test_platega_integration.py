"""Интеграционный тест Platega API.

Этот тест использует реальные API ключи из .env для проверки
полного цикла оплаты через Platega.

Запуск:
    python -m pytest tests/manual/test_platega_integration.py -v -s

Или напрямую:
    python tests/manual/test_platega_integration.py
"""

import asyncio
import logging
from decimal import Decimal
from uuid import UUID

from src.config import settings
from src.infrastructure.payments.platega import PlategaProvider
from src.infrastructure.payments.schemas import PlategaPaymentMethod

logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


async def test_platega_create_payment() -> None:
    """Тест создания платежа через Platega API."""
    logger.info("=" * 80)
    logger.info("ИНТЕГРАЦИОННЫЙ ТЕСТ PLATEGA API")
    logger.info("=" * 80)

    logger.info(f"Merchant ID: {settings.platega_merchant_id[:8]}...")
    logger.info(f"API URL: {settings.platega_api_url}")
    logger.info(f"API Key: {settings.platega_secret[:8]}...")

    provider = PlategaProvider()

    test_amount = Decimal("299.00")
    test_currency = "RUB"
    test_description = "Тестовый платеж: 1 месяц — 299 ₽"

    logger.info(f"\nТестовые параметры:")
    logger.info(f"  Amount: {test_amount}")
    logger.info(f"  Currency: {test_currency}")
    logger.info(f"  Description: {test_description}")

    payment_methods_to_test = [
        PlategaPaymentMethod.SBP_QR,
        PlategaPaymentMethod.CARD_ACQUIRING,
        PlategaPaymentMethod.INTERNATIONAL,
    ]

    results = []

    for method in payment_methods_to_test:
        logger.info(f"\n{'=' * 80}")
        logger.info(f"ТЕСТИРУЮ МЕТОД: {method.name} (код: {method.value})")
        logger.info("=" * 80)

        try:
            result = await provider.create_payment(
                amount=test_amount,
                currency=test_currency,
                description=test_description,
                payment_method=method,
                metadata={"test": "integration_test", "method": method.name},
            )

            logger.info(f"\nРЕЗУЛЬТАТ:")
            logger.info(f"  Success: {result.success}")
            logger.info(f"  Payment ID: {result.payment_id}")
            logger.info(f"  External ID: {result.external_id}")
            logger.info(f"  Payment URL: {result.payment_url}")
            logger.info(f"  Transaction ID: {result.transaction_id}")
            logger.info(f"  QR Code: {result.qr_code}")
            logger.info(f"  Expires In: {result.expires_in}")
            logger.info(f"  Error Message: {result.error_message}")
            logger.info(f"  Raw Response: {result.raw_response}")

            if result.success:
                results.append(
                    {
                        "method": method.name,
                        "external_id": result.external_id,
                        "payment_url": result.payment_url,
                        "success": True,
                    }
                )

                logger.info(f"\n✅ ПЛАТЕЖ УСПЕШНО СОЗДАН!")
                logger.info(f"   Transaction ID: {result.external_id}")
                logger.info(f"   Payment URL: {result.payment_url}")

                logger.info(f"\nПроверка статуса платежа...")
                try:
                    status_result = await provider.get_payment_status(result.external_id)
                    logger.info(f"\nСТАТУС ПЛАТЕЖА:")
                    logger.info(f"  Success: {status_result.success}")
                    logger.info(f"  Payment ID: {status_result.payment_id}")
                    logger.info(f"  Status: {status_result.status.value}")
                    logger.info(f"  External Status: {status_result.external_status}")
                    logger.info(f"  Amount: {status_result.amount}")
                    logger.info(f"  Currency: {status_result.currency}")
                    logger.info(f"  Raw Response: {status_result.raw_response}")
                except Exception as e:
                    logger.error(f"❌ Ошибка проверки статуса: {e}")
            else:
                results.append(
                    {
                        "method": method.name,
                        "success": False,
                        "error": result.error_message,
                    }
                )
                logger.warning(f"\n⚠️  ПЛАТЕЖ НЕ СОЗДАН")
                logger.warning(f"   Причина: {result.error_message}")

                if result.external_id:
                    logger.info(f"   Но transactionId присутствует: {result.external_id}")

        except Exception as e:
            logger.error(f"\n❌ ИСКЛЮЧЕНИЕ: {type(e).__name__}: {e}")
            results.append(
                {
                    "method": method.name,
                    "success": False,
                    "error": str(e),
                }
            )

        logger.info(f"\n{'-' * 80}")

    await provider.close()

    logger.info(f"\n{'=' * 80}")
    logger.info("СВОДКА РЕЗУЛЬТАТОВ")
    logger.info("=" * 80)

    for r in results:
        status = "✅" if r["success"] else "❌"
        logger.info(f"{status} {r['method']}: {r.get('external_id', r.get('error', 'N/A'))}")

    logger.info("=" * 80)

    successful = [r for r in results if r["success"]]
    logger.info(f"\nУспешно создано: {len(successful)} из {len(results)} методов")

    if successful:
        logger.info(f"\nДля завершения оплаты откройте URL:")
        for r in successful:
            if r.get("payment_url"):
                logger.info(f"  {r['method']}: {r['payment_url']}")


async def test_platega_webhook_parsing() -> None:
    """Тест парсинга webhook от Platega."""
    logger.info("\n" + "=" * 80)
    logger.info("ТЕСТ PARSING WEBHOOK")
    logger.info("=" * 80)

    provider = PlategaProvider()

    sample_webhook_body = {
        "transactionId": "550e8400-e29b-41d4-a716-446655440000",
        "status": "CONFIRMED",
        "paymentDetails": {"amount": 299.00, "currency": "RUB"},
        "payload": "test_payload",
    }

    raw_body = str(sample_webhook_body).encode("utf-8")

    signature = "test_signature"

    headers = {"X-Signature": signature}

    try:
        webhook_data = provider.parse_webhook(raw_body, headers)
        logger.info(f"\nParsed webhook:")
        logger.info(f"  Payment ID: {webhook_data.payment_id}")
        logger.info(f"  Status: {webhook_data.status.value}")
        logger.info(f"  Amount: {webhook_data.amount}")
        logger.info(f"  Currency: {webhook_data.currency}")
        logger.info(f"  Raw Data: {webhook_data.raw_data}")
    except Exception as e:
        logger.error(f"❌ Ошибка парсинга webhook: {e}")

    await provider.close()


def main() -> None:
    """Запуск всех интеграционных тестов."""
    logger.info("\n" + "=" * 80)
    logger.info("ЗАПУСК ИНТЕГРАЦИОННЫХ ТЕСТОВ PLATEGA")
    logger.info("=" * 80)

    asyncio.run(test_platega_create_payment())

    asyncio.run(test_platega_webhook_parsing())


if __name__ == "__main__":
    main()
