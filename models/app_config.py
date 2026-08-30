from pydantic import BaseModel
from sqladmin import ModelView
from sqlalchemy import Column, Integer, String, Boolean
from markupsafe import Markup
from wtforms import Field, StringField
from wtforms.widgets import TextInput, html_params

from models.base import Base


class AppConfig(Base):
    """Key/value application configuration editable from the admin dashboard.

    Values are resolved DB-first with an environment fallback (see
    services/config.py ConfigService). Secret values are masked in the admin UI
    and revealed on demand.
    """
    __tablename__ = 'app_config'

    id = Column(Integer, primary_key=True)
    key = Column(String, unique=True, nullable=False, index=True)
    value = Column(String, nullable=True)
    is_secret = Column(Boolean, default=True, nullable=False)
    description = Column(String, nullable=True)

    def __repr__(self):
        return f"AppConfig[{self.key}]"


class AppConfigDTO(BaseModel):
    id: int | None = None
    key: str | None = None
    value: str | None = None
    is_secret: bool = True
    description: str | None = None


class SecretInput(TextInput):
    """Password-style input with a reveal toggle for masked API keys."""

    def __call__(self, field: Field, **kwargs):
        if field.data and not kwargs.get("type"):
            kwargs["type"] = "password"
        kwargs.setdefault("class", "form-control")
        base = super().__call__(field, **kwargs)
        toggle = (
            '<button type="button" class="btn btn-outline-secondary btn-sm ms-1 btn-toggle-secret" '
            'data-target="%s">Show</button>'
            '<script>'
            'document.addEventListener("click", function(e){'
            '  var b=e.target.closest(".btn-toggle-secret");'
            '  if(!b)return;'
            '  var inp=document.getElementById(b.dataset.target);'
            '  if(inp){ var pw=inp.type==="password"; inp.type=pw?"text":"password"; '
            'b.textContent=pw?"Hide":"Show"; }'
            '});'
            '</script>'
        ) % field.id
        return Markup(base) + Markup(toggle)


class SecretField(StringField):
    widget = SecretInput()


def _mask(value: str | None) -> str:
    if not value:
        return ""
    if len(value) <= 6:
        return value[0] + "****"
    return value[:3] + "***" + value[-4:]


def _value_formatter(model, attribute):
    value = getattr(model, "value", None)
    if model.is_secret:
        return _mask(value)
    return value


class AppConfigAdmin(ModelView, model=AppConfig):
    name = "Bot Settings"
    name_plural = "Bot Settings"
    icon = "fa-solid fa-gear"
    category = "Settings"

    page_size = 100
    page_size_options = [25, 50, 100, 200, 500]
    column_searchable_list = [AppConfig.key]
    column_list = [AppConfig.key, AppConfig.value, AppConfig.is_secret, AppConfig.description]
    column_labels = {
        AppConfig.key: "Key",
        AppConfig.value: "Value",
        AppConfig.is_secret: "Secret",
        AppConfig.description: "Description",
    }
    column_details_exclude_list = [AppConfig.description]
    column_sortable_list = [AppConfig.key]

    form_columns = ["key", "value", "is_secret", "description"]
    form_overrides = {"value": SecretField}

    column_formatters = {AppConfig.value: _value_formatter}

    can_delete = False
    can_create = True
    can_edit = True
    can_export = False
