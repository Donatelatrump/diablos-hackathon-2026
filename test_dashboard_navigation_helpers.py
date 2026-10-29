"""Drive the same native navigation buttons used by the application."""


def navigate(app, view):
    return next(button for button in app.button if button.key == 'nav-' + view).click()
