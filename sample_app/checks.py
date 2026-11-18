def clean_host(value):
    host = value.strip()
    if not host:
        raise ValueError("Please enter a host name.")
    if len(host) > 100:
        raise ValueError("Host name is too long.")
    return host