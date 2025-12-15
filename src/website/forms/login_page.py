
from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, SubmitField, BooleanField
from wtforms.validators import DataRequired, Length


class LoginForm(FlaskForm):
    username = StringField(
        "Username",
        validators=[DataRequired(), Length(min=3, max=50)],
        render_kw={"placeholder": "Enter your username"},
    )
    password = PasswordField(
        "Password",
        validators=[DataRequired(), Length(min=8, max=50)],
        render_kw={"placeholder": "Enter your password"},
    )
    remember = BooleanField(
        "Remember me:",
        default=False,
        render_kw={"class": "remember-me"},
    )
    submit = SubmitField(label="Login", render_kw={"class": "w98-button"})