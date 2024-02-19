from celery import shared_task
from django.conf import settings
from django.core.mail import EmailMultiAlternatives

from backend.models import User, ConfirmEmailToken


@shared_task()
def password_reset_token_created(reset_password_token, **kwargs):
    """
    Отправляем письмо с токеном для сброса пароля
    When a token is created, an e-mail needs to be sent to the user
    :param reset_password_token: Token Model Object
    :param kwargs:
    :return:
    """
    # send an e-mail to the user

    msg = EmailMultiAlternatives(
        # title:
        f"Password Reset Token for {reset_password_token.user}",
        # message:
        reset_password_token.key,
        # from:
        settings.EMAIL_HOST_USER,
        # to:
        [reset_password_token.user.email],
    )
    msg.send()


@shared_task()
def new_user_registered(
    instance: User, created: bool, **kwargs
):
    """
    Отправляем письмо для подтверждения почты
    """
    if created and not instance.is_active:
        # send an e-mail to the user
        token, _ = ConfirmEmailToken.objects.get_or_create(user_id=instance.pk)

        msg = EmailMultiAlternatives(
            # title:
            f"Password Reset Token for {instance.email}",
            # message:
            token.key,
            # from:
            settings.EMAIL_HOST_USER,
            # to:
            [instance.email],
        )
        msg.send()


@shared_task()
def new_order(user_id, **kwargs):
    """
    Отправяем письмо при изменении статуса заказа
    """
    # send an e-mail to the user
    user = User.objects.get(id=user_id)

    msg = EmailMultiAlternatives(
        # title:
        f"Обновление статуса заказа",
        # message:
        "Заказ сформирован",
        # from:
        settings.EMAIL_HOST_USER,
        # to:
        [user.email],
    )
    msg.send()