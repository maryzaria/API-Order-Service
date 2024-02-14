API Сервиса для магазина

[Задание](./reference/diploma_project.md)

[Документация по запросам в PostMan](https://documenter.getpostman.com/view/5037826/SVfJUrSc) 


## Запуск приложения
1. ```docker-compose -f docker-compose.prod.yml up -d --build```
2. ```docker-compose -f docker-compose.prod.yml exec web python manage.py migrate --noinput  ```
3. ```docker-compose -f docker-compose.prod.yml exec web python manage.py collectstatic --no-input --clear  ```

Проверить работоспособность: запрос на ```http://localhost:1337/```
