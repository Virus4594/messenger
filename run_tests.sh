#!/bin/bash
# run_tests.sh

echo "==================================="
echo "🧪 Запуск тестов Messenger в Docker"
echo "==================================="

# Пересобираем тестовый образ
docker-compose -f docker-compose.yml build test

# Запускаем тесты
docker-compose -f docker-compose.yml run --rm test

# Сохраняем код возврата
EXIT_CODE=$?

echo "==================================="
if [ $EXIT_CODE -eq 0 ]; then
    echo "✅ Все тесты пройдены успешно!"
else
    echo "❌ Некоторые тесты не прошли"
fi
echo "==================================="

exit $EXIT_CODE