# API Сервис заказа товаров для розничных сетей

[Документация по запросам в Swagger](https://app.swaggerhub.com/apis/ZARIPOVAMARYM/Diploma/1.0.0) 

[Документация по запросам в PostMan](https://documenter.getpostman.com/view/5037826/SVfJUrSc)

1. Запускаем контейнер:
```docker-compose up -d --build```
2. Проверяем, запустилась ли база данных и применились ли миграции:
```docker-compose exec web python manage.py migrate --noinput  ```
3. Создаем суперпользователя
```docker-compose exec web python manage.py createsuperuser```

### Проверить работоспособность

Отправить запрос на ```http://localhost:1337/admin/```
Документация: ```http://localhost:1337/openapi/```
