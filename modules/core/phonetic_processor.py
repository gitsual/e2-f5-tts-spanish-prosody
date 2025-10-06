#!/usr/bin/env python3
"""
====================================================================================================
TRANSFORMADOR FONÉTICO ESPAÑOL - SIMULACIÓN DE VARIACIONES DIALECTALES
====================================================================================================

Descripción:
    Sistema de transformación fonética que simula variaciones dialectales del español,
    principalmente fenómenos como betacismo, yeísmo y seseo. Diseñado para generar
    versiones de texto que reflejen cómo se pronuncian realmente las palabras.

Fenómenos Fonéticos Implementados:

    1. BETACISMO (b/v)
       - Confusión entre 'b' y 'v' (pronunciación idéntica en español)
       - Ejemplo: "llevar" → "yevar", "haber" → "aber"

    2. YEÍSMO (ll/y)
       - Pérdida de distinción entre 'll' y 'y'
       - Ejemplo: "llevar" → "yevar", "calle" → "caye"

    3. SESEO (c/z/s)
       - Pronunciación de 'c' (antes de e,i) y 'z' como 's'
       - Ejemplo: "hacer" → "aser", "vez" → "ves"

    4. ASPIRACIÓN/PÉRDIDA DE H
       - Eliminación de 'h' muda o aspiración
       - Ejemplo: "hacer" → "acer"

    5. ADAPTACIÓN DE ANGLICISMOS
       - Castellanización de términos ingleses
       - Ejemplo: "marketing" → "márquetin"

Características Técnicas:
    - Sistema de caché multicapa para rendimiento
    - Reglas aplicadas por prioridad
    - Mantenimiento de consistencia en transformaciones
    - Excepciones configurables por regla
    - Soporte para contexto (caracteres circundantes)

Aplicación:
    Útil para TTS que necesita generar audio más natural reflejando
    cómo se pronuncia realmente el español en diferentes dialectos.

Autor: Sistema de transformación fonética
Versión: 2.0
====================================================================================================
"""

import re
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, field
from collections import defaultdict


@dataclass
class PhoneticRule:
    """
    Representa una regla de transformación fonética.

    Attributes:
        pattern (str): Patrón regex a buscar
        replacement (str): Texto de reemplazo
        context (str, optional): Contexto requerido (antes/después)
        exceptions (List[str]): Palabras que no aplican esta regla
        priority (int): Prioridad de aplicación (mayor = primero)
    """
    pattern: str
    replacement: str
    context: Optional[str] = None
    exceptions: List[str] = field(default_factory=list)
    priority: int = 0


class SpanishPhoneticTransformer:
    """
    Transformador fonético para español con simulación de variaciones dialectales.

    Implementa un sistema de reglas que transforma texto escrito en español
    a su forma fonética, reflejando fenómenos comunes de pronunciación como
    betacismo, yeísmo, seseo, etc.

    Características:
        - Caché de transformaciones para rendimiento
        - Sistema de prioridades en reglas
        - Consistencia en transformaciones repetidas
        - Soporte para excepciones por palabra

    Attributes:
        word_cache (dict): Caché de palabras individuales transformadas
        phrase_cache (dict): Caché de frases completas
        transformation_history (defaultdict): Historial para mantener consistencia
        phonetic_rules (list): Conjunto de reglas fonéticas a aplicar
    """

    def __init__(self):
        """
        Inicializa el transformador con reglas fonéticas predefinidas.

        Configura el sistema de caché multicapa y carga todas las reglas
        de transformación fonética organizadas por fenómeno.
        """
        # Sistema de caché multicapa
        self.word_cache = {}  # Caché de palabras individuales
        self.phrase_cache = {}  # Caché de frases comunes
        self.transformation_history = defaultdict(list)  # Historial para consistencia

        # Reglas fonéticas españolas sistemáticas
        self.phonetic_rules = self._initialize_rules()

        # Diccionario exhaustivo de anglicismos con pronunciación castellana toledana
        # Organizado por categorías para mejor mantenimiento
        self.anglicisms_dictionary = self._build_complete_anglicisms_dictionary()

    def _build_complete_anglicisms_dictionary(self):
        """Construye el diccionario completo de anglicismos organizados por categorías"""
        dictionary = {}

        # TECNOLOGÍA Y DISPOSITIVOS
        tech_devices = {
            # Dispositivos
            'smartphone': 'esmárfon',
            'iphone': 'áifon',
            'android': 'ándroid',
            'tablet': 'táblet',
            'ipad': 'áipad',
            'laptop': 'láptop',
            'notebook': 'nóutbuk',
            'desktop': 'déstop',
            'pc': 'pisi',
            'mac': 'mak',
            'macbook': 'mákbuk',
            'imac': 'áimak',
            'mouse': 'maus',
            'keyboard': 'kíbord',
            'touchpad': 'táchpad',
            'trackpad': 'trákpad',
            'screen': 'eskrín',
            'display': 'displéi',
            'monitor': 'mónitor',
            'printer': 'prínter',
            'scanner': 'eskáner',
            'router': 'ráuter',
            'modem': 'módem',
            'switch': 'suích',
            'hub': 'jab',
            'server': 'sérver',
            'storage': 'estórech',
            'device': 'diváis',
            'gadget': 'gádyet',
            'smartwatch': 'esmárguach',
            'airpods': 'érpods',
            'kindle': 'kíndel',
            'playstation': 'pléisteichon',
            'xbox': 'éksbox',
            'nintendo': 'nintendo',
            'controller': 'contróler',
            'joystick': 'yóistik',
            'gamepad': 'guéimpad',
            'headphones': 'jédfons',
            'headset': 'jédset',
            'earphones': 'írfons',
            'speaker': 'espíker',
            'bluetooth': 'blutús',
            'powerbank': 'páuerbánk',
            'charger': 'cháryer',
            'cable': 'kéibol',
            'adapter': 'adápter',
            'dongle': 'dóngol',
            'dock': 'dok',
            'pen drive': 'pendráif',
            'pendrive': 'pendráif',
            'flash drive': 'fláchdráif',
            'hard drive': 'járdráif',
            'ssd': 'ese-ese-dé',
            'ram': 'ram',
            'cpu': 'sipiyú',
            'gpu': 'yipiyú',
            'motherboard': 'máderbord',
            'chipset': 'chípset',
            'firmware': 'férmgüer',
            'driver': 'dráiver',

        }

        # Conectividad y red
        connectivity = {
            'wifi': 'güáifai',
            'wi-fi': 'güáifai',
            'internet': 'ínternet',
            'ethernet': 'ízernet',
            'lan': 'lan',
            'wan': 'güan',
            'vpn': 'bebepené',
            'proxy': 'próksi',
            'firewall': 'fáiergüol',
            'bandwidth': 'bándgüiz',
            'broadband': 'bródbánd',
            '4g': 'cuatro-yé',
            '5g': 'cinco-yé',
            'lte': 'ele-te-é',
            'hotspot': 'jótspot',
            'tethering': 'téderin',
        }

        # Software y aplicaciones
        software = {
            'software': 'sófgüer',
            'hardware': 'járdgüer',
            'app': 'ap',
            'apps': 'aps',
            'application': 'aplicéichon',
            'program': 'próugram',
            'browser': 'bráuser',
            'chrome': 'cróum',
            'firefox': 'fáierfoks',
            'safari': 'safári',
            'edge': 'ech',
            'explorer': 'eksplórer',
            'windows': 'güíndous',
            'linux': 'línuks',
            'ubuntu': 'ubúntu',
            'macos': 'makós',
            'ios': 'áios',
            'update': 'apdéit',
            'upgrade': 'apgréid',
            'patch': 'pach',
            'bug': 'bag',
            'debug': 'dibág',
            'plugin': 'pláguin',
            'addon': 'ádon',
            'extension': 'eksténchon',
            'widget': 'güídyet',
            'toolbar': 'túlbar',
            'taskbar': 'táskbar',
            'wallpaper': 'güólpeiper',
            'screensaver': 'eskrínseiber',
            'virus': 'báirus',
            'malware': 'málgüer',
            'spyware': 'espáigüer',
            'ransomware': 'ránsamgüer',
            'antivirus': 'antibáirus',
            'backup': 'bákap',
            'recovery': 'recóberi',
            'restore': 'restór',
            'reset': 'risét',
            'reboot': 'ribút',
            'shutdown': 'chátdaun',
            'startup': 'estártap',
            'boot': 'but',
            'bios': 'báios',
            'setup': 'sétap',
            'settings': 'sétins',
            'preferences': 'préferenses',
            'configuration': 'configuréichon',
            'default': 'difólt',
            'custom': 'cástom',
            'template': 'témplet',
            'theme': 'zim',
            'skin': 'eskín',
            'font': 'font',
            'icon': 'áikon',
            'thumbnail': 'zámneil',
            'preview': 'príviu',
        }

        # Términos web y email
        web_terms = {
            'website': 'güébsait',
            'web': 'güeb',
            'webpage': 'güébpeich',
            'homepage': 'jóumpeich',
            'site': 'sait',
            'portal': 'pórtal',
            'blog': 'blog',
            'vlog': 'vlog',
            'forum': 'fórum',
            'chat': 'chat',
            'email': 'iméil',
            'e-mail': 'iméil',
            'mail': 'méil',
            'gmail': 'yiméil',
            'outlook': 'áutluk',
            'hotmail': 'jótmeil',
            'yahoo': 'yáju',
            'spam': 'espam',
            'inbox': 'ínboks',
            'outbox': 'áutboks',
            'draft': 'draft',
            'attachment': 'atáchment',
            'forward': 'fórgüard',
            'reply': 'ripláy',
            'cc': 'sisi',
            'bcc': 'bisisi',
            'subject': 'sábyect',
            'signature': 'sígneitur',
            'newsletter': 'niúsleter',
            'subscribe': 'sabskráib',
            'unsubscribe': 'ansabskráib',
            'notification': 'notifikéichon',
            'alert': 'alért',
            'popup': 'pópap',
            'banner': 'báner',
            'cookie': 'cúki',
            'cache': 'cach',
            'history': 'jístori',
            'bookmark': 'búkmark',
            'favorites': 'féiborits',
            'tab': 'tab',
            'window': 'güíndou',
            'frame': 'fréim',
            'scroll': 'eskról',
            'click': 'clik',
            'double click': 'dábol clik',
            'right click': 'ráit clik',
            'drag': 'drag',
            'drop': 'drop',
            'drag and drop': 'drag and drop',
            'copy': 'cópi',
            'paste': 'péist',
            'cut': 'cat',
            'undo': 'andú',
            'redo': 'ridú',
            'save': 'séif',
            'save as': 'séif as',
            'open': 'óupen',
            'close': 'clóus',
            'exit': 'éksit',
            'quit': 'cuit',
            'print': 'print',
            'scan': 'eskán',
            'search': 'serch',
            'find': 'fáind',
            'replace': 'ripléis',
            'zoom': 'zum',
            'zoom in': 'zum in',
            'zoom out': 'zum áut',
            'fullscreen': 'fuleskrín',
            'minimize': 'mínimais',
            'maximize': 'máksimais',
            'resize': 'risáis',
        }

        # Acciones digitales
        digital_actions = {
            'online': 'onláin',
            'offline': 'ofláin',
            'download': 'dáunloud',
            'upload': 'áploud',
            'stream': 'estrím',
            'streaming': 'estrímin',
            'buffer': 'báfer',
            'buffering': 'báferin',
            'loading': 'lóudin',
            'processing': 'prósesin',
            'rendering': 'rénderin',
            'encoding': 'encóudin',
            'decoding': 'dicóudin',
            'compress': 'comprés',
            'decompress': 'dicomprés',
            'zip': 'sip',
            'unzip': 'ansíp',
            'extract': 'ekstrákt',
            'install': 'instól',
            'uninstall': 'aninstól',
            'run': 'ran',
            'execute': 'éksikiut',
            'launch': 'lónch',
            'load': 'loud',
            'refresh': 'rifréch',
            'reload': 'rilóud',
            'sync': 'sink',
            'synchronize': 'sínkronais',
            'share': 'cher',
            'sharing': 'chérin',
            'post': 'poust',
            'posting': 'póustin',
            'comment': 'cóment',
            'like': 'láik',
            'unlike': 'anláik',
            'follow': 'fólou',
            'unfollow': 'anfólou',
            'block': 'blok',
            'unblock': 'anblók',
            'report': 'ripórt',
            'flag': 'flag',
            'tag': 'tag',
            'hashtag': 'jáchtag',
            'mention': 'ménchon',
            'dm': 'diém',
            'pm': 'piém',
            'message': 'mésech',
            'messenger': 'mésényer',
            'voice message': 'bóis mésech',
            'videocall': 'bídeocol',
            'call': 'col',
        }

        # Seguridad y cuentas
        security = {
            'password': 'pásgüerd',
            'username': 'yúserneym',
            'user': 'yúser',
            'account': 'acáunt',
            'profile': 'próufail',
            'avatar': 'ábatar',
            'login': 'lóguin',
            'log in': 'log in',
            'logout': 'lógaut',
            'log out': 'log áut',
            'sign in': 'sáin in',
            'sign up': 'sáin ap',
            'sign out': 'sáin áut',
            'register': 'réyister',
            'authentication': 'ozentikéichon',
            'verification': 'berifikéichon',
            'captcha': 'cápcha',
            'token': 'tóuken',
            'key': 'ki',
            'encryption': 'encríption',
            'decrypt': 'dicrípt',
            'secure': 'sekiúr',
            'privacy': 'práibasi',
            'permissions': 'permíchons',
            'admin': 'ádmin',
            'administrator': 'administréitor',
            'moderator': 'moderéitor',
            'guest': 'gest',
        }

        # Formatos de archivo
        file_formats = {
            'file': 'fáil',
            'folder': 'fólder',
            'directory': 'dairéktori',
            'path': 'paz',
            'format': 'fórmat',
            'pdf': 'pedéefe',
            'doc': 'dok',
            'docx': 'dókekis',
            'xls': 'ékselis',
            'xlsx': 'ékselisekis',
            'ppt': 'pepeté',
            'pptx': 'pepetéekis',
            'txt': 'téekseté',
            'rtf': 'erteéfe',
            'csv': 'seesebé',
            'xml': 'ékseméle',
            'json': 'yéison',
            'html': 'ácheteméle',
            'css': 'seeses',
            'js': 'yéiés',
            'php': 'peáchepé',
            'sql': 'ésekiuéle',
            'jpg': 'yéipeg',
            'jpeg': 'yéipeg',
            'png': 'piéneyi',
            'gif': 'yif',
            'bmp': 'biémpí',
            'svg': 'ésebeyí',
            'mp3': 'émepetré',
            'mp4': 'émepecuátro',
            'avi': 'ábi',
            'mov': 'mob',
            'wmv': 'dábliuémebé',
            'flv': 'éfeélebé',
            'mkv': 'émekabé',
            'wav': 'güab',
            'flac': 'flak',
            'rar': 'rar',
            'tar': 'tar',
            '7z': 'sébenzip',
            'iso': 'áiso',
            'exe': 'ékse',
            'dmg': 'diémyi',
            'apk': 'ápeka',
            'dll': 'diéleéle',
            'bat': 'bat',
            'sh': 'ésache',
            'ini': 'íni',
            'log': 'log',
            'tmp': 'téemepé',
            'bak': 'bak',
        }

        # REDES SOCIALES Y PLATAFORMAS
        social_media = {
            'facebook': 'féisbuk',
            'instagram': 'ínstagram',
            'twitter': 'tuíter',
            'x': 'eks',
            'whatsapp': 'guásap',
            'telegram': 'télegram',
            'snapchat': 'esnápchát',
            'tiktok': 'tíktok',
            'youtube': 'yútub',
            'twitch': 'tuích',
            'discord': 'díscord',
            'reddit': 'rédit',
            'pinterest': 'pínterest',
            'tumblr': 'támbler',
            'linkedin': 'línkedin',
            'skype': 'eskáip',
            'teams': 'tims',
            'slack': 'eslák',
            'clubhouse': 'clábjaus',
            'tinder': 'tínder',
            'bumble': 'bámbel',
            'grindr': 'gráinder',
            'badoo': 'badú',
            'meetup': 'mítap',
            'wechat': 'güíchát',
            'viber': 'báiber',
            'line': 'láin',
            'signal': 'sígnal',
            'flickr': 'flíker',
            'vimeo': 'bímeo',
            'soundcloud': 'sáundclaud',
            'spotify': 'espótifai',
            'apple music': 'ápel miúsik',
            'deezer': 'díser',
            'pandora': 'pandóra',
            'netflix': 'nétflis',
            'hbo': 'áchebió',
            'disney plus': 'dísney plas',
            'disney+': 'dísney plas',
            'amazon prime': 'ámazon práim',
            'hulu': 'júlu',
            'peacock': 'píkok',
            'paramount': 'páramaunt',
            'crunchyroll': 'cránchirol',
            'onlyfans': 'ónlifans',
            'patreon': 'péitreon',
            'mixer': 'míkser',
            'periscope': 'périscoup',
            'vine': 'báin',
            'myspace': 'máispeis',
            'orkut': 'órkut',
            'hi5': 'jáifaib',
            'friendster': 'fréndster',
            'google plus': 'gúgol plas',
            'google+': 'gúgol plas',
        }

        # MARCAS Y EMPRESAS TECNOLÓGICAS
        tech_brands = {
            'google': 'gúgol',
            'apple': 'ápel',
            'microsoft': 'máicrosoft',
            'amazon': 'ámazon',
            'meta': 'méta',
            'tesla': 'tésla',
            'spacex': 'espéiseks',
            'uber': 'úber',
            'airbnb': 'érbienbi',
            'paypal': 'péipal',
            'ebay': 'íbei',
            'alibaba': 'alibába',
            'samsung': 'sámsun',
            'sony': 'sóni',
            'lg': 'élyí',
            'huawei': 'juágüei',
            'xiaomi': 'cháomi',
            'oppo': 'ópo',
            'oneplus': 'guánplas',
            'nokia': 'nókia',
            'motorola': 'motoróla',
            'blackberry': 'blákberi',
            'htc': 'ácheteséi',
            'asus': 'ásus',
            'acer': 'éiser',
            'dell': 'del',
            'hp': 'áchepí',
            'lenovo': 'lenóbo',
            'toshiba': 'tochíba',
            'panasonic': 'panasónik',
            'canon': 'cánon',
            'nikon': 'níkon',
            'gopro': 'góuprou',
            'adobe': 'adóubi',
            'oracle': 'órakel',
            'sap': 'esaépí',
            'salesforce': 'séilsfors',
            'cisco': 'sísko',
            'intel': 'íntel',
            'amd': 'áemedí',
            'nvidia': 'enbídia',
            'qualcomm': 'cuálcom',
            'broadcom': 'bródcom',
            'western digital': 'güéstern díyital',
            'seagate': 'sígeit',
            'kingston': 'kínston',
            'corsair': 'corsér',
            'logitech': 'lóyitek',
            'razer': 'réiser',
            'steelseries': 'estílsiris',
            'bose': 'bous',
            'jbl': 'yéibiél',
            'beats': 'bits',
            'sennheiser': 'sénjáiser',
            'fitbit': 'fítbit',
            'garmin': 'gármin',
            'dji': 'diyiái',
            'roku': 'róku',
            'chromecast': 'cróumcast',
            'fire tv': 'fáier tibí',
            'apple tv': 'ápel tibí',
            'steam': 'estím',
            'epic games': 'épik guéims',
            'ea': 'íei',
            'activision': 'aktibíchon',
            'blizzard': 'blísard',
            'ubisoft': 'yúbisoft',
            'rockstar': 'rókstar',
            'bethesda': 'betésda',
            'square enix': 'eskuér éniks',
            'capcom': 'cápcom',
            'konami': 'konámi',
            'bandai': 'bándai',
            'sega': 'séga',
            'atari': 'atári',
        }

        # COMIDA Y BEBIDA
        food_drink = {
            # Comida rápida
            'burger': 'búrguer',
            'hamburger': 'jambúrguer',
            'cheeseburger': 'chísburguer',
            'hot dog': 'jot dog',
            'hotdog': 'jótdog',
            'sandwich': 'sánguich',
            'sub': 'sab',
            'bagel': 'béiguel',
            'donut': 'dónut',
            'muffin': 'máfin',
            'pancake': 'pánkeik',
            'waffle': 'guáfol',
            'toast': 'tóust',
            'bacon': 'béikon',
            'nuggets': 'náguets',
            'pizza': 'písa',
            'pepperoni': 'peperóni',
            'barbecue': 'bárbeku',
            'bbq': 'bárbekiu',
            'grill': 'gril',
            'steak': 'estéik',
            'chicken': 'chíken',
            'beef': 'bif',
            'pork': 'pórk',
            'turkey': 'túrki',
            'salmon': 'sálmon',
            'tuna': 'túna',
            'shrimp': 'chrímp',
            'lobster': 'lóbster',
            'clam': 'clam',
            'crab': 'crab',
            'fish and chips': 'fich and chíps',
            'ketchup': 'kéchap',
            'mustard': 'mástard',
            'mayo': 'méyo',
            'mayonnaise': 'meyonéis',
            'cheese': 'chís',
            'cheddar': 'chédar',
            'mozzarella': 'mosaréla',
            'parmesan': 'parmesan',
            'feta': 'féta',
            'yogurt': 'yógurt',
            'ice cream': 'áis crím',
            'milkshake': 'mílkshéik',
            'smoothie': 'esmúzi',
            'cookies': 'cúkis',
            'brownie': 'bráuni',
            'cheesecake': 'chískeik',
            'cupcake': 'cápkeik',
            'pie': 'pái',
            'chips': 'chíps',
            'popcorn': 'pópkorn',
            'crackers': 'crákers',
            'pretzel': 'prétsel',
            'snack': 'esnák',
            'snacks': 'esnáks',

            # Bebidas
            'coffee': 'cófi',
            'cappuccino': 'capuchíno',
            'espresso': 'esprés',
            'latte': 'láte',
            'macchiato': 'makiáto',
            'americano': 'amerikáno',
            'frappuccino': 'frapuchíno',
            'tea': 'tí',
            'chai': 'chái',
            'matcha': 'mácha',
            'juice': 'yús',
            'smoothie': 'esmúzi',
            'soda': 'sóuda',
            'cola': 'kóla',
            'pepsi': 'pépsi',
            'coca cola': 'kóka kóla',
            'sprite': 'espráit',
            'fanta': 'fánta',
            'red bull': 'red bul',
            'energy drink': 'éneryí drink',
            'beer': 'bír',
            'light beer': 'láit bír',
            'ale': 'éil',
            'lager': 'láger',
            'stout': 'estáut',
            'wine': 'guáin',
            'champagne': 'champéin',
            'whiskey': 'güíski',
            'whisky': 'güíski',
            'bourbon': 'búrbon',
            'vodka': 'bódka',
            'gin': 'yin',
            'rum': 'ram',
            'tequila': 'tekíla',
            'brandy': 'brándi',
            'cocktail': 'kóktel',
            'mojito': 'mojíto',
            'margarita': 'margaríta',
            'bloody mary': 'bládi méri',
            'manhattan': 'manján',
            'martini': 'martíni',
            'cosmopolitan': 'kosmopolítan',
            'shot': 'chot',
            'on the rocks': 'on de roks',
            'shake': 'chéik',
            'stir': 'estér',
        }

        # NOMBRES PROPIOS INGLESES
        english_names = {
            # Nombres masculinos
            'john': 'yon',
            'james': 'yéims',
            'robert': 'róbert',
            'michael': 'máikel',
            'william': 'güíliam',
            'david': 'déivid',
            'richard': 'ríchard',
            'joseph': 'yósef',
            'thomas': 'tómas',
            'christopher': 'crístofher',
            'charles': 'chárles',
            'daniel': 'dániel',
            'matthew': 'mázyu',
            'anthony': 'ántoni',
            'mark': 'márk',
            'donald': 'dónald',
            'steven': 'estíven',
            'steve': 'estíf',
            'paul': 'pol',
            'andrew': 'ándru',
            'joshua': 'yóxua',
            'kenneth': 'kénes',
            'kevin': 'kévin',
            'brian': 'bráian',
            'george': 'yórch',
            'edward': 'édgüard',
            'ronald': 'rónald',
            'timothy': 'tímozi',
            'jason': 'yéison',
            'jeffrey': 'yéfri',
            'ryan': 'ráian',
            'jacob': 'yéikob',
            'gary': 'géri',
            'nicholas': 'níkolas',
            'eric': 'érik',
            'jonathan': 'yónatan',
            'stephen': 'estífen',
            'larry': 'léri',
            'justin': 'yástin',
            'scott': 'eskót',
            'brandon': 'brándon',
            'benjamin': 'bényamin',
            'samuel': 'sámiuel',
            'frank': 'fránk',
            'mike': 'máik',
            'peter': 'píter',

            # Nombres femeninos
            'mary': 'méri',
            'patricia': 'patrísya',
            'jennifer': 'yénifer',
            'linda': 'línda',
            'elizabeth': 'elísabes',
            'barbara': 'bárbara',
            'susan': 'sús an',
            'jessica': 'yésika',
            'sarah': 'séra',
            'karen': 'kéren',
            'nancy': 'nánsi',
            'lisa': 'lísa',
            'betty': 'béti',
            'helen': 'jélen',
            'sandra': 'sándra',
            'donna': 'dóna',
            'carol': 'kérol',
            'ruth': 'ruz',
            'sharon': 'chéron',
            'michelle': 'michél',
            'laura': 'lóra',
            'sarah': 'séra',
            'kimberly': 'kímberli',
            'deborah': 'débora',
            'dorothy': 'dórozi',
            'amy': 'éimi',
            'angela': 'ányela',
            'ashley': 'áchli',
            'brenda': 'brénda',
            'emma': 'éma',
            'olivia': 'olívia',
            'cynthia': 'sínzia',
            'marie': 'méri',
            'janet': 'yánet',
            'catherine': 'kázerin',
            'frances': 'fránses',
            'christine': 'cristín',
            'samantha': 'samánza',
            'debra': 'débra',
            'rachel': 'réichel',
            'carolyn': 'kérolyn',
            'janet': 'yánet',
            'virginia': 'viryínia',
            'maria': 'maría',
            'heather': 'jézer',
            'diane': 'dáian',
            'julie': 'yúli',
            'joyce': 'yóis',
            'kelly': 'kéli',
            'christina': 'cristína',
            'joan': 'yóan',
            'evelyn': 'évelin',
            'lauren': 'lóren',
            'judith': 'yúdiz',
            'megan': 'mégan',
            'cheryl': 'chéril',
            'andrea': 'ándrea',
            'hannah': 'ján a',
            'jacqueline': 'yakelin',
            'martha': 'márza',
            'gloria': 'glória',
        }

        # PALABRAS COMUNES Y EXPRESIONES
        common_words = {
            'ok': 'okey',
            'okay': 'okey',
            'yes': 'yes',
            'hello': 'jélou',
            'hi': 'jái',
            'bye': 'bái',
            'goodbye': 'gudbái',
            'please': 'plís',
            'thanks': 'zénks',
            'thank you': 'zénk yu',
            'sorry': 'sóri',
            'excuse me': 'ekskiús mi',
            'happy': 'jápi',
            'birthday': 'bérzdeí',
            'christmas': 'crísmas',
            'new year': 'niu yír',
            'party': 'párti',
            'weekend': 'guíkend',
            'holiday': 'jólidei',
            'vacation': 'veikéishon',
            'shopping': 'chópin',
            'sale': 'séil',
            'offer': 'ófer',
            'deal': 'díl',
            'discount': 'dískáunt',
            'price': 'práis',
            'money': 'máni',
            'cash': 'cách',
            'credit card': 'crédit card',
            'card': 'card',
            'check': 'chek',
            'receipt': 'risípt',
            'change': 'chéinch',
            'tip': 'típ',
            'bill': 'bil',
            'service': 'sérvis',
            'customer': 'cástomer',
            'client': 'cláient',
            'business': 'bísnes',
            'company': 'cómpani',
            'office': 'ófis',
            'work': 'guórk',
            'job': 'yob',
            'career': 'karír',
            'boss': 'bos',
            'manager': 'mánayer',
            'employee': 'emploí',
            'team': 'tím',
            'meeting': 'mítin',
            'conference': 'cónferens',
            'presentation': 'presentéishon',
            'project': 'próyekt',
            'deadline': 'dédlain',
            'schedule': 'eskédiul',
            'appointment': 'apóintment',
            'interview': 'ínterviu',
            'resume': 'resiumé',
            'cv': 'sibí',
            'experience': 'ekspíriens',
            'skill': 'eskíl',
            'training': 'tréinin',
            'course': 'kórs',
            'workshop': 'guórkchop',
            'seminar': 'semínar',
            'feedback': 'fídbak',
            'review': 'rivíu',
            'performance': 'perfórmans',
            'goal': 'góul',
            'target': 'tárget',
            'result': 'risált',
            'success': 'sákses',
            'achievement': 'achívment',
            'challenge': 'chálench',
            'problem': 'próblem',
            'solution': 'solúshon',
            'opportunity': 'oportúniti',
            'strategy': 'estrátyi',
            'plan': 'plan',
            'budget': 'báyet',
            'cost': 'kost',
            'profit': 'prófit',
            'investment': 'invéstment',
            'market': 'márket',
            'marketing': 'márketin',
            'sales': 'séils',
            'brand': 'brand',
            'product': 'prádakt',
            'quality': 'kuáliti',
            'service': 'sérvis',
            'support': 'sapórt',
            'help': 'jélp',
            'assistance': 'asístens',
            'information': 'informéishon',
            'data': 'déita',
            'report': 'ripórt',
            'analysis': 'análisis',
            'research': 'risérch',
            'study': 'estádi',
            'survey': 'sórvei',
            'test': 'test',
            'exam': 'eksám',
            'score': 'eskór',
            'grade': 'gréid',
            'level': 'lével',
            'degree': 'digrí',
            'certificate': 'sertífiket',
            'diploma': 'diplóma',
            'license': 'láisens',
            'permit': 'pérmit',
            'visa': 'vísa',
            'passport': 'páspórt',
            'flight': 'fláit',
            'ticket': 'tíket',
            'booking': 'búkin',
            'reservation': 'reservéishon',
            'hotel': 'jótel',
            'room': 'rum',
            'bed': 'bed',
            'bathroom': 'bázrum',
            'shower': 'cháuer',
            'towel': 'táuel',
            'soap': 'sóup',
            'shampoo': 'champú',
            'toothbrush': 'túzbrach',
            'toothpaste': 'túzpeist',
        }

        # DEPORTES Y FITNESS
        sports_fitness = {
            'sport': 'espórt',
            'sports': 'espórts',
            'football': 'fútbol',
            'soccer': 'sóker',
            'basketball': 'básketbol',
            'baseball': 'béisbol',
            'tennis': 'ténis',
            'golf': 'golf',
            'swimming': 'suímin',
            'running': 'ránin',
            'jogging': 'yógin',
            'walking': 'guókin',
            'cycling': 'sáiklin',
            'biking': 'báikin',
            'hiking': 'jáikin',
            'climbing': 'kláimin',
            'surfing': 'sérfin',
            'skiing': 'eskíin',
            'snowboarding': 'esnóubordin',
            'skateboarding': 'eskéitbordin',
            'boxing': 'bóksin',
            'wrestling': 'réslin',
            'martial arts': 'márshial arts',
            'karate': 'karáte',
            'judo': 'yúdo',
            'taekwondo': 'tekuándou',
            'yoga': 'yóga',
            'pilates': 'pilátes',
            'fitness': 'fítnes',
            'gym': 'yím',
            'workout': 'guórkaut',
            'exercise': 'eksersáis',
            'training': 'tréinin',
            'coach': 'kóuch',
            'trainer': 'tréiner',
            'team': 'tím',
            'player': 'pléier',
            'athlete': 'ázlit',
            'championship': 'chámpianchip',
            'tournament': 'túrnament',
            'match': 'mách',
            'game': 'guéim',
            'score': 'eskór',
            'goal': 'góul',
            'point': 'póint',
            'win': 'guin',
            'lose': 'lús',
            'victory': 'víktori',
            'defeat': 'difít',
            'champion': 'chámpioen',
            'winner': 'guíner',
            'loser': 'lúser',
            'medal': 'médal',
            'trophy': 'trófi',
            'award': 'aguárd',
            'prize': 'práis',
            'record': 'récord',
            'performance': 'perfórmans',
            'speed': 'espíd',
            'strength': 'estréngz',
            'power': 'páuer',
            'endurance': 'endúrans',
            'flexibility': 'fleksibíliti',
            'balance': 'bálans',
            'coordination': 'koordinéishon',
            'technique': 'teknk',
            'skill': 'eskíl',
            'talent': 'tálent',
        }

        # VERBOS ADAPTADOS (SPANGLISH)
        adapted_verbs = {
            'scrolling': 'escrolín',
            'scrolleando': 'escroliando',
            'scrollear': 'escrolear',
            'chatting': 'chateando',
            'chatear': 'chatear',
            'surfing': 'surfeando',
            'surfear': 'surfear',
            'clicking': 'clikeando',
            'clickear': 'clikear',
            'shopping': 'chopeando',
            'shopear': 'chopear',
            'parking': 'parkeando',
            'parkear': 'parkear',
            'googling': 'googleando',
            'googlear': 'googlear',
            'streaming': 'estrimineando',
            'strimear': 'estrimear',
            'posting': 'posteando',
            'postear': 'postear',
            'sharing': 'shareando',
            'sharear': 'charear',
            'liking': 'likeando',
            'likear': 'likear',
            'following': 'followeando',
            'followear': 'folowear',
            'unfollowing': 'anfollowing',
            'anfollowear': 'anfolowear',
            'blocking': 'bloqueando',
            'bloquear': 'blokear',
            'reporting': 'reporteando',
            'reportear': 'reportear',
            'tagging': 'tagueando',
            'taguear': 'taguear',
            'mentioning': 'mencionando',
            'mencionar': 'mencionar',
            'messaging': 'mensajeando',
            'mensajear': 'mensayear',
            'calling': 'caleando',
            'calear': 'calear',
            'texting': 'texteando',
            'textear': 'tektear',
            'emailing': 'emaileando',
            'emailear': 'imeilear',
            'downloading': 'downloadeando',
            'downloadear': 'daunlodear',
            'uploading': 'uploadeando',
            'uploadear': 'aplodear',
            'installing': 'instalando',
            'instalar': 'instalar',
            'updating': 'updateando',
            'updatear': 'apdeitear',
            'rebooting': 'rebootteando',
            'rebootear': 'ributear',
            'logging': 'logueando',
            'loguear': 'loguear',
            'signing': 'signeando',
            'signear': 'sainear',
            'registering': 'registreando',
            'registrear': 'reyistrear',
        }

        # TÉRMINOS FILOSÓFICOS Y ACADÉMICOS
        philosophical_terms = {
            # Corrientes filosóficas
            'existentialism': 'eksistensialísmo',
            'phenomenology': 'fenomenoloyía',
            'nihilism': 'nijilísmo',
            'positivism': 'positibísmo',
            'empiricism': 'empirisísmo',
            'rationalism': 'racionálismo',
            'idealism': 'idealísmo',
            'materialism': 'materialísmo',
            'stoicism': 'estoicísmo',
            'skepticism': 'eseptisísmo',
            'pragmatism': 'pragmatísmo',
            'utilitarianism': 'utilitariánismo',
            'hedonism': 'jedonísmo',
            'determinism': 'determinísmo',
            'relativism': 'relatibísmo',
            'absolutism': 'absolutísmo',
            'fatalism': 'fatalísmo',
            'humanism': 'jumanísmo',
            'structuralism': 'estrukturalísmo',
            'postmodernism': 'postmodernísmo',
            'deconstructionism': 'dekonstruksionísmo',
            'functionalism': 'funcionálismo',
            'behaviorism': 'bijebiorísmo',
            'cognitivism': 'kognitibísmo',
            'constructivism': 'konstruktibísmo',
            'reductionism': 'reduksionísmo',
            'holism': 'jolísmo',
            'dualism': 'dualísmo',
            'monism': 'monísmo',
            'pluralism': 'pluralísmo',
            'anarchism': 'anarkísmo',
            'socialism': 'sosialísmo',
            'capitalism': 'kapitalísmo',
            'liberalism': 'liberalísmo',
            'conservatism': 'konservabatísmo',
            'feminism': 'feminísmo',

            # Conceptos filosóficos
            'epistemology': 'epistemoloyía',
            'ontology': 'ontoloyía',
            'metaphysics': 'metafísiks',
            'ethics': 'éziks',
            'aesthetics': 'eszétiks',
            'logic': 'lóyik',
            'dialectic': 'diálektik',
            'synthesis': 'sínzesis',
            'antithesis': 'antízesis',
            'thesis': 'zísis',
            'syllogism': 'siloyísmo',
            'paradox': 'páradoks',
            'axiom': 'áksion',
            'premise': 'prémis',
            'conclusion': 'konklusión',
            'inference': 'ínferens',
            'deduction': 'dedáksion',
            'induction': 'indáksion',
            'abduction': 'abdáksion',
            'fallacy': 'fálasi',
            'sophism': 'sófismo',
            'tautology': 'tautoloyía',
            'contradiction': 'kontradíksion',
            'contingency': 'kontinénsí',
            'necessity': 'nesésiti',
            'possibility': 'posibilíti',
            'actuality': 'aktuáliti',
            'potentiality': 'potensialíti',
            'causality': 'kasualíti',
            'correlation': 'koreláshion',
            'synchronicity': 'sinkronísiti',
            'determinacy': 'determinásí',
            'indeterminacy': 'indeterminásí',
            'freedom': 'frídom',
            'autonomy': 'autonímí',
            'heteronomy': 'jeteronímí',
            'authenticity': 'ozentísiti',
            'alienation': 'alien-éishon',
            'reification': 'reifikéishon',
            'objectification': 'obyektifikéishon',
            'subjectivity': 'sábyektibiti',
            'objectivity': 'obyektíbiti',
            'intersubjectivity': 'intersábyektibiti',
            'consciousness': 'kónshusnes',
            'unconscious': 'ánkonshus',
            'subconsciousness': 'sabkónshusnes',
            'self-consciousness': 'self-kónshusnes',
            'intentionality': 'intensionalíti',
            'qualia': 'kuália',
            'phenomenality': 'fenomenáliti',
            'transcendence': 'transendéns',
            'immanence': 'ímamens',
            'finitude': 'fínitud',
            'infinity': 'infíniti',
            'eternity': 'etérniti',
            'temporality': 'temporáliti',
            'spatiality': 'espashiáliti',
            'being': 'bíin',
            'becoming': 'bikámin',
            'nothingness': 'názingnes',
            'void': 'bóid',
            'essence': 'ésens',
            'existence': 'eksístens',
            'substance': 'sábstans',
            'accident': 'áksidént',
            'attribute': 'átribut',
            'property': 'próperi',
            'quality': 'kuáliti',
            'quantity': 'kuántiti',
            'relation': 'reláshion',
            'modality': 'modalíti',
            'category': 'kátegori',
            'universal': 'unibérsol',
            'particular': 'partíkular',
            'individual': 'indibídual',
            'singular': 'síngular',
            'general': 'yéneral',
            'specific': 'espesífik',
            'generic': 'yenérik',
            'abstract': 'ábstrakt',
            'concrete': 'kónkrit',
            'absolute': 'ábsolut',
            'relative': 'rélativ',
            'conditional': 'kondíshonal',
            'unconditional': 'ankondíshonal',
        }

        # NOMBRES DE CIENTÍFICOS Y FILÓSOFOS
        scientists_philosophers = {
            # Filósofos clásicos
            'socrates': 'sókrates',
            'plato': 'pléito',
            'aristotle': 'arístotol',
            'pythagoras': 'pazágoras',
            'heraclitus': 'jeráklitus',
            'parmenides': 'parménides',
            'democritus': 'demókritus',
            'epicurus': 'epikúrus',
            'seneca': 'séneka',
            'marcus aurelius': 'márkus aurélios',
            'augustine': 'agástín',
            'aquinas': 'akuáinas',

            # Filósofos modernos
            'descartes': 'dekártes',
            'spinoza': 'espinósa',
            'leibniz': 'láibnis',
            'locke': 'lok',
            'berkeley': 'bérkli',
            'hume': 'jum',
            'kant': 'kant',
            'fichte': 'fíjte',
            'schelling': 'chélin',
            'hegel': 'jégel',
            'schopenhauer': 'chopénjauer',
            'kierkegaard': 'kírkegár',
            'nietzsche': 'níche',
            'mill': 'mil',
            'bentham': 'béntam',
            'comte': 'kont',
            'marx': 'marks',
            'engels': 'éngels',
            'james': 'yéims',
            'dewey': 'diúi',
            'peirce': 'pirs',

            # Filósofos contemporáneos
            'husserl': 'júserl',
            'heidegger': 'jáideger',
            'sartre': 'sártr',
            'camus': 'kamú',
            'beauvoir': 'bobóir',
            'merleau-ponty': 'merló-pontí',
            'levinas': 'lebínas',
            'derrida': 'derída',
            'foucault': 'fukó',
            'deleuze': 'deléus',
            'baudrillard': 'bodriyár',
            'lyotard': 'liotár',
            'habermas': 'jábermas',
            'gadamer': 'gadámer',
            'ricoeur': 'rikér',
            'rawls': 'rols',
            'nozick': 'nósik',
            'dworkin': 'duórkin',
            'rorty': 'rórti',
            'putnam': 'pátnam',
            'kripke': 'krípke',
            'quine': 'kuáin',
            'davidson': 'déibidson',
            'searle': 'sérl',
            'dennett': 'dénet',
            'chalmers': 'chálmers',
            'nagel': 'néigel',
            'parfit': 'párfit',
            'singer': 'sínger',
            'nussbaum': 'núsbaum',
            'butler': 'bátler',
            'irigaray': 'irigárai',
            'kristeva': 'kristéba',
            'cixous': 'siksú',

            # Científicos famosos
            'newton': 'niúton',
            'galileo': 'galíleo',
            'kepler': 'képler',
            'copernicus': 'kopérníkus',
            'darwin': 'dárguin',
            'mendel': 'méndel',
            'pasteur': 'pastér',
            'curie': 'kiúri',
            'edison': 'édison',
            'tesla': 'tésla',
            'faraday': 'fáradei',
            'maxwell': 'máksguel',
            'planck': 'plank',
            'bohr': 'bor',
            'heisenberg': 'jáisenberg',
            'schrödinger': 'chródinger',
            'einstein': 'áinshtain',
            'hawking': 'jókin',
            'feynman': 'fáinman',
            'watson': 'guátson',
            'crick': 'krik',
            'franklin': 'frángklin',
            'turing': 'túrin',
            'von neumann': 'bon nóiman',
            'gödel': 'gódel',
            'cantor': 'kántor',
            'russell': 'rásel',
            'whitehead': 'guáitjed',
            'wittgenstein': 'bitgenstáin',
            'frege': 'frége',
            'tarski': 'társki',
            'church': 'cherch',
            'curry': 'kéri',
            'shannon': 'chánon',
            'wiener': 'guíner',
            'chomsky': 'chómski',
            'skinner': 'eskíner',
            'pavlov': 'páblov',
            'freud': 'fróid',
            'jung': 'yung',
            'adler': 'ádler',
            'piaget': 'piayé',
            'vygotsky': 'bigótski',
            'bandura': 'bandúra',
            'maslow': 'máslou',
            'rogers': 'róyers',
            'beck': 'bek',
            'ellis': 'élis',
            'bowlby': 'bóulbi',
            'ainsworth': 'áinsguerz',
            'milgram': 'mílgram',
            'zimbardo': 'simbárdo',
            'asch': 'ash',
            'festinger': 'féstinger',
            'kahneman': 'káneman',
            'tversky': 'tbérski',
        }

        # NOMBRES DE CIUDADES INTERNACIONALES
        international_cities = {
            # Estados Unidos
            'new york': 'niu yórk',
            'los angeles': 'los ányeles',
            'chicago': 'chikágo',
            'houston': 'júston',
            'philadelphia': 'filalédfia',
            'phoenix': 'fíniks',
            'san antonio': 'san antóunio',
            'san diego': 'san diégo',
            'dallas': 'dálas',
            'san jose': 'san yosé',
            'austin': 'óstin',
            'jacksonville': 'yáksenbil',
            'fort worth': 'fort guórz',
            'columbus': 'kolámbus',
            'charlotte': 'chárlet',
            'san francisco': 'san fransísko',
            'indianapolis': 'indianápolis',
            'seattle': 'siátl',
            'denver': 'dénber',
            'washington': 'guáshington',
            'boston': 'bóston',
            'el paso': 'el páso',
            'detroit': 'detróit',
            'nashville': 'náshbil',
            'memphis': 'ménfis',
            'portland': 'pórtland',
            'oklahoma city': 'okláoma síti',
            'las vegas': 'las bégas',
            'louisville': 'lúisbil',
            'baltimore': 'báltimor',
            'milwaukee': 'miluóki',
            'albuquerque': 'álbukerk',
            'tucson': 'túkson',
            'fresno': 'frésno',
            'sacramento': 'sakraménto',
            'kansas city': 'kánsos síti',
            'mesa': 'mésa',
            'atlanta': 'atlánta',
            'omaha': 'omája',
            'colorado springs': 'kolorádo espríngs',
            'raleigh': 'ráli',
            'miami': 'miámi',
            'cleveland': 'klíbland',
            'tulsa': 'tálsa',
            'oakland': 'óukland',
            'minneapolis': 'minéapolis',
            'wichita': 'guíchita',
            'arlington': 'árlington',
            'buffalo': 'báfalo',
            'tampa': 'támpa',
            'aurora': 'auróra',
            'anaheim': 'anájáim',
            'honolulu': 'jonolúlu',
            'santa ana': 'santa ána',
            'st. louis': 'sant lúis',
            'riverside': 'ríbersáid',
            'corpus christi': 'kórpus krístai',
            'lexington': 'léksington',
            'pittsburgh': 'pítsburg',
            'anchorage': 'ánkoreych',
            'stockton': 'estókton',
            'cincinnati': 'sisinátai',
            'st. paul': 'sant pol',

            # Reino Unido
            'london': 'lóndon',
            'birmingham': 'bérmingan',
            'manchester': 'mánchester',
            'glasgow': 'glásgo',
            'liverpool': 'líberpul',
            'leeds': 'lids',
            'sheffield': 'chéfild',
            'edinburgh': 'édimburgo',
            'bristol': 'brístol',
            'cardiff': 'kárif',
            'leicester': 'léster',
            'coventry': 'kóbentri',
            'hull': 'jal',
            'bradford': 'brádfórd',
            'belfast': 'bélfast',
            'stoke': 'estóuk',
            'wolverhampton': 'guólberjámpton',
            'plymouth': 'plímaz',
            'derby': 'dérbi',
            'swansea': 'suánsi',
            'southampton': 'sázámpton',
            'salford': 'sálfórd',
            'aberdeen': 'aberdín',
            'westminster': 'güéstminster',
            'newcastle': 'niukásl',
            'northampton': 'norzámpton',
            'norwich': 'nórich',
            'luton': 'lúton',
            'portsmouth': 'pórtsmauz',
            'preston': 'préston',
            'milton keynes': 'mílton kíns',
            'sunderland': 'sánderlond',
            'canterbury': 'kánterberi',
            'york': 'yórk',
            'oxford': 'óksfórd',
            'cambridge': 'kéimbrich',
            'bath': 'baz',
            'stratford': 'estrátfórd',
            'brighton': 'bráiton',
            'bournemouth': 'bórnmauz',
            'blackpool': 'blákpul',
            'ipswich': 'ípsguich',
            'reading': 'rídin',
            'slough': 'esjau',
            'gloucester': 'glóster',
            'watford': 'guátfórd',
            'rotherham': 'rózerján',
            'dudley': 'dádli',
            'exeter': 'ékseter',
            'woking': 'guókin',
            'crawley': 'kráuli',

            # Canadá
            'toronto': 'torónto',
            'montreal': 'montriól',
            'vancouver': 'bankúber',
            'calgary': 'kálgari',
            'edmonton': 'édmonton',
            'ottawa': 'otágua',
            'winnipeg': 'guínipeg',
            'quebec': 'kebék',
            'hamilton': 'jámilton',
            'kitchener': 'kíchener',
            'london': 'lóndon',
            'halifax': 'jálifax',
            'victoria': 'biktória',
            'windsor': 'guínsór',
            'oshawa': 'óchaua',
            'saskatoon': 'saskátun',
            'regina': 'reyína',
            'sherbrooke': 'chérbruk',
            'kelowna': 'kelóuna',
            'barrie': 'bári',
            'kingston': 'kínston',
            'abbotsford': 'ábotsfórd',
            'trois-rivières': 'troá ribiér',
            'guelph': 'guélf',
            'cambridge': 'kéimbrich',
            'whitby': 'guítbi',
            'sudbury': 'sádberi',
            'thunder bay': 'zánder béi',
            'waterloo': 'guáterlú',
            'brantford': 'bránfórd',
            'red deer': 'red dír',
            'nanaimo': 'nanáimo',
            'kamloops': 'kámlups',
            'fredericton': 'frederíkton',
            'moncton': 'mónkton',
            'saint john': 'séint yon',
            'charlottetown': 'chárletaun',

            # Australia
            'sydney': 'sídney',
            'melbourne': 'mélburn',
            'brisbane': 'brísbein',
            'perth': 'perz',
            'adelaide': 'ádeléid',
            'gold coast': 'góld kóst',
            'newcastle': 'niukásl',
            'canberra': 'kanbéra',
            'sunshine coast': 'sánshain kóst',
            'wollongong': 'gulóngong',
            'geelong': 'yilóng',
            'hobart': 'jóbart',
            'townsville': 'táunsbil',
            'cairns': 'kérns',
            'darwin': 'dárguin',
            'toowoomba': 'tuúmba',
            'ballarat': 'balárat',
            'bendigo': 'béndigo',
            'albury': 'álberi',
            'launceston': 'lónston',
            'mackay': 'makéi',
            'rockhampton': 'rokjámpton',
            'bunbury': 'bánberi',
            'bundaberg': 'bándaberg',
            'coffs harbour': 'kofs járbor',
            'wagga wagga': 'gága gága',
            'hervey bay': 'jérbi béi',
            'mildura': 'míldura',
            'shepparton': 'chéparton',
            'port macquarie': 'pórt makuéri',
            'gladstone': 'gládstoun',
            'tamworth': 'támguórz',
            'traralgon': 'trarálgon',
            'orange': 'óranch',
            'dubbo': 'dábo',
            'geraldton': 'yéraldton',
            'kalgoorlie': 'kalgúrli',
            'alice springs': 'ális espríngs',
            'whyalla': 'guaiála',
            'mount gambier': 'máunt gámbier',
            'lismore': 'lísmor',
            'nelson bay': 'nélson béi',
            'warrnambool': 'guárnambul',
        }

        # Combinar todos los diccionarios
        dictionary.update(tech_devices)
        dictionary.update(connectivity)
        dictionary.update(software)
        dictionary.update(web_terms)
        dictionary.update(digital_actions)
        dictionary.update(security)
        dictionary.update(file_formats)
        dictionary.update(social_media)
        dictionary.update(tech_brands)
        dictionary.update(food_drink)
        dictionary.update(english_names)
        dictionary.update(common_words)
        dictionary.update(sports_fitness)
        dictionary.update(adapted_verbs)
        dictionary.update(philosophical_terms)
        dictionary.update(scientists_philosophers)
        dictionary.update(international_cities)

        return dictionary

    def _initialize_rules(self) -> List[PhoneticRule]:
        """Inicializa reglas de transformación fonética española"""
        return [
            # H muda - prioridad alta (eliminar h inicial)
            PhoneticRule(r'\bhab', 'ab', priority=10),  # haber -> aber
            PhoneticRule(r'\bhac', 'ac', priority=10),   # hacer -> acer
            PhoneticRule(r'\bha([^s])', r'a\1', priority=9),  # general h inicial
            PhoneticRule(r'\bhe', 'e', priority=9),      # hecho -> echo
            PhoneticRule(r'\bhi', 'i', priority=9),      # hijo -> ijo
            PhoneticRule(r'\bho', 'o', priority=9),      # hora -> ora
            PhoneticRule(r'\bhu', 'u', priority=9),      # huevo -> uevo

            # B/V confusion (betacismo) - muy común en español
            PhoneticRule(r'mb', 'mb', priority=8),  # mantener mb siempre
            PhoneticRule(r'nv', 'nb', priority=8),  # enviar -> enbiar
            PhoneticRule(r'\bv', 'b', priority=7),  # vez -> bez
            PhoneticRule(r'([aeiou])v([aeiou])', r'\1b\2', priority=6),  # intervocálica

            # LL/Y confusion (yeísmo) - muy extendido
            PhoneticRule(r'll', 'y', priority=7),  # llamar -> yamar

            # G/J ante e,i - confusión común
            PhoneticRule(r'g([ei])', r'j\1', priority=6),  # generar -> jenerar

            # ELIMINADO: C/S/Z (seseo) - No aplica en español toledano

            # QU -> K (simplificación)
            PhoneticRule(r'qu', 'k', priority=4),  # queso -> keso

            # X -> S en posición inicial
            PhoneticRule(r'\bx', 's', priority=4),  # xenofobia -> senofobia

            # CC -> C (simplificación)
            PhoneticRule(r'cc', 'c', priority=3),  # acción -> ación

            # Terminación -ado -> -ao (relajación)
            PhoneticRule(r'ado\b', 'ao', priority=3),  # cansado -> cansao

            # Terminación -ada -> -á (relajación)
            PhoneticRule(r'ada\b', 'á', priority=3),  # cansada -> cansá
        ]

    def _number_to_phonetic_spanish(self, number: int) -> str:
        """
        Convierte números (0-999,999,999) a su representación fonética en español
        Aplicando las reglas de transformación fonética correspondientes
        """
        if number == 0:
            return "sero"

        # Diccionarios de números básicos con transformaciones fonéticas aplicadas
        unidades = {
            1: "uno", 2: "dos", 3: "tres", 4: "cuatro", 5: "cinco",
            6: "seis", 7: "siete", 8: "ocho", 9: "nueve"
        }

        # Del 10 al 19 (casos especiales)
        especiales = {
            10: "diez", 11: "once", 12: "doce", 13: "trece", 14: "catorce",
            15: "quince", 16: "dieciséis", 17: "diecisiete", 18: "dieciocho", 19: "diecinueve"
        }

        # Decenas
        decenas = {
            20: "veinte", 30: "treinta", 40: "cuarenta", 50: "cincuenta",
            60: "sesenta", 70: "setenta", 80: "ochenta", 90: "noventa"
        }

        # Centenas
        centenas = {
            100: "cien", 200: "doscientos", 300: "trescientos", 400: "cuatrocientos",
            500: "quinientos", 600: "seiscientos", 700: "setecientos", 800: "ochocientos", 900: "novecientos"
        }

        def convertir_cientos(n):
            """Convierte números de 0-999 a texto"""
            if n == 0:
                return ""

            resultado = []

            # Centenas
            if n >= 100:
                if n == 100:
                    resultado.append("cien")
                elif n < 200:
                    resultado.append("ciento")
                else:
                    resultado.append(centenas[n // 100 * 100])
                n %= 100

            # Decenas y unidades
            if n >= 10:
                if n < 20:
                    # Casos especiales 10-19
                    resultado.append(especiales[n])
                elif n < 30:
                    # 20-29: veinti...
                    if n == 20:
                        resultado.append("veinte")
                    else:
                        resultado.append(f"veinti{unidades[n % 10]}")
                else:
                    # 30-99
                    decena = n // 10 * 10
                    unidad = n % 10
                    if unidad == 0:
                        resultado.append(decenas[decena])
                    else:
                        resultado.append(f"{decenas[decena]} y {unidades[unidad]}")
            elif n > 0:
                # 1-9
                resultado.append(unidades[n])

            return " ".join(resultado)

        # Procesar el número completo
        if number < 1000:
            texto = convertir_cientos(number)
        elif number < 1000000:
            # Miles
            miles = number // 1000
            resto = number % 1000

            if miles == 1:
                texto = "mil"
            else:
                texto = f"{convertir_cientos(miles)} mil"

            if resto > 0:
                texto += f" {convertir_cientos(resto)}"
        else:
            # Millones (hasta 999,999,999)
            millones = number // 1000000
            resto = number % 1000000

            if millones == 1:
                texto = "un millón"
            else:
                texto = f"{convertir_cientos(millones)} millones"

            if resto > 0:
                if resto >= 1000:
                    miles = resto // 1000
                    unidades_resto = resto % 1000

                    if miles == 1:
                        texto += " mil"
                    else:
                        texto += f" {convertir_cientos(miles)} mil"

                    if unidades_resto > 0:
                        texto += f" {convertir_cientos(unidades_resto)}"
                else:
                    texto += f" {convertir_cientos(resto)}"

        # Aplicar transformaciones fonéticas específicas a los números
        # Yeísmo: ll -> y
        texto = texto.replace("millón", "miyón")
        texto = texto.replace("millones", "miyones")

        # Betacismo: v -> b (en algunos casos)
        texto = texto.replace("veinte", "beinte")
        texto = texto.replace("veinti", "beinti")
        texto = texto.replace("noventa", "nobenta")
        texto = texto.replace("nueve", "nuebe")

        # H muda aplicada
        texto = texto.replace("ocho", "ocho")  # Ya no tiene h inicial

        return texto

    def transform_text(self, text: str, adapt_english: bool = True) -> str:
        """
        Transforma texto completo manteniendo consistencia

        Args:
            text: Texto a transformar
            adapt_english: Si adaptar anglicismos a pronunciación castellana

        Returns:
            Texto transformado fonéticamente
        """
        # Dividir en palabras manteniendo puntuación y estructura
        words = re.findall(r'\b\w+\b|[^\w\s]|\s+', text)
        transformed_words = []

        for word in words:
            # Mantener espacios sin cambios
            if not word.strip():
                transformed_words.append(word)
                continue

            # NUEVO: Fonetizar números (0-999,999,999)
            if word.isdigit():
                number = int(word)
                if 0 <= number <= 999999999:
                    phonetic_number = self._number_to_phonetic_spanish(number)
                    transformed_words.append(phonetic_number)
                    continue

            # Mantener puntuación sin cambios
            if not word[0].isalpha():
                transformed_words.append(word)
                continue

            word_lower = word.lower()

            # Verificar caché primero
            if word_lower in self.word_cache:
                # Mantener capitalización original
                transformed = self._preserve_capitalization(
                    word,
                    self.word_cache[word_lower]
                )
                transformed_words.append(transformed)
                continue

            # Primero verificar si es un anglicismo conocido
            if adapt_english and word_lower in self.anglicisms_dictionary:
                # Aplicar pronunciación castellana al anglicismo
                transformed = self.anglicisms_dictionary[word_lower]

                # También aplicar reglas fonéticas españolas al resultado
                transformed = self._apply_phonetic_rules(transformed)
            else:
                # Intentar detectar patrones ingleses no registrados
                english_transformed = self._detect_unknown_english_patterns(word_lower) if adapt_english else None

                if english_transformed:
                    # Usar la transformación inglesa y aplicar reglas españolas
                    transformed = self._apply_phonetic_rules(english_transformed)
                else:
                    # Aplicar transformación normal con reglas españolas
                    transformed = self._apply_phonetic_rules(word_lower)

            # Guardar en caché
            self.word_cache[word_lower] = transformed
            self.transformation_history[word_lower].append(transformed)

            # Mantener capitalización
            final_word = self._preserve_capitalization(word, transformed)
            transformed_words.append(final_word)

        return ''.join(transformed_words)

    def _apply_phonetic_rules(self, word: str) -> str:
        """Aplica reglas fonéticas a una palabra"""
        result = word

        # Ordenar reglas por prioridad
        sorted_rules = sorted(self.phonetic_rules, key=lambda r: r.priority, reverse=True)

        for rule in sorted_rules:
            # Verificar excepciones
            if word in rule.exceptions:
                continue

            # Aplicar regla
            result = re.sub(rule.pattern, rule.replacement, result)

        return result

    def _detect_unknown_english_patterns(self, word: str) -> Optional[str]:
        """
        Detecta y transforma patrones ingleses no registrados en el diccionario
        usando reglas genéricas de adaptación castellana
        """
        # Si ya está en el diccionario, no procesar
        if word.lower() in self.anglicisms_dictionary:
            return None

        # Detectar si tiene patrones típicamente ingleses
        has_english_pattern = any([
            'w' in word,
            'k' in word and word not in ['kilo', 'kilómetro', 'kilogramo'],
            'ph' in word,
            'th' in word,
            'sh' in word,
            'ck' in word,
            'ght' in word,
            'ough' in word,
            word.endswith('ing'),
            word.endswith('tion'),
            word.endswith('ly'),
            word.endswith('ness')
        ])

        if not has_english_pattern:
            return None

        # Aplicar reglas genéricas de castellanización
        result = word

        # Transformaciones de consonantes
        result = re.sub(r'ph', 'f', result)        # phone -> fone
        result = re.sub(r'th', 't', result)        # think -> tink
        result = re.sub(r'sh', 'ch', result)       # shop -> chop
        result = re.sub(r'ck', 'k', result)        # clock -> clok
        result = re.sub(r'wh', 'gu', result)       # what -> guat
        result = re.sub(r'w', 'gu', result)        # water -> guater
        result = re.sub(r'ght', 't', result)       # night -> nait
        result = re.sub(r'ough', 'of', result)     # tough -> tof

        # Transformaciones de terminaciones
        result = re.sub(r'ing\b', 'in', result)    # running -> runnin
        result = re.sub(r'tion\b', 'chon', result) # nation -> nachon
        result = re.sub(r'sion\b', 'sion', result) # vision -> vision
        result = re.sub(r'ly\b', 'li', result)     # really -> reali
        result = re.sub(r'ness\b', 'nes', result)  # happiness -> hapines
        result = re.sub(r'ful\b', 'ful', result)   # beautiful -> biutiful
        result = re.sub(r'less\b', 'les', result)  # homeless -> joumles

        # Transformaciones vocálicas
        result = re.sub(r'ee', 'i', result)        # see -> si
        result = re.sub(r'oo', 'u', result)        # book -> buk
        result = re.sub(r'ea', 'i', result)        # team -> tim
        result = re.sub(r'ou', 'au', result)       # house -> jaus

        return result if result != word else None

    def _preserve_capitalization(self, original: str, transformed: str) -> str:
        """Preserva el patrón de capitalización original"""
        if not transformed:
            return transformed

        if original.isupper():
            return transformed.upper()
        elif original[0].isupper():
            return transformed.capitalize()
        return transformed

    def transform_paragraphs(self, paragraphs: List[str]) -> List[str]:
        """
        Transforma una lista de párrafos manteniendo consistencia global

        Args:
            paragraphs: Lista de párrafos a transformar

        Returns:
            Lista de párrafos transformados
        """
        transformed_paragraphs = []

        for paragraph in paragraphs:
            if not paragraph.strip():
                transformed_paragraphs.append(paragraph)
                continue

            # Transformar párrafo completo
            transformed = self.transform_text(paragraph)
            transformed_paragraphs.append(transformed)

        return transformed_paragraphs

    def get_transformation_stats(self) -> Dict:
        """Retorna estadísticas de las transformaciones realizadas"""
        unique_words = len(self.word_cache)
        total_transformations = sum(len(v) for v in self.transformation_history.values())

        # Calcular las transformaciones más comunes
        most_common = []
        for original, transformations in self.transformation_history.items():
            if transformations and original != transformations[0]:
                most_common.append((original, transformations[0]))

        most_common.sort(key=lambda x: len(self.transformation_history[x[0]]), reverse=True)

        return {
            'unique_words_transformed': unique_words,
            'total_transformations': total_transformations,
            'cache_size': len(self.word_cache),
            'most_common_transformations': most_common[:10],
            'consistency_score': (unique_words / total_transformations * 100) if total_transformations > 0 else 100
        }

    def clear_cache(self):
        """Limpia el caché de transformaciones"""
        self.word_cache.clear()
        self.phrase_cache.clear()
        self.transformation_history.clear()


def transform_file(input_path: str, output_path: str = None) -> str:
    """
    Función de conveniencia para transformar un archivo completo

    Args:
        input_path: Ruta del archivo de entrada
        output_path: Ruta del archivo de salida (opcional)

    Returns:
        Texto transformado
    """
    # Leer archivo
    with open(input_path, 'r', encoding='utf-8') as f:
        content = f.read()

    # Crear transformador
    transformer = SpanishPhoneticTransformer()

    # Transformar contenido
    transformed = transformer.transform_text(content)

    # Guardar si se especificó archivo de salida
    if output_path:
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(transformed)

        # Guardar estadísticas
        stats = transformer.get_transformation_stats()
        stats_path = output_path.replace('.txt', '_stats.txt')
        with open(stats_path, 'w', encoding='utf-8') as f:
            f.write("Estadísticas de Transformación Fonética\n")
            f.write("=" * 40 + "\n\n")
            f.write(f"Palabras únicas transformadas: {stats['unique_words_transformed']}\n")
            f.write(f"Total de transformaciones: {stats['total_transformations']}\n")
            f.write(f"Puntuación de consistencia: {stats['consistency_score']:.2f}%\n\n")

            if stats['most_common_transformations']:
                f.write("Transformaciones más comunes:\n")
                for original, transformed in stats['most_common_transformations']:
                    f.write(f"  {original} → {transformed}\n")

    return transformed


def main():
    """Función principal para pruebas"""
    # Texto de ejemplo
    ejemplo = """Veinte minutos tarde. Otra vez.

Kelly estaba esperando en el banco frente a su portal, piernas cruzadas, scrolleando en el móvil. Cuando aparqué y me vio bajar del coche, su cara se iluminó como si no llevara ahí esperando desde hace... joder, desde hace veinte minutos. Esa alegría genuina, esa euforia de "¡por fin estás aquí!" después de dos semanas sin vernos.

Me hizo sentir como una mierda."""

    print("Texto original:")
    print("=" * 50)
    print(ejemplo)
    print("\n")

    # Crear transformador
    transformer = SpanishPhoneticTransformer()

    # Transformar
    resultado = transformer.transform_text(ejemplo)

    print("Texto transformado fonéticamente:")
    print("=" * 50)
    print(resultado)
    print("\n")

    # Mostrar estadísticas
    stats = transformer.get_transformation_stats()
    print("Estadísticas:")
    print("=" * 50)
    print(f"Palabras transformadas: {stats['unique_words_transformed']}")
    print(f"Consistencia: {stats['consistency_score']:.2f}%")

    if stats['most_common_transformations']:
        print("\nTransformaciones aplicadas:")
        for original, transformed in stats['most_common_transformations'][:5]:
            print(f"  {original} → {transformed}")


if __name__ == "__main__":
    main()
