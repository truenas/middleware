import argparse
import email
import email.parser
import json
import requests
import sys

from truenas_api_client import Client


def do_sendmail(msg, to_addrs=None, parse_recipients=False):
    to_addrs = ["root"] if to_addrs is None else to_addrs
    if to_addrs is None and not parse_recipients:
        raise ValueError("Do not know who to send the message to.")

    em = email.parser.Parser().parsestr(msg)
    if parse_recipients:
        # Strip away the comma based delimiters and whitespace.
        for addr in map(str.strip, em.get("To", "").split(",")):
            if addr:
                to_addrs.append(addr)

    to_addrs_repl = []
    aliases = get_aliases()
    for i in to_addrs:
        for to_addr in i.split(","):
            if "@" in to_addr:
                to_addrs_repl.append(to_addr)
            elif to_addr in aliases:
                to_addrs_repl.append(aliases[to_addr])

    if not to_addrs_repl:
        print(
            f'No aliases found to send email to {", ".join(to_addrs)}', file=sys.stderr
        )
        sys.exit(1)

    with Client() as c:
        sw_name = "TrueNAS"
        margs = dict()
        margs["extra_headers"] = dict(em)
        margs["extra_headers"].update(
            {
                "X-Mailer": sw_name,
                f"X-{sw_name}-Host": c.call("system.hostname"),
                "To": ", ".join(to_addrs_repl),
            }
        )
        margs["subject"] = em.get("Subject")
        if em.is_multipart():
            attachments = [
                part for part in em.walk() if part.get_content_maintype() != "multipart"
            ]
            margs["attachments"] = True if attachments else False
            margs["text"] = (
                "This is a MIME formatted message.  If you see "
                "this text it means that your email software "
                "does not support MIME formatted messages."
            )
            margs["html"] = None
        else:
            margs["text"] = "".join(email.iterators.body_line_iterator(em))

        margs["to"] = to_addrs_repl
        if not margs.get("attachments"):
            c.call("mail.send", margs)
        else:
            token = c.call("auth.generate_token")
            files = []
            for attachment in attachments:
                entry = {"headers": []}
                for k, v in attachment.items():
                    entry["headers"].append({"name": k, "value": v})
                entry["content"] = attachment.get_payload()
                files.append(entry)

            requests.post(
                f"http://localhost:6000/_upload?auth_token={token}",
                files={
                    "data": json.dumps({"method": "mail.send", "params": [margs]}),
                    "file": json.dumps(files),
                },
            )


def get_aliases():
    aliases = {}
    with open("/etc/aliases", "r") as f:
        for line in f:
            # looks like
            # admin1: name@domain.com, another@domain.com
            # admin2: name@domain.com
            try:
                name, addresses = line.strip().split(":")
                if name != addresses:
                    aliases[name] = addresses
            except ValueError:
                continue
    return aliases


def main():
    parser = argparse.ArgumentParser(description="Process email")
    parser.add_argument(
        "-i",
        dest="strip_leading_dot",
        action="store_false",
        default=True,
        help="see sendmail(8) -i",
    )
    parser.add_argument(
        "-t",
        dest="parse_recipients",
        action="store_true",
        default=False,
        help="parse recipients from message",
    )
    parser.usage = " ".join(parser.format_usage().split(" ")[1:-1])
    parser.usage += " [email_addr|user] .."
    args, to = parser.parse_known_args()
    if not to and not args.parse_recipients:
        parser.exit(message=parser.format_usage())
    msg = sys.stdin.read()
    do_sendmail(msg, to_addrs=to, parse_recipients=args.parse_recipients)


if __name__ == "__main__":
    main()
