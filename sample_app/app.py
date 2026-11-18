from checks import clean_host
from network import ping_host


def check_host(request):
    host = clean_host(request.args.get("host", ""))
    return ping_host(host)