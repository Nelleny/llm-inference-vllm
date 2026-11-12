# Титов А. — Команда исследования технологий машинного обучения

Локальный CPU-only inference-сервис на vLLM 0.27.0, Docker и Kubernetes (Minikube).
Бонусные задания не реализованы намеренно.

## Архитектура

- Модель: `Qwen/Qwen2.5-1.5B-Instruct` (публичная instruct-модель).
- Инференс: CPU-only через официальный CPU runtime image vLLM.
- Контейнер: пользователь UID/GID `10001`, `runAsNonRoot`, capabilities dropped.
- Модель скачивается при первом старте в `/models/model` (PVC). Маркер `.download_complete`
  предотвращает повторное обращение к Hugging Face после успешной загрузки.
- HF token и клиентский API bearer token передаются через Kubernetes Secret.
- Параметры vLLM задаются через ConfigMap.
- `--disable-log-requests` отключает логирование тел запросов vLLM. Сервисные логи
  не должны содержать prompt или generated text.

> Важно о воспроизводимости: Dockerfile наследуется от официального CPU-образа
> `vllm/vllm-openai-cpu:v0.27.0`, в котором зафиксирован весь runtime vLLM и
> его транзитивные зависимости. `requirements.txt` фиксирует версию vLLM;
> приложение использует стандартную библиотеку Python и `huggingface_hub`,
> уже входящий в runtime. Для максимально строгой supply-chain фиксации
> перед сдачей следует закрепить базовый образ по digest (`image@sha256:...`)
> после `docker image inspect`/получения digest из registry.

## Требования

- Docker Desktop запущен.
- Kubernetes/Minikube.
- kubectl.
- Для локального запуска на Windows рекомендуется Docker Desktop с WSL2 backend.
- Для модели нужно несколько гигабайт диска и оперативной памяти; CPU-инференс будет
  существенно медленнее GPU.

## 1. Сборка образа

Из корня проекта:

```powershell
docker build -t titov-vllm-cpu:0.27.0 .
```

Проверка версии и пользователя:

```powershell
docker run --rm --entrypoint sh titov-vllm-cpu:0.27.0 -c "id && python -c 'import vllm; print(vllm.__version__)'"
```

Ожидается UID `10001` и версия `0.27.0`.

## 2. Запуск Minikube

```powershell
minikube start --driver=docker --cpus=8 --memory=16384
kubectl get nodes
```

Если Docker Desktop использует WSL2, Minikube с Docker driver использует уже работающий Docker Engine.

## 3. Подготовка секретов

Сгенерируйте длинный API-токен и задайте HF токен (для публичной модели HF token необязателен):

```powershell
$env:API_ACCESS_TOKEN = "replace-with-a-long-random-token"
$env:HF_TOKEN = ""
kubectl create namespace llm-inference --dry-run=client -o yaml | kubectl apply -f -
kubectl -n llm-inference create secret generic llm-secrets `
  --from-literal=API_ACCESS_TOKEN=$env:API_ACCESS_TOKEN `
  --from-literal=HF_TOKEN=$env:HF_TOKEN `
  --dry-run=client -o yaml | kubectl apply -f -
```

Не добавляйте реальные токены в Git. `k8s/secret.yaml` — только шаблон; используйте
команды выше или заполните его локально, не коммитя изменённый файл.

## 4. Применение Kubernetes-манифестов

Сначала создайте namespace, затем остальные ресурсы:

```powershell
kubectl apply -f k8s/namespace.yaml
kubectl apply -f k8s/pvc.yaml
kubectl apply -f k8s/configmap.yaml
kubectl apply -f k8s/deployment.yaml
kubectl apply -f k8s/service.yaml
```

Для Minikube используйте локальный образ без публикации в registry. После `minikube start`:

```powershell
minikube image load titov-vllm-cpu:0.27.0
```

Убедитесь, что `image` в deployment соответствует тегу `titov-vllm-cpu:0.27.0`.

Наблюдение за запуском (первое скачивание модели может занять время):

```powershell
kubectl -n llm-inference get pods -w
kubectl -n llm-inference logs deployment/vllm-cpu -f
```

Проверка PVC:

```powershell
kubectl -n llm-inference get pvc
```

## 5. Проверка API

В отдельном PowerShell:

```powershell
kubectl -n llm-inference port-forward service/vllm-service 8000:8000
```

В другом окне:

```powershell
$headers = @{ Authorization = "Bearer $env:API_ACCESS_TOKEN" }
Invoke-RestMethod -Uri http://localhost:8000/v1/models -Headers $headers
```

Пример генерации:

```powershell
$headers = @{
  Authorization = "Bearer $env:API_ACCESS_TOKEN"
  "Content-Type" = "application/json"
}
$body = @{
  model = "Qwen/Qwen2.5-1.5B-Instruct"
  messages = @(@{ role = "user"; content = "Кратко объясни, что такое Kubernetes." })
  max_tokens = 100
} | ConvertTo-Json -Depth 6

Invoke-RestMethod -Method Post -Uri http://localhost:8000/v1/chat/completions `
  -Headers $headers -Body $body
```

## 6. Проверка приватности логов

```powershell
kubectl -n llm-inference logs deployment/vllm-cpu
```

Проверьте, что запросы обслуживаются, но prompt и текст ответа в логах отсутствуют.
Флаг `--disable-log-requests` отключает request logging vLLM. Не включайте DEBUG
и не добавляйте middleware, печатающий тела HTTP-запросов/ответов.

## 7. Изменение конфигурации без пересборки

Отредактируйте `k8s/configmap.yaml`, затем:

```powershell
kubectl apply -f k8s/configmap.yaml
kubectl -n llm-inference rollout restart deployment/vllm-cpu
```

Переменные окружения из ConfigMap применяются при создании нового контейнера.

## 8. Повторный запуск и кэш

При первом старте `download_model.py` скачивает модель в PVC и создаёт
`.download_complete`. При последующих стартах скрипт обнаруживает маркер и
использует локальные веса. Удаление PVC удалит и кэш модели.

## 9. Удаление ресурсов

```powershell
kubectl delete namespace llm-inference
minikube stop
```

## Примечания и ограничения

- В текущей реализации скачивание выполняется entrypoint основного контейнера;
  перенос в отдельный initContainer относится к бонусному заданию и не сделан.
- Нагрузочные тесты и таблица TTFT/Latency/Throughput относятся к бонусному заданию
  и не выполнялись.
- Для CPU backend доступность конкретной модели и подходящий dtype зависят от
  версии runtime и CPU-инструкций. Если загрузка модели выдаёт ошибку kernel/dtype,
  проверьте официальную CPU installation guide.
- Для реального production-развёртывания дополнительно настройте NetworkPolicy,
  TLS/Ingress, внешнее управление секретами и image digest pinning.
