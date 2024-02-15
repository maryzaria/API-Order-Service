API Сервиса для магазина

[Задание](./reference/diploma_project.md)

[Документация по запросам в PostMan](https://documenter.getpostman.com/view/5037826/SVfJUrSc) 


## Запуск приложения
1. Запускаем контейнер:
```docker-compose up -d --build```
2. Проверяем, запустилась ли база данных и применились ли миграции:
```docker-compose exec web python manage.py migrate --noinput  ```

Должно получиться: Running migrations: No migrations to apply

3. Собираем статические файлы
```docker-compose exec web python manage.py collectstatic --no-input --clear  ```

Проверить работоспособность: запрос на ```http://localhost:1337/```
