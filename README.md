# API Сервис заказа товаров для розничных сетей

[Задание здесь](./reference/diploma_project.md)
## Запуск приложения
1. Запускаем контейнер:

```docker-compose up -d --build```

Должно получиться:
![started.png](reference/started.png)

1. Проверяем, запустилась ли база данных и применились ли миграции:
   
```docker-compose exec web python manage.py migrate --noinput  ```

Должно получиться:
![migrations.png](reference/migrations.png)

1. Создаем суперпользователя
   
```docker-compose exec web python manage.py createsuperuser```

### Проверить работоспособность

Отправить запрос на ```http://localhost:1337/admin/```

Документация API: ```http://localhost:1337/openapi/```

[Описание документации по запросам в Swagger](https://app.swaggerhub.com/apis/ZARIPOVAMARYM/Diploma/1.0.0) 