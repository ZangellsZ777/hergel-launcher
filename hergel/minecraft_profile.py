"""Link an authorized Microsoft account to its Minecraft Java profile."""
from io import BytesIO
from urllib.parse import urlparse
from urllib.request import urlopen


def minecraft_access_token(response):
    """Distinguish a Minecraft API error response from a successful token."""
    if isinstance(response, dict) and response.get('access_token'):
        return response['access_token']
    if not isinstance(response, dict):
        raise RuntimeError('Minecraft devolvió una respuesta de autenticación inesperada.')
    reason = str(response.get('errorMessage') or response.get('error_description') or
                 response.get('error') or response.get('message') or '')
    if 'invalid app registration' in reason.lower():
        raise RuntimeError('La aplicación Hergel Launcher no tiene autorización para la API de Minecraft '
                           '(Invalid app registration). El propietario de la aplicación debe solicitar '
                           'ese acceso a Minecraft; volver a iniciar sesión no lo concede.')
    if reason:
        raise RuntimeError('Minecraft rechazó la autenticación: ' + reason[:300])
    raise RuntimeError('Minecraft no entregó un token de juego. Revisa el permiso de la aplicación '
                       'para Minecraft Services y vuelve a intentarlo.')


def get_minecraft_profile(microsoft_access_token):
    try:
        from minecraft_launcher_lib import microsoft_account
    except ImportError as exc:
        raise RuntimeError('Falta minecraft-launcher-lib. Ejecuta: py -m pip install -r requirements.txt') from exc
    xbl = microsoft_account.authenticate_with_xbl(microsoft_access_token)
    xsts = microsoft_account.authenticate_with_xsts(xbl['Token'])
    userhash = xbl['DisplayClaims']['xui'][0]['uhs']
    minecraft = microsoft_account.authenticate_with_minecraft(userhash, xsts['Token'])
    minecraft_token = minecraft_access_token(minecraft)
    profile = microsoft_account.get_profile(minecraft_token)
    if not profile.get('id') or not profile.get('name'):
        raise RuntimeError('La cuenta no tiene un perfil de Minecraft Java disponible.')
    return profile, minecraft_token


def load_skin_image(profile):
    try:
        from PIL import Image
    except ImportError as exc:
        raise RuntimeError('Falta Pillow. Ejecuta: py -m pip install -r requirements.txt') from exc
    skins = profile.get('skins') or []
    skin = next((s for s in skins if s.get('state') == 'ACTIVE'), None)
    if not skin:
        return None
    parsed = urlparse(skin.get('url', ''))
    if parsed.hostname != 'textures.minecraft.net' or parsed.scheme not in ('http', 'https'):
        raise ValueError('El perfil devolvió una URL de skin inesperada.')
    with urlopen('https://textures.minecraft.net' + parsed.path, timeout=15) as response:
        raw = response.read(1024 * 1024 + 1)
    if len(raw) > 1024 * 1024:
        raise ValueError('El archivo de skin es demasiado grande.')
    with Image.open(BytesIO(raw)) as source:
        if source.width not in (64, 128) or source.height not in (source.width // 2, source.width):
            raise ValueError('Dimensiones de skin incompatibles.')
        image = source.convert('RGBA')
    return image, skin.get('variant', 'CLASSIC')


def render_skin_face(profile):
    image_and_variant = load_skin_image(profile)
    if image_and_variant is None:
        return None
    image, _ = image_and_variant
    scale = image.width // 64
    base = image.crop((8*scale, 8*scale, 16*scale, 16*scale))
    if image.height >= 16*scale:
        overlay = image.crop((40*scale, 8*scale, 48*scale, 16*scale))
        base.alpha_composite(overlay)
    base = base.resize((64, 64), Image.Resampling.NEAREST)
    out = BytesIO()
    base.save(out, format='PNG')
    return out.getvalue()


def render_skin_bust(profile):
    """Draw the front of the head, arms and upper torso from an authentic skin."""
    try:
        from PIL import Image
    except ImportError as exc:
        raise RuntimeError('Falta Pillow. Ejecuta: py -m pip install -r requirements.txt') from exc
    image_and_variant = load_skin_image(profile)
    if image_and_variant is None:
        return None
    image, variant = image_and_variant
    scale = image.width // 64
    slim = variant.upper() == 'SLIM'
    bust = Image.new('RGBA', (16, 18))

    def part(box, x, y):
        x0, y0, x1, y1 = box
        piece = image.crop((x0*scale, y0*scale, x1*scale, y1*scale))
        piece = piece.resize((x1-x0, y1-y0), Image.Resampling.NEAREST)
        bust.alpha_composite(piece, (x, y))

    # Back layer first, then the hat, jacket and sleeves when present.
    part((44, 20, 47 if slim else 48, 30), 13 if slim else 12, 8)
    part((20, 20, 28, 30), 4, 8)
    if image.height >= 64*scale:
        part((36, 52, 39 if slim else 40, 62), 0, 8)
        part((20, 36, 28, 46), 4, 8)
        part((44, 36, 47 if slim else 48, 46), 13 if slim else 12, 8)
        part((52, 52, 55 if slim else 56, 62), 0, 8)
    else:
        # The old 64x32 format stores one arm; display it on both sides.
        left = image.crop((44*scale, 20*scale, 48*scale, 30*scale))
        left = left.resize((4, 10), Image.Resampling.NEAREST)
        from PIL import ImageOps
        bust.alpha_composite(ImageOps.mirror(left), (0, 8))
    part((8, 8, 16, 16), 4, 0)
    part((40, 8, 48, 16), 4, 0)
    return _bust_png(bust)


def _bust_png(bust):
    from PIL import Image
    canvas = Image.new('RGBA', (100, 100), '#2d2049')
    pixels = bust.resize((80, 90), Image.Resampling.NEAREST)
    canvas.alpha_composite(pixels, (10, 5))
    out = BytesIO()
    canvas.convert('RGB').save(out, format='PNG')
    return out.getvalue()


def render_placeholder_bust():
    from PIL import Image, ImageDraw
    bust = Image.new('RGBA', (16, 18))
    draw = ImageDraw.Draw(bust)
    draw.rectangle((0, 8, 3, 17), fill='#777788')
    draw.rectangle((12, 8, 15, 17), fill='#777788')
    draw.rectangle((4, 8, 11, 17), fill='#9999aa')
    draw.rectangle((4, 0, 11, 7), fill='#b1b1bc')
    draw.point((6, 4), fill='#646477')
    draw.point((9, 4), fill='#646477')
    return _bust_png(bust)
