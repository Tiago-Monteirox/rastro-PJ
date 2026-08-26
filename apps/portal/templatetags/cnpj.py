from django import template

from apps.registry.cnpj import format_cnpj, format_cnpj_basic

register = template.Library()


@register.filter(name="cnpj")
def format_cnpj_filter(value: object) -> str:
    return format_cnpj(value)


@register.filter(name="cnpj_basic")
def format_cnpj_basic_filter(value: object) -> str:
    return format_cnpj_basic(value)
