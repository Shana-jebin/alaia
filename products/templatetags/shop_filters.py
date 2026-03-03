from django import template

register = template.Library()

COLOR_HEX_MAP = {
    'black': '#000000',
    'white': '#ffffff',
    'nude': '#e3bc9a',
    'beige': '#f5f5dc',
    'brown': '#8b4513',
    'tan': '#d2b48c',
    'gold': '#d4af37',
    'silver': '#c0c0c0',
    'rose_gold': '#b76e79',
    'maroon': '#800000',
    'navy': '#000080',
    'olive': '#808000',
    'peach': '#ffcba4',
}

@register.filter
def color_hex(value):
    return COLOR_HEX_MAP.get(value, '#cccccc')

@register.filter
def split_last_word(value):
    if value:
        return value.split()[-1]
    return ""