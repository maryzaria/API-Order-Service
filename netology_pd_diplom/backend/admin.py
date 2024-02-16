from django.contrib import admin
from django.contrib.auth.admin import UserAdmin

from backend.models import (
    Category,
    ConfirmEmailToken,
    Contact,
    Order,
    OrderItem,
    Parameter,
    Product,
    ProductInfo,
    ProductParameter,
    Shop,
    User,
)


class ProductInline(admin.TabularInline):
    model = Product
    extra = 1


class ProductParameterInline(admin.TabularInline):
    model = ProductParameter
    extra = 1


class OrderItemInline(admin.TabularInline):
    model = OrderItem
    extra = 1


@admin.register(User)
class CustomUserAdmin(UserAdmin):
    """
    Панель управления пользователями
    """

    model = User

    fieldsets = (
        (None, {"fields": ("email", "password", "type")}),
        (
            "Personal info",
            {"fields": ("first_name", "last_name", "company", "position")},
        ),
        (
            "Permissions",
            {
                "fields": (
                    "is_active",
                    "is_staff",
                    "is_superuser",
                    "groups",
                    "user_permissions",
                ),
            },
        ),
        ("Important dates", {"fields": ("last_login", "date_joined")}),
    )
    list_display = ("email", "first_name", "last_name", "is_staff")


@admin.register(Shop)
class ShopAdmin(admin.ModelAdmin):
    fieldsets = (
        (None, {"fields": ("name", "state")}),
        ("Additional Info", {"fields": ("url", "user")}),
    )
    list_display = ("name", "state", "url")
    list_filter = ("name", "state")


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    inlines = [ProductInline]


@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = ("id", "name", "category")
    list_filter = ("id", "name", "category")


@admin.register(ProductInfo)
class ProductInfoAdmin(admin.ModelAdmin):
    fieldsets = (
        (None, {"fields": ("product", "model", "external_id", "quantity")}),
        ("Цены", {"fields": ("price", "price_rrc")}),
    )
    list_display = ("product", "external_id", "price", "price_rrc", "quantity")
    inlines = [ProductParameterInline]


@admin.register(Parameter)
class ParameterAdmin(admin.ModelAdmin):
    list_display = ("name",)


@admin.register(ProductParameter)
class ProductParameterAdmin(admin.ModelAdmin):
    list_display = ("product_info", "parameter", "value")
    list_filter = ("value", "parameter")


@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = ("id", "user", "dt", "state")
    list_filter = ("id", "user", "dt", "state")
    inlines = [OrderItemInline]


@admin.register(OrderItem)
class OrderItemAdmin(admin.ModelAdmin):
    list_display = ("id", "order", "product_info", "quantity")


@admin.register(Contact)
class ContactAdmin(admin.ModelAdmin):
    list_display = ("id", "city", "phone")
    list_filter = ("id", "city")


@admin.register(ConfirmEmailToken)
class ConfirmEmailTokenAdmin(admin.ModelAdmin):
    list_display = (
        "user",
        "key",
        "created_at",
    )
