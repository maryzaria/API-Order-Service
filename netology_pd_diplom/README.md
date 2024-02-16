# API Сервис заказа товаров для розничных сетей

[Документация по запросам в Swagger](https://app.swaggerhub.com/apis/ZARIPOVAMARYM/Diploma/1.0.0) 

[Документация по запросам в PostMan](https://documenter.getpostman.com/view/5037826/SVfJUrSc) 


## Запуск приложения
1. ```docker-compose up -d --build```
2. ```docker-compose exec web python manage.py migrate --noinput  ```
3. ```docker-compose exec web python manage.py collectstatic --no-input --clear  ```

Проверить работоспособность: запрос на ```http://localhost:1337/```
