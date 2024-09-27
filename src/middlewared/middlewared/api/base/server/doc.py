import inspect
import json
import os
import re
import shutil
import textwrap

from ..jsonschema import replace_refs
from .api import API
from .method import Method

GENERATION_ERROR = None
try:
    from bs4 import BeautifulSoup
    from json_schema_for_humans.generate import generate_from_filename
    from json_schema_for_humans.generation_configuration import GenerationConfiguration
except ImportError as e:
    GENERATION_ERROR = str(e)


class DocumentationGenerator:
    def __init__(self, version: str, api: API, output_dir: str):
        self.version = version
        self.api = api
        self.output_dir = output_dir

    def generate(self):
        if GENERATION_ERROR is not None:
            raise Exception(f"API documentation generation is not supported: {GENERATION_ERROR}")

        shutil.copytree(
            os.path.join(os.path.dirname(__file__), "../../../assets/api_doc"),
            self.output_dir,
            dirs_exist_ok=True,
        )

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
                if (
                    method.name.rsplit(".", 1)[0] == plugin and
                    hasattr(method.methodobj, "new_style_accepts")
                )
            ]
            if not methods:
                continue

            index += f"   {plugin}\n"

            self._write_plugin(plugin, methods)

        with open(f"{self.output_dir}/api_methods.rst", "w") as f:
            f.write(index)

    def _write_plugin(self, plugin: str, methods: list[Method]):
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

    def _generate_method_schemas_html(self, method: Method):
        json_path = f"{self.output_dir}/{method.name}.json"
        try:
            with open(json_path, "w") as f:
                json.dump(self._generate_method_schemas(method), f)

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

    def _generate_method_schemas(self, method: Method):
        accepts_json_schema = method.methodobj.new_style_accepts.model_json_schema()
        accepts_json_schema = replace_refs(accepts_json_schema, accepts_json_schema.get("$defs", {}))

        returns_json_schema = method.methodobj.new_style_returns.model_json_schema(mode="serialization")
        returns_json_schema = replace_refs(returns_json_schema, returns_json_schema.get("$defs", {}))

        return {
            "type": "object",
            "properties": {
                "Call parameters": {
                    "type": "array",
                    "prefixItems": [
                        {
                            **accepts_json_schema["properties"][field],
                            "title": field,
                        }
                        for field in method.methodobj.new_style_accepts.model_fields
                    ],
                    "items": False,
                },
                "Return value": {
                    **returns_json_schema["properties"]["result"],
                },
            },
        }

    def _generate_method_rst(self, method: Method, method_schemas_html: str):
        result = f"{method.name}\n" + "=" * len(method.name) + "\n\n"

        if doc := inspect.getdoc(method.methodobj):
            doc = re.sub(r"(\S)\n[ ]*(\S)", "\\1 \\2", doc)

            result += f"{doc}\n\n"

        result += f".. raw:: html\n\n"
        result += textwrap.indent(f"<div id=\"json-schema\">" + method_schemas_html + "</div>", " " * 4) + "\n\n"

        return result
