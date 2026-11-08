"""Small presentation helpers shared by FOLDO templates: ``{% load foldo_tags %}``.

The project keeps ``LANGUAGE_CODE = "en-us"`` (tests and Django's built-in
messages depend on it), so Thai dates are formatted here instead of through
the ``date`` filter.
"""

import datetime
from urllib.parse import urlsplit

from django import template
from django.utils import timezone

register = template.Library()

TH_MONTHS = ("ม.ค.", "ก.พ.", "มี.ค.", "เม.ย.", "พ.ค.", "มิ.ย.",
             "ก.ค.", "ส.ค.", "ก.ย.", "ต.ค.", "พ.ย.", "ธ.ค.")


def _local(value):
    if isinstance(value, datetime.datetime) and timezone.is_aware(value):
        return timezone.localtime(value)
    return value


@register.filter
def th_month(value):
    """``date(2022, 8, 1)`` → ``ส.ค. 2022``. Empty for None."""
    if not value:
        return ""
    value = _local(value)
    return f"{TH_MONTHS[value.month - 1]} {value.year}"


@register.filter
def th_date(value, with_time=""):
    """``8 พ.ย. 2026``; ``|th_date:"time"`` adds ``14:05``."""
    if not value:
        return ""
    value = _local(value)
    text = f"{value.day} {TH_MONTHS[value.month - 1]} {value.year}"
    if with_time and isinstance(value, datetime.datetime):
        text += f" {value:%H:%M}"
    return text


@register.filter
def ago(value):
    """Relative time in Thai: เมื่อสักครู่ / 5 นาทีที่แล้ว / 3 ชม.ที่แล้ว / 2 วันที่แล้ว."""
    if not value:
        return ""
    seconds = (timezone.now() - value).total_seconds()
    if seconds < 60:
        return "เมื่อสักครู่"
    if seconds < 3600:
        return f"{int(seconds // 60)} นาทีที่แล้ว"
    if seconds < 86400:
        return f"{int(seconds // 3600)} ชม.ที่แล้ว"
    if seconds < 86400 * 7:
        return f"{int(seconds // 86400)} วันที่แล้ว"
    return th_date(value)


@register.filter
def domain(url):
    """``https://www.github.com/x`` → ``github.com/x`` (for compact link labels)."""
    if not url:
        return ""
    parts = urlsplit(url)
    host = parts.netloc.removeprefix("www.")
    path = parts.path.rstrip("/")
    return f"{host}{path}" if host else url


@register.filter
def initial(value):
    """First visible character, upper-cased (for generated covers)."""
    text = str(value or "").strip()
    return text[:1].upper() or "?"


@register.filter
def level(value):
    """Skill proficiency key → 1–4 (for the level meter)."""
    return {"beginner": 1, "intermediate": 2, "advanced": 3, "expert": 4}.get(value, 0)


@register.filter
def times(value):
    """``{% for i in 4|times %}`` → 0..3."""
    try:
        return range(int(value))
    except (TypeError, ValueError):
        return range(0)


@register.filter
def file_url(field):
    """URL of an ImageField/FileField, or "" when empty (``.url`` would raise)."""
    try:
        return field.url if field else ""
    except ValueError:
        return ""


@register.filter
def errored_fields(form):
    """Bound fields that have errors, in form order (for the error summary)."""
    try:
        return [form[name] for name in form.fields if form[name].errors]
    except (AttributeError, KeyError, TypeError):
        return []


@register.filter
def field_anchor(bound_field):
    """The id to jump to for a field: its input, or (radio groups) its fieldset."""
    return bound_field.id_for_label or bound_field.auto_id


@register.filter
def lookup(mapping, key):
    """``{{ counts|lookup:theme.key }}`` — dict access with a variable key (0/"" if missing)."""
    try:
        return mapping.get(key, 0)
    except AttributeError:
        return 0
