from flask import jsonify, render_template
from flask_wtf import FlaskForm
from wtforms import StringField, TextAreaField, SubmitField
from wtforms.validators import DataRequired, Length, Optional, Regexp
from flask_limiter import RateLimitExceeded
from flask_limiter.util import get_remote_address
from src.automated_emails import AutomatedEmails
from src.limiter import limiter
from src.util.rcon_client import RconClient, RconError, DEF_CRED_PATH
import json
import requests

ADMIN_EMAIL = "alice@araxia.xyz"
MOJANG_PROFILE_URL = "https://api.mojang.com/users/profiles/minecraft/{}"
DEFAULT_GROUP = "player"

# The username is interpolated into a console command, so it must stay strictly alphanumeric/underscore.
MC_USERNAME_PATTERN = r"^[A-Za-z0-9_]{3,16}$"
DISCORD_PATTERN = r"^[A-Za-z0-9_.]{2,32}(#\d{4})?$"


class MinecraftRegisterForm(FlaskForm):
    mc_username = StringField(
        "MC Username",
        validators=[
            DataRequired(),
            Regexp(MC_USERNAME_PATTERN, message="3-16 characters: letters, numbers and underscores."),
        ],
        render_kw={"placeholder": "Your Minecraft Java username", "maxlength": 16},
    )
    discord = StringField(
        "Discord",
        validators=[
            DataRequired(),
            Regexp(DISCORD_PATTERN, message="Enter a valid Discord username."),
        ],
        render_kw={"placeholder": "Your Discord username", "maxlength": 37},
    )
    message = TextAreaField(
        "Message",
        validators=[Optional(), Length(max=500)],
        render_kw={"placeholder": "Optional - who invited you, etc.", "rows": 4, "maxlength": 500},
    )
    submit = SubmitField("Register")


class MinecraftRegistration:
    def __init__(self, log):
        self.log = log
        try:
            with DEF_CRED_PATH.open("r") as f:
                config = json.load(f)
        except (OSError, ValueError) as e:
            self.log.error(f"Could not load Minecraft RCON config {DEF_CRED_PATH}: {e}")
            config = {}
        self.group = config.get("group", DEFAULT_GROUP)
        # Disable for offline-mode servers, where names don't map to Mojang accounts
        self.check_mojang = config.get("check_mojang", True)

    def render_form(self, form=None):
        if not form:
            form = MinecraftRegisterForm()
        return render_template("minecraft/register.html", form=form)

    def process_registration(self):
        form = MinecraftRegisterForm()
        if not form.validate_on_submit():
            return jsonify({"status": "error", "html": self.render_form(form)})

        try:
            with limiter.limit("5 per hour"):
                pass
        except RateLimitExceeded:
            self.log.warning(f"Minecraft registration rate limit exceeded for {get_remote_address()}")
            return jsonify({"status": "error", "message": "Too many registrations. Please try again later."}), 429

        username = form.mc_username.data.strip()
        discord = form.discord.data.strip()
        message = (form.message.data or "").strip()

        if self.check_mojang:
            try:
                canonical_name = self.lookup_mojang_name(username)
            except requests.RequestException as e:
                # Don't block registration on a Mojang outage; LuckPerms will resolve the name itself
                self.log.warning(f"Mojang lookup failed for {username}, continuing: {e}")
                canonical_name = username
            if not canonical_name:
                form.mc_username.errors.append("No Minecraft account exists with that username.")
                return jsonify({"status": "error", "html": self.render_form(form)})
            username = canonical_name

        command = f"lp user {username} parent add {self.group}"
        try:
            with RconClient.from_config() as rcon:
                rcon_response = rcon.command(command)
            applied = True
            rcon_result = f"OK - response: {rcon_response or '(empty - LuckPerms replies asynchronously)'}"
            self.log.info(f"Added Minecraft user {username} to group {self.group} via RCON")
        except (RconError, OSError, KeyError, ValueError) as e:
            applied = False
            rcon_result = f"FAILED - {e}\nRun manually: {command}"
            self.log.error(f"RCON command failed for Minecraft user {username}: {e}")

        self.send_admin_email(username, discord, message, applied, rcon_result)

        if applied:
            return jsonify({
                "status": "success",
                "message": f"{username} has been added to the {self.group} group. See you in game!",
            })
        return jsonify({
            "status": "pending",
            "message": "The Minecraft server couldn't be reached right now. Your request has been sent to the admin and will be applied manually.",
        })

    def lookup_mojang_name(self, username):
        """Return the correctly-cased Mojang account name, or None if no account exists."""
        response = requests.get(MOJANG_PROFILE_URL.format(username), timeout=5)
        if response.status_code in (204, 404):
            return None
        response.raise_for_status()
        return response.json().get("name", username)

    def send_admin_email(self, username, discord, message, applied, rcon_result):
        status = "Applied" if applied else "NEEDS MANUAL ACTION"
        body = f"""New Minecraft registration ({status})

Minecraft username: {username}
Discord: {discord}
IP: {get_remote_address()}

Message:
{message or '(none)'}

RCON: {rcon_result}
"""
        try:
            AutomatedEmails().send_email(
                from_name="Alice",
                to_email=[ADMIN_EMAIL],
                subject=f"Minecraft registration: {username} [{status}]",
                body=body,
            )
        except Exception as e:
            self.log.error(f"Failed to send Minecraft registration email for {username}: {e}")
