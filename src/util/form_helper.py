
def clear_form_errors(form):
    for field in form:
        field.errors.clear()
    return form