import math

UNIT_NAMES = {
    "B": dict(kibi=1,kilo=1), 
    "KB": dict(kibi=2**10,kilo=10**3), 
    "MB": dict(kibi=2**20, kilo=10**6), 
    "GB": dict(kibi=2**30, kil=10**9), 
    "TB": dict(kibi=2**40, kilo=10**12)
    }

def parse_size_name(size: str, format='kibi') -> int:
    if format != 'kibi' and format != 'kilo':
        raise Exception(f'Unrecognized format {format}. Accepted values are "kibi" (1 KB = 1024 B) and "kilo" (1 KB = 1000 B)')

    number, unit = [string.strip() for string in size.split()]
    return int(float(number)*UNIT_NAMES[unit][format])

def parse_size_bytes(bytes: int, format='kibi') -> str:
    if bytes < 0:
        raise ValueError(f"Bytes value cannot be negative, is {bytes}")
    if bytes == 0:
        return "0 B"
    b = 2 if format == 'kibi' else 10
    p = int(math.log(bytes, b))
    dim = int(p/(10 if format == 'kibi' else 3))
    return f"{bytes/list(UNIT_NAMES.values())[dim][format]:.2f} {list(UNIT_NAMES.keys())[dim]}"

def parse_download_name(name: str) -> str:
    return name.replace('/', '|').replace('.', '_')

class Color:
    PURPLE = '\033[95m'
    CYAN = '\033[96m'
    DARKCYAN = '\033[36m'
    BLUE = '\033[94m'
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    RED = '\033[91m'
    BOLD = '\033[1m'
    UNDERLINE = '\033[4m'
    END = '\033[0m'

    @staticmethod
    def with_color(message: str, color: str,bold=False,underline=False) -> str:
        return f"{Color.UNDERLINE if underline else ''}{Color.BOLD if bold else ''}{color}{message}{Color.END}"
    
    @staticmethod
    def bold(message: str) -> str:
        return f"{Color.BOLD}{message}{Color.END}"
    
    @staticmethod
    def underline(message: str) -> str:
        return f"{Color.UNDERLINE}{message}{Color.END}"
