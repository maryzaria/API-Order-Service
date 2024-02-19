from django.contrib.auth.password_validation import validate_password


def check_password(request):
    try:
        validate_password(request.data["password"])
        return True, []
    except Exception as password_error:
        error_array = []
        # noinspection PyTypeChecker
        for item in password_error:
            error_array.append(item)
        return False, error_array
