# -*- coding=utf-8 -*-
import json
import logging
import os
import re
import shutil
import subprocess
import sys
import textwrap

from bs4 import BeautifulSoup
from json_schema_for_humans.generate import generate_from_filename
from json_schema_for_humans.generation_configuration import GenerationConfiguration

from middlewared.api.base.server.doc import APIDump, APIDumpMethod

logger = logging.getLogger(__name__)


class DocumentationGenerator:
    def __init__(self, api: APIDump, output_dir: str):
        self.api = api
        self.output_dir = output_dir

    def generate(self):
        shutil.copytree("docs", self.output_dir, dirs_exist_ok=True)

        with open(f"{self.output_dir}/conf.py") as f:
            conf = f.read()

        conf = conf.replace("$VERSION", self.api.version)

        with open(f"{self.output_dir}/conf.py", "w") as f:
            f.write(conf)

        self._write_api_methods()

    def _write_api_methods(self):
        plugins = sorted({method.name.rsplit(".", 1)[0] for method in self.api.methods})

        index = textwrap.dedent("""\
            API Methods
            -----------

            .. toctree::

        """)
        for plugin in plugins:
            methods = [
                method
                for method in self.api.methods
                if method.name.rsplit(".", 1)[0] == plugin
            ]
            if not methods:
                continue

            index += f"   {plugin}\n"

            self._write_plugin(plugin, methods)

        with open(f"{self.output_dir}/api_methods.rst", "w") as f:
            f.write(index)

    def _write_plugin(self, plugin: str, methods: list[APIDumpMethod]):
        index = textwrap.dedent(f"""\
            {plugin}
            {'-' * len(plugin)}

            .. toctree::

        """)

        for method in methods:
            method_schemas_html = self._generate_method_schemas_html(method)

            with open(f"{self.output_dir}/{method.name}.rst", "w") as f:
                f.write(self._generate_method_rst(method, method_schemas_html))

            index += f"   {method.name}\n"

        with open(f"{self.output_dir}/{plugin}.rst", "w") as f:
            f.write(index)

    def _generate_method_schemas_html(self, method: APIDumpMethod):
        json_path = f"{self.output_dir}/{method.name}.json"
        try:
            with open(json_path, "w") as f:
                json.dump(method.schemas, f)

            html_path = f"{self.output_dir}/{method.name}.html"
            try:
                config = GenerationConfiguration(
                    show_breadcrumbs=False,
                    collapse_long_descriptions=False,
                    collapse_long_examples=False,
                    copy_css=False,
                    copy_js=False,
                    with_footer=False,
                )
                generate_from_filename(json_path, html_path, config=config)

                with open(html_path) as f:
                    html = f.read()
            finally:
                os.unlink(html_path)

            soup = BeautifulSoup(html)

            for h4 in soup.find_all("h4"):
                if h4.text.endswith(":"):
                    h4["style"] = "display: block;"

            for h5 in soup.find("div", {"id": "Call_parameters"}).find().find_all("h5", recursive=False):
                if m := re.match("Item at ([0-9]+) must be:", h5.text):
                    number = int(m.group(1))

                    next_sibling = h5.next_sibling
                    while next_sibling and next_sibling.name is None:
                        next_sibling = next_sibling.next_sibling

                    name = next_sibling.find("h4").text
                    h5.string = f"Parameter {number}: {name}"

            return soup.find("body").decode_contents()
        finally:
            os.unlink(json_path)

    def _generate_method_rst(self, method: APIDumpMethod, method_schemas_html: str):
        result = f"{method.name}\n" + "=" * len(method.name) + "\n\n"

        if method.doc:
            result += f"{method.doc}\n\n"

        result += f".. raw:: html\n\n"
        result += textwrap.indent(f"<div id=\"json-schema\">" + method_schemas_html + "</div>", " " * 4) + "\n\n"

        return result


def main(output_dir):
    data = json.loads(
        subprocess.run(
            ["middlewared", "--dump-api"],
            check=True,
            stdout=subprocess.PIPE,
            text=True,
        ).stdout
    )
    for api_dump in data["versions"]:
        api = APIDump.model_validate(api_dump)

        rst_dir = f"{output_dir}/rst/{api.version}"
        DocumentationGenerator(api, rst_dir).generate()

        build_dir = f"{output_dir}/html/{api.version}"
        subprocess.run(
            [
                os.path.join(os.path.dirname(sys.executable), "sphinx-build"),
                "-M", "html",
                rst_dir,
                build_dir,
            ],
            check=True,
        )

        shutil.move(f"{build_dir}/html", f"{output_dir}/{api.version}")

    shutil.rmtree(f"{output_dir}/rst")
    shutil.rmtree(f"{output_dir}/html")


if __name__ == "__main__":
    main(sys.argv[1])
