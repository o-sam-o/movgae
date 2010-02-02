from django import template
from django.template.defaultfilters import stringfilter

register = template.Library()

@register.filter(name='js_var')
@stringfilter
def js_var(value):
    "Clean a string so it can be used as a js va name"
    return value.replace('-', '').lower()