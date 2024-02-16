import pytest
from django.urls import reverse
from model_bakery import baker
from rest_framework.authtoken.models import Token
from rest_framework.test import APIClient


@pytest.fixture
def client():
    return APIClient()


@pytest.fixture
def user(db, client, django_user_model):
    data = {"username": "user1", "email": "test_email@mail.ru", "password": "test1234"}
    user = django_user_model.objects.create_user(**data)
    client.force_login(user)
    return user


@pytest.fixture
def token(db, client, user):
    Token.objects.create(user=user)
    token = Token.objects.get(user=user)
    return token


@pytest.fixture
def auth_client(db, client, user, token):
    client.force_authenticate(user=user, token=token)
    return client


@pytest.fixture
def partner(db, client, django_user_model):
    data = {
        "email": "partner_email@mail.ru",
        "password": "partner_pass",
        "type": "shop",
    }
    partner = django_user_model.objects.create_user(**data)
    client.force_login(partner)
    return partner


@pytest.fixture
def partner_token(db, client, partner):
    Token.objects.create(user=partner)
    token_partner = Token.objects.get(user=partner)
    return token_partner


@pytest.fixture
def auth_partner(db, client, partner, partner_token):
    client.force_authenticate(user=partner, token=partner_token)
    return client


@pytest.fixture
def shop_factory(partner):
    def factory(**kwargs):
        return baker.make("Shop", user=partner, **kwargs)

    return factory


@pytest.fixture
def order_factory():
    def factory(**kwargs):
        return baker.make("Order", **kwargs)

    return factory


@pytest.fixture
def category_factory():
    def factory(**kwargs):
        return baker.make("Category", **kwargs)

    return factory


@pytest.fixture
def product_info_factory():
    def factory(**kwargs):
        category = baker.make("Category", **kwargs)
        product = baker.make("Product", category_id=category.id, **kwargs)
        shop = baker.make("Shop", **kwargs)
        return baker.make(
            "ProductInfo", product_id=product.id, shop_id=shop.id, **kwargs
        )

    return factory


@pytest.mark.django_db
def test_get_basket(user, auth_client, order_factory):
    order_factory(make_m2m=True, user=user)
    url = reverse("backend:basket")
    response = auth_client.get(url)
    assert response.status_code == 200


@pytest.mark.django_db
def test_get_categories(client):
    url = reverse("backend:categories")
    response = client.get(url)
    assert response.status_code == 200


@pytest.mark.django_db
def test_add_into_basket(user, auth_client, order_factory, product_info_factory):
    product = product_info_factory(make_m2m=True)
    order_factory(make_m2m=True, user=user)
    url = reverse("backend:basket")
    response = auth_client.post(url, [{"product_info": product.id, "quantity": "1"}])
    assert response.status_code == 201
    response_json = response.json()
    assert response_json["Status"] is True


@pytest.mark.django_db
def test_get_partner_status(auth_partner, shop_factory):
    url = reverse("backend:partner-state")
    shop_factory()
    response = auth_partner.get(url)
    assert response.status_code == 200


@pytest.mark.django_db
def test_partner_update_status(auth_partner):
    url = reverse("backend:partner-state")
    response = auth_partner.post(url, {"state": True})
    assert response.status_code == 201
    assert response.json() == {"Status": True}


@pytest.mark.django_db
def test_get_shop(client, shop_factory):
    url = reverse("backend:shops")
    response = client.get(url)
    assert response.status_code == 200
