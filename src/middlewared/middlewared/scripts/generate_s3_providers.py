import json
import re
import subprocess


def main():
    output = subprocess.check_output(["rclone", "help", "backend", "s3"], encoding="utf-8")
    providers_doc = re.search(r"#### --s3-provider([\s\S]+?)####", output).group(1)
    providers = dict(re.findall(r" {4}- \"(.+)\"\n {8}- (.+)", providers_doc))
    other_value = providers.pop("Other")  # Should be first as it is the default
    providers = {"Other": other_value, **providers}
    with open("middlewared/rclone/remote/s3_providers.py", "w") as f:
        f.write("S3_PROVIDERS = " + json.dumps(providers, indent=4) + "\n")


if __name__ == "__main__":
    main()
