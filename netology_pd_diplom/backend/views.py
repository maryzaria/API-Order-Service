from django.shortcuts import render, redirect

from backend.models import (
    Category,
    ConfirmEmailToken,
    Contact,
    Order,
    OrderItem,
    ProductInfo,
    Shop,
)
from backend.permissions import IsOwner, IsShop
from backend.serializers import (
    AddContactSerializer,
    CategorySerializer,
    ConfirmAccountSerializer,
    ContactSerializer,
    LoginAccountSerializer,
    OrderFromBasketSerializer,
    OrderItemSerializer,
    OrderSerializer,
    ProductInfoSerializer,
    ShopSerializer,
    UserSerializer,
)
from django.contrib.auth import authenticate
from django.core.exceptions import PermissionDenied
from django.db import IntegrityError
from django.db.models import F, Q, Sum
from django.http import JsonResponse
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import (
    OpenApiParameter,
    OpenApiResponse,
    extend_schema,
    inline_serializer,
)
from rest_framework import serializers as s
from rest_framework import status
from rest_framework.authtoken.models import Token
from rest_framework.generics import ListAPIView
from rest_framework.permissions import IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.throttling import AnonRateThrottle, UserRateThrottle
from rest_framework.views import APIView

from .tasks import do_import, new_order, new_user_registered
from .utils import check_password


def auth(request):
    return render(request, "oauth.html")


def index(request):
    return redirect("openapi")


class RegisterAccount(APIView):
    """Регистрация покупателей"""

    @extend_schema(
        request=UserSerializer,
        responses={
            (201, "application/json"): OpenApiResponse(
                description="Success",
                response=inline_serializer(
                    name="user_register",
                    fields={"status": s.BooleanField()},
                ),
            ),
            400: OpenApiResponse(
                description="Не указаны все необходимые аргументы, либо они некорректны"
            ),
            403: OpenApiResponse(description="Учетные данные не были предоставлены"),
        },
    )
    def post(self, request, *args, **kwargs):
        """
        Process a POST request and create a new user.

        Args:
            request (Request): The Django request object.

        Returns:
            JsonResponse: The response indicating the status of the operation and any errors.
        """
        # проверяем обязательные аргументы
        if {
            "first_name",
            "last_name",
            "email",
            "password",
            "company",
            "position",
        }.issubset(request.data):

            # проверяем пароль на сложность
            check, error_array = check_password(request)
            if not check:
                return JsonResponse(
                    {"Status": False, "Errors": {"password": error_array}},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            else:
                # проверяем данные для уникальности имени пользователя
                user_serializer = UserSerializer(data=request.data)
                if user_serializer.is_valid():
                    # сохраняем пользователя
                    user = user_serializer.save()
                    user.set_password(request.data["password"])
                    user.save()
                    new_user_registered.delay(instance=request.user, created=True)
                    return JsonResponse(
                        {"Status": True}, status=status.HTTP_201_CREATED
                    )
                else:
                    return JsonResponse(
                        {"Status": False, "Errors": user_serializer.errors},
                        status=status.HTTP_400_BAD_REQUEST,
                    )

        return JsonResponse(
            {"Status": False, "Errors": "Не указаны все необходимые аргументы"},
            status=status.HTTP_400_BAD_REQUEST,
        )


class ConfirmAccount(APIView):
    """
    Класс для подтверждения почтового адреса
    """

    throttle_classes = (AnonRateThrottle,)

    # Регистрация методом POST
    @extend_schema(
        request=ConfirmAccountSerializer,
        responses={
            (200, "application/json"): OpenApiResponse(
                description="Success",
                response=inline_serializer(
                    name="confirm_account",
                    fields={"status": s.BooleanField()},
                ),
            ),
            400: OpenApiResponse(
                description="Не указаны все необходимые аргументы, либо они некорректны"
            ),
            403: OpenApiResponse(description="Учетные данные не были предоставлены"),
        },
    )
    def post(self, request, *args, **kwargs):
        """
        Подтверждает почтовый адрес пользователя.

        Args:
        - request (Request): The Django request object.

        Returns:
        - JsonResponse: The response indicating the status of the operation and any errors.
        """
        # проверяем обязательные аргументы
        if {"email", "token"}.issubset(request.data):

            token = ConfirmEmailToken.objects.filter(
                user__email=request.data["email"], key=request.data["token"]
            ).first()
            if token:
                token.user.is_active = True
                token.user.save()
                token.delete()
                return JsonResponse({"Status": True}, status=status.HTTP_200_OK)
            else:
                return JsonResponse(
                    {"Status": False, "Errors": "Неправильно указан токен или email"},
                    status=status.HTTP_400_BAD_REQUEST,
                )

        return JsonResponse(
            {"Status": False, "Errors": "Не указаны все необходимые аргументы"},
            status=status.HTTP_400_BAD_REQUEST,
        )


class AccountDetails(APIView):
    """
    A class for managing user account details.

    Methods:
    - get: Retrieve the details of the authenticated user.
    - post: Update the account details of the authenticated user.

    Attributes:
    - None
    """

    permission_classes = (IsAuthenticated, IsOwner)
    throttle_classes = (UserRateThrottle,)

    # получить данные
    @extend_schema(
        responses={
            (200, "application/json"): UserSerializer,
            403: OpenApiResponse(description="Учетные данные не были предоставлены"),
        }
    )
    def get(self, request: Request, *args, **kwargs):
        """
        Retrieve the details of the authenticated user.

        Args:
        - request (Request): The Django request object.

        Returns:
        - Response: The response containing the details of the authenticated user.
        """

        serializer = UserSerializer(request.user)
        return Response(serializer.data, status=status.HTTP_200_OK)

    # Редактирование методом POST
    @extend_schema(
        request=UserSerializer,
        responses={
            (200, "application/json"): OpenApiResponse(
                description="Success",
                response=inline_serializer(
                    name="account_details",
                    fields={"status": s.BooleanField()},
                ),
            ),
            400: OpenApiResponse(description="Некорректные данные"),
            403: OpenApiResponse(description="Учетные данные не были предоставлены"),
        },
    )
    def post(self, request, *args, **kwargs):
        """
        Update the account details of the authenticated user.

        Args:
        - request (Request): The Django request object.

        Returns:
        - JsonResponse: The response indicating the status of the operation and any errors.
        """

        if "password" in request.data:
            # проверяем пароль на сложность
            check, error_array = check_password(request)
            if not check:
                return JsonResponse(
                    {"Status": False, "Errors": {"password": error_array}},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            else:
                request.user.set_password(request.data["password"])

        # проверяем остальные данные
        user_serializer = UserSerializer(request.user, data=request.data, partial=True)
        if user_serializer.is_valid():
            user_serializer.save()
            return JsonResponse({"Status": True}, status=status.HTTP_200_OK)
        else:
            return JsonResponse(
                {"Status": False, "Errors": user_serializer.errors},
                status=status.HTTP_400_BAD_REQUEST,
            )


class LoginAccount(APIView):
    """
    Класс для авторизации пользователей
    """

    throttle_classes = (AnonRateThrottle,)

    # Авторизация методом POST
    @extend_schema(
        request=LoginAccountSerializer,
        responses={
            (200, "application/json"): OpenApiResponse(
                description="Success",
                response=inline_serializer(
                    name="login_account",
                    fields={
                        "Status": s.BooleanField(),
                        "Token": s.CharField(max_length=200),
                    },
                ),
            ),
            400: OpenApiResponse(description="Некорректные данные"),
        },
    )
    def post(self, request, *args, **kwargs):
        """
        Authenticate a user.

        Args:
            request (Request): The Django request object.

        Returns:
            JsonResponse: The response indicating the status of the operation and any errors.
        """
        if {"email", "password"}.issubset(request.data):
            user = authenticate(
                request,
                username=request.data["email"],
                password=request.data["password"],
            )

            if user is not None:
                if user.is_active:
                    token, _ = Token.objects.get_or_create(user=user)

                    return JsonResponse(
                        {"Status": True, "Token": token.key}, status=status.HTTP_200_OK
                    )

            return JsonResponse(
                {"Status": False, "Errors": "Не удалось авторизовать"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        return JsonResponse(
            {"Status": False, "Errors": "Не указаны все необходимые аргументы"},
            status=status.HTTP_400_BAD_REQUEST,
        )


class CategoryView(ListAPIView):
    """
    Класс для просмотра категорий
    """

    queryset = Category.objects.all()
    serializer_class = CategorySerializer
    throttle_classes = (AnonRateThrottle,)


class ShopView(ListAPIView):
    """
    Класс для просмотра списка магазинов
    """

    queryset = Shop.objects.filter(state=True)
    serializer_class = ShopSerializer
    throttle_classes = (AnonRateThrottle,)


class ProductInfoView(APIView):
    """
    A class for searching products.

    Methods:
    - get: Retrieve the product information based on the specified filters.

    Attributes:
    - None
    """

    throttle_classes = (AnonRateThrottle,)

    @extend_schema(
        parameters=[
            OpenApiParameter(
                "shop_id",
                type=OpenApiTypes.INT,
                location=OpenApiParameter.QUERY,
                description="Enter shop_id",
            ),
            OpenApiParameter(
                "category_id",
                type=OpenApiTypes.INT,
                location=OpenApiParameter.QUERY,
                description="Enter category_id",
            ),
        ],
        responses={
            (200, "application/json"): ProductInfoSerializer(many=True),
        },
    )
    def get(self, request: Request, *args, **kwargs):
        """
        Retrieve the product information based on the specified filters.

        Args:
        - request (Request): The Django request object.

        Returns:
        - Response: The response containing the product information.
        """
        query = Q(shop__state=True)
        shop_id = request.query_params.get("shop_id")
        category_id = request.query_params.get("category_id")

        if shop_id:
            query = query & Q(shop_id=shop_id)

        if category_id:
            query = query & Q(product__category_id=category_id)

        # фильтруем и отбрасываем дубликаты
        queryset = (
            ProductInfo.objects.filter(query)
            .select_related("shop", "product__category")
            .prefetch_related("product_parameters__parameter")
            .distinct()
        )

        serializer = ProductInfoSerializer(queryset, many=True)

        return Response(serializer.data, status=status.HTTP_200_OK)


class BasketView(APIView):
    """
    A class for managing the user's shopping basket.

    Methods:
    - get: Retrieve the items in the user's basket.
    - post: Add an item to the user's basket.
    - put: Update the quantity of an item in the user's basket.
    - delete: Remove an item from the user's basket.

    Attributes:
    - None
    """

    permission_classes = (IsAuthenticated,)
    throttle_classes = (UserRateThrottle,)

    # получить корзину
    @extend_schema(
        responses={
            (200, "application/json"): OrderSerializer(many=True),
            403: OpenApiResponse(description="Учетные данные не были предоставлены"),
        }
    )
    def get(self, request, *args, **kwargs):
        """
        Retrieve the items in the user's basket.

        Args:
        - request (Request): The Django request object.

        Returns:
        - Response: The response containing the items in the user's basket.
        """

        basket = (
            Order.objects.filter(user_id=request.user.id, state="basket")
            .prefetch_related(
                "ordered_items__product_info__product__category",
                "ordered_items__product_info__product_parameters__parameter",
            )
            .annotate(
                total_sum=Sum(
                    F("ordered_items__quantity")
                    * F("ordered_items__product_info__price")
                )
            )
            .distinct()
        )

        serializer = OrderSerializer(basket, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)

    # редактировать корзину
    @extend_schema(
        request=OrderItemSerializer(many=True),
        responses={
            (201, "application/json"): OpenApiResponse(
                description="Success",
                response=inline_serializer(
                    name="basket_post",
                    fields={
                        "Status": s.BooleanField(),
                        "Создано объектов": s.IntegerField(),
                    },
                ),
            ),
            400: OpenApiResponse(description="Некорректные данные"),
            403: OpenApiResponse(description="Учетные данные не были предоставлены"),
        },
    )
    def post(self, request, *args, **kwargs):
        """
        Add an items to the user's basket.

        Args:
        - request (Request): The Django request object.

        Returns:
        - JsonResponse: The response indicating the status of the operation and any errors.
        """
        try:
            items_list = request.data
            if items_list:
                basket, _ = Order.objects.get_or_create(
                    user_id=request.user.id, state="basket"
                )
                objects_created = 0
                for order_item in items_list:
                    order_item.update({"order": basket.id})
                    serializer = OrderItemSerializer(data=order_item)
                    if serializer.is_valid():
                        try:
                            serializer.save()
                        except IntegrityError as error:
                            return JsonResponse(
                                {"Status": False, "Errors": str(error)},
                                status=status.HTTP_400_BAD_REQUEST,
                            )
                        else:
                            objects_created += 1
                    else:
                        return JsonResponse(
                            {"Status": False, "Errors": serializer.errors},
                            status=status.HTTP_400_BAD_REQUEST,
                        )

                return JsonResponse(
                    {"Status": True, "Создано объектов": objects_created},
                    status=status.HTTP_201_CREATED,
                )
            return JsonResponse(
                {"Status": False, "Errors": "Не указаны все необходимые аргументы"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        except (ValueError, TypeError):
            return JsonResponse(
                {"Status": False, "Errors": "Неверный формат запроса"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        except PermissionDenied as err:
            return JsonResponse(
                {"Status": False, "Error": err},
                status=status.HTTP_403_FORBIDDEN,
            )
        except Exception as err:
            return JsonResponse(
                {"Status": False, "Error": str(err)}, status=status.HTTP_400_BAD_REQUEST
            )

    # удалить товары из корзины
    @extend_schema(
        parameters=[
            OpenApiParameter(
                "items_id",
                type=OpenApiTypes.INT,
                location=OpenApiParameter.QUERY,
                description="перечислите id через запятую",
            ),
        ],
        responses={
            (201, "application/json"): OpenApiResponse(
                description="Success",
                response=inline_serializer(
                    name="basket_delete",
                    fields={
                        "Status": s.BooleanField(),
                        "Удалено объектов": s.IntegerField(),
                    },
                ),
            ),
            400: OpenApiResponse(description="Некорректные данные"),
            403: OpenApiResponse(description="Учетные данные не были предоставлены"),
        },
    )
    def delete(self, request, *args, **kwargs):
        """
        Remove  items from the user's basket.

        Args:
        - request (Request): The Django request object.

        Returns:
        - JsonResponse: The response indicating the status of the operation and any errors.
        """
        try:
            items_sting = request.query_params.get("items_id")
            if items_sting:
                items_list = items_sting.split(",")
                basket, _ = Order.objects.get_or_create(
                    user_id=request.user.id, state="basket"
                )
                query = Q()
                objects_deleted = False
                for order_item_id in items_list:
                    if order_item_id.isdigit():
                        query = query | Q(order_id=basket.id, id=order_item_id)
                        objects_deleted = True

                if objects_deleted:
                    deleted_count = OrderItem.objects.filter(query).delete()[0]
                    return JsonResponse(
                        {"Status": True, "Удалено объектов": deleted_count},
                        status=status.HTTP_200_OK,
                    )
            return JsonResponse(
                {"Status": False, "Errors": "Не указаны все необходимые аргументы"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        except PermissionDenied as err:
            return JsonResponse(
                {"Status": False, "Error": err},
                status=status.HTTP_403_FORBIDDEN,
            )
        except Exception as err:
            return JsonResponse(
                {"Status": False, "Error": str(err)}, status=status.HTTP_400_BAD_REQUEST
            )

    # добавить позиции в корзину
    @extend_schema(
        request=OrderItemSerializer(many=True),
        responses={
            (201, "application/json"): OpenApiResponse(
                description="Success",
                response=inline_serializer(
                    name="basket_update",
                    fields={
                        "Status": s.BooleanField(),
                        "Обновлено объектов": s.IntegerField(),
                    },
                ),
            ),
            400: OpenApiResponse(description="Некорректные данные"),
            403: OpenApiResponse(description="Учетные данные не были предоставлены"),
        },
    )
    def put(self, request, *args, **kwargs):
        """
        Update the items in the user's basket.

        Args:
        - request (Request): The Django request object.

        Returns:
        - JsonResponse: The response indicating the status of the operation and any errors.
        """
        try:
            items_list = request.data
            if items_list:
                basket, _ = Order.objects.get_or_create(
                    user_id=request.user.id, state="basket"
                )
                objects_updated = 0
                for order_item in items_list:
                    if (
                        type(order_item["id"]) == int
                        and type(order_item["quantity"]) == int
                    ):
                        objects_updated += OrderItem.objects.filter(
                            order_id=basket.id, id=order_item["id"]
                        ).update(quantity=order_item["quantity"])

                return JsonResponse(
                    {"Status": True, "Обновлено объектов": objects_updated},
                    status=status.HTTP_200_OK,
                )
            return JsonResponse(
                {"Status": False, "Errors": "Не указаны все необходимые аргументы"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        except (ValueError, TypeError):
            return JsonResponse(
                {"Status": False, "Errors": "Неверный формат запроса"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        except PermissionDenied as err:
            return JsonResponse(
                {"Status": False, "Error": err},
                status=status.HTTP_403_FORBIDDEN,
            )
        except Exception as err:
            return JsonResponse(
                {"Status": False, "Error": str(err)}, status=status.HTTP_400_BAD_REQUEST
            )


class PartnerUpdate(APIView):
    """
    A class for updating partner information.

    Methods:
    - post: Update the partner information.

    Attributes:
    - None
    """

    permission_classes = (IsAuthenticated, IsShop)
    throttle_classes = (UserRateThrottle,)

    @extend_schema(
        parameters=[
            OpenApiParameter(
                "url",
                type=OpenApiTypes.INT,
                location=OpenApiParameter.QUERY,
                description="Укажите url с информацией",
                required=True,
            ),
        ],
        responses={
            (200, "application/json"): OpenApiResponse(
                description="Success",
                response=inline_serializer(
                    name="partner_update",
                    fields={"status": s.BooleanField()},
                ),
            ),
            400: OpenApiResponse(
                description="Не указаны все необходимые аргументы, либо они некорректны"
            ),
            403: OpenApiResponse(description="Учетные данные не были предоставлены"),
        },
    )
    def post(self, request, *args, **kwargs):
        """
        Update the partner price list information.

        Args:
        - request (Request): The Django request object.

        Returns:
        - JsonResponse: The response indicating the status of the operation and any errors.
        """

        url = request.query_params.get("url")
        if url:
            try:
                do_import.delay(url, request.user.id)
                return JsonResponse({"Status": True}, status=status.HTTP_200_OK)
            except Exception as error:
                return JsonResponse({"Status": False, "Error": str(error)})
        return JsonResponse(
            {"Status": False, "Errors": "Не указан url"},
            status=status.HTTP_400_BAD_REQUEST,
        )


class PartnerState(APIView):
    """
    A class for managing partner state.

    Methods:
    - get: Retrieve the state of the partner.

    Attributes:
    - None
    """

    permission_classes = (IsAuthenticated, IsShop)
    throttle_classes = (UserRateThrottle,)

    # получить текущий статус
    @extend_schema(
        responses={
            (200, "application/json"): ShopSerializer,
            403: OpenApiResponse(description="Учетные данные не были предоставлены"),
        },
    )
    def get(self, request, *args, **kwargs):
        """
        Retrieve the state of the partner.

        Args:
        - request (Request): The Django request object.

        Returns:
        - Response: The response containing the state of the partner.
        """
        # shop = request.user.shop
        shop = Shop.objects.get(user=request.user)
        serializer = ShopSerializer(shop)
        return Response(serializer.data, status=status.HTTP_200_OK)

    # изменить текущий статус
    @extend_schema(
        parameters=[
            OpenApiParameter(
                "state",
                type=OpenApiTypes.BOOL,
                location=OpenApiParameter.QUERY,
                description="Укажите новый статус",
                required=True,
            ),
        ],
        responses={
            (201, "application/json"): OpenApiResponse(
                description="Success",
                response=inline_serializer(
                    name="change_partner_state",
                    fields={"status": s.BooleanField()},
                ),
            ),
            400: OpenApiResponse(
                description="Не указаны все необходимые аргументы, либо они некорректны"
            ),
            403: OpenApiResponse(description="Учетные данные не были предоставлены"),
        },
    )
    def post(self, request, *args, **kwargs):
        """
        Update the state of a partner.

        Args:
        - request (Request): The Django request object.

        Returns:
        - JsonResponse: The response indicating the status of the operation and any errors.
        """

        state = request.query_params.get("state")
        state = state if state else request.data.get("state")
        if state:
            try:
                Shop.objects.filter(user_id=request.user.id).update(state=state)
                return JsonResponse({"Status": True}, status=status.HTTP_201_CREATED)

            except ValueError as error:
                return JsonResponse(
                    {"Status": False, "Errors": str(error)},
                    status=status.HTTP_400_BAD_REQUEST,
                )

        return JsonResponse(
            {"Status": False, "Errors": "Не указаны все необходимые аргументы"},
            status=status.HTTP_400_BAD_REQUEST,
        )


class PartnerOrders(APIView):
    """
    Класс для получения заказов поставщиками
     Methods:
    - get: Retrieve the orders associated with the authenticated partner.

    Attributes:
    - None
    """

    permission_classes = (IsAuthenticated, IsShop)
    throttle_classes = (UserRateThrottle,)

    @extend_schema(
        responses={
            (200, "application/json"): OrderSerializer(many=True),
            403: OpenApiResponse(description="Учетные данные не были предоставлены"),
        },
    )
    def get(self, request, *args, **kwargs):
        """
        Retrieve the orders associated with the authenticated partner.

        Args:
        - request (Request): The Django request object.

        Returns:
        - Response: The response containing the orders associated with the partner.
        """

        order = (
            Order.objects.filter(
                ordered_items__product_info__shop__user_id=request.user.id
            )
            .exclude(state="basket")
            .prefetch_related(
                "ordered_items__product_info__product__category",
                "ordered_items__product_info__product_parameters__parameter",
            )
            .select_related("contact")
            .annotate(
                total_sum=Sum(
                    F("ordered_items__quantity")
                    * F("ordered_items__product_info__price")
                )
            )
            .distinct()
        )

        serializer = OrderSerializer(order, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)


class ContactView(APIView):
    """
    A class for managing contact information.

    Methods:
    - get: Retrieve the contact information of the authenticated user.
    - post: Create a new contact for the authenticated user.
    - put: Update the contact information of the authenticated user.
    - delete: Delete the contact of the authenticated user.

    Attributes:
    - None
    """

    permission_classes = (IsAuthenticated,)
    throttle_classes = (UserRateThrottle,)

    # получить мои контакты
    @extend_schema(
        responses={
            (200, "application/json"): ContactSerializer(many=True),
            403: OpenApiResponse(description="Учетные данные не были предоставлены"),
        },
    )
    def get(self, request, *args, **kwargs):
        """
        Retrieve the contact information of the authenticated user.

        Args:
        - request (Request): The Django request object.

        Returns:
        - Response: The response containing the contact information.
        """

        contact = Contact.objects.filter(user_id=request.user.id)
        serializer = ContactSerializer(contact, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)

    # добавить новый контакт
    @extend_schema(
        request=AddContactSerializer,
        responses={
            (201, "application/json"): ContactSerializer(many=True),
            400: OpenApiResponse(description="Предоставлены некорректные данные"),
            403: OpenApiResponse(description="Учетные данные не были предоставлены"),
        },
    )
    def post(self, request, *args, **kwargs):
        """
        Create a new contact for the authenticated user.

        Args:
        - request (Request): The Django request object.

        Returns:
        - JsonResponse: The response indicating the status of the operation and any errors.
        """

        if {"city", "street", "phone"}.issubset(request.data):
            request.data.update({"user": request.user.id})
            serializer = ContactSerializer(data=request.data)

            if serializer.is_valid():
                serializer.save()
                return JsonResponse({"Status": True}, status=status.HTTP_201_CREATED)
            else:
                return JsonResponse(
                    {"Status": False, "Errors": serializer.errors},
                    status=status.HTTP_400_BAD_REQUEST,
                )

        return JsonResponse(
            {"Status": False, "Errors": "Не указаны все необходимые аргументы"},
            status=status.HTTP_400_BAD_REQUEST,
        )

    # удалить контакт
    @extend_schema(
        parameters=[
            OpenApiParameter(
                "items_id",
                type=OpenApiTypes.INT,
                location=OpenApiParameter.QUERY,
                description="перечислите id контактов через запятую",
            ),
        ],
        responses={
            (201, "application/json"): OpenApiResponse(
                description="Success",
                response=inline_serializer(
                    name="contact_delete",
                    fields={
                        "Status": s.BooleanField(),
                        "Удалено объектов": s.IntegerField(),
                    },
                ),
            ),
            400: OpenApiResponse(description="Некорректные данные"),
            403: OpenApiResponse(description="Учетные данные не были предоставлены"),
        },
    )
    def delete(self, request, *args, **kwargs):
        """
        Delete the contact of the authenticated user.

        Args:
        - request (Request): The Django request object.

        Returns:
        - JsonResponse: The response indicating the status of the operation and any errors.
        """

        try:
            items_sting = request.query_params.get("items")
            if items_sting:
                items_list = items_sting.split(",")
                query = Q()
                objects_deleted = False
                for contact_id in items_list:
                    if contact_id.isdigit():
                        query = query | Q(user_id=request.user.id, id=contact_id)
                        objects_deleted = True

                if objects_deleted:
                    deleted_count = Contact.objects.filter(query).delete()[0]
                    return JsonResponse(
                        {"Status": True, "Удалено объектов": deleted_count},
                        status=status.HTTP_200_OK,
                    )
            return JsonResponse(
                {"Status": False, "Errors": "Не указаны все необходимые аргументы"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        except Exception as err:
            return JsonResponse(
                {"Status": False, "Errors": str(err)},
                status=status.HTTP_400_BAD_REQUEST,
            )

    # редактировать контакт
    @extend_schema(
        parameters=[
            OpenApiParameter(
                "contact_id",
                type=OpenApiTypes.INT,
                location=OpenApiParameter.QUERY,
                description="Введите id контакта",
                required=True,
            ),
        ],
        responses={
            (201, "application/json"): OpenApiResponse(
                description="Success",
                response=inline_serializer(
                    name="update_contact",
                    fields={"Status": s.BooleanField()},
                ),
            ),
            400: OpenApiResponse(description="Некорректный contact_id"),
            403: OpenApiResponse(description="Учетные данные не были предоставлены"),
        },
    )
    def put(self, request, *args, **kwargs):
        """
        Update the contact information of the authenticated user.

        Args:
        - request (Request): The Django request object.

        Returns:
        - JsonResponse: The response indicating the status of the operation and any errors.
        """

        contact_id = request.query_params.get("contact_id")
        if contact_id and contact_id.isdigit():
            contact = Contact.objects.filter(
                id=request.data["id"], user_id=request.user.id
            ).first()
            if contact:
                serializer = ContactSerializer(contact, data=request.data, partial=True)
                if serializer.is_valid():
                    serializer.save()
                    return JsonResponse({"Status": True}, status=status.HTTP_200_OK)
                else:
                    return JsonResponse(
                        {"Status": False, "Errors": serializer.errors},
                        status=status.HTTP_400_BAD_REQUEST,
                    )
        return JsonResponse(
            {"Status": False, "Errors": "Неверный contact_id"},
            status=status.HTTP_400_BAD_REQUEST,
        )


class OrderView(APIView):
    """
    Класс для получения и размешения заказов пользователями
    Methods:
    - get: Retrieve the details of a specific order.
    - post: Create a new order.
    - put: Update the details of a specific order.
    - delete: Delete a specific order.

    Attributes:
    - None
    """

    permission_classes = (IsAuthenticated,)
    throttle_classes = (UserRateThrottle,)

    # получить мои заказы
    @extend_schema(
        responses={
            (200, "application/json"): OrderSerializer(many=True),
            403: OpenApiResponse(description="Учетные данные не были предоставлены"),
        }
    )
    def get(self, request, *args, **kwargs):
        """
        Retrieve the details of user orders.

        Args:
        - request (Request): The Django request object.

        Returns:
        - Response: The response containing the details of the order.
        """

        order = (
            Order.objects.filter(user_id=request.user.id)
            .exclude(state="basket")
            .prefetch_related(
                "ordered_items__product_info__product__category",
                "ordered_items__product_info__product_parameters__parameter",
            )
            .select_related("contact")
            .annotate(
                total_sum=Sum(
                    F("ordered_items__quantity")
                    * F("ordered_items__product_info__price")
                )
            )
            .distinct()
        )

        serializer = OrderSerializer(order, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)

    # разместить заказ из корзины
    @extend_schema(
        request=OrderFromBasketSerializer,
        responses={
            (201, "application/json"): OpenApiResponse(
                description="Success",
                response=inline_serializer(
                    name="order_get",
                    fields={"Status": s.BooleanField()},
                ),
            ),
            400: OpenApiResponse(description="Некорректные данные"),
            403: OpenApiResponse(description="Учетные данные не были предоставлены"),
        },
    )
    def post(self, request, *args, **kwargs):
        """
        Put an order and send a notification.

        Args:
        - request (Request): The Django request object.

        Returns:
        - JsonResponse: The response indicating the status of the operation and any errors.
        """

        if {"id", "contact"}.issubset(request.data):
            if request.data["id"].isdigit():
                try:
                    is_updated = Order.objects.filter(
                        user_id=request.user.id, id=request.data["id"]
                    ).update(contact_id=request.data["contact"], state="new")
                except IntegrityError as error:
                    return JsonResponse(
                        {"Status": False, "Errors": "Неправильно указаны аргументы"}
                    )
                else:
                    if is_updated:
                        new_order.delay(user_id=request.user.id)
                        return JsonResponse({"Status": True}, status=status.HTTP_200_OK)

        return JsonResponse(
            {"Status": False, "Errors": "Не указаны все необходимые аргументы"},
            status=status.HTTP_400_BAD_REQUEST,
        )
